"""Native model boundary: short API prepare, one worker IO, current persistence.

No provider selection, settlement, hold release or run completion occurs here.
The local API engine remains on the signed host and never enters a job payload.
"""
import uuid
from sqlalchemy import select,text
from ..db.session import tenant_session
from ..db.contact import ProviderOperation
from ..db.outbox import OutboxEvent
from ..db.budget import BudgetReservation
from ..providers.base import ProviderIntent
from ..services.run_search import require_run_allocation
from ..providers.live_model import LiveModelAdapter,ModelRequest
from ..providers.model_receipts import PostgresModelReceipts
from ..services.run_model import prepare_run_model
from .external_runner import execute_external
from .live_fit_runner import LiveFitDomainRunner

def _matches_original_model_payload(actual, expected):
    """Legacy/original status proof, independent of new-submit registry authority."""
    if actual == expected:
        return True
    if not isinstance(actual, dict) or set(actual) != set(expected) | {'model_registry_contract_hash'}:
        return False
    frozen = actual['model_registry_contract_hash']
    return (isinstance(frozen, str) and len(frozen) == 64
            and all(char in '0123456789abcdef' for char in frozen)
            and all(actual[key] == value for key, value in expected.items()))


async def _require_original_received(session,store,operation_id,request,ref):
    """Current original envelope, receipt, liability and native runtime proof."""
    from .external_runner import input_digest
    basis=request.basis;ws=store.workspace_id
    key='run-model:'+str(uuid.uuid5(ws,f"{basis['run_id']}:{basis['buyer_id']}"))
    if request.key!=key or operation_id!=uuid.uuid5(ws,'run-model-operation:'+key) or ref!=str(uuid.uuid5(ws,key)):
        raise ValueError('canonical original native model intent required')
    operation=(await session.execute(select(ProviderOperation).where(ProviderOperation.workspace_id==ws,ProviderOperation.id==operation_id).with_for_update())).scalar_one_or_none()
    event=(await session.execute(select(OutboxEvent).where(OutboxEvent.workspace_id==ws,OutboxEvent.id==uuid.uuid5(ws,'run-model-event:'+key)).with_for_update())).scalar_one_or_none()
    receipt=(await session.execute(text('SELECT * FROM model_receipts WHERE workspace_id=:ws AND id=:id'),{'ws':ws,'id':uuid.UUID(ref)})).mappings().one_or_none()
    hold=(await session.execute(select(BudgetReservation).where(BudgetReservation.workspace_id==ws,BudgetReservation.operation_id==operation_id).with_for_update())).scalar_one_or_none()
    control=(await session.execute(text('SELECT backend,epoch FROM worker_runtime_control'))).one()
    intent=ProviderIntent(key,'model',request.market,request.language,request.role);bound=store.capability.max_liability
    payload={'operation_id':str(operation_id),'service':'model','market':request.market,'language':request.language,'role':request.role,
             'run_id':basis['run_id'],'buyer_id':basis['buyer_id'],'basis_hash':basis['basis_hash'],'model_request_hash':request.digest,'model_contract_hash':store.contract_hash}
    from .provider_context import active_execution
    from .external_runner import reconcile_intent_key
    execution=active_execution.get()
    status_payload={'operation_id':str(operation_id),'service':'model','market':request.market,'language':request.language,'role':request.role,'original_intent_key':key}
    if (execution is None or execution.envelope.workspace_id!=ws or execution.row.event_type!='provider.reconcile' or
        execution.row.intent_key!=reconcile_intent_key(operation_id) or execution.row.payload!=status_payload):
        raise ValueError('current original model status child required for publication')
    if (operation is None or operation.intent_key!=key or operation.capability!='model' or operation.input_hash!=input_digest(intent) or operation.status not in {'accepted','unknown','succeeded'} or operation.cancel_requested or operation.provider_ref!=ref or
        event is None or event.event_type!='provider.external' or event.intent_key!=key or event.state!='done' or not _matches_original_model_payload(event.payload,payload) or
        receipt is None or receipt['operation_id']!=operation_id or receipt['outbox_id']!=event.id or receipt['intent_key']!=key or receipt['request_hash']!=request.digest or receipt['state']!='received' or receipt['redacted_at'] is not None or
        receipt['contract_hash']!=store.contract_hash or receipt['pricing_version']!=store.capability.pricing_version or receipt['project_id']!=uuid.UUID(basis['project_id']) or receipt['actor_id']!=uuid.UUID(basis['actor_id']) or receipt['generation']<1 or event.fencing_generation<receipt['generation'] or
        (receipt['runtime_backend'],receipt['runtime_epoch'])!=tuple(control) or (event.runtime_backend,event.runtime_epoch)!=tuple(control) or
        hold is None or hold.state!='active' or hold.currency!=bound.currency or hold.price_version!=store.capability.pricing_version or hold.upper_bound!=bound.amount or hold.remaining_hold<bound.amount):
        raise ValueError('current original received model, envelope, hold or runtime unavailable')
    await require_run_allocation(session,workspace_id=ws,run_id=uuid.UUID(basis['run_id']),operation_id=operation_id)

