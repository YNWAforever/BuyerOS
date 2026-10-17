"""API-role frozen research preparation; no network or provider activation.

Only the original run.discover envelope is accepted. Its payload is never
rewritten. A separate worker role claims the receipt before external IO.
"""
import re,uuid
from ..providers.base import LIVE_SEARCH_PROVIDERS
from dataclasses import dataclass
from datetime import datetime,timezone
from sqlalchemy import select,text
from ..api.deps import permission_for_roles
from ..db.models import Membership
from ..db.icp import Project,IcpVersion,canonical_hash
from ..db.runs import SearchRun
from ..db.outbox import OutboxEvent
from ..db.contact import ProviderOperation
from ..db.budget import BudgetAccount,BudgetReservation,BudgetReservationAllocation
from ..providers.base import ProviderIntent
from ..providers.registry import ProviderRegistration
from ..providers.live_search import SearchRequest,PostgresSearchReceipts
from ..execution.external_runner import input_digest
from ..execution.run_emitter import emit_run_event
from .policy_service import evaluate_current_policy
from .budget_service import reserve_operation
from .run_usage import advance_usage,UsageExceeded

@dataclass(frozen=True)
class PreparedRunSearch:
    run_id:uuid.UUID
    operation_id:uuid.UUID
    receipt_id:uuid.UUID
    request:SearchRequest
    intent:ProviderIntent

def require_current_run_search_scope(frozen,query,capability):
    """Authorize a NEW hold/call using current code-owned reviewed registry scope.

    Original uncertain receipts use their original contract for reconciliation;
    lack of a new scope hash never creates fresh execution authority.
    """
    from ..providers import registry
    current=registry.DEFAULT_REGISTRY.search_run_capability(environment='production')
    if (current is None or frozen.get('registry_contract_hash')!=current['registry_contract_hash'] or
        frozen.get('receipt_contract_hash')!=current['receipt_contract_hash'] or
        current['receipt_contract_hash']!=ProviderRegistration(capability,lambda:None).contract_hash or
        frozen.get('market_languages')!=current['market_languages'] or
        query.get('language') not in current['market_languages'].get(query.get('market'),[])):
        raise ValueError('current reviewed search registry scope required for new work')

