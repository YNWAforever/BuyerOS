"""Server-owned native model schedule/atomic preparation; no external IO.

Scheduling freezes hashes, not source prose. Only a current dispatched child
envelope can reserve money/tokens and insert a receipt in the caller transaction.
The unselected production gate remains closed. Received/unknown work must use
reconciliation; this module never resets an intent or releases its liability.
"""
import uuid
from ..providers.base import LIVE_MODEL_PROVIDERS
from dataclasses import dataclass
from datetime import datetime,timezone
from sqlalchemy import select,text
from ..db.runs import SearchRun
from ..db.icp import Project,IcpVersion,canonical_hash
from ..db.outbox import OutboxEvent
from ..db.contact import ProviderOperation
from ..providers.base import ProviderIntent,activation_blockers
from ..providers.registry import ProviderRegistration
from ..providers.live_model import ModelRequest
from ..providers.model_receipts import PostgresModelReceipts
from ..execution.live_fit_runner import LiveFitDomainRunner
from ..execution.external_runner import input_digest
from ..settings import get_settings
from .budget_service import reserve_operation
from .run_usage import advance_usage
from .run_search import require_run_allocation

@dataclass(frozen=True)
class PreparedRunModel:
    run_id:uuid.UUID
    buyer_id:uuid.UUID
    operation_id:uuid.UUID
    receipt_id:uuid.UUID
    request:ModelRequest
    intent:ProviderIntent

def require_current_run_model_configuration(capability, route, model_id, market, language, *, frozen_hash=None):
    """Pure current registry check; no adapter/factory or original receipt rewrite."""
    from ..providers import registry
    selected=registry.DEFAULT_REGISTRY.model_run_configuration(market=market,language=language,environment='production')
    if (selected is None or selected['capability']!=capability or selected['route']!=route
        or selected['model_id']!=model_id or (frozen_hash is not None and frozen_hash!=selected['registry_contract_hash'])):
        raise ValueError('current complete reviewed model registry scope required')
    return selected


def require_current_run_model_scope(event, request, capability):
    """Only a prepared native receipt may obtain NEW submit authority."""
    frozen=(event.payload or {}).get('model_registry_contract_hash')
    if not isinstance(frozen,str) or len(frozen)!=64:
        raise ValueError('complete frozen model registry hash required')
    require_current_run_model_configuration(capability,request.route,request.model_id,request.market,request.language,frozen_hash=frozen)


