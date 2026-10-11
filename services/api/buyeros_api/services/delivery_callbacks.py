"""Private signed delivery callback transaction; no HTTP route or account selected.

Only an original retained provider/account/message reference can receive an event.
Callback state is not economic proof: original liability/hold is never released.
"""
import hashlib
import json
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from ..api.errors import ApiError
from ..db.delivery import DeliveryEvent, DeliveryLiability, DeliveryMessage
from ..db.policy import SUPPRESSIBLE_PURPOSES, Suppression
from ..providers.delivery import delivery_transition, verify_delivery_webhook
from .approval_service import invalidate_approvals_for_subject
from .policy_service import policy_workspace_lock, quarantine_contacts_for_suppression

_EVENTS = {
    "email.sent": "accepted",
    "email.delivered": "delivered",
    "email.bounced": "bounced",
    "email.complained": "complained",
    "email.failed": "failed",
    "email.suppressed": "failed",
}
_ADVERSE = frozenset({"email.bounced", "email.complained", "email.suppressed"})


@dataclass(frozen=True)
class DeliveryWebhookEndpoint:
    """Retained server-owned endpoint identity; separate from new send admission.

    Never construct this from HTTP body/headers. No production endpoint registry
    or synthetic key is installed by this service. Preserve the original account
    for callbacks even when new admission is disabled.
    """
    workspace_id: uuid.UUID
    account_reference: str
    reviewed_contract_hash: str
    signing_secret: str = field(repr=False)
    reviewed: bool
    valid_until: datetime

    def __post_init__(self):
        if not isinstance(self.workspace_id, uuid.UUID) or not self.workspace_id.int:
            raise ValueError("canonical delivery endpoint workspace required")
        if not isinstance(self.account_reference, str) or re.fullmatch(r"[A-Za-z0-9:_/-]{1,128}", self.account_reference) is None:
            raise ValueError("original bounded delivery account required")
        if not isinstance(self.reviewed_contract_hash, str) or re.fullmatch(r"[0-9a-f]{64}", self.reviewed_contract_hash) is None:
            raise ValueError("reviewed delivery endpoint contract required")
        if not isinstance(self.signing_secret, str) or not self.signing_secret.startswith("whsec_") or len(self.signing_secret) > 256:
            raise ValueError("bounded private delivery endpoint key required")
        if type(self.reviewed) is not bool or not isinstance(self.valid_until, datetime) or self.valid_until.utcoffset() is None:
            raise ValueError("explicit reviewed delivery endpoint expiry required")


@dataclass(frozen=True)
class DeliveryCallbackReceipt:
    message_id: uuid.UUID
    event_id: uuid.UUID
    state: str
    replayed: bool


def _pairs_without_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate callback field")
        result[key] = value
    return result


def _event_metadata(raw):
    # Only authenticated bytes arrive here. Addresses, tenant selectors, body and
    # caller-chosen account/recipient/actor fields are never authority or stored.
    try:
        value = json.loads(raw, object_pairs_hook=_pairs_without_duplicates)
        event_type = value["type"]
        if event_type not in _EVENTS:
            raise ValueError()
        ref = value["data"]["email_id"]
        if not isinstance(ref, str) or str(uuid.UUID(ref)) != ref or not uuid.UUID(ref).int:
            raise ValueError()
        stamp = value["created_at"]
        if not isinstance(stamp, str) or len(stamp) > 64:
            raise ValueError()
        occurred_at = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if occurred_at.utcoffset() is None:
            raise ValueError()
        return event_type, ref, occurred_at
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError, UnicodeError):
        raise ApiError(422, "INVALID_REQUEST", "unsupported delivery callback metadata") from None


def _require_endpoint(endpoint):
    if (not isinstance(endpoint, DeliveryWebhookEndpoint) or endpoint.reviewed is not True
            or endpoint.valid_until <= datetime.now(timezone.utc)):
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "reviewed retained delivery endpoint unavailable")


