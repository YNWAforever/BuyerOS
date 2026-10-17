"""Private durable delivery submit claim. No provider I/O or runner activation.

Call in a fresh tenant transaction with a real native worker execution. Policy
and canonical draft locks precede the runtime/outbox fence, matching admission
ordering. Commit the claim and close the transaction before any external await.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select

from ..api.errors import ApiError
from ..db.budget import BudgetReservation
from ..db.contact import ProviderOperation
from ..db.delivery import DeliveryMessage
from ..db.outbox import OutboxEvent
from ..execution.config import get_settings
from ..execution.step_runner import LocalExecution
from .delivery_admission import _original_admission, _outbox_binding
from .delivery_budget import DeliveryBudgetAuthorization
from .delivery_service import PreparedDelivery, prepare_delivery_intent


@dataclass(frozen=True)
class DeliverySubmissionClaim:
    message_id: uuid.UUID
    operation_id: uuid.UUID
    reservation_id: uuid.UUID
    outbox_id: uuid.UUID
    scope_hash: str
    provider_name: str
    account_reference: str
    generation: int
    runtime_epoch: int
    owner: uuid.UUID
    prepared: PreparedDelivery = field(repr=False)


def _require_submit_authority(authorization):
    try:
        if type(authorization) is not DeliveryBudgetAuthorization:
            raise ValueError()
        authorization.__post_init__()
        if (authorization.selected is not True or authorization.reviewed is not True
                or authorization.sender_verified is not True
                or authorization.valid_until <= datetime.now(timezone.utc)):
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "selected reviewed delivery submit authority unavailable") from None


def _require_dispatch_flags():
    settings = get_settings()
    if not settings.paid_dispatch_enabled or not settings.delivery_dispatch_enabled:
        raise ApiError(503, "CAPABILITY_DISABLED", "delivery dispatch is disabled")


async def claim_delivery_submission(session, *, execution: LocalExecution,
                                    authorization: DeliveryBudgetAuthorization | None = None) -> DeliverySubmissionClaim:
    _require_submit_authority(authorization)
    _require_dispatch_flags()
    if type(execution) is not LocalExecution:
        raise ApiError(422, "INVALID_REQUEST", "native delivery execution required")
    if authorization.workspace_id != execution.envelope.workspace_id:
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", "original delivery workspace differs")
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
        if message.state != "prepared" or message.provider_ref is not None:
            raise ApiError(409, "RETRY_UNSAFE", "original delivery submit requires reconciliation")
        admission = await _original_admission(session, message, authorization)
        if admission.outbox_id != row.id:
            raise ApiError(409, "RETRY_UNSAFE", "original delivery outbox differs")
        prepared = await prepare_delivery_intent(
            session, workspace_id=message.workspace_id, actor_id=message.actor_id,
            draft_id=message.draft_id, draft_revision_id=message.draft_revision_id,
            recipient_ref=message.recipient_ref, sender_identity_id=message.sender_identity_id,
            approval_id=message.approval_id, key=message.intent_key,
        )
        from .provider_policy_context import require_delivery_policy
        await require_delivery_policy(session, prepared=prepared, authorization=authorization,
                                      project_id=message.project_id, draft_id=message.draft_id)
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
        if message.state != "prepared" or message.provider_ref is not None:
            raise ApiError(409, "RETRY_UNSAFE", "original delivery submit requires reconciliation")
        operation = (await session.execute(select(ProviderOperation).where(
            ProviderOperation.workspace_id == message.workspace_id,
            ProviderOperation.id == admission.operation_id,
        ).with_for_update())).scalar_one()
        reservation = (await session.execute(select(BudgetReservation).where(
            BudgetReservation.workspace_id == message.workspace_id,
            BudgetReservation.id == admission.reservation_id,
        ).with_for_update())).scalar_one()
        if (operation.status != "intent" or operation.provider_ref is not None
                or reservation.state != "active" or reservation.remaining_hold != reservation.upper_bound):
            raise ApiError(409, "RETRY_UNSAFE", "original delivery liability requires reconciliation")
        # These are committed before any provider side effect. A crashed worker
        # finds submitting and may only reconcile the original intent/ref.
        message.state = "submitting"
        operation.status = "submitted"
        await session.flush()
        _require_submit_authority(authorization)
        _require_dispatch_flags()
        if not await execution.guard(session):
            raise ApiError(409, "STALE_FENCE", "native delivery claim fence expired")
        return DeliverySubmissionClaim(
            message.id, operation.id, reservation.id, row.id, authorization.scope_hash,
            message.provider_name, message.account_reference, execution.envelope.generation,
            execution.envelope.runtime_epoch, execution.owner, prepared,
        )