async def _request(session,*,workspace_id,run_id,buyer_id,capability,route,model_id,market,language,environment):
    if environment not in {'test','production'}:raise ValueError('explicit model environment required')
    if environment!='test' and not get_settings().paid_admission_enabled:raise ValueError('paid model admission disabled')
    if any(not isinstance(value,uuid.UUID) for value in [workspace_id,run_id,buyer_id]):raise ValueError('canonical model scope required')
    if (await session.execute(text("SELECT current_setting('app.workspace_id',true)"))).scalar_one()!=str(workspace_id):raise ValueError('current model tenant scope required')
    if (capability.provider not in LIVE_MODEL_PROVIDERS or capability.service!='model' or capability.max_liability is None or
        activation_blockers(capability,market=market,language=language,role='company',environment=environment)):
        raise ValueError('verified bounded model capability unavailable')
    selected=require_current_run_model_configuration(capability,route,model_id,market,language)
    run=(await session.execute(select(SearchRun).where(SearchRun.workspace_id==workspace_id,SearchRun.id==run_id).with_for_update())).scalar_one_or_none()
    if run is None:raise ValueError('current model run required')
    control=(await session.execute(text('SELECT backend,epoch FROM worker_runtime_control'))).one()
    snapshot=run.execution_snapshot or {}
    if snapshot.get('runtime_selector')!={'backend':control.backend,'epoch':control.epoch}:raise ValueError('current model runtime selector required')
    plan=snapshot.get('query_plan') or {}
    queries=plan.get('queries') if isinstance(plan,dict) and plan.get('schema')=='query-plan.v1' else None
    if not isinstance(queries,list) or not any(isinstance(q,dict) and (q.get('market'),q.get('language'))==(market,language) for q in queries):
        raise ValueError('model market/language outside frozen run plan')
    project=(await session.execute(select(Project).where(Project.workspace_id==workspace_id,Project.id==run.project_id))).scalar_one_or_none()
    icp=(await session.execute(select(IcpVersion).where(IcpVersion.workspace_id==workspace_id,IcpVersion.id==run.icp_version_id,IcpVersion.project_id==run.project_id))).scalar_one_or_none()
    if project is None or icp is None or icp.approved_by is None or icp.basis_offer_revision!=project.offer_revision or icp.content_hash!=canonical_hash(icp.content):
        raise ValueError('current canonical model profile required')
    runner=LiveFitDomainRunner(session.bind,workspace_id,run_id,buyer_id,receipts=None)
    digest,_,_,_=await runner._basis(session,lock_buyer=True)
    state={'workspace_id':str(workspace_id),'run_id':str(run_id),'buyer_id':str(buyer_id),'workflow_version':'fit-v1','basis_hash':digest}
    basis,_=await runner._model_basis(session,state,lock_buyer=True)
    from .research_policy_context import research_use,selected_binding,evidence_urls
    from .policy_service import evaluate_current_policy
    urls=await evidence_urls(session,project_id=run.project_id,source_ids=[item['source_id'] for item in basis['evidence']])
    policy=await evaluate_current_policy(session,{'workspace_id':workspace_id,'project_id':run.project_id},
        'account_research',datetime.now(timezone.utc),
        use_context=research_use(run.project_id,'research.model',binding=selected_binding(capability),urls=urls))
    if not policy['allowed']:raise ValueError('exact current model admission policy required')
    # One stable logical run/buyer intent, even if route/source material changes.
    # Explicit recovery needs a separate contract; it cannot silently replace it.
    key='run-model:'+str(uuid.uuid5(workspace_id,f'{run_id}:{buyer_id}'))
    request=ModelRequest(key,basis,route,model_id,market,language,'company')
    contract=ProviderRegistration(capability,lambda:None).contract_hash
    operation_id=uuid.uuid5(workspace_id,'run-model-operation:'+key)
    payload={'operation_id':str(operation_id),'service':'model','market':market,'language':language,'role':'company',
             'run_id':str(run_id),'buyer_id':str(buyer_id),'basis_hash':digest,'model_request_hash':request.digest,'model_contract_hash':contract,'model_registry_contract_hash':selected['registry_contract_hash']}
    return run,request,payload,control

async def queue_run_model(session,*,workspace_id,run_id,buyer_id,capability,route,model_id,market,language,environment='production'):
    """Freeze one child wakeup only; dispatch preparation is monetary admission."""
    run,request,payload,control=await _request(session,workspace_id=workspace_id,run_id=run_id,buyer_id=buyer_id,
        capability=capability,route=route,model_id=model_id,market=market,language=language,environment=environment)
    store=PostgresModelReceipts(session.bind,workspace_id,capability,model_id=model_id,route=route);await store._schema(session)
    event_id=uuid.uuid5(workspace_id,'run-model-event:'+request.key)
    event=(await session.execute(select(OutboxEvent).where(OutboxEvent.workspace_id==workspace_id,OutboxEvent.intent_key==request.key,OutboxEvent.event_type=='provider.external').with_for_update())).scalar_one_or_none()
    if event is not None:
        if event.id!=event_id or event.payload!=payload or (event.runtime_backend,event.runtime_epoch)!=tuple(control):raise ValueError('frozen model intent changed; reconciliation required')
        return event.id
    session.add(OutboxEvent(id=event_id,workspace_id=workspace_id,intent_key=request.key,event_type='provider.external',payload=payload,runtime_backend=control.backend,runtime_epoch=control.epoch))
    await session.flush()
    return event_id

