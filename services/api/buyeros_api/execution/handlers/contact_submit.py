"""Fixture-first contact job dispatch with one job hold and committed paid intents.

The outbox carries only a job ID. Each buyer intent is committed as submitting
before the provider call. A recovered submitting intent becomes unknown; it is
never submitted again without a vendor-specific verified recovery protocol.
"""

import uuid
import asyncio
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select, text

from buyeros_api.db.budget import BudgetReservation
from buyeros_api.db.buyers import ProjectBuyer
from buyeros_api.db.contact import EnrichmentJob, EnrichmentQuote, ProviderOperation
from buyeros_api.db.icp import Project
from buyeros_api.db.models import Membership
from buyeros_api.api.deps import permission_for_roles
from buyeros_api.db.outbox import OutboxEvent
from ..provider_context import execution_session as tenant_session
from buyeros_api.providers.base import ProviderAdapter, ProviderIntent, activation_blockers
from buyeros_api.services.policy_service import evaluate_current_policy, policy_workspace_lock
from buyeros_api.services.quote_service import quote_hash
from buyeros_api.services.settlement import release_unsubmitted_operation
from buyeros_api.services.contact_result_service import settle_contact_job_if_ready


@dataclass(frozen=True)
class Preparation:
    action: str
    operation_id: uuid.UUID | None = None
    intent: ProviderIntent | None = None


def reconcile_key(operation_id: uuid.UUID) -> str:
    return f"contact.reconcile:{operation_id}"


async def _prepare(engine, workspace_id, job_id, generation, adapter: ProviderAdapter,
                   environment: str) -> Preparation:
    async with tenant_session(engine, workspace_id) as session:
        # Suppression writers use this same transaction-scoped gate. Cancellation
        # and all worker transitions lock the job before any child/outbox row.
        await policy_workspace_lock(session, workspace_id)
        job = (await session.execute(select(EnrichmentJob).where(
            EnrichmentJob.workspace_id == workspace_id, EnrichmentJob.id == job_id,
        ).with_for_update())).scalar_one_or_none()
        if job is None:
            return Preparation("missing")
        quote = (await session.execute(select(EnrichmentQuote).where(
            EnrichmentQuote.workspace_id == workspace_id, EnrichmentQuote.id == job.quote_id,
        ))).scalar_one()
        # Old actorless fixture quotes are historical test data only. Every
        # bounded execution and every production quote needs the admitting actor.
        from ..provider_context import active_execution
        context = active_execution.get()
        bounded = context is not None and hasattr(context, 'finish')
        if quote.actor_id is None:
            if bounded or environment != 'test':
                return Preparation('actor_changed')
        else:
            member = (await session.execute(select(Membership).where(
                Membership.workspace_id == workspace_id, Membership.user_id == quote.actor_id,
                Membership.active.is_(True),
            ))).scalar_one_or_none()
            if member is None or not permission_for_roles(member.roles, 'confirmLookup'):
                return Preparation('actor_changed')
        operations = (await session.execute(select(ProviderOperation).where(
            ProviderOperation.workspace_id == workspace_id, ProviderOperation.job_id == job_id,
        ).order_by(ProviderOperation.id).with_for_update())).scalars().all()
        outbox = (await session.execute(select(OutboxEvent).where(
            OutboxEvent.workspace_id == workspace_id,
            OutboxEvent.intent_key == f"contact.lookup:{job_id}",
        ).with_for_update())).scalar_one_or_none()
        if outbox is None or outbox.state != "dispatched" or outbox.fencing_generation != generation:
            return Preparation("stale")
        if not operations:
            return Preparation("blocked")
        reservation = (await session.execute(select(BudgetReservation).where(
            BudgetReservation.workspace_id == workspace_id,
            BudgetReservation.id == job.reservation_id,
        ))).scalar_one_or_none()
        if reservation is None or reservation.state != "active" or reservation.operation_id != job.id:
            return Preparation("blocked")
        if reservation.upper_bound != quote.max_cost or reservation.price_version != quote.price_version:
            return Preparation("blocked")
        if quote.price_version != adapter.capability.pricing_version or quote.adapter_version != adapter.capability.adapter_version:
            return Preparation("blocked")
        if adapter.capability.service != "contact" or (getattr(adapter, "test_only", False) and environment != "test"):
            return Preparation("blocked")
        project = (await session.execute(select(Project).where(
            Project.workspace_id == workspace_id, Project.id == quote.project_id,
        ))).scalar_one_or_none()
        if project is None or project.status != "active" or not project.markets or not project.language_preferences or not quote.roles:
            return Preparation("blocked")
        market, language, role = project.markets[0], project.language_preferences[0], quote.roles[0]
        if activation_blockers(adapter.capability, market=market, language=language,
                               role=role, environment=environment):
            return Preparation("blocked")
        account_reference = getattr(adapter, "account_reference", None)
        if account_reference is None and environment == "test" and getattr(adapter, "test_only", False):
            account_reference = "fixture-test"
        if not isinstance(account_reference, str) or not account_reference or len(account_reference) > 128:
            return Preparation("blocked")
        if job.cancel_requested:
            undispatched = all(op.status in {"intent", "reserved", "cancelled"} for op in operations)
            for op in operations:
                if op.status in {"intent", "reserved"}:
                    op.status = "cancelled"
                    op.observed_cost = Decimal("0.000000")
                    op.external_event_id = f"not-submitted:{op.id}"
            if undispatched:
                await release_unsubmitted_operation(session, job.id)
                job.state = "cancelled"
            outbox.state = "done"
            return Preparation("cancelled")
        stale = [op for op in operations if op.status == "submitting"]
        if stale:
            # The prior worker may have reached the provider. Its result was
            # never committed, so recovery must not issue another submit.
            for op in stale:
                op.status = "unknown"
            job.state = "unknown"
            job.version += 1
        next_op = next((op for op in operations if op.status in {"intent", "reserved"}), None)
        if next_op is None:
            outbox.state = "done"
            outbox.lease_owner = None
            outbox.lease_expires_at = None
            return Preparation("unknown" if any(op.status == "unknown" for op in operations) else "done")
        basis = next((row for row in (quote.selection or {}).get("resolved", [])
                      if row.get("buyer_id") == str(next_op.buyer_id)), None)
        if not basis or not basis.get("eligible") or basis.get("company_id") is None:
            return Preparation("blocked")
        buyer = (await session.execute(select(ProjectBuyer).where(
            ProjectBuyer.workspace_id == workspace_id, ProjectBuyer.id == next_op.buyer_id,
            ProjectBuyer.project_id == quote.project_id,
        ))).scalar_one_or_none()
        if buyer is None or buyer.version != basis.get("buyer_version") or str(buyer.company_id) != basis["company_id"]:
            return Preparation("blocked")
        policy = await evaluate_current_policy(session, {
            "workspace_id": workspace_id, "project_id": quote.project_id,
            "company_id": buyer.company_id,
        }, "contact_research", datetime.now(timezone.utc))
        if not policy["allowed"]:
            next_op.status = "cancelled"
            next_op.observed_cost = Decimal("0.000000")
            next_op.external_event_id = f"not-submitted:{next_op.id}"
            job.version += 1
            if all(op.status in {"intent", "reserved", "cancelled"} for op in operations):
                await release_unsubmitted_operation(session, job.id)
                job.state = "cancelled"
                outbox.state = "done"
            else:
                await settle_contact_job_if_ready(session, job, operations)
            return Preparation("policy_blocked")
        expected_hash = quote_hash({"quote_hash": quote.quote_hash,
            "buyer_id": str(next_op.buyer_id), "roles": quote.roles,
            "contact_type": quote.contact_type})
        if next_op.input_hash != expected_hash:
            return Preparation("blocked")
        intent = ProviderIntent(next_op.intent_key, "contact", market, language, role)
        next_op.status = "submitting"
        next_op.provider_name = adapter.capability.provider
        next_op.account_reference = account_reference
        job.state = "submitting"
        job.version += 1
        return Preparation("submit", next_op.id, intent)


