"""Idempotent quote confirmation primitives (BO-018)."""

import hashlib
import json
from dataclasses import dataclass


class IdempotencyConflict(Exception):
    pass


class QuoteChanged(Exception):
    pass


class QuoteExpired(Exception):
    pass


@dataclass
class ConfirmResult:
    job_id: str
    reservation_id: str
    idempotent_replay: bool = False


def request_fingerprint(body: dict) -> str:
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def same_request(key_a: str, hash_a: str, key_b: str, hash_b: str, raise_on_conflict: bool = False) -> bool:
    if key_a != key_b:
        return False
    if hash_a == hash_b:
        return True
    if raise_on_conflict:
        raise IdempotencyConflict("same key with a different body")
    return False


async def confirm_lookup(session, actor_id, quote_id, request, idempotency_key: str, *,
                         workspace_id, capability, environment: str) -> dict:
    """Consume one exact quote and admit one bounded, durable lookup job atomically.

    The caller owns the idempotency row in this same transaction. This function
    never invokes a provider or publishes to the broker.
    """
    import uuid
    from datetime import datetime, timezone
    from decimal import Decimal

    from sqlalchemy import select

    from ..api.errors import ApiError
    from ..api.schemas import QuoteRequest
    from ..db.buyers import ProjectBuyer
    from ..db.contact import EnrichmentJob, ProviderOperation
    from ..db.outbox import OutboxEvent
    from .audit_service import append_audit
    from .budget_service import reserve_operation
    from .quote_service import quote_hash, quote_lookup, require_quote
    from .policy_service import policy_workspace_lock

    quote = await require_quote(session, workspace_id, quote_id, lock=True)
    if quote.actor_id != actor_id:
        raise ApiError(403, "PERMISSION_DENIED", "only the quoted actor can confirm")
    if quote.status != "quoted" or quote.consumed_job_id or quote.reservation_id:
        raise ApiError(409, "INVALID_STATE", "quote is no longer confirmable")
    if quote.expires_at is None or quote.expires_at <= datetime.now(timezone.utc):
        raise ApiError(409, "QUOTE_EXPIRED", "quote expired; obtain a fresh quote")
    if request.quote_hash != quote.quote_hash:
        raise ApiError(409, "QUOTE_CHANGED", "quote hash changed; obtain a fresh quote")
    # Policy/suppression writers hold this same workspace lock through commit.
    # If they commit first, revalidation sees them; if we commit first, the
    # later writer wins before worker dispatch and T23 must gate that boundary.
    await policy_workspace_lock(session, workspace_id)
    frozen = quote.selection or {}
    selected = frozen.get("resolved")
    if not isinstance(selected, list) or not selected or not isinstance(frozen.get("request"), dict):
        raise ApiError(409, "QUOTE_CHANGED", "quote has no verifiable selection")
    buyer_ids = sorted({uuid.UUID(row["buyer_id"]) for row in selected})
    # Buyer mutation uses row locks; keep a stable order before the budget hierarchy.
    await session.execute(select(ProjectBuyer.id).where(
        ProjectBuyer.workspace_id == workspace_id, ProjectBuyer.project_id == quote.project_id,
        ProjectBuyer.id.in_(buyer_ids),
    ).order_by(ProjectBuyer.id).with_for_update())
    try:
        quote_request = QuoteRequest.model_validate(frozen["request"])
        current = await quote_lookup(session, actor_id, quote.project_id, quote_request,
                                     workspace_id=workspace_id, capability=capability,
                                     environment=environment, persist=False)
    except ApiError as exc:
        if exc.code == "PROVIDER_UNAVAILABLE":
            raise
        raise ApiError(409, "QUOTE_CHANGED", "quote context changed; obtain a fresh quote") from exc
    if (current.selection["context_hash"] != frozen.get("context_hash") or
        current.eligibility != quote.eligibility or current.max_cost != quote.max_cost or
        current.price_version != quote.price_version or current.adapter_version != quote.adapter_version):
        raise ApiError(409, "QUOTE_CHANGED", "quote context changed; obtain a fresh quote")
    eligible_ids = [row["buyer_id"] for row in current.eligibility if row["eligible"]]
    if not eligible_ids or quote.max_cost <= Decimal("0"):
        raise ApiError(409, "QUOTE_CHANGED", "no currently eligible buyer remains")

    job_id = uuid.uuid4()
    reservation_id = await reserve_operation(
        session, job_id,
        {"workspace_id": workspace_id, "project_id": quote.project_id,
         "category": "contact_lookup"},
        quote.max_cost, "USD", quote.price_version,
    )
    job = EnrichmentJob(id=job_id, workspace_id=workspace_id, quote_id=quote.id,
                        reservation_id=reservation_id, state="reserved")
    session.add(job)
    operations = []
    for buyer_id in eligible_ids:
        operation = ProviderOperation(
            workspace_id=workspace_id, job_id=job_id, buyer_id=uuid.UUID(buyer_id),
            intent_key=f"contact:{job_id}:{buyer_id}", capability="contact",
            input_hash=quote_hash({"quote_hash": quote.quote_hash, "buyer_id": buyer_id,
                                   "roles": quote.roles, "contact_type": quote.contact_type}),
            status="intent",
        )
        session.add(operation)
        operations.append(operation)
    session.add(OutboxEvent(
        workspace_id=workspace_id, intent_key=f"contact.lookup:{job_id}",
        event_type="contact.lookup",
        payload={"workspace_id": str(workspace_id), "job_id": str(job_id)},
        state="ready",
    ))
    quote.status = "consumed"
    quote.version += 1
    quote.reservation_id = reservation_id
    quote.consumed_job_id = job_id
    append_audit(session, workspace_id=workspace_id, actor_id=actor_id,
                 action="contact_lookup.confirmed", entity_type="enrichment_job", entity_id=job_id)
    await session.flush()
    await session.refresh(job)
    return {
        "id": str(job.id), "workspace_id": str(workspace_id), "version": 1,
        "created_at": job.created_at.isoformat(), "updated_at": job.updated_at.isoformat(),
        "data_mode": "live", "project_id": str(quote.project_id),
        "quote_id": str(quote.id), "status": "reserved", "cancel_requested": False,
        "reservation_id": str(reservation_id),
        "provider_operation_ids": [str(operation.id) for operation in operations],
        "completed_count": 0, "found_count": 0, "unknown_count": 0,
        "result_contact_ids": [],
        "max_cost": {"amount": format(quote.max_cost, ".6f"), "currency": "USD"},
        "settled_cost": {"amount": "0.000000", "currency": "USD"},
        "held_cost": {"amount": format(quote.max_cost, ".6f"), "currency": "USD"},
        "reconciliation_state": "not_required",
    }