async def prepare_run_model(session,*,workspace_id,outbox_id,generation,capability,route,model_id,environment='production'):
    """Reserve original operation/receipt/run token bound together; never submit."""
    if not isinstance(workspace_id,uuid.UUID) or not isinstance(outbox_id,uuid.UUID) or type(generation) is not int or generation<1:raise ValueError('canonical dispatched model reference required')
    observed=(await session.execute(select(OutboxEvent).where(OutboxEvent.workspace_id==workspace_id,OutboxEvent.id==outbox_id))).scalar_one_or_none()
    if observed is None or observed.event_type!='provider.external' or not isinstance(observed.payload,dict):raise ValueError('original model envelope required')
    data=dict(observed.payload)
    try:run_id=uuid.UUID(data['run_id']);buyer_id=uuid.UUID(data['buyer_id']);market=data['market'];language=data['language']
    except (KeyError,TypeError,ValueError,AttributeError) as exc:raise ValueError('original model scope required') from exc
    run,request,payload,control=await _request(session,workspace_id=workspace_id,run_id=run_id,buyer_id=buyer_id,
        capability=capability,route=route,model_id=model_id,market=market,language=language,environment=environment)
    # Lock order is run/buyer then event, matching queue and native fit readers.
    event=(await session.execute(select(OutboxEvent).where(OutboxEvent.workspace_id==workspace_id,OutboxEvent.id==outbox_id).with_for_update().execution_options(populate_existing=True))).scalar_one()
    if (event.id!=uuid.uuid5(workspace_id,'run-model-event:'+request.key) or event.intent_key!=request.key or event.payload!=payload or
        event.state!='dispatched' or event.fencing_generation!=generation or (event.runtime_backend,event.runtime_epoch)!=tuple(control)):
        raise ValueError('current frozen dispatched model fence required')
    operation_id=uuid.UUID(payload['operation_id']);intent=ProviderIntent(request.key,'model',market,language,'company')
    store=PostgresModelReceipts(session.bind,workspace_id,capability,model_id=model_id,route=route);await store._schema(session)
    operation=(await session.execute(select(ProviderOperation).where(ProviderOperation.workspace_id==workspace_id,ProviderOperation.intent_key==request.key).with_for_update())).scalar_one_or_none()
    row=(await session.execute(text("SELECT r.*,public.buyeros_receipt_dependency_expired(r.workspace_id,'model',r.id,r.request) AS dependency_expired FROM model_receipts r WHERE intent_key=:key"),{'key':request.key})).mappings().one_or_none()
    if operation is not None:
        saved=store._decode(row)
        if (operation.id!=operation_id or operation.status!='reserved' or operation.input_hash!=input_digest(intent) or
            saved is None or saved['state']!='prepared' or saved['request']!=request):
            raise ValueError('existing model operation requires reconciliation')
        await require_run_allocation(session,workspace_id=workspace_id,run_id=run_id,operation_id=operation_id)
        await store._authorize(session,request,operation_id,outbox_id,statuses={'reserved'})
    else:
        if row is not None:raise ValueError('existing model receipt requires reconciliation')
        bound=capability.max_liability
        await reserve_operation(session,operation_id,{'workspace_id':workspace_id,'project_id':run.project_id,'run_id':run_id,'category':'discovery'},bound.amount,bound.currency,capability.pricing_version)
        # This is a conservative reservation of the entire bounded route, not
        # observed supplier usage. Unknown/accepted attempts keep this ceiling.
        tokens=(route.max_input_tokens+route.max_output_tokens)*(route.repair_limit+1)
        advance_usage(run,{'model_tokens':tokens,'in_flight':1},at=datetime.now(timezone.utc),external=True)
        session.add(ProviderOperation(id=operation_id,workspace_id=workspace_id,intent_key=request.key,capability='model',input_hash=input_digest(intent),status='reserved'))
        run.version+=1;await session.flush()
    ref=await store.prepare_in_session(session,request,operation_id=operation_id,outbox_id=outbox_id)
    operation=(await session.execute(select(ProviderOperation).where(ProviderOperation.id==operation_id).with_for_update())).scalar_one()
    if operation.provider_ref not in {None,ref}:raise ValueError('frozen local model reference differs')
    operation.provider_ref=ref
    return PreparedRunModel(run_id,buyer_id,operation_id,uuid.UUID(ref),request,intent)


