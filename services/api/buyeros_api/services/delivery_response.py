"""Private durable delivery submit observations; no provider I/O or activation.

Apply only after the one POST permit was committed and its transaction closed.
Retained reconciliation authority survives revocation of new send permissions.
submission: events are local typed response receipts, not signed webhooks.
"""
import hashlib,json,uuid
from dataclasses import dataclass
from datetime import datetime,timezone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from ..api.errors import ApiError
from ..db.budget import BudgetReservation
from ..db.contact import ProviderOperation
from ..db.delivery import DeliveryAuthorization,DeliveryEvent,DeliveryMessage
from ..providers.base import SubmissionResult
from ..providers.delivery import DeliveryIntent,delivery_transition,validate_delivery_submission
from .delivery_admission import _original_admission
from .delivery_post import DeliveryPostPermit
from .delivery_service import PreparedDelivery
from .delivery_submission import DeliverySubmissionClaim
from .delivery_status import DeliveryStatusAuthority,_require_status_authority,_retained_admission_authority
from .policy_service import policy_workspace_lock

@dataclass(frozen=True)
class DeliverySubmissionReceipt:
    message_id:uuid.UUID
    event_id:uuid.UUID|None
    state:str
    provider_ref:str|None
    replayed:bool

def _require_original_permit(permit,authority):
    try:
        if (type(permit) is not DeliveryPostPermit or type(permit.claim) is not DeliverySubmissionClaim
                or type(permit.prepared) is not PreparedDelivery or type(permit.claim.prepared) is not PreparedDelivery
                or type(permit.prepared.intent) is not DeliveryIntent):
            raise ValueError()
        intent=permit.prepared.intent;intent.__post_init__();claim=permit.claim
        if (claim.prepared.intent!=intent or dict(claim.prepared.payload)!=dict(permit.prepared.payload)
                or claim.provider_name!=authority.provider_name or claim.account_reference!=authority.account_reference
                or claim.scope_hash!=authority.scope_hash or intent.workspace_id!=authority.workspace_id
                or any(not isinstance(value,uuid.UUID) or not value.int for value in
                       (claim.message_id,claim.operation_id,claim.reservation_id,claim.outbox_id))):
            raise ValueError()
        return claim,intent
    except (ValueError,TypeError,AttributeError):
        raise ApiError(409,'RETRY_UNSAFE','original delivery POST permit cannot be rebound') from None

