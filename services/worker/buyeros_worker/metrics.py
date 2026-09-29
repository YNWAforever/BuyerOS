"""Tenant-scoped operational aggregates with no payload or identity fields."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import uuid

from sqlalchemy import and_, func, select

from buyeros_api.db.budget import BudgetReservation
from buyeros_api.db.contact import ProviderOperation
from buyeros_api.db.outbox import AsyncJob, OutboxEvent
from buyeros_api.db.session import tenant_session


async def collect_operational_metrics(engine, workspace_id: uuid.UUID, now: datetime) -> dict:
    async with tenant_session(engine, workspace_id) as session:
        ready_count, oldest_ready = (await session.execute(select(
            func.count(OutboxEvent.id), func.min(OutboxEvent.created_at),
        ).where(OutboxEvent.workspace_id == workspace_id,
                OutboxEvent.state == "ready"))).one()
        expired_leases = (await session.execute(select(func.count(OutboxEvent.id)).where(
            OutboxEvent.workspace_id == workspace_id,
            OutboxEvent.state == "dispatched",
            OutboxEvent.lease_expires_at <= now,
        ))).scalar_one()
        failed_intents = (await session.execute(select(func.count(OutboxEvent.id)).where(
            OutboxEvent.workspace_id == workspace_id,
            OutboxEvent.state == "failed",
        ))).scalar_one()
        pending_jobs = (await session.execute(select(func.count(AsyncJob.id)).where(
            AsyncJob.workspace_id == workspace_id,
            AsyncJob.status.in_(("queued", "running", "cancel_requested")),
        ))).scalar_one()
        unknown_count, unknown_amount = (await session.execute(select(
            func.count(BudgetReservation.id),
            func.coalesce(func.sum(BudgetReservation.remaining_hold), 0),
        ).join(ProviderOperation, and_(
            ProviderOperation.workspace_id == BudgetReservation.workspace_id,
            ProviderOperation.id == BudgetReservation.operation_id,
        )).where(
            BudgetReservation.workspace_id == workspace_id,
            BudgetReservation.remaining_hold > Decimal("0"),
            ProviderOperation.status.in_(("submitting", "accepted", "pending", "unknown")),
        ))).one()
    age = max(0, int((now - oldest_ready).total_seconds())) if oldest_ready else 0
    return {
        "ready_intents": int(ready_count),
        "oldest_ready_seconds": age,
        "expired_leases": int(expired_leases),
        "failed_intents": int(failed_intents),
        "pending_jobs": int(pending_jobs),
        "unknown_hold_count": int(unknown_count),
        "unknown_hold_usd": format(Decimal(unknown_amount), ".6f"),
    }
