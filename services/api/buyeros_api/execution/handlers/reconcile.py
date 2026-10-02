"""Status-only contact reconciliation; no paid submit occurs on this path."""

import hashlib
import json
import uuid
import asyncio
from decimal import Decimal

from sqlalchemy import select

from buyeros_api.db.contact import EnrichmentJob, ProviderOperation
from buyeros_api.db.outbox import AsyncJob, OutboxEvent
from ..provider_context import execution_session as tenant_session
from buyeros_api.services.contact_result_service import apply_verified_result
from buyeros_api.services.policy_service import policy_workspace_lock


async def _finish_request(session, outbox: OutboxEvent, *, applied: bool) -> None:
    request_id = (outbox.payload or {}).get("async_job_id")
    if request_id:
        try:
            async_job_id = uuid.UUID(request_id)
        except (TypeError, ValueError):
            return
        row = (await session.execute(select(AsyncJob).where(
            AsyncJob.workspace_id == outbox.workspace_id,
            AsyncJob.id == async_job_id,
        ).with_for_update())).scalar_one_or_none()
        if row is not None and row.processed < row.requested:
            row.processed += 1
            if applied:
                row.updated += 1
            else:
                row.unchanged += 1
            row.status = "completed" if row.processed == row.requested else "running"


async def execute_contact_reconcile(engine, workspace_id: uuid.UUID, job_id: uuid.UUID,
                                    operation_id: uuid.UUID, outbox_intent_key: str,
                                    generation: int, adapter, *, environment: str = "production") -> str:
    async with tenant_session(engine, workspace_id) as session:
        job = (await session.execute(select(EnrichmentJob).where(
            EnrichmentJob.workspace_id == workspace_id, EnrichmentJob.id == job_id,
        ).with_for_update())).scalar_one_or_none()
        operation = (await session.execute(select(ProviderOperation).where(
            ProviderOperation.workspace_id == workspace_id, ProviderOperation.id == operation_id,
            ProviderOperation.job_id == job_id,
        ).with_for_update())).scalar_one_or_none()
        outbox = (await session.execute(select(OutboxEvent).where(
            OutboxEvent.workspace_id == workspace_id,
            OutboxEvent.intent_key == outbox_intent_key,
        ).with_for_update())).scalar_one_or_none()
        if job is None or operation is None or outbox is None:
            return "missing"
        if outbox.state != "dispatched" or outbox.fencing_generation != generation:
            return "stale"
        if operation.status in {"succeeded", "not_found", "failed", "cancelled"}:
            outbox.state = "done"
            await _finish_request(session, outbox, applied=False)
            return "done"
        if (operation.provider_name != adapter.capability.provider or
                adapter.capability.status != "verified" or
                not getattr(adapter, "status_nonbillable", False) or
                (getattr(adapter, "test_only", False) and environment != "test") or
                not operation.provider_ref):
            return "blocked"
        provider_ref = operation.provider_ref
    # A verified status query is the only provider call here and holds no DB lock.
    try:
        result = await asyncio.wait_for(adapter.status(provider_ref), timeout=45)
    except Exception:
        return "unknown"
    async with tenant_session(engine, workspace_id) as session:
        await policy_workspace_lock(session, workspace_id)
        await session.execute(select(EnrichmentJob.id).where(
            EnrichmentJob.workspace_id == workspace_id, EnrichmentJob.id == job_id,
        ).with_for_update())
        await session.execute(select(ProviderOperation.id).where(
            ProviderOperation.workspace_id == workspace_id, ProviderOperation.id == operation_id,
        ).with_for_update())
        outbox = (await session.execute(select(OutboxEvent).where(
            OutboxEvent.workspace_id == workspace_id,
            OutboxEvent.intent_key == outbox_intent_key,
        ).with_for_update())).scalar_one()
        if outbox.state != "dispatched" or outbox.fencing_generation != generation:
            return "stale"
        if result.provider_ref != provider_ref:
            return "unknown"
        if result.state in {"accepted", "pending", "unknown"}:
            outbox.state = "done"
            await _finish_request(session, outbox, applied=False)
            return "pending" if result.state != "unknown" else "unknown"
        if not result.event_id:
            return "unknown"
        digest = hashlib.sha256(json.dumps({
            "event_id": result.event_id, "ref": result.provider_ref,
            "state": result.state,
            "cost": str(result.observed_usage) if result.observed_usage is not None else None,
        }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        outcome = await apply_verified_result(
            session, workspace_id=workspace_id, operation_id=operation_id,
            provider=adapter.capability.provider,
            account_reference=operation.account_reference,
            provider_ref=provider_ref, event_id=result.event_id,
            digest=digest, state=result.state, observed_cost=result.observed_usage,
        )
        outbox.state = "done"
        outbox.lease_owner = None
        outbox.lease_expires_at = None
        await _finish_request(session, outbox, applied=outcome["applied"])
        return "reconciled" if outcome["applied"] else "unknown"