async def frozen_run_search(session,*,workspace_id,event,capability,new_call=False):
    """Recheck current actor/profile and frozen server query on both DB roles."""
    if (event is None or event.workspace_id!=workspace_id or event.event_type!='run.discover' or
        not isinstance(event.payload,dict) or set(event.payload)-{'run_id','query_index'}):
        raise ValueError('original research envelope required')
    try:run_id=uuid.UUID(event.payload['run_id'])
    except (KeyError,TypeError,ValueError,AttributeError) as exc:raise ValueError('canonical run reference required') from exc
    index=event.payload.get('query_index',0)
    if type(index) is not int or index<0:raise ValueError('frozen query index required')
    run=(await session.execute(select(SearchRun).where(SearchRun.workspace_id==workspace_id,SearchRun.id==run_id).with_for_update())).scalar_one_or_none()
    if run is None or run.status not in {'queued','running','partial'}:raise ValueError('current resumable run required')
    snapshot=run.execution_snapshot or {};frozen=snapshot.get('capability') or {};plan=snapshot.get('query_plan') or {}
    queries=plan.get('queries')
    if (capability.provider not in LIVE_SEARCH_PROVIDERS or capability.service!='search' or capability.max_liability is None or
        capability.idempotency!='verified' or capability.status!='verified' or
        frozen.get('receipt_contract_hash')!=ProviderRegistration(capability,lambda:None).contract_hash or
        frozen.get('provider')!=capability.provider or frozen.get('price_version')!=capability.pricing_version or
        not {'market','language'}.issubset(set(frozen.get('verified_filters',[]))) or
        plan.get('schema')!='query-plan.v1' or not isinstance(queries,list) or index>=len(queries)):
        raise ValueError('complete frozen verified search contract required')
    query=queries[index]
    if (not isinstance(query,dict) or not re.fullmatch(r'[0-9a-f]{24}',str(query.get('id',''))) or
        query.get('market') not in frozen.get('markets',[]) or query.get('market') not in capability.markets or
        query.get('language') not in frozen.get('languages',[]) or query.get('language') not in capability.languages or
        query.get('filters')!={'market':query.get('market'),'language':query.get('language')} or
        type(query.get('round')) is not int or not 1<=query['round']<=run.limits['query_rounds']):
        raise ValueError('frozen supported research query required')
    if new_call:require_current_run_search_scope(frozen,query,capability)
    try:actor=uuid.UUID(snapshot['actor_id'])
    except (KeyError,ValueError,TypeError,AttributeError) as exc:raise ValueError('canonical research actor required') from exc
    member=(await session.execute(select(Membership).where(Membership.workspace_id==workspace_id,Membership.user_id==actor,Membership.active.is_(True)).with_for_update(read=True))).scalar_one_or_none()
    project=(await session.execute(select(Project).where(Project.workspace_id==workspace_id,Project.id==run.project_id).with_for_update(read=True))).scalar_one_or_none()
    icp=(await session.execute(select(IcpVersion).where(IcpVersion.workspace_id==workspace_id,IcpVersion.project_id==run.project_id,IcpVersion.id==run.icp_version_id).with_for_update(read=True))).scalar_one_or_none()
    from .research_policy_context import research_use,selected_binding,metadata_binding
    binding=selected_binding(capability) if new_call else metadata_binding(frozen,historical=True)
    policy=await evaluate_current_policy(session,{'workspace_id':workspace_id,'project_id':run.project_id},
        'account_research',datetime.now(timezone.utc),
        use_context=research_use(run.project_id,'research.search',binding=binding))
    if (member is None or not permission_for_roles(member.roles,'startRun') or not policy['allowed'] or
        project is None or project.status!='active' or icp is None or project.active_icp_version_id!=icp.id or
        icp.approved_at is None or icp.approved_by is None or icp.superseded_at is not None or
        icp.basis_offer_revision!=project.offer_revision or project.offer_revision!=snapshot.get('offer_revision') or
        icp.content_hash!=snapshot.get('icp_content_hash') or icp.content_hash!=canonical_hash(icp.content)):
        raise ValueError('current research actor, purpose, offer and profile required')
    return run,query,index,actor

async def require_run_allocation(session,*,workspace_id,run_id,operation_id):
    account=(await session.execute(select(BudgetAccount.id).join(BudgetReservationAllocation,BudgetReservationAllocation.account_id==BudgetAccount.id)
        .join(BudgetReservation,BudgetReservation.id==BudgetReservationAllocation.reservation_id)
        .where(BudgetAccount.workspace_id==workspace_id,BudgetAccount.scope=='run',BudgetAccount.scope_id==run_id,BudgetReservation.operation_id==operation_id))).scalar_one_or_none()
    if account is None:raise ValueError('current operation run allocation required')

async def require_run_search_request(session,*,workspace_id,event,request,capability,operation_id,new_call=False):
    run,query,_,actor=await frozen_run_search(session,workspace_id=workspace_id,event=event,capability=capability,new_call=new_call)
    if (request.key!=event.intent_key or request.project_id!=run.project_id or request.actor_id!=actor or request.role!='company' or
        (request.query,request.market,request.language)!=(query.get('query'),query.get('market'),query.get('language'))):
        raise ValueError('receipt differs from frozen run query')
    await require_run_allocation(session,workspace_id=workspace_id,run_id=run.id,operation_id=operation_id)
    return run,query

