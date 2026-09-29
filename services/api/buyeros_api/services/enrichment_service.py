"""Actor-bound contact job read and cancellation with financial truth from the ledger."""

import uuid
from decimal import Decimal

from sqlalchemy import select

from ..api.errors import ApiError
from ..db.budget import BudgetReservation, CostEvent
from ..db.contact import EnrichmentJob, EnrichmentQuote, ProviderOperation
from ..db.outbox import OutboxEvent
from .audit_service import append_audit
from .settlement import release_unsubmitted_operation
from .contact_result_service import settle_contact_job_if_ready


async def require_job(session, workspace_id: uuid.UUID, job_id: uuid.UUID, *,
                      actor_id: uuid.UUID, is_admin: bool, lock: bool = False):
    query = select(EnrichmentJob, EnrichmentQuote).join(
        EnrichmentQuote,
        (EnrichmentQuote.workspace_id == EnrichmentJob.workspace_id) &
        (EnrichmentQuote.id == EnrichmentJob.quote_id),
    ).where(EnrichmentJob.workspace_id == workspace_id, EnrichmentJob.id == job_id)
    if lock:
        query = query.with_for_update(of=EnrichmentJob)
    row = (await session.execute(query)).one_or_none()
    if row is None or (not is_admin and row[1].actor_id != actor_id):
        raise ApiError(404, "NOT_FOUND", "contact job not found")
    return row


async def job_data(session, job: EnrichmentJob, quote: EnrichmentQuote) -> dict:
    operations = (await session.execute(select(ProviderOperation).where(
        ProviderOperation.workspace_id == job.workspace_id,
        ProviderOperation.job_id == job.id,
    ).order_by(ProviderOperation.id))).scalars().all()
    reservation = (await session.execute(select(BudgetReservation).where(
        BudgetReservation.workspace_id == job.workspace_id,
        BudgetReservation.id == job.reservation_id,
    ))).scalar_one()
    economic_events = (await session.execute(select(CostEvent).where(
        CostEvent.workspace_id == job.workspace_id,
        CostEvent.operation_id == job.id,
    ))).scalars().all()
    settled = sum((row.amount for row in economic_events), Decimal("0.000000"))
    completed = sum(row.status in {"succeeded", "not_found", "failed", "cancelled"} for row in operations)
    unknown = sum(row.status in {"unknown", "submitting"} for row in operations)
    found = [str(row.result_contact_id) for row in operations if row.result_contact_id is not None]
    reconciliation = ("manual_review" if unknown and any(row.provider_ref is None for row in operations
                         if row.status in {"unknown", "submitting"}) else
                      "pending" if unknown or any(row.status in {"accepted", "pending"} for row in operations)
                      else "resolved" if job.state in {"reconciled", "found", "not_found", "failed"}
                      else "not_required")
    return {
        "id": str(job.id), "workspace_id": str(job.workspace_id), "version": job.version,
        "created_at": job.created_at.isoformat(), "updated_at": job.updated_at.isoformat(),
        "data_mode": "live", "project_id": str(quote.project_id), "quote_id": str(quote.id),
        "status": job.state, "cancel_requested": job.cancel_requested,
        "reservation_id": str(job.reservation_id),
        "provider_operation_ids": [str(row.id) for row in operations],
        "completed_count": completed, "found_count": len(found), "unknown_count": unknown,
        "result_contact_ids": found,
        "max_cost": {"amount": format(quote.max_cost, ".6f"), "currency": "USD"},
        "settled_cost": {"amount": format(settled, ".6f"), "currency": "USD"},
        "held_cost": {"amount": format(reservation.remaining_hold, ".6f"), "currency": "USD"},
        "reconciliation_state": reconciliation,
    }