class NativeReceivedFitRunner(LiveFitDomainRunner):
    def __init__(self,*args,original_operation,original_request,original_ref,**kwargs):
        super().__init__(*args,**kwargs)
        self.original_operation,self.original_request,self.original_ref=original_operation,original_request,original_ref

    async def _model_basis(self,session,state,*,lock_buyer=False):
        result=await super()._model_basis(session,state,lock_buyer=lock_buyer)
        await _require_original_received(session,self.receipts,self.original_operation,self.original_request,self.original_ref)
        return result

async def persist_received_run_model(fit_engine,*,workspace_id,operation_id,capability,model_id,route):
    """Re-read received frozen request/current basis; never resubmit a model."""
    async with tenant_session(fit_engine,workspace_id,read_only=True) as session:
        operation=(await session.execute(select(ProviderOperation).where(ProviderOperation.workspace_id==workspace_id,ProviderOperation.id==operation_id))).scalar_one_or_none()
        if operation is None or operation.capability!='model' or operation.status not in {'accepted','unknown','succeeded'} or not operation.provider_ref:
            raise ValueError('received original model operation required')
        ref=operation.provider_ref;key=operation.intent_key
    store=PostgresModelReceipts(fit_engine,workspace_id,capability,model_id=model_id,route=route)
    saved=await store.get(ref)
    if saved is None or saved['state']!='received' or not isinstance(saved['request'],ModelRequest) or saved['request'].key!=key:
        raise ValueError('received current original model receipt required')
    basis=saved['request'].basis
    runner=NativeReceivedFitRunner(fit_engine,workspace_id,uuid.UUID(basis['run_id']),uuid.UUID(basis['buyer_id']),receipts=store,
        original_operation=operation_id,original_request=saved['request'],original_ref=ref)
    state={'workspace_id':str(workspace_id),'run_id':basis['run_id'],'buyer_id':basis['buyer_id'],
           'workflow_version':'fit-v1','basis_hash':basis['basis_hash'],'proposal_id':ref}
    state.update(await runner.verify(state))
    return await runner.persist(state)

