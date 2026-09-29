"""Apply authenticated provider status without weakening the shared job hold."""

import hashlib
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from ..api.errors import ApiError
from ..db.contact import EnrichmentJob, EnrichmentQuote, ProviderEvent, ProviderOperation
from ..providers.base import Money
from .policy_service import evaluate_current_policy, policy_workspace_lock
from .provider_op import reconcile_transition, transition
from .settlement import settle_operation

TERMINAL = frozenset({"succeeded", "not_found", "failed", "cancelled"})


async def settle_contact_job_if_ready(session, job: EnrichmentJob,
                                      operations: list[ProviderOperation]) -> bool:
    """Commit the aggregate cost once every child has authoritative cost evidence."""
    if not operations or not all(row.status in TERMINAL and row.observed_cost is not None
                                 and row.external_event_id for row in operations):
        return False
    total = sum((row.observed_cost for row in operations), Decimal("0.000000"))
    evidence = "|".join(sorted(row.external_event_id for row in operations))
    aggregate_id = f"contact-job:{job.id}:{hashlib.sha256(evidence.encode()).hexdigest()[:24]}"
    await settle_operation(session, job.id, total, aggregate_id)
    job.state = "found" if any(row.result_contact_id for row in operations) else "reconciled"
    return True


async def apply_verified_result(session, *, workspace_id: uuid.UUID, operation_id: uuid.UUID,
                                provider: str, account_reference: str, provider_ref: str,
                                event_id: str, digest: str, state: str,
                                observed_cost: Decimal | None) -> dict:
    """Deduplicate an authenticated event and settle only after every child is proven.

    Caller verifies vendor raw bytes or makes a verified nonbillable status call.
    This function does not infer authenticity from client-supplied normalized JSON.
    """
    if not event_id or len(event_id) > 128 or len(digest) != 64:
        raise ApiError(422, "INVALID_REQUEST", "verified event identity and digest required")
    if state not in {"accepted", "pending", "unknown", "succeeded", "not_found", "failed"}:
        raise ApiError(422, "INVALID_REQUEST", "unsupported provider state")
    await policy_workspace_lock(session, workspace_id)
    candidate = (await session.execute(select(ProviderOperation).where(
        ProviderOperation.workspace_id == workspace_id, ProviderOperation.id == operation_id,
    ))).scalar_one_or_none()
    if candidate is None or candidate.job_id is None:
        raise ApiError(404, "NOT_FOUND", "provider operation not found")
    job = (await session.execute(select(EnrichmentJob).where(
        EnrichmentJob.workspace_id == workspace_id, EnrichmentJob.id == candidate.job_id,
    ).with_for_update())).scalar_one()
    operation = (await session.execute(select(ProviderOperation).where(
        ProviderOperation.workspace_id == workspace_id, ProviderOperation.id == operation_id,
    ).with_for_update())).scalar_one()
    if (operation.provider_name != provider or operation.account_reference != account_reference or
            operation.provider_ref != provider_ref):
        raise ApiError(404, "NOT_FOUND", "provider operation not found")
    existing = (await session.execute(select(ProviderEvent).where(
        ProviderEvent.provider == provider,
        ProviderEvent.account_reference == account_reference,
        ProviderEvent.event_id == event_id,
    ).with_for_update())).scalar_one_or_none()
    if existing is not None:
        if existing.digest != digest or existing.operation_id != operation_id:
            raise ApiError(409, "IDEMPOTENCY_CONFLICT", "provider event identity changed")
        return {"accepted": True, "duplicate": True, "applied": existing.processing_state == "applied"}
    event = ProviderEvent(workspace_id=workspace_id, provider=provider,
        account_reference=account_reference, event_id=event_id, digest=digest,
        operation_id=operation_id, processing_state="received")
    session.add(event)
    await session.flush()
    if operation.status in TERMINAL:
        event.processing_state = "ignored"
        return {"accepted": True, "duplicate": False, "applied": False}
    if state in {"accepted", "pending"}:
        next_state = transition(operation.status, state)
        if next_state != operation.status:
            operation.status = next_state
            job.state = "pending"
            job.version += 1
            event.processing_state = "applied"
        else:
            event.processing_state = "ignored"
        return {"accepted": True, "duplicate": False, "applied": event.processing_state == "applied"}
    if state == "unknown":
        operation.status = "unknown"
        job.state = "unknown"
        job.version += 1
        event.processing_state = "applied"
        return {"accepted": True, "duplicate": False, "applied": True}
    quote = (await session.execute(select(EnrichmentQuote).where(
        EnrichmentQuote.workspace_id == workspace_id, EnrichmentQuote.id == job.quote_id,
    ))).scalar_one()
    operations = (await session.execute(select(ProviderOperation).where(
        ProviderOperation.workspace_id == workspace_id, ProviderOperation.job_id == job.id,
    ).order_by(ProviderOperation.id).with_for_update())).scalars().all()
    if not operations or quote.max_cost <= 0:
        raise ApiError(409, "BUDGET_LIMIT", "per-intent bound cannot be proven")
    per_intent_bound = quote.max_cost / len(operations)
    if per_intent_bound != per_intent_bound.quantize(Decimal("0.000001")):
        raise ApiError(409, "BUDGET_LIMIT", "per-intent bound is not exact")
    try:
        if observed_cost is None:
            raise ValueError("missing cost")
        Money(observed_cost)
        if observed_cost > per_intent_bound:
            raise ValueError("cost above bound")
    except (ValueError, TypeError):
        operation.status = "unknown"
        job.state = "unknown"
        job.version += 1
        event.processing_state = "unverified_cost"
        return {"accepted": True, "duplicate": False, "applied": False}
    next_state = reconcile_transition(operation.status, state, authoritative_event_id=event_id)
    if next_state == operation.status:
        event.processing_state = "ignored"
        return {"accepted": True, "duplicate": False, "applied": False}
    operation.status = next_state
    operation.observed_cost = observed_cost
    vendor_identity = f"{provider}:{account_reference}:{event_id}"
    operation.external_event_id = "provider-event:" + hashlib.sha256(vendor_identity.encode()).hexdigest()
    # No contact payload is accepted through this normalized status envelope.
    # Exposure requires separately verified provenance and an encryption owner.
    basis = next((row for row in (quote.selection or {}).get("resolved", [])
                  if row.get("buyer_id") == str(operation.buyer_id)), None)
    if basis and basis.get("company_id"):
        policy = await evaluate_current_policy(session, {
            "workspace_id": workspace_id, "project_id": quote.project_id,
            "company_id": basis["company_id"],
        }, "contact_research", datetime.now(timezone.utc))
        event.processing_state = "applied" if policy["allowed"] and not job.cancel_requested else "quarantined"
    else:
        event.processing_state = "quarantined"
    if not await settle_contact_job_if_ready(session, job, operations):
        job.state = "unknown" if any(row.status == "unknown" for row in operations) else "pending"
    job.version += 1
    return {"accepted": True, "duplicate": False, "applied": True}
