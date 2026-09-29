"""Atomic USD budget admission and period projections (BO-010)."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select, text

from ..api.errors import ApiError
from ..db.budget import BudgetAccount, BudgetReservation, BudgetReservationAllocation
from ..db.icp import Project

ZERO = Decimal("0.000000")
UNIT = Decimal("0.000001")
CATEGORIES = frozenset({"discovery", "extraction", "assessment", "contact_lookup", "draft_generation"})
RANK = {"workspace": 0, "project": 1, "run": 2, "category": 3}


def would_exceed(limit: Decimal, settled: Decimal, reserved: Decimal, proposed: Decimal) -> bool:
    return settled + reserved + proposed > limit


def lock_order(account_ids: list[str]) -> list[str]:
    return sorted(account_ids)


def _money(value: Decimal, *, positive: bool = False) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value.as_tuple().exponent < -6:
        raise ApiError(422, "INVALID_REQUEST", "money requires a finite Decimal with at most six places")
    if value < ZERO or (positive and value == ZERO) or value >= Decimal("100000000000000"):
        raise ApiError(422, "INVALID_REQUEST", "money is outside its allowed range")
    return value.quantize(UNIT)


def _period(at: datetime | None) -> tuple[datetime, datetime, str]:
    at = at or datetime.now(timezone.utc)
    if at.tzinfo is None:
        raise ApiError(422, "INVALID_REQUEST", "budget time must be timezone aware")
    start = at.astimezone(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
    return start, end, start.strftime("%Y-%m")


async def lock_budget_workspace(session, workspace_id: uuid.UUID) -> None:
    # A single workspace gate serializes creation and admission across a UTC rollover.
    # Callers hold the short DB transaction only, never across provider/network work.
    await session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                          {"key": f"budget:{workspace_id}"})


def _keys(workspace_id, project_id, run_id, category):
    keys = [("workspace", workspace_id, "all")]
    if project_id is not None:
        keys.append(("project", project_id, "all"))
    if run_id is not None:
        keys.append(("run", run_id, "all"))
    if project_id is not None and category is not None:
        keys.append(("category", project_id, category))
    return keys


async def ensure_period_accounts(session, workspace_id: uuid.UUID, project_id: uuid.UUID | None,
                                 run_id: uuid.UUID | None, category: str | None, *, at: datetime | None = None):
    if category is not None and category not in CATEGORIES:
        raise ApiError(422, "INVALID_REQUEST", "unsupported budget category")
    if project_id is not None:
        project = (await session.execute(select(Project).where(Project.id == project_id,
                                Project.workspace_id == workspace_id))).scalar_one_or_none()
        if project is None:
            raise ApiError(404, "NOT_FOUND", "project not found")
    if run_id is not None:
        if project_id is None:
            raise ApiError(422, "INVALID_REQUEST", "run requires a project")
        from ..db.runs import SearchRun
        run = (await session.execute(select(SearchRun).where(SearchRun.id == run_id,
                            SearchRun.workspace_id == workspace_id, SearchRun.project_id == project_id))).scalar_one_or_none()
        if run is None:
            raise ApiError(404, "NOT_FOUND", "run not found")
    start, end, label = _period(at)
    rows = []
    for kind, scope_id, cat in _keys(workspace_id, project_id, run_id, category):
        row = (await session.execute(select(BudgetAccount).where(
            BudgetAccount.workspace_id == workspace_id, BudgetAccount.scope == kind,
            BudgetAccount.scope_id == scope_id, BudgetAccount.category == cat,
            BudgetAccount.currency == "USD", BudgetAccount.period_start == start,
        ))).scalar_one_or_none()
        if row is None:
            row = BudgetAccount(workspace_id=workspace_id, scope=kind, scope_id=scope_id,
                                category=cat, currency="USD", period=label, period_start=start,
                                period_end=end, approved_limit=ZERO, settled_spend=ZERO)
            session.add(row)
            await session.flush()
        rows.append(row)
    return rows


async def _held(session, account: BudgetAccount) -> tuple[Decimal, Decimal]:
    result = (await session.execute(
        select(func.coalesce(func.sum(BudgetReservation.remaining_hold), 0),
               func.coalesce(func.sum(BudgetReservation.remaining_hold).filter(
                   BudgetAccount.period_start < account.period_start), 0))
        .select_from(BudgetReservationAllocation)
        .join(BudgetReservation, BudgetReservation.id == BudgetReservationAllocation.reservation_id)
        .join(BudgetAccount, BudgetAccount.id == BudgetReservationAllocation.account_id)
        .where(BudgetReservationAllocation.workspace_id == account.workspace_id,
               BudgetAccount.scope == account.scope, BudgetAccount.scope_id == account.scope_id,
               BudgetAccount.category == account.category, BudgetAccount.currency == account.currency,
               BudgetAccount.period_start <= account.period_start,
               BudgetReservation.remaining_hold > ZERO)
    )).one()
    return Decimal(result[0]), Decimal(result[1])


def _as_money(value: Decimal, currency: str = "USD") -> dict:
    return {"amount": format(value.quantize(UNIT), ".6f"), "currency": currency}


async def budget_data(session, row: BudgetAccount) -> dict:
    held, carried = await _held(session, row)
    remaining = row.approved_limit - row.settled_spend - held
    return {
        "id": str(row.id), "workspace_id": str(row.workspace_id), "version": row.version,
        "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat(),
        "data_mode": "live", "scope": row.scope, "scope_id": str(row.scope_id),
        "period_start": row.period_start.isoformat(), "period_end": row.period_end.isoformat(),
        "category": row.category, "approved_limit": _as_money(row.approved_limit),
        "settled": _as_money(row.settled_spend), "reserved": _as_money(held),
        "carried_reserved": _as_money(carried), "remaining": _as_money(max(ZERO, remaining)),
        "effective_state": "frozen_pending_budget" if row.frozen or remaining <= ZERO else "active",
    }


async def account_snapshot(session, workspace_id: uuid.UUID, project_id: uuid.UUID | None,
                           run_id: uuid.UUID | None, category: str | None, *, at: datetime | None = None) -> list[dict]:
    await lock_budget_workspace(session, workspace_id)
    accounts = await ensure_period_accounts(session, workspace_id, project_id, run_id, category, at=at)
    return [await budget_data(session, row) for row in accounts]


async def reserve_operation(session, operation_id: uuid.UUID, scope: dict, upper_bound: Decimal,
                            currency: str, price_version: str, *, at: datetime | None = None) -> uuid.UUID:
    """Reserve exactly once; caller inserts job/outbox in this same transaction."""
    workspace_id = scope.get("workspace_id")
    project_id = scope.get("project_id")
    run_id = scope.get("run_id")
    category = scope.get("category")
    if not isinstance(workspace_id, uuid.UUID) or not isinstance(project_id, uuid.UUID) or category not in CATEGORIES:
        raise ApiError(422, "INVALID_REQUEST", "workspace, project and category are required")
    if currency != "USD" or not price_version or price_version.startswith("legacy-"):
        raise ApiError(409, "POLICY_BLOCKED", "verified USD upper-bound pricing is required")
    upper_bound = _money(upper_bound, positive=True)
    await lock_budget_workspace(session, workspace_id)
    existing = (await session.execute(select(BudgetReservation).where(
        BudgetReservation.workspace_id == workspace_id, BudgetReservation.operation_id == operation_id
    ).with_for_update())).scalar_one_or_none()
    if existing:
        assigned = (await session.execute(select(BudgetAccount.scope, BudgetAccount.scope_id, BudgetAccount.category)
            .join(BudgetReservationAllocation, BudgetReservationAllocation.account_id == BudgetAccount.id)
            .where(BudgetReservationAllocation.reservation_id == existing.id))).all()
        if (existing.upper_bound != upper_bound or existing.price_version != price_version or
            existing.currency != currency or set(assigned) != set(_keys(workspace_id, project_id, run_id, category))):
            raise ApiError(409, "IDEMPOTENCY_CONFLICT", "operation reservation differs")
        return existing.id
    accounts = await ensure_period_accounts(session, workspace_id, project_id, run_id, category, at=at)
    accounts.sort(key=lambda a: (RANK[a.scope], str(a.id)))
    for account in accounts:
        await session.execute(select(BudgetAccount.id).where(BudgetAccount.id == account.id).with_for_update())
        held, _ = await _held(session, account)
        if account.frozen or would_exceed(account.approved_limit, account.settled_spend, held, upper_bound):
            raise ApiError(409, "BUDGET_LIMIT", "approved scope limit cannot cover operation")
    start, _, _ = _period(at)
    reservation = BudgetReservation(workspace_id=workspace_id, account_id=accounts[0].id,
        operation_id=operation_id, intent_key=str(operation_id), upper_bound=upper_bound,
        remaining_hold=upper_bound, state="active", price_version=price_version,
        currency=currency, origin_period_start=start)
    session.add(reservation)
    await session.flush()
    for account in accounts:
        session.add(BudgetReservationAllocation(workspace_id=workspace_id,
                    reservation_id=reservation.id, account_id=account.id))
    await session.flush()
    return reservation.id