async def _existing_original_model(worker_engine,execution,adapter):
    """Recover a previously claimed original via status only; never reprepare."""
    from .provider_context import execution_session
    from .external_runner import input_digest
    envelope=execution.envelope
    async with execution_session(worker_engine,envelope.workspace_id) as session:
        payload=execution.row.payload;operation_id=uuid.UUID(payload['operation_id'])
        operation=(await session.execute(select(ProviderOperation).where(ProviderOperation.workspace_id==envelope.workspace_id,ProviderOperation.id==operation_id))).scalar_one_or_none()
        if operation is None or operation.status=='reserved':return None
        store=PostgresModelReceipts(worker_engine,envelope.workspace_id,adapter.capability,model_id=adapter.client.model_id,route=adapter.receipts.route)
        row=(await session.execute(text("SELECT r.*,public.buyeros_receipt_dependency_expired(r.workspace_id,'model',r.id,r.request) AS dependency_expired FROM model_receipts r WHERE operation_id=:operation"),{'operation':operation_id})).mappings().one_or_none()
        saved=store._decode(row)
        if saved is None or not isinstance(saved['request'],ModelRequest):raise ValueError('retained original model requires reconciliation')
        request=saved['request'];basis=request.basis;key=request.key
        expected={'operation_id':str(operation_id),'service':'model','market':request.market,'language':request.language,'role':request.role,
             'run_id':basis['run_id'],'buyer_id':basis['buyer_id'],'basis_hash':basis['basis_hash'],'model_request_hash':request.digest,'model_contract_hash':store.contract_hash}
        intent=ProviderIntent(key,'model',request.market,request.language,request.role)
        if (key!='run-model:'+str(uuid.uuid5(envelope.workspace_id,f"{basis['run_id']}:{basis['buyer_id']}")) or operation_id!=uuid.uuid5(envelope.workspace_id,'run-model-operation:'+key) or
            operation.intent_key!=key or operation.capability!='model' or operation.status not in {'submitting','unknown','accepted','pending','succeeded'} or operation.cancel_requested or operation.input_hash!=input_digest(intent) or operation.provider_ref!=saved['ref'] or
            execution.row.id!=uuid.uuid5(envelope.workspace_id,'run-model-event:'+key) or not _matches_original_model_payload(payload,expected) or row['outbox_id']!=envelope.outbox_id or
            row['generation']<1 or envelope.generation<row['generation'] or (row['runtime_backend'],row['runtime_epoch'])!=(execution.row.runtime_backend,envelope.runtime_epoch)):
            raise ValueError('frozen original model status scope changed')
        return operation_id,intent

def _scoped_model(worker_engine,workspace_id,adapter):
    if type(adapter) is not LiveModelAdapter or type(adapter.receipts) is not PostgresModelReceipts:
        raise ValueError('code-owned live model and durable receipt contract required')
    return LiveModelAdapter(capability=adapter.capability,client=adapter.client,
        receipts=PostgresModelReceipts(worker_engine,workspace_id,adapter.capability,model_id=adapter.client.model_id,route=adapter.receipts.route))

async def execute_received_run_model_status(worker_engine,execution,adapter,operation_id,intent,*,environment):
    scoped=_scoped_model(worker_engine,execution.envelope.workspace_id,adapter)
    await persist_received_run_model(worker_engine,workspace_id=execution.envelope.workspace_id,
        operation_id=operation_id,capability=scoped.capability,model_id=scoped.client.model_id,route=scoped.receipts.route)
    return await execute_external(worker_engine,execution.envelope.workspace_id,operation_id,execution.envelope.generation,
        scoped,intent,environment=environment,outbox_intent_key=execution.row.intent_key)

async def execute_live_run_model(worker_engine,execution,adapter,*,research_engine,environment):
    if type(adapter) is not LiveModelAdapter or type(adapter.receipts) is not PostgresModelReceipts:
        return 'capability_unavailable'
    envelope=execution.envelope;route=adapter.receipts.route;model_id=adapter.client.model_id
    scoped=_scoped_model(worker_engine,envelope.workspace_id,adapter)
    existing=await _existing_original_model(worker_engine,execution,scoped)
    if existing is not None:
        # Original process loss can precede creation of a status child. The
        # frozen submitting/accepted/unknown operation is status-only here.
        return await execute_external(worker_engine,envelope.workspace_id,existing[0],envelope.generation,
            scoped,existing[1],environment=environment,outbox_intent_key=existing[1].key)
    if research_engine is None:return 'capability_unavailable'
    async with tenant_session(research_engine,envelope.workspace_id) as session:
        prepared=await prepare_run_model(session,workspace_id=envelope.workspace_id,outbox_id=envelope.outbox_id,
            generation=envelope.generation,capability=adapter.capability,route=route,model_id=model_id,environment=environment)
    state=await execute_external(worker_engine,envelope.workspace_id,prepared.operation_id,envelope.generation,
        scoped,prepared.intent,environment=environment,outbox_intent_key=prepared.intent.key)
    # The accepted submit has already finished its native owner. A current
    # original status child owns received-result publication and reconciliation.
    return state