async def cancel_job(session, workspace_id: uuid.UUID, job_id: uuid.UUID,
                     actor_id: uuid.UUID, *, version: int, reason: str, is_admin: bool) -> dict:
    job, quote = await require_job(session, workspace_id, job_id, actor_id=actor_id,
                                   is_admin=is_admin, lock=True)
    if job.version != version:
        raise ApiError(412, "STALE_REVISION", "contact job version changed")
    if job.state in {"cancelled", "found", "not_found", "failed", "reconciled"}:
        raise ApiError(409, "INVALID_STATE", "contact job is terminal")
    operations = (await session.execute(select(ProviderOperation).where(
        ProviderOperation.workspace_id == workspace_id, ProviderOperation.job_id == job_id,
    ).order_by(ProviderOperation.id).with_for_update())).scalars().all()
    if not operations:
        raise ApiError(409, "INVALID_STATE", "contact job has no provider intents")
    job.cancel_requested = True
    job.version += 1
    for row in operations:
        row.cancel_requested = True
    if all(row.status in {"intent", "reserved"} for row in operations):
        await release_unsubmitted_operation(session, job.id)
        for row in operations:
            row.status = "cancelled"
        job.state = "cancelled"
        outbox = (await session.execute(select(OutboxEvent).where(
            OutboxEvent.workspace_id == workspace_id,
            OutboxEvent.intent_key == f"contact.lookup:{job_id}",
        ).with_for_update())).scalar_one_or_none()
        if outbox is not None and outbox.state in {"ready", "dispatched"}:
            outbox.state = "done"
            outbox.lease_owner = None
            outbox.lease_expires_at = None
    else:
        for row in operations:
            if row.status in {"intent", "reserved"}:
                row.status = "cancelled"
                row.observed_cost = Decimal("0.000000")
                row.external_event_id = f"not-submitted:{row.id}"
        if not await settle_contact_job_if_ready(session, job, operations) and job.state != "unknown":
            job.state = "pending"
    append_audit(session, workspace_id=workspace_id, actor_id=actor_id,
                 action="contact_lookup.cancel_requested", entity_type="enrichment_job",
                 entity_id=job.id, reason=reason)
    await session.flush()
    await session.refresh(job)
    return await job_data(session, job, quote)


async def queue_reconciliation(session, workspace_id: uuid.UUID, job_id: uuid.UUID,
                               actor_id: uuid.UUID, *, reason: str,
                               capability, environment: str,
                               status_nonbillable: bool) -> dict:
    from ..db.outbox import AsyncJob
    from .bulk_service import job_data as async_job_data

    job, quote = await require_job(session, workspace_id, job_id,
                                   actor_id=actor_id, is_admin=True, lock=True)
    operations = (await session.execute(select(ProviderOperation).where(
        ProviderOperation.workspace_id == workspace_id,
        ProviderOperation.job_id == job_id,
        ProviderOperation.status.in_(["accepted", "pending", "unknown"]),
    ).order_by(ProviderOperation.id).with_for_update())).scalars().all()
    if not operations or any(not row.provider_ref for row in operations):
        raise ApiError(409, "INVALID_STATE", "no safely addressable provider status exists")
    if (capability is None or capability.service != "contact" or
            capability.status != "verified" or not status_nonbillable or
            any(row.provider_name != capability.provider for row in operations)):
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "verified nonbillable status is unavailable")
    if capability.provider == "fixture" and environment != "test":
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "fixture status is test-only")
    async_job = AsyncJob(workspace_id=workspace_id, project_id=quote.project_id,
        actor_user_id=actor_id, kind="reconciliation", operation="reconcileEnrichmentJob",
        command={"enrichment_job_id": str(job_id)}, status="queued",
        requested=len(operations), processed=0, updated=0, unchanged=0,
        blocked=0, conflicts=0)
    session.add(async_job)
    await session.flush()
    for operation in operations:
        session.add(OutboxEvent(
            workspace_id=workspace_id,
            intent_key=f"contact.reconcile:{operation.id}:manual:{async_job.id}",
            event_type="contact.reconcile",
            payload={"workspace_id": str(workspace_id), "job_id": str(job_id),
                     "operation_id": str(operation.id), "async_job_id": str(async_job.id)},
            state="ready",
        ))
    append_audit(session, workspace_id=workspace_id, actor_id=actor_id,
                 action="contact_lookup.reconciliation_requested",
                 entity_type="enrichment_job", entity_id=job_id, reason=reason)
    await session.flush()
    await session.refresh(async_job)
    return async_job_data(async_job)