async def schedule_reviewed_run_model(session, *, workspace_id, run_id, buyer_id, raw_candidate_id, search_capability):
    """First accepted review only; freeze one wakeup, never reserve or call a provider.

    Discovery may stream alongside fit. Its original pending events and economic
    intents remain fenced from run completion by pending_run_work.
    """
    from ..db.runs import RawCandidate
    from ..providers import registry
    from ..providers.live_search import PostgresSearchReceipts
    from .run_events import append_event
    run=(await session.execute(select(SearchRun).where(SearchRun.workspace_id==workspace_id,SearchRun.id==run_id).with_for_update())).scalar_one()
    raw=(await session.execute(select(RawCandidate).where(RawCandidate.workspace_id==workspace_id,RawCandidate.run_id==run_id,RawCandidate.id==raw_candidate_id))).scalar_one()

    async def blocked(code):
        await append_event(session,run,'candidate.model_queue_blocked',payload={
            'raw_candidate_id':str(raw_candidate_id),'buyer_id':str(buyer_id),'code':code,
            'next_action':'review_model_readiness_then_start_new_run'})
        return None

    if not get_settings().paid_admission_enabled:
        return await blocked('PAID_ADMISSION_DISABLED')
    try:
        receipt_id=uuid.UUID((raw.raw_payload or {})['receipt_id'])
    except (KeyError,ValueError,TypeError,AttributeError):
        return await blocked('ORIGINAL_SEARCH_SCOPE_UNAVAILABLE')
    row=(await session.execute(text("SELECT r.*,public.buyeros_receipt_dependency_expired(r.workspace_id,'search',r.id,r.request) AS dependency_expired FROM search_receipts r WHERE r.workspace_id=:ws AND r.id=:id"),{'ws':workspace_id,'id':receipt_id})).mappings().one_or_none()
    saved=PostgresSearchReceipts(session.bind,workspace_id,search_capability)._decode(row)
    if saved is None or saved['state']!='received' or row['operation_id']!=raw.provider_operation_id:
        return await blocked('ORIGINAL_SEARCH_SCOPE_UNAVAILABLE')
    original=saved['request']
    selected=registry.DEFAULT_REGISTRY.model_run_configuration(market=original.market,language=original.language,environment='production')
    if selected is None:
        return await blocked('MODEL_SCOPE_UNAVAILABLE')
    if run.status!='running' or run.stage not in {'discovery','fit'} or (run.execution_snapshot or {}).get('runtime_selector',{}).get('backend')!='cloudflare':
        return await blocked('CURRENT_NATIVE_RUN_REQUIRED')
    # Downstream model readiness can disappear without invalidating the accepted
    # entity/source review. Roll back only this new wakeup and stage transition.
    try:
        async with session.begin_nested():
            if run.stage!='fit':
                run.stage='fit';run.version+=1
                await session.flush()
            event_id=await queue_run_model(session,workspace_id=workspace_id,run_id=run_id,buyer_id=buyer_id,
                capability=selected['capability'],route=selected['route'],model_id=selected['model_id'],
                market=original.market,language=original.language,environment='production')
    except ValueError:
        await session.refresh(run)
        return await blocked('CURRENT_MODEL_BASIS_CHANGED')
    await append_event(session,run,'candidate.model_queued',payload={
        'raw_candidate_id':str(raw_candidate_id),'buyer_id':str(buyer_id),'outbox_id':str(event_id),
        'search_receipt_id':str(receipt_id),'market':original.market,'language':original.language,
        'model_registry_contract_hash':selected['registry_contract_hash']})
    return event_id