async def record_resend_delivery_webhook(session, raw_body: bytes, headers: Mapping[str, str], *, endpoint: DeliveryWebhookEndpoint | None = None):
    _require_endpoint(endpoint)
    try:
        verified = verify_delivery_webhook(raw_body, headers, secret=endpoint.signing_secret)
    except ValueError:
        raise ApiError(403, "PERMISSION_DENIED", "invalid delivery webhook") from None
    event_type, ref, occurred_at = _event_metadata(verified.raw_body)
    state = _EVENTS[event_type]
    async with session.begin_nested():
        # Match policy writer ordering; callbacks do not require current send
        # permission, since an already submitted message still needs readback.
        await policy_workspace_lock(session, endpoint.workspace_id)
        message = (await session.execute(select(DeliveryMessage).where(
            DeliveryMessage.workspace_id == endpoint.workspace_id,
            DeliveryMessage.provider_name == "resend",
            DeliveryMessage.account_reference == endpoint.account_reference,
            DeliveryMessage.provider_ref == ref).with_for_update())).scalar_one_or_none()
        if message is None:
            raise ApiError(404, "NOT_FOUND", "original delivery message not found")
        if message.state == "prepared":
            raise ApiError(409, "RETRY_UNSAFE", "delivery callback requires an original submit claim")
        liability = (await session.execute(select(DeliveryLiability.id).where(
            DeliveryLiability.workspace_id == message.workspace_id,
            DeliveryLiability.message_id == message.id,
            DeliveryLiability.operation_id == message.operation_id))).scalar_one_or_none()
        if liability is None:
            raise ApiError(409, "RETRY_UNSAFE", "delivery callback requires original retained liability")
        existing = (await session.execute(select(DeliveryEvent).where(
            DeliveryEvent.workspace_id == message.workspace_id,
            DeliveryEvent.provider_name == "resend",
            DeliveryEvent.account_reference == message.account_reference,
            DeliveryEvent.external_event_id == verified.event_id))).scalar_one_or_none()
        if existing is not None:
            if (existing.message_id != message.id or existing.provider_ref != ref
                    or existing.body_digest != verified.body_digest or existing.state != state):
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "original delivery event binding differs")
            _require_endpoint(endpoint)
            return DeliveryCallbackReceipt(message.id, existing.id, message.state, True)
        event_id = uuid.uuid4()
        inserted = (await session.execute(insert(DeliveryEvent).values(
            id=event_id, workspace_id=message.workspace_id, message_id=message.id,
            provider_name="resend", account_reference=message.account_reference,
            external_event_id=verified.event_id, provider_ref=ref, state=state,
            body_digest=verified.body_digest, occurred_at=occurred_at
        ).on_conflict_do_nothing(constraint="uq_delivery_events_external").returning(DeliveryEvent.id))).scalar_one_or_none()
        if inserted is None:
            # Global account/event uniqueness may conflict with a row hidden by
            # RLS. Never infer another tenant or silently bind its event here.
            raise ApiError(409, "IDEMPOTENCY_CONFLICT", "original delivery event binding differs")
        message.state = delivery_transition(message.state, state)
        if event_type in _ADVERSE:
            await apply_delivery_adverse_event(session, message, event_id)
        await session.flush()
        _require_endpoint(endpoint)
        return DeliveryCallbackReceipt(message.id, event_id, message.state, False)


async def apply_delivery_adverse_event(session, message, event_id):
    """Persist independent suppression and invalidate approvals atomically."""
    overlay = (await session.execute(select(Suppression.id).where(
        Suppression.workspace_id == message.workspace_id,
        Suppression.subject_type == "contact_point",
        Suppression.subject_id == message.recipient_ref,
        Suppression.controller_scope_id == message.workspace_id,
        Suppression.active.is_(True),
        Suppression.source_reference.like("delivery-event:%")))).first()
    if overlay is None:
        session.add(Suppression(
            workspace_id=message.workspace_id,
            subject_key_hash=hashlib.sha256(f"contact_point:{message.recipient_ref}".encode()).hexdigest(),
            subject_type="contact_point", subject_id=message.recipient_ref,
            controller_scope_id=message.workspace_id, purpose="outreach",
            purposes=list(SUPPRESSIBLE_PURPOSES),
            reason="Authenticated delivery provider adverse event",
            source_reference="delivery-event:" + str(event_id),
            active=True, actor_id=message.actor_id, version=1))
    await invalidate_approvals_for_subject(session, workspace_id=message.workspace_id,
        subject_type="contact_point", subject_id=message.recipient_ref, reason="delivery_adverse_event")
    await quarantine_contacts_for_suppression(session, workspace_id=message.workspace_id,
        subject_type="contact_point", subject_id=message.recipient_ref, normalized_domain=None)