async def record_delivery_submission(session,*,permit:DeliveryPostPermit,result:SubmissionResult,
                                     authority:DeliveryStatusAuthority|None=None)->DeliverySubmissionReceipt:
    _require_status_authority(authority)
    try:validate_delivery_submission(result)
    except (ValueError,TypeError,AttributeError):
        raise ApiError(422,'INVALID_REQUEST','invalid delivery submit observation') from None
    claim,intent=_require_original_permit(permit,authority)
    try:
        # Only DB application here. Any actual provider await must already have
        # completed outside this fresh tenant transaction. Never require a new
        # send approval/lease to retain an already attempted original response.
        async with session.begin_nested():
            await policy_workspace_lock(session,authority.workspace_id)
            message=(await session.execute(select(DeliveryMessage).where(
                DeliveryMessage.workspace_id==authority.workspace_id,DeliveryMessage.id==claim.message_id,
                DeliveryMessage.provider_name==authority.provider_name,
                DeliveryMessage.account_reference==authority.account_reference,
            ).with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
            if message is None:
                raise ApiError(404,'NOT_FOUND','original delivery message not found')
            if (message.state in {'prepared','submitting','rejected'} or message.operation_id!=claim.operation_id
                    or message.intent_key!=intent.key or message.payload_digest!=intent.payload_digest
                    or message.draft_revision_id!=intent.draft_revision_id or message.approval_id!=intent.approval_id
                    or message.recipient_ref!=intent.recipient_ref or message.sender_identity_id!=intent.sender_identity_id):
                raise ApiError(409,'RETRY_UNSAFE','original delivery response requires a committed POST permit')
            recorded=(await session.execute(select(DeliveryAuthorization).where(
                DeliveryAuthorization.workspace_id==message.workspace_id,
                DeliveryAuthorization.message_id==message.id))).scalar_one_or_none()
            original=_retained_admission_authority(recorded,authority)
            admission=await _original_admission(session,message,original)
            if (claim.reservation_id!=admission.reservation_id or claim.outbox_id!=admission.outbox_id):
                raise ApiError(409,'RETRY_UNSAFE','original delivery POST permit cannot be rebound')
            operation=(await session.execute(select(ProviderOperation).where(
                ProviderOperation.workspace_id==message.workspace_id,ProviderOperation.id==admission.operation_id,
            ).with_for_update().execution_options(populate_existing=True))).scalar_one()
            reservation=(await session.execute(select(BudgetReservation).where(
                BudgetReservation.workspace_id==message.workspace_id,BudgetReservation.id==admission.reservation_id,
            ).with_for_update().execution_options(populate_existing=True))).scalar_one()
            if (operation.provider_ref!=message.provider_ref or operation.status not in {'unknown_acceptance','accepted'}
                    or reservation.state!='active' or reservation.remaining_hold!=reservation.upper_bound
                    or message.provider_ref is None and (message.state!='unknown' or operation.status!='unknown_acceptance')):
                raise ApiError(409,'RETRY_UNSAFE','original delivery liability requires reconciliation')
            if message.provider_ref is not None and result.provider_ref is not None and message.provider_ref!=result.provider_ref:
                raise ApiError(409,'IDEMPOTENCY_CONFLICT','original delivery response reference differs')
            changed=False
            if message.provider_ref is None and result.provider_ref is not None:
                message.provider_ref=result.provider_ref;operation.provider_ref=result.provider_ref;changed=True
            # Rejection alone is not no-charge/absence evidence. Keep the
            # permanent unknown marker and full original hold, just as the
            # generic durable runner does; never turn it into another POST.
            if result.state!='accepted':
                await session.flush();_require_status_authority(authority)
                return DeliverySubmissionReceipt(message.id,None,message.state,message.provider_ref,not changed)
            message.state=delivery_transition(message.state,'accepted')
            operation.status='accepted'
            await session.flush()  # event FK/guard requires the bound reference
            metadata={'source':'submission-observation-v1','scope_hash':recorded.scope_hash,
                      'workspace_id':str(message.workspace_id),'message_id':str(message.id),
                      'operation_id':str(operation.id),'intent_key':message.intent_key,
                      'payload_digest':message.payload_digest,'provider_name':message.provider_name,
                      'account_reference':message.account_reference,'provider_ref':message.provider_ref,'state':'accepted'}
            digest=hashlib.sha256(json.dumps(metadata,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
            external_id='submission:'+digest
            event=(await session.execute(select(DeliveryEvent).where(
                DeliveryEvent.workspace_id==message.workspace_id,DeliveryEvent.provider_name==message.provider_name,
                DeliveryEvent.account_reference==message.account_reference,
                DeliveryEvent.external_event_id==external_id))).scalar_one_or_none()
            replayed=event is not None
            if event is not None:
                if (event.message_id!=message.id or event.provider_ref!=message.provider_ref
                        or event.state!='accepted' or event.body_digest!=digest):
                    raise ApiError(409,'IDEMPOTENCY_CONFLICT','original delivery submit observation differs')
            else:
                event=DeliveryEvent(id=uuid.uuid4(),workspace_id=message.workspace_id,message_id=message.id,
                                    provider_name=message.provider_name,account_reference=message.account_reference,
                                    external_event_id=external_id,provider_ref=message.provider_ref,state='accepted',
                                    body_digest=digest,occurred_at=datetime.now(timezone.utc))
                session.add(event)
            await session.flush();_require_status_authority(authority)
            return DeliverySubmissionReceipt(message.id,event.id,message.state,message.provider_ref,replayed)
    except IntegrityError as error:
        if getattr(error.orig,'sqlstate',None)!='23505':raise
        raise ApiError(409,'IDEMPOTENCY_CONFLICT','original delivery response binding conflicts') from None
