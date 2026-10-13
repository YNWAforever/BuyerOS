"""Runtime-role model receipts; no fixture, selection, retry or billing inference."""
import hashlib,uuid
from .live_model import ModelRequest,canonical_json,validate_live_proposal,MAX_RESPONSE_BYTES
from .model import ModelRoute
from .base import LIVE_MODEL_PROVIDERS,ProviderIntent
from .registry import ProviderRegistration
from ..db.session import tenant_session
from ..execution.provider_context import execution_session
from sqlalchemy import select,text

class PostgresModelReceipts:
    def __init__(self,engine,workspace_id,capability,*,model_id,route):
        if (engine is None or not isinstance(workspace_id,uuid.UUID) or capability.provider not in LIVE_MODEL_PROVIDERS or capability.service!='model' or capability.max_liability is None or not isinstance(route,ModelRoute) or not route.route_id or route.permitted_tools):raise ValueError('bounded code-owned model receipt contract required')
        self.engine,self.workspace_id,self.capability,self.model_id,self.route=engine,workspace_id,capability,model_id,route
        self.contract_hash=ProviderRegistration(capability,lambda:None).contract_hash

    async def _schema(self,session):
        if (await session.execute(text('SELECT public.buyeros_model_receipts_writable()'))).scalar_one() is not True:raise ValueError('compatible0041 model receipt writes required')

    def _decode(self,row):
        if row is None:return None
        from ..services.receipt_retention import redacted_receipt
        erased=redacted_receipt(row,response_key='response')
        if erased is not None:return erased
        data=dict(row['request']);route=dict(data['route']);route['permitted_tools']=frozenset(route['permitted_tools']);data['route']=ModelRoute(**route)
        request=ModelRequest(**data)
        if (request.digest!=row['request_hash'] or request.key!=row['intent_key'] or request.model_id!=self.model_id or request.route!=self.route or row['contract_hash']!=self.contract_hash or row['pricing_version']!=self.capability.pricing_version or
            request.basis['workspace_id']!=str(self.workspace_id) or request.basis['project_id']!=str(row['project_id']) or request.basis['actor_id']!=str(row['actor_id'])):raise ValueError('frozen model receipt changed')
        response=row['response']
        if row['state']=='received' and (not isinstance(response,dict) or len(canonical_json(response))>MAX_RESPONSE_BYTES or hashlib.sha256(canonical_json(response)).hexdigest()!=row['response_hash']):raise ValueError('model response receipt changed')
        return {'ref':str(row['id']),'request':request,'state':row['state'],'response':response,'digest':row['response_hash']}

    async def _authorize(self,session,request,operation_id,outbox_id,*,statuses):
        from ..db.contact import ProviderOperation
        from ..db.outbox import OutboxEvent
        from ..db.budget import BudgetReservation
        from ..execution.external_runner import input_digest
        from ..execution.live_fit_runner import LiveFitDomainRunner
        intent=ProviderIntent(request.key,'model',request.market,request.language,request.role);bound=self.capability.max_liability
        if request.model_id!=self.model_id or request.route!=self.route or request.market not in self.capability.markets or request.language not in self.capability.languages or request.role not in self.capability.roles:raise ValueError('model scope outside frozen contract')
        basis=request.basis
        if basis['workspace_id']!=str(self.workspace_id):raise ValueError('foreign model basis')
        runner=LiveFitDomainRunner(self.engine,self.workspace_id,uuid.UUID(basis['run_id']),uuid.UUID(basis['buyer_id']),receipts=self)
        state={key:basis[key] for key in ['workspace_id','run_id','buyer_id','basis_hash']};state['workflow_version']='fit-v1'
        current,_=await runner._model_basis(session,state)
        if current!=basis:raise ValueError('model basis changed')
        operation=(await session.execute(select(ProviderOperation).where(ProviderOperation.id==operation_id).with_for_update())).scalar_one_or_none()
        event=(await session.execute(select(OutboxEvent).where(OutboxEvent.id==outbox_id).with_for_update())).scalar_one_or_none()
        reservation=(await session.execute(select(BudgetReservation).where(BudgetReservation.operation_id==operation_id).with_for_update())).scalar_one_or_none()
        control=(await session.execute(text('SELECT backend,epoch FROM worker_runtime_control'))).one()
        if (operation is None or operation.intent_key!=request.key or operation.capability!='model' or operation.input_hash!=input_digest(intent) or operation.status not in statuses or operation.cancel_requested or
            event is None or event.intent_key!=request.key or event.event_type!='provider.external' or event.state!='dispatched' or event.fencing_generation<1 or (event.runtime_backend,event.runtime_epoch)!=tuple(control) or
            not isinstance(event.payload,dict) or event.payload.get('operation_id')!=str(operation_id) or any(event.payload.get(k)!=v for k,v in {'service':'model','market':request.market,'language':request.language,'role':request.role}.items()) or
            reservation is None or reservation.state!='active' or reservation.currency!=bound.currency or reservation.price_version!=self.capability.pricing_version or reservation.upper_bound!=bound.amount or reservation.remaining_hold<bound.amount):raise ValueError('current model operation, hold or fence unavailable')
        if request.key.startswith('run-model:'):
            from ..services.run_model import require_current_run_model_scope
            require_current_run_model_scope(event,request,self.capability)
        return event

    async def prepare(self,request,*,operation_id,outbox_id):
        async with tenant_session(self.engine,self.workspace_id) as session:
            return await self.prepare_in_session(session,request,operation_id=operation_id,outbox_id=outbox_id)

    async def prepare_in_session(self,session,request,*,operation_id,outbox_id):
        """Caller owns the atomic operation/hold/counter/receipt transaction."""
        if (await session.execute(text("SELECT current_setting('app.workspace_id',true)"))).scalar_one()!=str(self.workspace_id):
            raise ValueError('current model tenant scope required')
        if not isinstance(request,ModelRequest):raise ValueError('frozen model request required')
        ref=uuid.uuid5(self.workspace_id,request.key)
        await self._schema(session)
        row=(await session.execute(text('SELECT r.*,public.buyeros_receipt_dependency_expired(r.workspace_id,$service$model$service$,r.id,r.request) AS dependency_expired FROM model_receipts r WHERE intent_key=:key'),{'key':request.key})).mappings().one_or_none()
        if row is not None:
            saved=self._decode(row)
            if saved['request']!=request or row['operation_id']!=operation_id or row['outbox_id']!=outbox_id:raise ValueError('model intent already frozen')
            return saved['ref']
        event=await self._authorize(session,request,operation_id,outbox_id,statuses={'reserved'})
        await session.execute(text("""INSERT INTO model_receipts(id,workspace_id,project_id,actor_id,operation_id,outbox_id,intent_key,request,request_hash,contract_hash,pricing_version,generation,runtime_epoch,runtime_backend)
            VALUES(:id,:ws,:project,:actor,:operation,:outbox,:key,CAST(:request AS jsonb),:hash,:contract,:price,:generation,:epoch,:backend) ON CONFLICT(workspace_id,intent_key) DO NOTHING"""),
            {'id':ref,'ws':self.workspace_id,'project':uuid.UUID(request.basis['project_id']),'actor':uuid.UUID(request.basis['actor_id']),'operation':operation_id,'outbox':outbox_id,'key':request.key,'request':canonical_json(request.payload).decode(),'hash':request.digest,'contract':self.contract_hash,'price':self.capability.pricing_version,'generation':event.fencing_generation,'epoch':event.runtime_epoch,'backend':event.runtime_backend})
        row=(await session.execute(text('SELECT r.*,public.buyeros_receipt_dependency_expired(r.workspace_id,$service$model$service$,r.id,r.request) AS dependency_expired FROM model_receipts r WHERE intent_key=:key'),{'key':request.key})).mappings().one()
        if (row['request_hash'],row['operation_id'],row['outbox_id'])!=(request.digest,operation_id,outbox_id):raise ValueError('concurrent model intent changed')
        return str(ref)

    async def claim(self,intent):
        if intent.service!='model':raise ValueError('model intent required')
        async with execution_session(self.engine,self.workspace_id) as session:
            await self._schema(session)
            row=(await session.execute(text('SELECT r.*,public.buyeros_receipt_dependency_expired(r.workspace_id,$service$model$service$,r.id,r.request) AS dependency_expired FROM model_receipts r WHERE intent_key=:key FOR UPDATE'),{'key':intent.key})).mappings().one_or_none();saved=self._decode(row)
            if saved is None:raise ValueError('durable model receipt unavailable')
            if saved['state'] in {'redacted','expired'}:return saved,False
            request=saved['request']
            if (request.market,request.language,request.role)!=(intent.market,intent.language,intent.role):raise ValueError('frozen model scope changed')
            if saved['state']!='prepared':return saved,False
            event=await self._authorize(session,request,row['operation_id'],row['outbox_id'],statuses={'submitting'})
            if (event.fencing_generation,event.runtime_backend,event.runtime_epoch)!=(row['generation'],row['runtime_backend'],row['runtime_epoch']):raise ValueError('stale model receipt')
            await session.execute(text("UPDATE model_receipts SET state='submitting',updated_at=now() WHERE id=:id AND state='prepared'"),{'id':row['id']});saved['state']='submitting'
        return saved,True

    async def finish(self,ref,*,state,response=None,digest=None):
        if state not in {'received','unknown'} or (state=='unknown' and (response is not None or digest is not None)):raise ValueError('terminal model response required')
        if state=='received' and (not isinstance(response,dict) or len(canonical_json(response))>MAX_RESPONSE_BYTES or hashlib.sha256(canonical_json(response)).hexdigest()!=digest):raise ValueError('bounded hashed model response required')
        async with execution_session(self.engine,self.workspace_id) as session:
            await self._schema(session)
            await session.execute(text("""UPDATE model_receipts r SET state=:state,response=CAST(:response AS jsonb),response_hash=:digest,updated_at=now()
                WHERE r.id=:id AND r.state='submitting' AND r.redacted_at IS NULL AND EXISTS(SELECT 1 FROM outbox_events e JOIN worker_runtime_control c ON c.singleton=1
                WHERE e.id=r.outbox_id AND e.workspace_id=r.workspace_id AND e.state='dispatched' AND e.fencing_generation=r.generation
                AND e.runtime_backend=r.runtime_backend AND e.runtime_epoch=r.runtime_epoch AND c.backend=r.runtime_backend AND c.epoch=r.runtime_epoch)"""),
                {'id':uuid.UUID(ref),'state':state,'response':canonical_json(response).decode() if response is not None else None,'digest':digest})

    async def get(self,ref):
        try:receipt_id=uuid.UUID(ref)
        except (ValueError,TypeError,AttributeError):return None
        async with tenant_session(self.engine,self.workspace_id,read_only=True) as session:
            row=(await session.execute(text('SELECT r.*,public.buyeros_receipt_dependency_expired(r.workspace_id,$service$model$service$,r.id,r.request) AS dependency_expired FROM model_receipts r WHERE id=:id'),{'id':receipt_id})).mappings().one_or_none()
            saved=self._decode(row)
            if saved is not None and saved['state']=='received':
                from ..services.receipt_retention import require_current_receipt_read
                request=saved['request']
                await require_current_receipt_read(session,workspace_id=self.workspace_id,actor_id=uuid.UUID(request.basis['actor_id']),project_id=uuid.UUID(request.basis['project_id']))
            return saved
