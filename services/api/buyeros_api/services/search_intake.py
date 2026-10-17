"""API-role intake of received search metadata; no entity or billing settlement.

This port consumes a code-owned receipt in the caller's short transaction. It
does not select/activate a provider, claim a dispatch, fetch a page, or score fit.
The production research coordinator must bind this port before activation.
"""
from datetime import datetime,timezone
import uuid
from sqlalchemy import select,text
from ..api.deps import permission_for_roles
from ..db.models import Membership
from ..db.icp import Project,IcpVersion,canonical_hash
from ..db.runs import SearchRun,RawCandidate,RunEvent
from ..db.buyers import SourceDocument
from ..db.contact import ProviderOperation
from ..db.outbox import OutboxEvent
from ..db.budget import BudgetAccount,BudgetReservation,BudgetReservationAllocation
from ..providers.live_search import PostgresSearchReceipts,source_candidate
from .policy_service import evaluate_current_policy
from .receipt_retention import bind_receipt_source
from .run_events import append_event
from .run_usage import advance_usage,UsageExceeded


async def ingest_received_search(session,*,workspace_id,run_id,receipt_id,capability):
    """Persist bounded needs-review metadata once; caller commits all or none.

    Company is the provider's output scope. A query's buyer-role phrase is not
    evidence that a result is a distributor, subsidiary, or canonical company.
    """
    if not all(isinstance(value,uuid.UUID) for value in (workspace_id,run_id,receipt_id)):
        raise ValueError('canonical receipt/run/workspace references required')
    if (await session.execute(text("SELECT current_setting('app.workspace_id',true)"))).scalar_one()!=str(workspace_id):
        raise ValueError('current tenant scope required')
    run=(await session.execute(select(SearchRun).where(SearchRun.workspace_id==workspace_id,SearchRun.id==run_id).with_for_update())).scalar_one_or_none()
    if run is None or run.status not in {'running','partial'}:raise ValueError('current resumable run required')
    store=PostgresSearchReceipts(session.bind,workspace_id,capability)
    await store._require_schema(session)
    if (await session.execute(text('SELECT public.buyeros_lock_search_receipt(:ws,:id)'),{'ws':workspace_id,'id':receipt_id})).scalar_one() is not True:
        raise ValueError('current atomic receipt read lock required')
    row=(await session.execute(text("""SELECT r.*,public.buyeros_receipt_dependency_expired(r.workspace_id,'search',r.id,r.request) AS dependency_expired
      FROM search_receipts r WHERE r.workspace_id=:ws AND r.id=:id"""),{'ws':workspace_id,'id':receipt_id})).mappings().one_or_none()
    saved=store._decode(row)
    if saved is None or saved['state']!='received':raise ValueError('current received search metadata required')
    request=saved['request'];snapshot=run.execution_snapshot
    member=(await session.execute(select(Membership).where(Membership.workspace_id==workspace_id,Membership.user_id==request.actor_id,Membership.active.is_(True)).with_for_update(read=True))).scalar_one_or_none()
    project=(await session.execute(select(Project).where(Project.workspace_id==workspace_id,Project.id==run.project_id).with_for_update(read=True))).scalar_one_or_none()
    icp=(await session.execute(select(IcpVersion).where(IcpVersion.workspace_id==workspace_id,IcpVersion.project_id==run.project_id,IcpVersion.id==run.icp_version_id).with_for_update(read=True))).scalar_one_or_none()
    from .research_policy_context import research_use,metadata_binding
    # An empty, already-received response creates only a zero-result checkpoint.
    # No source content is copied; bind that bookkeeping to the original search.
    use=research_use(run.project_id,'research.persist',urls=[item.get('source_url') for item in saved['sources']]) if saved['sources'] else research_use(
        run.project_id,'research.search',binding=metadata_binding(snapshot.get('capability',{}),historical=True))
    policy=await evaluate_current_policy(session,{'workspace_id':workspace_id,'project_id':run.project_id},
        'account_research',datetime.now(timezone.utc),use_context=use)
    if (request.project_id!=run.project_id or snapshot.get('actor_id')!=str(request.actor_id) or
        member is None or not permission_for_roles(member.roles,'startRun') or not policy['allowed'] or
        project is None or project.status!='active' or icp is None or project.active_icp_version_id!=icp.id or
        icp.approved_at is None or icp.approved_by is None or icp.superseded_at is not None or
        icp.basis_offer_revision!=project.offer_revision or project.offer_revision!=snapshot.get('offer_revision') or
        icp.content_hash!=snapshot.get('icp_content_hash') or icp.content_hash!=canonical_hash(icp.content) or
        snapshot.get('capability',{}).get('provider')!=capability.provider or
        snapshot.get('capability',{}).get('price_version')!=capability.pricing_version):
        raise ValueError('current research actor, purpose, offer and profile required')
    operation=(await session.execute(select(ProviderOperation).where(ProviderOperation.workspace_id==workspace_id,ProviderOperation.id==row['operation_id']).with_for_update(read=True))).scalar_one_or_none()
    event=(await session.execute(select(OutboxEvent).where(OutboxEvent.workspace_id==workspace_id,OutboxEvent.id==row['outbox_id']).with_for_update(read=True))).scalar_one_or_none()
    control=(await session.execute(text('SELECT backend,epoch FROM worker_runtime_control'))).one()
    queries=snapshot.get('query_plan',{}).get('queries',[])
    query=next((q for q in queries if isinstance(q,dict) and event is not None and q.get('id')==event.payload.get('query_id')),None)
    scope_ok=False
    if event is not None and isinstance(event.payload,dict):
        if event.event_type=='provider.external':
            scope_ok=(event.payload.get('operation_id')==str(row['operation_id']) and event.payload.get('run_id')==str(run.id) and
                all(event.payload.get(k)==v for k,v in {'service':'search','market':request.market,'language':request.language,'role':'company'}.items()))
        elif event.event_type=='run.discover':
            from .run_search import require_run_search_request
            scoped_run,query=await require_run_search_request(session,workspace_id=workspace_id,event=event,request=request,capability=capability,operation_id=row['operation_id'])
            scope_ok=scoped_run.id==run.id
    allocation=(await session.execute(select(BudgetAccount.id).join(BudgetReservationAllocation,BudgetReservationAllocation.account_id==BudgetAccount.id)
        .join(BudgetReservation,BudgetReservation.id==BudgetReservationAllocation.reservation_id)
        .where(BudgetAccount.workspace_id==workspace_id,BudgetAccount.scope=='run',BudgetAccount.scope_id==run_id,BudgetReservation.operation_id==row['operation_id']))).scalar_one_or_none()
    if (operation is None or operation.status not in {'accepted','settled','succeeded'} or operation.cancel_requested or
        operation.intent_key!=request.key or operation.capability!='search' or operation.provider_ref!=str(receipt_id) or
        event is None or not scope_ok or event.intent_key!=request.key or event.state!='done' or
        (event.fencing_generation,event.runtime_backend,event.runtime_epoch)!=(row['generation'],row['runtime_backend'],row['runtime_epoch']) or
        (row['runtime_backend'],row['runtime_epoch'])!=tuple(control) or allocation is None or query is None or
        (query.get('query'),query.get('market'),query.get('language'))!=(request.query,request.market,request.language)):
        raise ValueError('received operation, frozen query, run allocation and current fence required')
    prior=(await session.execute(select(RunEvent).where(RunEvent.workspace_id==workspace_id,RunEvent.run_id==run_id,
        RunEvent.event_type=='node.committed',RunEvent.payload['receipt_id'].astext==str(receipt_id)))).scalar_one_or_none()
    if prior is not None:return dict(prior.payload)
    sources=saved['sources'];checked=[];now=datetime.now(timezone.utc)
    for item in sources:
        if not isinstance(item,dict):raise ValueError('bounded search metadata required')
        normalized=source_candidate({'url':item.get('source_url'),'title':item.get('title'),'snippet':item.get('excerpt')})
        if any(item.get(k)!=normalized[k] for k in ('source_url','title','excerpt','company_ref','registry_id','entity_status','entity_reason','content_hash','content_kind','page_retrieved')):
            raise ValueError('search metadata cannot supply entity proof or page retrieval')
        observed=datetime.fromisoformat(item.get('retrieved_at',''))
        if observed.tzinfo is None or observed>now or observed<row['created_at']:raise ValueError('receipt metadata observation time required')
        checked.append((item,observed))
    if sum(len(item['excerpt'].encode('utf-8')) for item,_ in checked)>run.limits['max_page_bytes']:
        raise UsageExceeded('metadata byte ceiling exceeded')
    # Search response counts are usage, never a supplier invoice or CostEvent.
    increments={'raw_results':len(checked)}
    if event.event_type=='run.discover':increments['in_flight']=-1
    advance_usage(run,increments,at=now)
    run.raw_result_count+=len(checked)
    unique={item['content_hash']:(item,observed) for item,observed in checked}
    for item,observed in unique.values():
        fingerprint=item['content_hash'];source_id=uuid.uuid5(receipt_id,'source:'+fingerprint)
        raw_id=uuid.uuid5(run_id,str(row['operation_id'])+':'+fingerprint)
        source=SourceDocument(id=source_id,workspace_id=workspace_id,project_id=run.project_id,run_id=run.id,
            canonical_url=item['source_url'],digest=fingerprint,retrieved_at=observed,language=request.language,
            storage_mode='search_result_metadata',excerpt=item['excerpt'],retention_until=row['retention_until'],permission_purpose='account_research')
        session.add(source);await session.flush()
        await bind_receipt_source(session,service='search',receipt_id=receipt_id,source_id=source_id)
        session.add(RawCandidate(id=raw_id,workspace_id=workspace_id,run_id=run.id,source_url=item['source_url'],normalized_url=item['source_url'],
            raw_digest=fingerprint,canonical_company_id=None,merge_state='needs_review',provider_operation_id=row['operation_id'],candidate_fingerprint=fingerprint,
            raw_payload={'source_document_id':str(source_id),'receipt_id':str(receipt_id),'content_kind':'search_result_metadata','page_retrieved':False,
                'entity_status':'needs_review','entity_reason':'legal_entity_proof_required'}))
    result={'receipt_id':str(receipt_id),'operation_id':str(row['operation_id']),'query_id':query['id'],
        'source_count':len(unique),'candidate_count':len(unique),'content_kind':'search_result_metadata','entity_status':'needs_review'}
    continuation=None
    if event.event_type=='run.discover':
        from .run_search import queue_received_run_successor
        continuation=await queue_received_run_successor(session,run=run,event=event,capability=capability,at=now)
        if continuation is not None:result['continuation']=continuation
    run.version+=1
    await append_event(session,run,'node.committed',payload=result)
    if continuation is not None and continuation['state'] in {'blocked','stopped'}:
        await append_event(session,run,'run.partial',payload={'reason':run.terminal_reason,'next_action':'review_discovery_gate'})
    return result
