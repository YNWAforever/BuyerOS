"""Idempotent settlement and compensating cost events (BO-010/020)."""
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select

from ..api.errors import ApiError
from ..db.budget import BudgetAccount, BudgetReservation, BudgetReservationAllocation, CostEvent
from .budget_service import RANK, ZERO, _money, lock_budget_workspace


def settle_effect(state: str, charge: str) -> dict:
    if state == "succeeded":
        return {"commit": Decimal(charge), "release": ZERO}
    return {"commit": ZERO, "release": ZERO}


def cancel_effect(state: str) -> str:
    return "release" if state in {"intent", "reserved"} else "reconcile"


async def _operation(session, operation_id):
    candidate = (await session.execute(select(BudgetReservation).where(
        BudgetReservation.operation_id == operation_id))).scalar_one_or_none()
    if candidate is None:
        raise ApiError(404, "NOT_FOUND", "budget operation not found")
    await lock_budget_workspace(session, candidate.workspace_id)
    return (await session.execute(select(BudgetReservation).where(
        BudgetReservation.id == candidate.id).with_for_update())).scalar_one()


async def _accounts(session, reservation):
    rows = (await session.execute(select(BudgetAccount).join(
        BudgetReservationAllocation, BudgetReservationAllocation.account_id == BudgetAccount.id
    ).where(BudgetReservationAllocation.reservation_id == reservation.id,
            BudgetReservationAllocation.workspace_id == reservation.workspace_id))).scalars().all()
    rows.sort(key=lambda row: (RANK[row.scope], str(row.id)))
    for row in rows:
        await session.execute(select(BudgetAccount.id).where(BudgetAccount.id == row.id).with_for_update())
    return rows


async def _event(session, workspace_id, external_event_id):
    return (await session.execute(select(CostEvent).where(
        CostEvent.workspace_id == workspace_id, CostEvent.external_event_id == external_event_id
    ))).scalar_one_or_none()


def _event_id(external_event_id: str):
    if not external_event_id or len(external_event_id) > 200:
        raise ApiError(422, "INVALID_REQUEST", "a verified external cost event ID is required")


async def settle_operation(session, operation_id, actual: Decimal, external_event_id: str,
                           *, at: datetime | None = None) -> dict:
    """Only a proven charge releases unused bound; unknown retains the entire hold."""
    _event_id(external_event_id)
    actual = _money(actual)
    reservation = await _operation(session, operation_id)
    existing = await _event(session, reservation.workspace_id, external_event_id)
    if existing:
        if existing.operation_id == operation_id and existing.kind == "commit" and existing.amount == actual:
            return {"settled": format(actual, ".6f"), "currency": reservation.currency,
                    "event_id": str(existing.id), "replayed": True}
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", "external event identity differs")
    if reservation.state != "active" or actual > reservation.upper_bound:
        raise ApiError(409, "BUDGET_LIMIT", "charge cannot be safely reconciled within reservation")
    for account in await _accounts(session, reservation):
        account.settled_spend += actual
    reservation.remaining_hold = ZERO
    reservation.state = "settled"
    event = CostEvent(workspace_id=reservation.workspace_id, operation_id=operation_id,
        external_event_id=external_event_id, kind="commit", amount=actual,
        pricing_version=reservation.price_version, occurred_at=reservation.origin_period_start,
        recorded_at=at or datetime.now(timezone.utc))
    session.add(event)
    await session.flush()
    return {"settled": format(actual, ".6f"), "currency": reservation.currency,
            "event_id": str(event.id), "replayed": False}


async def refund_operation(session, operation_id, amount: Decimal, external_event_id: str,
                           *, at: datetime | None = None) -> dict:
    """Append a verified reversal to the origin period, without minting current capacity."""
    _event_id(external_event_id)
    amount = _money(amount, positive=True)
    reservation = await _operation(session, operation_id)
    existing = await _event(session, reservation.workspace_id, external_event_id)
    if existing:
        if existing.operation_id == operation_id and existing.kind == "reversal" and existing.amount == -amount:
            return {"refunded": format(amount, ".6f"), "event_id": str(existing.id), "replayed": True}
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", "external event identity differs")
    events = (await session.execute(select(CostEvent).where(
        CostEvent.workspace_id == reservation.workspace_id, CostEvent.operation_id == operation_id
    ))).scalars().all()
    net = sum((event.amount for event in events), ZERO)
    if reservation.state != "settled" or amount > net:
        raise ApiError(409, "BUDGET_LIMIT", "refund exceeds verified settled cost")
    for account in await _accounts(session, reservation):
        account.settled_spend -= amount
    event = CostEvent(workspace_id=reservation.workspace_id, operation_id=operation_id,
        external_event_id=external_event_id, kind="reversal", amount=-amount,
        pricing_version=reservation.price_version, occurred_at=reservation.origin_period_start,
        recorded_at=at or datetime.now(timezone.utc))
    session.add(event)
    await session.flush()
    return {"refunded": format(amount, ".6f"), "event_id": str(event.id), "replayed": False}


async def release_unsubmitted_operation(session, operation_id) -> None:
    """Release a hold only when the caller has locked and proven every intent unsubmitted."""
    reservation = await _operation(session, operation_id)
    if reservation.state != "active":
        raise ApiError(409, "INVALID_STATE", "reservation is no longer releasable")
    reservation.remaining_hold = ZERO
    reservation.state = "released"
    await session.flush()
