"""Private durable status observations for an original retained delivery.

No provider factory, network call, submit route or economic settlement is wired.
The server-owned status authority is independent of new send admission. Events
with status: IDs are local observation receipts; they are not signed webhooks.
"""
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from ..api.errors import ApiError
from ..db.budget import BudgetReservation
from ..db.contact import ProviderOperation
from ..db.delivery import DeliveryAuthorization, DeliveryEvent, DeliveryMessage
from ..providers.delivery import DeliveryStatusResult, delivery_transition, validate_delivery_status
from .delivery_admission import _original_admission
from .delivery_budget import DeliveryBudgetAuthorization
from .delivery_callbacks import apply_delivery_adverse_event
from .policy_service import policy_workspace_lock


@dataclass(frozen=True)
class DeliveryStatusAuthority:
    """Retained server-owned account/contract/scope; never accept client JSON.

    New admission may be closed/revoked/expired while this separately reviewed
    reconciliation authority remains valid. No production selection is installed.
    """
    workspace_id: uuid.UUID
    provider_name: str
    account_reference: str
    scope_hash: str
    reviewed_contract_hash: str
    reviewed: bool
    valid_until: datetime

    def __post_init__(self):
        if not isinstance(self.workspace_id, uuid.UUID) or not self.workspace_id.int:
            raise ValueError("invalid retained delivery status authority")
        for value, pattern in (
            (self.provider_name, r"[A-Za-z0-9_-]{1,64}"),
            (self.account_reference, r"[A-Za-z0-9:_/-]{1,128}"),
            (self.scope_hash, r"[0-9a-f]{64}"),
            (self.reviewed_contract_hash, r"[0-9a-f]{64}"),
        ):
            if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
                raise ValueError("invalid retained delivery status authority")
        if type(self.reviewed) is not bool or not isinstance(self.valid_until, datetime) or self.valid_until.utcoffset() is None:
            raise ValueError("invalid retained delivery status authority")


@dataclass(frozen=True)
class DeliveryStatusReceipt:
    message_id: uuid.UUID
    event_id: uuid.UUID | None
    state: str
    replayed: bool


def _require_status_authority(authority):
    try:
        if type(authority) is not DeliveryStatusAuthority:
            raise ValueError()
        authority.__post_init__()
        if authority.reviewed is not True or authority.valid_until <= datetime.now(timezone.utc):
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "reviewed retained delivery status authority unavailable") from None


def _retained_admission_authority(recorded, authority):
    # 0050 stores complete immutable metadata and a DB-enforced digest. Recheck
    # those bindings at this boundary; do not renew or rewrite the old authority.
    try:
        if recorded is None or recorded.scope_hash != authority.scope_hash:
            raise ValueError()
        if hashlib.sha256(recorded.scope_json.encode("utf-8")).hexdigest() != recorded.scope_hash:
            raise ValueError()
        values = json.loads(recorded.scope_json)
        for key in ("workspace_id", "project_id", "sender_identity_id"):
            values[key] = uuid.UUID(values[key])
        values["recipient_refs"] = tuple(uuid.UUID(value) for value in values["recipient_refs"])
        values["upper_bound"] = Decimal(values["upper_bound"])
        values["valid_until"] = datetime.fromisoformat(values["valid_until"])
        original = DeliveryBudgetAuthorization(**values)
        if (original.scope_json != recorded.scope_json or original.valid_until != recorded.valid_until
                or original.reviewed_contract_hash != authority.reviewed_contract_hash
                or original.workspace_id != authority.workspace_id
                or original.provider_name != authority.provider_name
                or original.account_reference != authority.account_reference):
            raise ValueError()
        return original
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ApiError(409, "RETRY_UNSAFE", "original delivery status authority requires reconciliation") from None


