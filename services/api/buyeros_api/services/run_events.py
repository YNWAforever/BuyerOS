"""Durable run event ordering and tenant-scoped run snapshots (BO-016)."""

import uuid
from decimal import Decimal

from sqlalchemy import func, select

from ..api.errors import ApiError
from ..db.budget import BudgetAccount, BudgetReservation, BudgetReservationAllocation
from ..db.buyers import FitAssessment
from ..db.runs import RawCandidate, RunEvent, SearchRun


def next_sequence(last_sequence: int) -> int:
    return last_sequence + 1


def apply_event(applied: int, incoming: int) -> bool:
    """True only for a strictly newer sequence; duplicates/out-of-order ignored."""
    return incoming > applied


def _money(amount: Decimal) -> dict:
    return {"amount": format(amount, ".6f"), "currency": "USD"}


async def require_run(session, workspace_id: uuid.UUID, run_id: uuid.UUID, *, lock: bool = False) -> SearchRun:
    query = select(SearchRun).where(SearchRun.workspace_id == workspace_id, SearchRun.id == run_id)
    run = (await session.execute(query.with_for_update() if lock else query)).scalar_one_or_none()
    if run is None:
        raise ApiError(404, "NOT_FOUND", "run not found")
    return run


async def run_snapshot(session, run: SearchRun) -> dict:
    workspace_id = run.workspace_id
    run_id = run.id
    latest = (await session.execute(select(func.coalesce(func.max(RunEvent.sequence), 0)).where(
        RunEvent.workspace_id == workspace_id, RunEvent.run_id == run_id))).scalar_one()
    companies = (await session.execute(select(func.count(func.distinct(RawCandidate.canonical_company_id))).where(
        RawCandidate.workspace_id == workspace_id, RawCandidate.run_id == run_id,
        RawCandidate.canonical_company_id.is_not(None)))).scalar_one()
    assessed = (await session.execute(select(func.count()).select_from(FitAssessment).where(
        FitAssessment.workspace_id == workspace_id, FitAssessment.run_id == run_id))).scalar_one()
    spent = (await session.execute(select(func.coalesce(func.sum(BudgetAccount.settled_spend), 0)).where(
        BudgetAccount.workspace_id == workspace_id, BudgetAccount.scope == "run",
        BudgetAccount.scope_id == run_id))).scalar_one()
    held = (await session.execute(select(func.coalesce(func.sum(BudgetReservation.remaining_hold), 0))
        .join(BudgetReservationAllocation,
              (BudgetReservationAllocation.reservation_id == BudgetReservation.id) &
              (BudgetReservationAllocation.workspace_id == BudgetReservation.workspace_id))
        .join(BudgetAccount,
              (BudgetAccount.id == BudgetReservationAllocation.account_id) &
              (BudgetAccount.workspace_id == BudgetReservation.workspace_id))
        .where(BudgetAccount.workspace_id == workspace_id, BudgetAccount.scope == "run",
               BudgetAccount.scope_id == run_id, BudgetReservation.state == "active"))).scalar_one()
    data = {
        "id": str(run.id), "workspace_id": str(workspace_id), "project_id": str(run.project_id),
        "icp_version_id": str(run.icp_version_id), "version": run.version,
        "created_at": run.created_at.isoformat(), "updated_at": run.updated_at.isoformat(),
        "data_mode": "live", "status": run.status, "stage": run.stage,
        "target_companies": run.target_companies, "raw_count": run.raw_result_count, "company_count": int(companies),
        "assessed_count": int(assessed), "last_event_sequence": int(latest),
        "max_cost": _money(run.max_cost), "spent": _money(Decimal(spent)),
        "reserved": _money(Decimal(held)), "limits": run.limits, "attempt": run.attempt,
    }
    if run.terminal_reason:
        data["failure_code"] = run.terminal_reason
    return data


async def append_event(session, run: SearchRun, event_type: str, *, payload: dict | None = None) -> RunEvent:
    """Caller holds the run row lock; state and event share its transaction."""
    latest = (await session.execute(select(func.coalesce(func.max(RunEvent.sequence), 0)).where(
        RunEvent.workspace_id == run.workspace_id, RunEvent.run_id == run.id))).scalar_one()
    event = RunEvent(workspace_id=run.workspace_id, run_id=run.id, sequence=next_sequence(int(latest)),
                     event_type=event_type, payload=payload or {})
    session.add(event)
    await session.flush()
    return event


async def event_page(session, run: SearchRun, after: int, limit: int) -> dict:
    latest = (await session.execute(select(func.coalesce(func.max(RunEvent.sequence), 0)).where(
        RunEvent.workspace_id == run.workspace_id, RunEvent.run_id == run.id))).scalar_one()
    rows = (await session.execute(select(RunEvent).where(
        RunEvent.workspace_id == run.workspace_id, RunEvent.run_id == run.id,
        RunEvent.sequence > after).order_by(RunEvent.sequence).limit(limit + 1))).scalars().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    data = [
        {"event_id": str(row.id), "workspace_id": str(run.workspace_id), "run_id": str(run.id),
         "sequence": row.sequence, "type": row.event_type, "occurred_at": row.created_at.isoformat(),
         "run_version": row.payload.get("version", 1),
         "stage": row.payload.get("stage", "queued" if row.event_type == "run.queued" else "unknown"), "company_count": row.payload.get("company_count", 0),
         "raw_count": row.payload.get("raw_count", 0),
         "message_code": row.event_type.upper().replace(".", "_"),
         "data_mode": "live"} for row in rows
    ]
    return {"items": data, "next_after_sequence": rows[-1].sequence if rows else after,
            "has_more": has_more, "latest_sequence": int(latest)}