async def prepare_run_search(session,*,workspace_id,outbox_id,generation,capability):
    """Caller commits request/operation/hold/counters together; never submits."""
    if not isinstance(workspace_id,uuid.UUID) or not isinstance(outbox_id,uuid.UUID) or type(generation) is not int or generation<1:
        raise ValueError('canonical workspace/outbox and generation required')
    if (await session.execute(text("SELECT current_setting('app.workspace_id',true)"))).scalar_one()!=str(workspace_id):
        raise ValueError('current tenant scope required')
    store=PostgresSearchReceipts(session.bind,workspace_id,capability);await store._require_schema(session)
    event=(await session.execute(select(OutboxEvent).where(OutboxEvent.workspace_id==workspace_id,OutboxEvent.id==outbox_id).with_for_update())).scalar_one_or_none()
    control=(await session.execute(text('SELECT backend,epoch FROM worker_runtime_control'))).one()
    if event is None or event.state!='dispatched' or event.fencing_generation!=generation or (event.runtime_backend,event.runtime_epoch)!=tuple(control):
        raise ValueError('current dispatched research fence required')
    run,query,index,actor=await frozen_run_search(session,workspace_id=workspace_id,event=event,capability=capability,new_call=True)
    intent=ProviderIntent(event.intent_key,'search',query['market'],query['language'],'company')
    operation_id=uuid.uuid5(workspace_id,'run-search:'+event.intent_key)
    existing=(await session.execute(select(ProviderOperation).where(ProviderOperation.workspace_id==workspace_id,ProviderOperation.intent_key==event.intent_key).with_for_update())).scalar_one_or_none()
    if existing is not None:
        # Recovered accepted/unknown work can only reconcile, never reprepare.
        saved=(await session.execute(text("SELECT r.*,public.buyeros_receipt_dependency_expired(r.workspace_id,'search',r.id,r.request) AS dependency_expired FROM search_receipts r WHERE intent_key=:key"),{'key':event.intent_key})).mappings().one_or_none()
        decoded=store._decode(saved)
        if existing.id!=operation_id or existing.status!='reserved' or decoded is None or decoded['state']!='prepared':
            raise ValueError('existing research operation requires reconciliation')
        request=decoded['request']
    else:
        if index!=(run.usage_counters or {}).get('queries',0):raise ValueError('next unclaimed frozen query required')
        remaining=run.limits['max_results']-(run.usage_counters or {}).get('raw_results',0)
        if remaining<=0:raise UsageExceeded('raw result ceiling reached')
        request=SearchRequest(key=intent.key,query=query['query'],market=intent.market,language=intent.language,role='company',
            limit=min(20,remaining),project_id=run.project_id,actor_id=actor)
        bound=capability.max_liability
        await reserve_operation(session,operation_id,{'workspace_id':workspace_id,'project_id':run.project_id,'run_id':run.id,'category':'discovery'},
            bound.amount,bound.currency,capability.pricing_version)
        rounds=(run.usage_counters or {}).get('rounds',0)
        if query['round']<rounds or query['round']>rounds+1:raise ValueError('next bounded query round required')
        advance_usage(run,{'queries':1,'in_flight':1,'rounds':query['round']-rounds},at=datetime.now(timezone.utc))
        session.add(ProviderOperation(id=operation_id,workspace_id=workspace_id,intent_key=intent.key,capability='search',input_hash=input_digest(intent),status='reserved'))
        if run.status=='queued':await emit_run_event(session,run.id,'run.started',transition='start',payload={'query_id':query['id']})
        if run.stage!='fit':run.stage='discovery'
        run.version+=1;await session.flush()
    ref=await store.prepare_in_session(session,request,operation_id=operation_id,outbox_id=outbox_id)
    operation=(await session.execute(select(ProviderOperation).where(ProviderOperation.id==operation_id).with_for_update())).scalar_one()
    if operation.provider_ref not in {None,ref}:raise ValueError('frozen local search reference differs')
    # This is the durable local receipt reference. It asserts neither supplier
    # acceptance nor a native vendor request/status/idempotency guarantee.
    operation.provider_ref=ref
    return PreparedRunSearch(run.id,operation_id,uuid.UUID(ref),request,intent)