async def record_delivery_status(session, *, message_id: uuid.UUID, result: DeliveryStatusResult,
                                 authority: DeliveryStatusAuthority | None = None) -> DeliveryStatusReceipt:
    _require_status_authority(authority)
    try:
        if not isinstance(message_id, uuid.UUID) or not message_id.int:
            raise ValueError()
        validate_delivery_status(result, provider_ref=result.provider_ref)
    except (ValueError, TypeError, AttributeError):
        raise ApiError(422, "INVALID_REQUEST", "invalid delivery status observation") from None
    # Only durable application occurs here. Provider I/O must finish before
    # opening this transaction; never pass a network await into this service.
    async with session.begin_nested():
        await policy_workspace_lock(session, authority.workspace_id)
        message = (await session.execute(select(DeliveryMessage).where(
            DeliveryMessage.workspace_id == authority.workspace_id,
            DeliveryMessage.id == message_id,
            DeliveryMessage.provider_name == authority.provider_name,
            DeliveryMessage.account_reference == authority.account_reference,
        ).with_for_update())).scalar_one_or_none()
        if message is None:
            raise ApiError(404, "NOT_FOUND", "original delivery message not found")
        try:
            if message.state in {"prepared", "submitting"}:
                raise ValueError()
            validate_delivery_status(result, provider_ref=message.provider_ref)
        except ValueError:
            raise ApiError(409, "RETRY_UNSAFE", "original delivery submit reference requires reconciliation") from None
        recorded = (await session.execute(select(DeliveryAuthorization).where(
            DeliveryAuthorization.workspace_id == message.workspace_id,
            DeliveryAuthorization.message_id == message.id,
        ))).scalar_one_or_none()
        original = _retained_admission_authority(recorded, authority)
        admission = await _original_admission(session, message, original)
        operation = (await session.execute(select(ProviderOperation).where(
            ProviderOperation.workspace_id == message.workspace_id,
            ProviderOperation.id == admission.operation_id,
        ))).scalar_one()
        reservation = (await session.execute(select(BudgetReservation).where(
            BudgetReservation.workspace_id == message.workspace_id,
            BudgetReservation.id == admission.reservation_id,
        ))).scalar_one()
        # Until independent economics is installed, every unresolved original
        # must retain its exact full active hold. Status is never monetary proof.
        if (operation.provider_ref != message.provider_ref or reservation.state != "active"
                or reservation.remaining_hold != reservation.upper_bound):
            raise ApiError(409, "RETRY_UNSAFE", "original delivery liability requires reconciliation")
        if result.state == "unknown":
            _require_status_authority(authority)
            return DeliveryStatusReceipt(message.id, None, message.state, False)
        metadata = {
            "source": "status-observation-v1", "scope_hash": recorded.scope_hash,
            "workspace_id": str(message.workspace_id), "message_id": str(message.id),
            "provider_name": message.provider_name, "account_reference": message.account_reference,
            "provider_ref": message.provider_ref, "state": result.state,
            "provider_event_id": result.event_id,
        }
        digest = hashlib.sha256(json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        external_id = "status:" + digest
        existing = (await session.execute(select(DeliveryEvent).where(
            DeliveryEvent.workspace_id == message.workspace_id,
            DeliveryEvent.provider_name == message.provider_name,
            DeliveryEvent.account_reference == message.account_reference,
            DeliveryEvent.external_event_id == external_id,
        ))).scalar_one_or_none()
        if existing is not None:
            if (existing.message_id != message.id or existing.provider_ref != message.provider_ref
                    or existing.body_digest != digest or existing.state != result.state):
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "original delivery status observation differs")
            _require_status_authority(authority)
            return DeliveryStatusReceipt(message.id, existing.id, message.state, True)
        event_id = uuid.uuid4()
        inserted = (await session.execute(insert(DeliveryEvent).values(
            id=event_id, workspace_id=message.workspace_id, message_id=message.id,
            provider_name=message.provider_name, account_reference=message.account_reference,
            external_event_id=external_id, provider_ref=message.provider_ref,
            state=result.state, body_digest=digest, occurred_at=datetime.now(timezone.utc),
        ).on_conflict_do_nothing(constraint="uq_delivery_events_external").returning(DeliveryEvent.id))).scalar_one_or_none()
        if inserted is None:
            raise ApiError(409, "IDEMPOTENCY_CONFLICT", "original delivery status observation differs")
        message.state = delivery_transition(message.state, result.state)
        if result.state in {"bounced", "complained", "unsubscribed"}:
            await apply_delivery_adverse_event(session, message, event_id)
        await session.flush()
        _require_status_authority(authority)
        return DeliveryStatusReceipt(message.id, event_id, message.state, False)
