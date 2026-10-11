"""Private one-time post-commit delivery permit; no provider I/O or activation.

Current approval/policy/fence is rechecked in a fresh transaction. Permanent
unknown is committed before the caller may POST outside that transaction. It
means acceptance is unresolved, never that a vendor accepted or delivered.
"""
import uuid
from dataclasses import dataclass,field
from sqlalchemy import select
from ..api.errors import ApiError
from ..db.budget import BudgetReservation
from ..db.contact import ProviderOperation
from ..db.delivery import DeliveryMessage
from ..db.outbox import OutboxEvent
from ..execution.step_runner import LocalExecution
from .delivery_admission import _original_admission,_outbox_binding
from .delivery_budget import DeliveryBudgetAuthorization
from .delivery_service import PreparedDelivery,prepare_delivery_intent
from .delivery_submission import DeliverySubmissionClaim,_require_submit_authority,_require_dispatch_flags

@dataclass(frozen=True)
class DeliveryPostPermit:
    claim:DeliverySubmissionClaim=field(repr=False)
    prepared:PreparedDelivery=field(repr=False)

async def claim_delivery_post(session,*,execution:LocalExecution,claim:DeliverySubmissionClaim,
                              authorization:DeliveryBudgetAuthorization|None=None)->DeliveryPostPermit:
    _require_submit_authority(authorization)
    _require_dispatch_flags()
    if type(execution) is not LocalExecution:
        raise ApiError(422, "INVALID_REQUEST", "native delivery execution required")
    if authorization.workspace_id != execution.envelope.workspace_id:
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", "original delivery workspace differs")
    if (type(claim) is not DeliverySubmissionClaim or type(claim.prepared) is not PreparedDelivery
            or claim.outbox_id != execution.envelope.outbox_id
            or claim.generation != execution.envelope.generation
            or claim.runtime_epoch != execution.envelope.runtime_epoch or claim.owner != execution.owner
            or claim.scope_hash != authorization.scope_hash
            or claim.provider_name != authorization.provider_name
            or claim.account_reference != authorization.account_reference):
        raise ApiError(409, "RETRY_UNSAFE", "original delivery claim cannot be rebound")
    async with session.begin_nested():
        # Read the original metadata without taking the runtime/control lock.
        # prepare_delivery_intent takes the current policy/draft locks first.
        row = (await session.execute(select(OutboxEvent).where(
            OutboxEvent.workspace_id == execution.envelope.workspace_id,
            OutboxEvent.id == execution.envelope.outbox_id,
        ))).scalar_one_or_none()
        try:
            if row is None or row.event_type != "delivery.submit" or type(row.payload) is not dict:
                raise ValueError()
            if set(row.payload) != {"workspace_id", "message_id", "operation_id", "scope_hash"}:
                raise ValueError()
            message_id = uuid.UUID(row.payload["message_id"])
            if str(message_id) != row.payload["message_id"] or not message_id.int:
                raise ValueError()
            if row.payload["workspace_id"] != str(authorization.workspace_id):
                raise ValueError()
        except (ValueError, TypeError, KeyError, AttributeError):
            raise ApiError(409, "RETRY_UNSAFE", "original delivery outbox requires reconciliation") from None
        message = (await session.execute(select(DeliveryMessage).where(
            DeliveryMessage.workspace_id == authorization.workspace_id,
            DeliveryMessage.id == message_id,
        ))).scalar_one_or_none()
        if message is None:
            raise ApiError(404, "NOT_FOUND", "original delivery message not found")
        if message.state != "submitting" or message.provider_ref is not None:
            raise ApiError(409, "RETRY_UNSAFE", "original delivery submit requires reconciliation")
        admission = await _original_admission(session, message, authorization)
        if admission.outbox_id != row.id:
            raise ApiError(409, "RETRY_UNSAFE", "original delivery outbox differs")
        if (claim.message_id != message.id or claim.operation_id != admission.operation_id
                or claim.reservation_id != admission.reservation_id or claim.outbox_id != admission.outbox_id):
            raise ApiError(409, "RETRY_UNSAFE", "original delivery claim cannot be rebound")
        prepared = await prepare_delivery_intent(
            session, workspace_id=message.workspace_id, actor_id=message.actor_id,
            draft_id=message.draft_id, draft_revision_id=message.draft_revision_id,
            recipient_ref=message.recipient_ref, sender_identity_id=message.sender_identity_id,
            approval_id=message.approval_id, key=message.intent_key,
        )
        if (prepared.intent != claim.prepared.intent
                or dict(prepared.payload) != dict(claim.prepared.payload)):
            raise ApiError(409, "RETRY_UNSAFE", "original delivery payload cannot be replaced")
        if prepared.intent.payload_digest != message.payload_digest:
            raise ApiError(412, "STALE_REVISION", "original delivery payload differs")
        # The original metadata was read before policy locks. Expire that
        # identity so the control-first native fence reads current locked rows.
        session.expire(row)
        if not await execution.guard(session):
            raise ApiError(409, "STALE_FENCE", "current native delivery worker fence required")
        if (execution.row.event_type != "delivery.submit"
                or execution.row.intent_key != message.intent_key
                or execution.row.payload != _outbox_binding(message, authorization.scope_hash)):
            raise ApiError(409, "RETRY_UNSAFE", "current original delivery outbox differs")
        message = (await session.execute(select(DeliveryMessage).where(
            DeliveryMessage.workspace_id == authorization.workspace_id,
            DeliveryMessage.id == message_id,
        ).with_for_update().execution_options(populate_existing=True))).scalar_one()
        if message.state != "submitting" or message.provider_ref is not None:
            raise ApiError(409, "RETRY_UNSAFE", "original delivery submit requires reconciliation")
        operation = (await session.execute(select(ProviderOperation).where(
            ProviderOperation.workspace_id == message.workspace_id,
            ProviderOperation.id == admission.operation_id,
        ).with_for_update())).scalar_one()
        reservation = (await session.execute(select(BudgetReservation).where(
            BudgetReservation.workspace_id == message.workspace_id,
            BudgetReservation.id == admission.reservation_id,
        ).with_for_update())).scalar_one()
        if (operation.status != "submitted" or operation.provider_ref is not None
                or reservation.state != "active" or reservation.remaining_hold != reservation.upper_bound):
            raise ApiError(409, "RETRY_UNSAFE", "original delivery liability requires reconciliation")
        # Permanent uncertainty is committed before returning the one POST
        # permit. A crash before or after network I/O cannot obtain another
        # permit, even after a vendor idempotency window expires.
        message.state = "unknown"
        operation.status = "unknown_acceptance"
        await session.flush()
        _require_submit_authority(authorization)
        _require_dispatch_flags()
        if not await execution.guard(session):
            raise ApiError(409, "STALE_FENCE", "native delivery claim fence expired")
        return DeliveryPostPermit(claim, prepared)