async def _finalize(engine, workspace_id, job_id, operation_id, generation, result) -> str:
    async with tenant_session(engine, workspace_id) as session:
        job = (await session.execute(select(EnrichmentJob).where(
            EnrichmentJob.workspace_id == workspace_id, EnrichmentJob.id == job_id,
        ).with_for_update())).scalar_one()
        operation = (await session.execute(select(ProviderOperation).where(
            ProviderOperation.workspace_id == workspace_id, ProviderOperation.id == operation_id,
        ).with_for_update())).scalar_one()
        outbox = (await session.execute(select(OutboxEvent).where(
            OutboxEvent.workspace_id == workspace_id,
            OutboxEvent.intent_key == f"contact.lookup:{job_id}",
        ).with_for_update())).scalar_one()
        if outbox.state != "dispatched" or outbox.fencing_generation != generation:
            return "stale"
        if operation.status != "submitting":
            return "stale"
        # Even an explicit reject is not proof of no charge for an unverified
        # vendor. Keep the hold until status/callback evidence closes it.
        operation.status = "accepted" if result.state == "accepted" else "unknown"
        operation.provider_ref = result.provider_ref
        if result.provider_ref:
            await session.flush()
            await session.execute(text("SELECT register_provider_callback_route(:workspace, :operation)"),
                                  {"workspace": workspace_id, "operation": operation.id})
        job.state = "pending" if operation.status == "accepted" else "unknown"
        job.version += 1
        if result.provider_ref:
            session.add(OutboxEvent(
                workspace_id=workspace_id, intent_key=reconcile_key(operation_id),
                event_type="contact.reconcile",
                payload={"workspace_id": str(workspace_id), "job_id": str(job_id),
                         "operation_id": str(operation_id)}, state="ready",
            ))
        from ..provider_context import finish_contact_unit
        await finish_contact_unit(session, job_id, operation.status)
        return operation.status


async def execute_contact_lookup(engine, workspace_id: uuid.UUID, job_id: uuid.UUID,
                                 generation: int, adapter: ProviderAdapter,
                                 *, environment: str = "production", max_operations: int | None = None) -> str:
    if max_operations not in {None, 1}:
        raise ValueError("bounded contact execution requires one operation")
    observed = []
    while True:
        prepared = await _prepare(engine, workspace_id, job_id, generation, adapter, environment)
        if prepared.action != "submit":
            if prepared.action == "done" and observed:
                return "unknown" if "unknown" in observed else "accepted"
            return prepared.action
        try:
            result = await asyncio.wait_for(adapter.submit(prepared.intent), timeout=45)
        except Exception:
            # A timeout, reset or process crash has indeterminate acceptance.
            # Committed submitting is recovered as unknown by the next worker.
            result = None
        if result is None:
            if max_operations == 1:
                from buyeros_api.providers.base import SubmissionResult
                return await _finalize(engine, workspace_id, job_id, prepared.operation_id,
                                       generation, SubmissionResult("unknown", None))
            observed.append("unknown")
            # Re-enter prepare to mark the committed submitting intent unknown.
            continue
        observed.append(await _finalize(engine, workspace_id, job_id,
                                        prepared.operation_id, generation, result))
        if max_operations == 1:
            return observed[-1]
