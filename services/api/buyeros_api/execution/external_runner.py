"""Short DB prepare -> provider call -> short DB finalize for reserved operations.

The broker carries only IDs. No selected live provider exists; this boundary is
exercised with the explicit test-only adapter until a verified vendor is added.
Unknown acceptance never releases a hold or blindly resubmits.
"""
from __future__ import annotations

import hashlib
import json
import uuid
import asyncio
from dataclasses import dataclass

from sqlalchemy import select

from buyeros_api.db.budget import BudgetReservation
from buyeros_api.db.contact import ProviderOperation
from buyeros_api.db.outbox import OutboxEvent
from .provider_context import execution_session as tenant_session
from buyeros_api.providers.base import (
    ProviderAdapter, ProviderIntent, SubmissionResult, StatusResult,
    activation_blockers,
)


@dataclass(frozen=True)
class Prepared:
    action: str
    provider_ref: str | None = None


def input_digest(intent: ProviderIntent) -> str:
    body = {"key": intent.key, "service": intent.service, "market": intent.market,
            "language": intent.language, "role": intent.role}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def reconcile_intent_key(operation_id: uuid.UUID) -> str:
    return f"provider:reconcile:{operation_id}"


async def _queue_reconciliation(session, outbox: OutboxEvent,
                                operation_id: uuid.UUID, intent: ProviderIntent) -> None:
    key = reconcile_intent_key(operation_id)
    existing = (await session.execute(select(OutboxEvent.id).where(
        OutboxEvent.workspace_id == outbox.workspace_id,
        OutboxEvent.intent_key == key,
        OutboxEvent.event_type == "provider.reconcile",
    ))).scalar_one_or_none()
    if existing is None:
        session.add(OutboxEvent(
            workspace_id=outbox.workspace_id, intent_key=key,
            event_type="provider.reconcile",
            payload={"operation_id": str(operation_id), "service": intent.service,
                     "market": intent.market, "language": intent.language,
                     "role": intent.role, "original_intent_key": intent.key},
            state="ready",
        ))
    outbox.state = "done"
    outbox.lease_owner = None
    outbox.lease_expires_at = None


async def _prepare(engine, workspace_id: uuid.UUID, operation_id: uuid.UUID,
                   generation: int, adapter: ProviderAdapter, intent: ProviderIntent,
                   outbox_intent_key: str) -> Prepared:
    async with tenant_session(engine, workspace_id) as session:
        outbox = (await session.execute(select(OutboxEvent).where(
            OutboxEvent.workspace_id == workspace_id,
            OutboxEvent.intent_key == outbox_intent_key,
        ).with_for_update())).scalar_one_or_none()
        if outbox is None or outbox.state != "dispatched" or outbox.fencing_generation != generation:
            return Prepared("stale")
        operation = (await session.execute(select(ProviderOperation).where(
            ProviderOperation.workspace_id == workspace_id, ProviderOperation.id == operation_id
        ).with_for_update())).scalar_one_or_none()
        if operation is None or operation.intent_key != intent.key or operation.capability != intent.service:
            return Prepared("blocked")
        reservation = (await session.execute(select(BudgetReservation).where(
            BudgetReservation.workspace_id == workspace_id,
            BudgetReservation.operation_id == operation_id
        ).with_for_update())).scalar_one_or_none()
        if (reservation is None or reservation.state != "active"
                or operation.input_hash != input_digest(intent)):
            return Prepared("blocked")
        if operation.status in {"intent", "reserved"}:
            bound = adapter.capability.max_liability
            if (outbox_intent_key != intent.key or bound is None
                    or reservation.currency != bound.currency
                    or reservation.upper_bound > bound.amount
                    or reservation.price_version != adapter.capability.pricing_version
                    or operation.cancel_requested):
                return Prepared("blocked")
            operation.status = "submitting"
            return Prepared("submit")
        if operation.status == "submitting":
            operation.status = "unknown"
            if outbox_intent_key == intent.key:
                await _queue_reconciliation(session, outbox, operation_id, intent)
            return Prepared("unknown")
        if operation.status in {"accepted", "pending", "unknown"}:
            if outbox_intent_key == intent.key:
                await _queue_reconciliation(session, outbox, operation_id, intent)
                return Prepared("unknown")
            if operation.provider_ref and adapter.capability.status == "verified":
                return Prepared("status", operation.provider_ref)
            return Prepared("unknown")
        return Prepared(operation.status)


async def _finalize(engine, workspace_id: uuid.UUID, operation_id: uuid.UUID,
                    intent: ProviderIntent, outbox_intent_key: str, generation: int,
                    result: SubmissionResult | StatusResult) -> str:
    async with tenant_session(engine, workspace_id) as session:
        outbox = (await session.execute(select(OutboxEvent).where(
            OutboxEvent.workspace_id == workspace_id,
            OutboxEvent.intent_key == outbox_intent_key,
        ).with_for_update())).scalar_one_or_none()
        if outbox is None or outbox.state != "dispatched" or outbox.fencing_generation != generation:
            return "stale"
        operation = (await session.execute(select(ProviderOperation).where(
            ProviderOperation.workspace_id == workspace_id, ProviderOperation.id == operation_id
        ).with_for_update())).scalar_one_or_none()
        if operation is None or operation.intent_key != intent.key:
            return "blocked"
        # Rejection alone is not authoritative no-charge evidence.
        state = "unknown" if result.state == "rejected" else result.state
        operation.status = state
        if result.provider_ref:
            operation.provider_ref = result.provider_ref
        if outbox_intent_key == intent.key:
            await _queue_reconciliation(session, outbox, operation_id, intent)
        elif state in {"succeeded", "failed", "not_found"}:
            outbox.state = "done"
            outbox.lease_owner = None
            outbox.lease_expires_at = None
        # Reconciliation stays leased while the outcome is unresolved. The
        # reservation is held until separate authoritative settlement.
        return state


async def execute_external(engine, workspace_id: uuid.UUID, operation_id: uuid.UUID,
                           generation: int, adapter: ProviderAdapter,
                           intent: ProviderIntent, *, environment: str = "production",
                           outbox_intent_key: str | None = None) -> str:
    """Never keep a DB transaction open across the external await."""
    if adapter.capability.service != intent.service:
        return "capability_blocked"
    if activation_blockers(adapter.capability, market=intent.market, language=intent.language,
                           role=intent.role, environment=environment):
        return "capability_blocked"
    key = outbox_intent_key or intent.key
    if key not in {intent.key, reconcile_intent_key(operation_id)}:
        return "blocked"
    prepared = await _prepare(engine, workspace_id, operation_id, generation, adapter, intent, key)
    if prepared.action not in {"submit", "status"}:
        return prepared.action
    try:
        if prepared.action == "submit":
            result = await asyncio.wait_for(adapter.submit(intent), timeout=45)
        else:
            assert prepared.provider_ref is not None
            result = await asyncio.wait_for(adapter.status(prepared.provider_ref), timeout=45)
    except Exception:
        result = SubmissionResult("unknown", prepared.provider_ref)
    return await _finalize(engine, workspace_id, operation_id, intent, key, generation, result)
