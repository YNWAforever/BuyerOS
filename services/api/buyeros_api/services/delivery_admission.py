"""Atomic private delivery producer. No public route or provider selection here.

The producer persists the exact reviewed authority with the original operation,
three-scope reservation, immutable message/liability and a paid delivery outbox.
Dispatch/receipt billing require their own reviewed implementation and gates.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime,timezone
from sqlalchemy import select
from ..api.errors import ApiError
from ..db.budget import BudgetAccount,BudgetReservation,BudgetReservationAllocation
from ..db.contact import ProviderOperation
from ..db.delivery import DeliveryAuthorization,DeliveryLiability,DeliveryMessage
from ..db.drafts import OutreachDraft
from ..db.outbox import OutboxEvent
from ..db.worker_execution import WorkerRuntimeControl
from ..settings import get_settings
from .delivery_budget import DeliveryBudgetAuthorization,reserve_delivery_operation
from .delivery_service import prepare_delivery_intent

@dataclass(frozen=True)
class DeliveryAdmission:
    message_id:uuid.UUID
    operation_id:uuid.UUID
    reservation_id:uuid.UUID
    outbox_id:uuid.UUID
    state:str
    replayed:bool

def _require_authority(authorization):
    if (not isinstance(authorization,DeliveryBudgetAuthorization)
        or not authorization.selected or not authorization.reviewed or not authorization.sender_verified
        or authorization.valid_until<=datetime.now(timezone.utc)):
        raise ApiError(503,'PROVIDER_UNAVAILABLE','selected reviewed delivery authority is unavailable')

def _outbox_binding(message,scope_hash):
    return {'workspace_id':str(message.workspace_id),'message_id':str(message.id),
            'operation_id':str(message.operation_id),'scope_hash':scope_hash}

async def _original_admission(session,message,authorization):
    recorded=(await session.execute(select(DeliveryAuthorization).where(
        DeliveryAuthorization.workspace_id==message.workspace_id,
        DeliveryAuthorization.message_id==message.id))).scalar_one_or_none()
    if recorded is None:
        raise ApiError(409,'RETRY_UNSAFE','original delivery authority requires reconciliation')
    if recorded.scope_hash!=authorization.scope_hash or recorded.scope_json!=authorization.scope_json:
        raise ApiError(409,'IDEMPOTENCY_CONFLICT','original reviewed delivery scope differs')
    liability=(await session.execute(select(DeliveryLiability).where(
        DeliveryLiability.workspace_id==message.workspace_id,
        DeliveryLiability.message_id==message.id))).scalar_one_or_none()
    operation=(await session.execute(select(ProviderOperation).where(
        ProviderOperation.workspace_id==message.workspace_id,
        ProviderOperation.id==message.operation_id))).scalar_one_or_none()
    outbox=(await session.execute(select(OutboxEvent).where(
        OutboxEvent.workspace_id==message.workspace_id,
        OutboxEvent.id==recorded.outbox_id))).scalar_one_or_none()
    reservation=(await session.execute(select(BudgetReservation).where(
        BudgetReservation.workspace_id==message.workspace_id,
        BudgetReservation.id==liability.reservation_id))).scalar_one_or_none() if liability else None
    allocations=(await session.execute(select(BudgetAccount.scope,BudgetAccount.scope_id,BudgetAccount.category)
        .join(BudgetReservationAllocation,BudgetReservationAllocation.account_id==BudgetAccount.id)
        .where(BudgetReservationAllocation.workspace_id==message.workspace_id,
               BudgetReservationAllocation.reservation_id==reservation.id))).all() if reservation else []
    if (liability is None or operation is None or outbox is None or reservation is None
        or liability.operation_id!=operation.id or reservation.operation_id!=operation.id
        or operation.capability!='delivery' or operation.intent_key!=message.intent_key
        or operation.input_hash!=message.payload_digest or operation.provider_name!=message.provider_name
        or operation.account_reference!=message.account_reference
        or outbox.intent_key!=message.intent_key or outbox.event_type!='delivery.submit'
        or outbox.payload!=_outbox_binding(message,recorded.scope_hash)
        or liability.max_liability!=authorization.upper_bound or reservation.upper_bound!=authorization.upper_bound
        or liability.currency!=authorization.currency or reservation.currency!=authorization.currency
        or liability.pricing_version!=authorization.pricing_version or reservation.price_version!=authorization.pricing_version
        or len(allocations)!=3 or set(allocations)!={('workspace',message.workspace_id,'all'),('project',message.project_id,'all'),('category',message.project_id,'delivery')}):
        raise ApiError(409,'RETRY_UNSAFE','original delivery admission requires reconciliation')
    # No reserve, enqueue, submit, ref/key change or release on a durable replay.
    return DeliveryAdmission(message.id,operation.id,reservation.id,outbox.id,message.state,True)

async def admit_delivery(session,*,authorization:DeliveryBudgetAuthorization|None=None,environment='production',**bindings)->DeliveryAdmission:
    # The object is supplied by server-owned selection, never HTTP/client JSON.
    # The selection remains absent and the existing public403 is retained.
    _require_authority(authorization)
    if environment not in {'production','test'} or (environment!='test' and not get_settings().paid_admission_enabled):
        raise ApiError(503,'CAPABILITY_DISABLED','new paid delivery admission is disabled')
    async with session.begin_nested():
        prepared=await prepare_delivery_intent(session,**bindings)
        intent=prepared.intent
        project_id,revision_number=(await session.execute(select(OutreachDraft.project_id,OutreachDraft.current_revision).where(
            OutreachDraft.workspace_id==intent.workspace_id,OutreachDraft.id==bindings['draft_id']))).one()
        if (authorization.workspace_id!=intent.workspace_id or authorization.project_id!=project_id
            or authorization.sender_identity_id!=intent.sender_identity_id or intent.recipient_ref not in authorization.recipient_refs):
            raise ApiError(503,'PROVIDER_UNAVAILABLE','original delivery scope is not authorized')
        existing=(await session.execute(select(DeliveryMessage).where(
            DeliveryMessage.workspace_id==intent.workspace_id,DeliveryMessage.intent_key==intent.key).with_for_update())).scalar_one_or_none()
        if existing is not None:
            expected={'project_id':project_id,'draft_id':bindings['draft_id'],'draft_revision_id':intent.draft_revision_id,
                'revision_number':revision_number,'recipient_ref':intent.recipient_ref,'sender_identity_id':intent.sender_identity_id,
                'approval_id':intent.approval_id,'actor_id':bindings['actor_id'],'provider_name':authorization.provider_name,
                'account_reference':authorization.account_reference,'payload_digest':intent.payload_digest}
            if any(getattr(existing,key)!=value for key,value in expected.items()):
                raise ApiError(409,'IDEMPOTENCY_CONFLICT','original delivery intent binding differs')
            result=await _original_admission(session,existing,authorization)
            _require_authority(authorization)
            return result
        # The locked canonical draft serializes new keys on the same message
        # identity. A fresh approval/account/key cannot blindly resend this copy.
        prior=(await session.execute(select(DeliveryMessage.id).where(
            DeliveryMessage.workspace_id==intent.workspace_id,
            DeliveryMessage.draft_revision_id==intent.draft_revision_id,
            DeliveryMessage.recipient_ref==intent.recipient_ref))).first()
        pending=(await session.execute(select(DeliveryMessage.id).where(
            DeliveryMessage.workspace_id==intent.workspace_id,DeliveryMessage.draft_id==bindings['draft_id'],
            DeliveryMessage.recipient_ref==intent.recipient_ref,
            DeliveryMessage.state.in_({'prepared','submitting','unknown','accepted'})))).first()
        orphan=(await session.execute(select(ProviderOperation.id).where(
            ProviderOperation.workspace_id==intent.workspace_id,ProviderOperation.intent_key==intent.key))).first()
        if prior is not None or pending is not None or orphan is not None:
            raise ApiError(409,'RETRY_UNSAFE','original delivery intent requires reconciliation')
        runtime=(await session.execute(select(WorkerRuntimeControl.backend,WorkerRuntimeControl.enabled,WorkerRuntimeControl.epoch))).one_or_none()
        if (runtime is None or not runtime.enabled or runtime.backend not in {'celery','cloudflare'}
            or type(runtime.epoch) is not int or not 1<=runtime.epoch<=9007199254740991):
            raise ApiError(503,'CAPABILITY_DISABLED','current delivery worker selector is unavailable')
        operation=ProviderOperation(id=uuid.uuid4(),workspace_id=intent.workspace_id,intent_key=intent.key,
            capability='delivery',input_hash=intent.payload_digest,provider_name=authorization.provider_name,
            account_reference=authorization.account_reference,status='intent',deadline=authorization.valid_until)
        session.add(operation);await session.flush()
        reservation_id=await reserve_delivery_operation(session,operation_id=operation.id,authorization=authorization,**bindings)
        message=DeliveryMessage(id=uuid.uuid4(),workspace_id=intent.workspace_id,project_id=project_id,
            draft_id=bindings['draft_id'],draft_revision_id=intent.draft_revision_id,revision_number=revision_number,
            recipient_ref=intent.recipient_ref,sender_identity_id=intent.sender_identity_id,
            approval_id=intent.approval_id,actor_id=bindings['actor_id'],operation_id=operation.id,
            intent_key=intent.key,provider_name=authorization.provider_name,account_reference=authorization.account_reference,
            payload_digest=intent.payload_digest,state='prepared')
        session.add(message);await session.flush()
        liability=DeliveryLiability(workspace_id=intent.workspace_id,message_id=message.id,operation_id=operation.id,
            reservation_id=reservation_id,max_liability=authorization.upper_bound,currency=authorization.currency,
            pricing_version=authorization.pricing_version)
        outbox=OutboxEvent(id=uuid.uuid4(),workspace_id=intent.workspace_id,intent_key=intent.key,
            event_type='delivery.submit',payload=_outbox_binding(message,authorization.scope_hash),
            runtime_backend=runtime.backend,runtime_epoch=runtime.epoch)
        session.add_all([liability,outbox]);await session.flush()
        session.add(DeliveryAuthorization(workspace_id=intent.workspace_id,message_id=message.id,outbox_id=outbox.id,
            scope_hash=authorization.scope_hash,scope_json=authorization.scope_json,valid_until=authorization.valid_until))
        await session.flush();_require_authority(authorization)
        return DeliveryAdmission(message.id,operation.id,reservation_id,outbox.id,message.state,False)
