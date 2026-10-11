"""Private retained original-reference status orchestration across closed transactions.

No production selector, scheduler, public reconcile route or economic settlement
is activated. GET may use independently reviewed retained authority after new send
admission/role/flags expire. A status observation never creates or releases money.
"""
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Protocol

from sqlalchemy import select

from ..api.errors import ApiError
from ..db.delivery import DeliveryMessage
from ..db.session import tenant_session
from ..providers.delivery import DeliveryStatusResult, validate_delivery_status
from .delivery_status import (DeliveryStatusAuthority, DeliveryStatusReceipt,
                              _require_status_authority, record_delivery_status)


class DeliveryStatusReader(Protocol):
    async def status(self) -> DeliveryStatusResult: ...


@dataclass(frozen=True)
class DeliveryReconciliationSelection:
    """Reviewed private GET-only binding; never deserialize HTTP/worker JSON.

    The pure factory receives only the durable original ref, never client text,
    an intent key or a renewed send scope. Its reviewed HTTP pool lifecycle and
    status quota/contract are independently selected by the server owner.
    """
    authority: DeliveryStatusAuthority
    reader_factory: Callable[[str], DeliveryStatusReader] = field(repr=False)


def _require_selection(selection, workspace_id):
    if type(selection) is not DeliveryReconciliationSelection:
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "retained delivery reader unavailable")
    _require_status_authority(selection.authority)
    if not callable(selection.reader_factory):
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "retained delivery reader unavailable")
    if type(workspace_id) is not uuid.UUID or workspace_id.int == 0:
        raise ApiError(422, "INVALID_REQUEST", "exact delivery workspace required")
    if selection.authority.workspace_id != workspace_id:
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", "original delivery workspace differs")


def _recheck(selection, workspace_id, original_authority):
    _require_selection(selection, workspace_id)
    if selection.authority != original_authority:
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "retained delivery authority changed")


def _reader(selection, ref):
    try:
        reader = selection.reader_factory(ref)
        if not callable(getattr(reader, "status", None)) or any(
            getattr(reader, name, None) is not None for name in ("submit", "estimate", "capability")
        ):
            raise ValueError()
        return reader
    except Exception:
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "GET-only delivery reader unavailable") from None


async def reconcile_delivery_status(engine, *, workspace_id: uuid.UUID, message_id: uuid.UUID,
                                    selection: DeliveryReconciliationSelection | None = None) -> DeliveryStatusReceipt:
    _require_selection(selection, workspace_id)
    if type(message_id) is not uuid.UUID or message_id.int == 0:
        raise ApiError(422, "INVALID_REQUEST", "exact original message required")
    # A frozen copy fixes every retained account/contract/scope field before a
    # factory/network await. Rechecks also reject renewal/rebinding mid-attempt.
    authority = replace(selection.authority)
    async with tenant_session(engine, workspace_id) as session:
        message = (await session.execute(select(DeliveryMessage).where(
            DeliveryMessage.workspace_id == workspace_id, DeliveryMessage.id == message_id,
            DeliveryMessage.provider_name == authority.provider_name,
            DeliveryMessage.account_reference == authority.account_reference,
        ))).scalar_one_or_none()
        if message is None:
            raise ApiError(404, "NOT_FOUND", "original delivery message not found")
        ref = message.provider_ref
        if ref is None:
            raise ApiError(409, "RETRY_UNSAFE", "original delivery reference requires reconciliation")
        # The unknown no-op validates the complete immutable original0050 scope,
        # operation/outbox/liability/full active hold before any provider GET.
        # It records no event and does not check or renew new-send permissions.
        await record_delivery_status(session, message_id=message_id,
            result=DeliveryStatusResult("unknown", ref), authority=authority)
    # Every canonical lock/session is closed and the successful context exit
    # observed before constructing the GET-only reader. Failed commit means0GET.
    _recheck(selection, workspace_id, authority)
    reader = _reader(selection, ref)
    _recheck(selection, workspace_id, authority)
    try:
        observed = await reader.status()
    except Exception:
        # Cancellation/SystemExit propagate; provider details/credentials never
        # enter logs or become no-charge/delivery/retry evidence.
        observed = DeliveryStatusResult("unknown", ref)
    _recheck(selection, workspace_id, authority)
    try:
        validate_delivery_status(observed, provider_ref=ref)
    except (ValueError, TypeError, AttributeError):
        raise ApiError(422, "INVALID_REQUEST", "invalid original delivery observation") from None
    # A fresh tenant transaction revalidates the original immutable bindings,
    # records a monotonic/deduplicated status: observation and adverse overlay.
    # No submit, new key/reservation/outbox, ref rewrite or cost settlement.
    async with tenant_session(engine, workspace_id) as session:
        return await record_delivery_status(session, message_id=message_id,
            result=observed, authority=authority)


def selected_delivery_reconciliation(*, workspace_id: uuid.UUID,
                                      message_id: uuid.UUID) -> DeliveryReconciliationSelection | None:
    """Reviewed retained provider/account/HTTP lifecycle selection remains closed."""
    return None


async def reconcile_delivery_message(engine, *, workspace_id: uuid.UUID,
                                     message_id: uuid.UUID) -> DeliveryStatusReceipt:
    selection = selected_delivery_reconciliation(workspace_id=workspace_id, message_id=message_id)
    return await reconcile_delivery_status(engine, workspace_id=workspace_id,
                                           message_id=message_id, selection=selection)