async def resume_received_run_search(session,*,workspace_id,operation_id,capability):
    """Current local response proof after status recovery; zero vendor calls."""
    if not isinstance(workspace_id,uuid.UUID) or not isinstance(operation_id,uuid.UUID):
        raise ValueError('canonical research operation required')
    row=(await session.execute(text('SELECT id,outbox_id FROM search_receipts WHERE workspace_id=:ws AND operation_id=:op'),
        {'ws':workspace_id,'op':operation_id})).mappings().one_or_none()
    event=(await session.execute(select(OutboxEvent).where(OutboxEvent.workspace_id==workspace_id,
        OutboxEvent.id==row['outbox_id']).with_for_update(read=True))).scalar_one_or_none() if row else None
    if event is None or event.event_type!='run.discover':raise ValueError('original research receipt binding required')
    from .search_intake import ingest_received_search
    run_id=uuid.UUID(event.payload['run_id'])
    result=await ingest_received_search(session,workspace_id=workspace_id,run_id=run_id,receipt_id=row['id'],capability=capability)
    # Internal continuation ID comes only from the guarded original outbox.
    # The stored checkpoint remains unchanged; this is not a public schema.
    return {**result,'run_id':str(run_id)}


async def queue_received_run_successor(session, *, run, event, capability, at):
    """Queue one unattempted frozen query in the received-intake transaction.

    This adds no monetary reservation and performs no IO. The next worker must
    recheck the current scope/fence and atomically reserve its own liability.
    The original accepted operation and its unknown economic hold stay intact.
    """
    from types import SimpleNamespace
    from .outbox_service import build_intent
    index = event.payload.get('query_index', 0) + 1
    queries = run.execution_snapshot['query_plan']['queries']
    if index >= len(queries):
        return None
    if run.status != 'running':
        return {'state': 'blocked', 'code': 'RUN_STATE'}
    if index != (run.usage_counters or {}).get('queries', 0):
        raise ValueError('received query must precede the next unclaimed query')
    payload = {'run_id': str(run.id), 'query_index': index}
    key = build_intent('run.discover', payload, index)
    child = OutboxEvent(id=uuid.uuid5(run.workspace_id, 'run-search-event:' + key),
        workspace_id=run.workspace_id, intent_key=key, event_type='run.discover',
        payload=payload, runtime_backend=event.runtime_backend, runtime_epoch=event.runtime_epoch)
    try:
        _, query, _, _ = await frozen_run_search(session, workspace_id=run.workspace_id,
            event=child, capability=capability, new_call=True)
    except ValueError:
        # Receipt ingestion must survive revocation of authority for NEW work.
        run.status = 'partial'; run.stage = 'discovery'; run.terminal_reason = 'capability_unavailable'
        return {'state': 'blocked', 'code': 'CAPABILITY_UNAVAILABLE'}
    try:
        usage = run.usage_counters or {}
        if run.limits['max_results'] - usage.get('raw_results', 0) <= 0:
            raise UsageExceeded('raw result ceiling reached')
        rounds = usage.get('rounds', 0)
        if query['round'] < rounds or query['round'] > rounds + 1:
            raise UsageExceeded('next bounded query round required')
        # Probe the existing ceiling rules without claiming usage before dispatch.
        probe = SimpleNamespace(limits=run.limits, target_companies=run.target_companies,
            usage_counters=dict(usage), first_dispatch_at=run.first_dispatch_at)
        advance_usage(probe, {'queries': 1, 'in_flight': 1, 'rounds': query['round'] - rounds}, at=at)
    except UsageExceeded:
        run.status = 'partial'; run.stage = 'discovery'; run.terminal_reason = 'query_limit'
        return {'state': 'stopped', 'code': 'RUN_LIMIT'}
    existing = (await session.execute(select(OutboxEvent).where(
        OutboxEvent.workspace_id == run.workspace_id, OutboxEvent.event_type == 'run.discover',
        OutboxEvent.intent_key == key).with_for_update())).scalar_one_or_none()
    if existing is not None:
        if (existing.id != child.id or existing.payload != payload or
            (existing.runtime_backend, existing.runtime_epoch) != (child.runtime_backend, child.runtime_epoch)):
            raise ValueError('frozen query continuation changed; reconciliation required')
    else:
        session.add(child)
        await session.flush()
    return {'state': 'queued', 'outbox_id': str(child.id), 'query_index': index}
