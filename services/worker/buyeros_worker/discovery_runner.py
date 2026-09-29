"""One bounded discovery query: prepare -> adapter await -> fenced finalize.

Only the explicit fixture adapter path is active. A production search adapter
must be selected and verified before this runner may make an external request.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import re
import uuid

from sqlalchemy import func, select

from buyeros_api.api.deps import permission_for_roles
from buyeros_api.api.errors import ApiError
from buyeros_api.db.buyers import SourceDocument
from buyeros_api.db.contact import ProviderOperation
from buyeros_api.db.icp import IcpVersion, Project
from buyeros_api.db.models import Membership
from buyeros_api.db.outbox import OutboxEvent
from buyeros_api.db.runs import RawCandidate, SearchRun
from buyeros_api.db.session import tenant_session
from buyeros_api.services.budget_service import reserve_operation
from buyeros_api.services.evidence_service import persist_candidate_evidence
from buyeros_api.services.outbox_service import build_intent
from buyeros_api.services.policy_service import evaluate_current_policy
from buyeros_api.services.run_usage import UsageExceeded, advance_usage
from buyeros_api.services.settlement import settle_operation
from buyeros_api.services.canonicalize import normalize_source_url

from .leases import fence_ok
from .run_emitter import emit_run_event


@dataclass(frozen=True)
class DiscoveryBatch:
    hits: list[dict]
    charge: Decimal
    billing_event_id: str


@dataclass(frozen=True)
class PreparedQuery:
    action: str
    run_id: uuid.UUID | None = None
    operation_id: uuid.UUID | None = None
    query: dict | None = None
    intent_key: str | None = None
    limit: int = 0


async def _prepare(engine, workspace_id, outbox_intent, generation, adapter) -> PreparedQuery:
    async with tenant_session(engine, workspace_id) as session:
        event = (await session.execute(select(OutboxEvent).where(
            OutboxEvent.workspace_id == workspace_id,
            OutboxEvent.intent_key == outbox_intent,
        ).with_for_update())).scalar_one_or_none()
        if event is None:
            return PreparedQuery("unknown_intent")
        if event.state in {"done", "failed"}:
            return PreparedQuery("duplicate")
        if event.state != "dispatched" or not fence_ok(generation, event.fencing_generation):
            return PreparedQuery("stale")
        if event.event_type != "run.discover" or not isinstance(event.payload, dict):
            return PreparedQuery("invalid_intent")
        try:
            run_id = uuid.UUID(event.payload["run_id"])
            query_index = event.payload.get("query_index", 0)
            if isinstance(query_index, bool) or not isinstance(query_index, int) or query_index < 0:
                raise ValueError("invalid index")
        except (KeyError, ValueError, TypeError):
            return PreparedQuery("invalid_intent")
        run = (await session.execute(select(SearchRun).where(
            SearchRun.workspace_id == workspace_id, SearchRun.id == run_id,
        ).with_for_update())).scalar_one_or_none()
        if run is None or run.status not in {"queued", "running"}:
            return PreparedQuery("invalid_run")
        snapshot = run.execution_snapshot or {}
        capability = snapshot.get("capability") or {}
        plan = snapshot.get("query_plan") or {}
        queries = plan.get("queries") if plan.get("schema") == "query-plan.v1" else None
        if (capability.get("provider") != "fixture" or
                capability.get("price_version") != adapter.price_version or
                not isinstance(queries, list) or query_index >= len(queries) or
                query_index != (run.usage_counters or {}).get("queries", 0)):
            return PreparedQuery("invalid_plan")
        query = queries[query_index]
        if (not isinstance(query, dict) or
                not re.fullmatch(r"[0-9a-f]{24}", str(query.get("id", ""))) or
                query.get("market") not in capability.get("markets", []) or
                query.get("language") not in capability.get("languages", []) or
                not {"market", "language"}.issubset(set(capability.get("verified_filters", []))) or
                query.get("filters") != {"market": query.get("market"), "language": query.get("language")}):
            return PreparedQuery("invalid_plan")
        project = (await session.execute(select(Project).where(
            Project.workspace_id == workspace_id, Project.id == run.project_id,
        ))).scalar_one_or_none()
        icp = (await session.execute(select(IcpVersion).where(
            IcpVersion.workspace_id == workspace_id, IcpVersion.project_id == run.project_id,
            IcpVersion.id == run.icp_version_id,
        ))).scalar_one_or_none()
        if (project is None or icp is None or project.status != "active" or
                project.active_icp_version_id != icp.id or icp.approved_at is None or
                icp.superseded_at is not None or icp.content_hash != snapshot.get("icp_content_hash") or
                project.offer_revision != snapshot.get("offer_revision")):
            return PreparedQuery("stale_profile")
        try:
            actor_id = uuid.UUID(snapshot["actor_id"])
        except (KeyError, ValueError, TypeError):
            return PreparedQuery("invalid_actor")
        member = (await session.execute(select(Membership).where(
            Membership.workspace_id == workspace_id, Membership.user_id == actor_id,
            Membership.active.is_(True),
        ))).scalar_one_or_none()
        if member is None or not permission_for_roles(member.roles, "startRun"):
            return PreparedQuery("actor_revoked")
        policy = await evaluate_current_policy(session, {
            "workspace_id": workspace_id, "project_id": run.project_id,
        }, "account_research", datetime.now(timezone.utc))
        if not policy["allowed"]:
            return PreparedQuery("policy_blocked")
        round_number = query.get("round")
        current_round = (run.usage_counters or {}).get("rounds", 0)
        if (isinstance(round_number, bool) or not isinstance(round_number, int) or
                round_number < 1 or round_number > run.limits["query_rounds"] or
                round_number < current_round or round_number > current_round + 1):
            return PreparedQuery("invalid_plan")
        intent_key = f"research:{run_id}:{query['id']}"
        existing = (await session.execute(select(ProviderOperation).where(
            ProviderOperation.workspace_id == workspace_id,
            ProviderOperation.intent_key == intent_key,
        ))).scalar_one_or_none()
        if existing is not None:
            # A crash after committing 'submitting' has unknown acceptance. Never
            # resubmit without an authoritative status check.
            return PreparedQuery("unknown", run.id, existing.id, query, intent_key)
        operation_id = uuid.uuid5(uuid.NAMESPACE_URL, intent_key)
        bound = adapter.quoted_upper_bound
        if not isinstance(bound, Decimal) or bound <= 0 or bound > run.max_cost:
            return PreparedQuery("invalid_tariff")
        remaining = max(0, run.limits["max_results"] - (run.usage_counters or {}).get("raw_results", 0))
        if remaining == 0:
            return PreparedQuery("limit_reached")
        await reserve_operation(session, operation_id, {
            "workspace_id": workspace_id, "project_id": run.project_id,
            "run_id": run.id, "category": "discovery",
        }, bound, "USD", adapter.price_version)
        try:
            advance_usage(run, {"queries": 1, "pages": 1, "in_flight": 1,
                                "rounds": round_number - current_round},
                          at=datetime.now(timezone.utc), page_bytes=0)
        except UsageExceeded:
            # The outer tenant transaction rolls back the just-created hold.
            raise
        digest = hashlib.sha256(json.dumps(query, sort_keys=True,
            separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        session.add(ProviderOperation(
            id=operation_id, workspace_id=workspace_id, intent_key=intent_key,
            capability="account_search", input_hash=digest, status="submitting",
        ))
        if query_index == 0:
            await emit_run_event(session, run.id, "run.started", transition="start",
                                 payload={"query_id": query["id"]})
        run.stage = "discovery"
        run.version += 1
        await session.flush()
        return PreparedQuery("submit", run.id, operation_id, query, intent_key, remaining)


async def _halt_before_dispatch(engine, workspace_id, outbox_intent, generation,
                                *, status: str, reason: str) -> str:
    """Record a pre-call denial in a fresh transaction after the failed prepare rolls back."""
    async with tenant_session(engine, workspace_id) as session:
        event = (await session.execute(select(OutboxEvent).where(
            OutboxEvent.workspace_id == workspace_id, OutboxEvent.intent_key == outbox_intent,
        ).with_for_update())).scalar_one_or_none()
        if event is None or event.state != "dispatched" or not fence_ok(generation, event.fencing_generation):
            return "stale"
        try:
            run_id = uuid.UUID(event.payload["run_id"])
        except (KeyError, ValueError, TypeError):
            event.state = "failed"
            return "invalid_intent"
        run = (await session.execute(select(SearchRun).where(
            SearchRun.workspace_id == workspace_id, SearchRun.id == run_id,
        ).with_for_update())).scalar_one_or_none()
        if run is not None:
            run.status = status
            run.stage = status
            run.terminal_reason = reason
            run.version += 1
            event_type = {"paused_budget": "budget.paused", "failed": "run.failed"}.get(
                status, "run.partial")
            await emit_run_event(session, run.id, event_type, payload={"reason": reason})
        event.state = "done"
        event.lease_owner = None
        event.lease_expires_at = None
    return status


async def _mark_dispatch(engine, workspace_id, prepared, outbox_intent, generation) -> bool:
    async with tenant_session(engine, workspace_id) as session:
        event = (await session.execute(select(OutboxEvent).where(
            OutboxEvent.workspace_id == workspace_id, OutboxEvent.intent_key == outbox_intent,
        ).with_for_update())).scalar_one_or_none()
        if event is None or event.state != "dispatched" or not fence_ok(generation, event.fencing_generation):
            return False
        run = (await session.execute(select(SearchRun).where(
            SearchRun.workspace_id == workspace_id, SearchRun.id == prepared.run_id,
        ).with_for_update())).scalar_one()
        advance_usage(run, {"in_flight": 0}, at=datetime.now(timezone.utc), external=True)
        return True


async def _mark_unknown(engine, workspace_id, prepared, outbox_intent, generation, reason) -> str:
    async with tenant_session(engine, workspace_id) as session:
        event = (await session.execute(select(OutboxEvent).where(
            OutboxEvent.workspace_id == workspace_id, OutboxEvent.intent_key == outbox_intent,
        ).with_for_update())).scalar_one_or_none()
        if event is None or event.state != "dispatched" or not fence_ok(generation, event.fencing_generation):
            return "stale"
        run = (await session.execute(select(SearchRun).where(
            SearchRun.workspace_id == workspace_id, SearchRun.id == prepared.run_id,
        ).with_for_update())).scalar_one()
        operation = (await session.execute(select(ProviderOperation).where(
            ProviderOperation.workspace_id == workspace_id,
            ProviderOperation.id == prepared.operation_id,
        ).with_for_update())).scalar_one()
        operation.status = "unknown"
        cancelling = run.status == "cancel_requested"
        run.status = "cancel_requested" if cancelling else "partial"
        run.stage = "reconciling_cancellation" if cancelling else "reconciliation_required"
        run.terminal_reason = reason
        run.version += 1
        await emit_run_event(session, run.id, "run.partial",
                             payload={"reason": reason, "query_id": prepared.query["id"]})
        if event.event_type == "run.discover":
            reconcile_key = f"research:reconcile:{operation.id}"
            existing_reconcile = (await session.execute(select(OutboxEvent.id).where(
                OutboxEvent.workspace_id == workspace_id,
                OutboxEvent.intent_key == reconcile_key,
            ))).scalar_one_or_none()
            if existing_reconcile is None:
                session.add(OutboxEvent(
                    workspace_id=workspace_id, intent_key=reconcile_key,
                    event_type="research.reconcile",
                    payload={"run_id": str(run.id), "operation_id": str(operation.id),
                             "query_id": prepared.query["id"]},
                ))
        event.state = "done"
        event.lease_owner = None
        event.lease_expires_at = None
    return "unknown"


async def _finalize(engine, workspace_id, prepared, outbox_intent, generation,
                    batch: DiscoveryBatch, adapter) -> str:
    if (not isinstance(batch, DiscoveryBatch) or not isinstance(batch.hits, list) or
            not isinstance(batch.charge, Decimal) or batch.charge < 0 or
            batch.charge > adapter.quoted_upper_bound or
            not batch.billing_event_id or len(batch.billing_event_id) > 200 or
            len(batch.hits) > prepared.limit):
        return await _mark_unknown(engine, workspace_id, prepared, outbox_intent,
                                   generation, "invalid_provider_result")
    async with tenant_session(engine, workspace_id) as session:
        event = (await session.execute(select(OutboxEvent).where(
            OutboxEvent.workspace_id == workspace_id, OutboxEvent.intent_key == outbox_intent,
        ).with_for_update())).scalar_one_or_none()
        if event is None or event.state != "dispatched" or not fence_ok(generation, event.fencing_generation):
            return "stale"
        run = (await session.execute(select(SearchRun).where(
            SearchRun.workspace_id == workspace_id, SearchRun.id == prepared.run_id,
        ).with_for_update())).scalar_one()
        operation = (await session.execute(select(ProviderOperation).where(
            ProviderOperation.workspace_id == workspace_id,
            ProviderOperation.id == prepared.operation_id,
        ).with_for_update())).scalar_one()
        if operation.status not in ({"submitting"} if event.event_type == "run.discover"
                                    else {"unknown"}):
            return "stale"
        try:
            advance_usage(run, {"raw_results": len(batch.hits),
                                "in_flight": -1}, at=datetime.now(timezone.utc))
        except UsageExceeded:
            # Billable response is known, so settle it, but persist no over-cap rows.
            await settle_operation(session, operation.id, batch.charge, batch.billing_event_id)
            operation.status = "settled"
            run.status = "partial"
            run.stage = "limit_reached"
            run.terminal_reason = "provider_result_exceeded_limits"
            run.version += 1
            await emit_run_event(session, run.id, "run.partial",
                payload={"reason": run.terminal_reason, "returned": len(batch.hits)})
            event.state = "done"
            return "partial"
        decoded_bytes = sum(len(hit["excerpt"].encode("utf-8")) for hit in batch.hits)
        if decoded_bytes > run.limits["max_page_bytes"]:
            await settle_operation(session, operation.id, batch.charge, batch.billing_event_id)
            operation.status = "settled"
            run.status = "partial"
            run.stage = "limit_reached"
            run.terminal_reason = "decoded_page_bytes_exceeded_limit"
            run.version += 1
            await emit_run_event(session, run.id, "run.partial",
                payload={"reason": run.terminal_reason, "decoded_bytes": decoded_bytes})
            event.state = "done"
            event.lease_owner = None
            event.lease_expires_at = None
            return "partial"
        operation.status = "accepted"
        # Permission and exact ICP/actor context may change during the external await.
        project = (await session.execute(select(Project).where(
            Project.workspace_id == workspace_id, Project.id == run.project_id,
        ))).scalar_one_or_none()
        icp = (await session.execute(select(IcpVersion).where(
            IcpVersion.workspace_id == workspace_id, IcpVersion.project_id == run.project_id,
            IcpVersion.id == run.icp_version_id,
        ))).scalar_one_or_none()
        actor_id = uuid.UUID(run.execution_snapshot["actor_id"])
        member = (await session.execute(select(Membership).where(
            Membership.workspace_id == workspace_id, Membership.user_id == actor_id,
            Membership.active.is_(True),
        ))).scalar_one_or_none()
        policy = await evaluate_current_policy(session, {
            "workspace_id": workspace_id, "project_id": run.project_id,
        }, "account_research", datetime.now(timezone.utc))
        if (project is None or project.status != "active" or icp is None or
                project.active_icp_version_id != icp.id or icp.approved_at is None or
                icp.superseded_at is not None or
                icp.content_hash != run.execution_snapshot.get("icp_content_hash") or
                project.offer_revision != run.execution_snapshot.get("offer_revision") or
                member is None or not permission_for_roles(member.roles, "startRun") or
                not policy["allowed"]):
            await settle_operation(session, operation.id, batch.charge, batch.billing_event_id)
            operation.status = "settled"
            run.status = "partial"
            run.stage = "policy_recheck_failed"
            run.terminal_reason = "policy_or_context_changed_during_search"
            run.version += 1
            await emit_run_event(session, run.id, "run.partial",
                payload={"reason": run.terminal_reason})
            event.state = "done"
            event.lease_owner = None
            event.lease_expires_at = None
            return "partial"
        for hit in batch.hits:
            if not isinstance(hit, dict):
                raise ValueError("invalid search hit")
            url = normalize_source_url(hit.get("url"))
            excerpt = hit.get("excerpt")
            legal_name = hit.get("legal_name")
            if (not isinstance(excerpt, str) or not excerpt.strip() or len(excerpt) > 4000 or
                    not isinstance(legal_name, str) or not legal_name.strip() or len(legal_name) > 400):
                raise ValueError("invalid source excerpt or legal name")
            source = SourceDocument(
                workspace_id=workspace_id, project_id=run.project_id, run_id=run.id,
                permission_purpose="account_research", canonical_url=url,
                digest=hashlib.sha256(excerpt.encode()).hexdigest(),
                retrieved_at=datetime.now(timezone.utc), language=hit.get("language", "und"),
                storage_mode="excerpt_only", excerpt=excerpt,
                retention_until=datetime.now(timezone.utc) + timedelta(seconds=adapter.retention_seconds),
            )
            session.add(source)
            await session.flush()
            await persist_candidate_evidence(
                session, run.id, operation.id,
                {"source_url": url, "legal_name": legal_name,
                 "registry_id": hit.get("registry_id"),
                 "external_ref": hit.get("external_ref")},
                [{"source_document_id": str(source.id), "excerpt": excerpt,
                  "stance": "supports", "requirement_id": prepared.query["requirement_id"],
                  "is_inference": False}],
            )
        unique_companies = (await session.execute(select(
            func.count(func.distinct(RawCandidate.canonical_company_id))
        ).where(RawCandidate.workspace_id == workspace_id, RawCandidate.run_id == run.id,
                RawCandidate.canonical_company_id.is_not(None)))).scalar_one()
        previous_companies = (run.usage_counters or {}).get("companies", 0)
        if unique_companies < previous_companies:
            raise ValueError("persisted company count exceeds canonical run state")
        advance_usage(run, {"companies": unique_companies - previous_companies},
                      at=datetime.now(timezone.utc))
        await settle_operation(session, operation.id, batch.charge, batch.billing_event_id)
        operation.status = "settled"
        # An authoritative status lookup may resolve an earlier partial run.
        # Resume the same logical run and preserve its cumulative usage.
        if run.status == "partial":
            await emit_run_event(session, run.id, "run.resumed", transition="resume",
                                 payload={"query_id": prepared.query["id"]})
        if run.status == "cancel_requested":
            run.status = "cancelled"
            run.stage = "cancelled"
            run.version += 1
            await emit_run_event(session, run.id, "run.cancelled",
                                 payload={"reason": "verified_provider_result_after_cancel"})
            event.state = "done"
            event.lease_owner = None
            event.lease_expires_at = None
            return "cancelled"
        plan = run.execution_snapshot["query_plan"]["queries"]
        next_index = run.usage_counters["queries"]
        if next_index < len(plan) and run.usage_counters["companies"] < run.target_companies:
            payload = {"run_id": str(run.id), "query_index": next_index}
            session.add(OutboxEvent(workspace_id=workspace_id,
                intent_key=build_intent("run.discover", payload, next_index),
                event_type="run.discover", payload=payload))
            await emit_run_event(session, run.id, "node.committed",
                payload={"query_id": prepared.query["id"], "next_query_index": next_index})
        else:
            payload = {"run_id": str(run.id)}
            session.add(OutboxEvent(workspace_id=workspace_id,
                intent_key=build_intent("run.fit", payload, run.attempt),
                event_type="run.fit", payload=payload))
            await emit_run_event(session, run.id, "node.committed",
                payload={"query_id": prepared.query["id"], "next_stage": "fit"})
            run.stage = "fit"
        run.version += 1
        event.state = "done"
        event.lease_owner = None
        event.lease_expires_at = None
    return "done"


async def execute_discovery(engine, workspace_id: uuid.UUID, outbox_intent: str,
                            generation: int, *, adapter=None,
                            environment: str = "production") -> str:
    """Execute one query with no DB transaction held across the adapter await."""
    if (environment != "test" or adapter is None or
            getattr(adapter, "test_only", False) is not True or
            getattr(adapter, "provider", None) != "fixture"):
        return "provider_unavailable"
    try:
        prepared = await _prepare(engine, workspace_id, outbox_intent, generation, adapter)
    except ApiError as exc:
        if exc.code == "BUDGET_LIMIT":
            return await _halt_before_dispatch(engine, workspace_id, outbox_intent,
                generation, status="paused_budget", reason="approved_budget_exhausted")
        raise
    except UsageExceeded:
        return await _halt_before_dispatch(engine, workspace_id, outbox_intent,
            generation, status="partial", reason="run_limit_reached")
    if prepared.action == "unknown" and prepared.operation_id is not None:
        return await _mark_unknown(engine, workspace_id, prepared, outbox_intent,
                                   generation, "previous_submission_unverified")
    if prepared.action in {"invalid_intent", "invalid_run", "invalid_plan",
                           "stale_profile", "invalid_actor", "actor_revoked",
                           "policy_blocked", "invalid_tariff", "limit_reached"}:
        return await _halt_before_dispatch(engine, workspace_id, outbox_intent,
            generation, status="partial" if prepared.action == "limit_reached" else "failed",
            reason=prepared.action)
    if prepared.action != "submit":
        return prepared.action
    if not await _mark_dispatch(engine, workspace_id, prepared, outbox_intent, generation):
        return "stale"
    try:
        batch = await adapter.search(
            prepared.query["query"], market=prepared.query["market"],
            language=prepared.query["language"], limit=prepared.limit,
            intent_key=prepared.intent_key,
        )
    except Exception:
        # A timeout is not proof of non-acceptance. Keep the full reservation.
        return await _mark_unknown(engine, workspace_id, prepared, outbox_intent,
                                   generation, "provider_acceptance_unknown")
    try:
        return await _finalize(engine, workspace_id, prepared, outbox_intent,
                               generation, batch, adapter)
    except Exception:
        # Finalization rolled back: acceptance/cost are uncertain, so retain the
        # full hold and make the run visibly partial for reconciliation.
        return await _mark_unknown(engine, workspace_id, prepared, outbox_intent,
                                   generation, "finalization_unverified")


async def execute_discovery_reconcile(engine, workspace_id: uuid.UUID,
                                      reconcile_intent: str, generation: int, *,
                                      adapter=None, environment: str = "production") -> str:
    """Status lookup for the original intent only; never calls search again."""
    if (environment != "test" or adapter is None or
            getattr(adapter, "test_only", False) is not True or
            getattr(adapter, "provider", None) != "fixture" or
            not callable(getattr(adapter, "status", None))):
        return "provider_unavailable"
    async with tenant_session(engine, workspace_id) as session:
        event = (await session.execute(select(OutboxEvent).where(
            OutboxEvent.workspace_id == workspace_id,
            OutboxEvent.intent_key == reconcile_intent,
        ).with_for_update())).scalar_one_or_none()
        if event is None:
            return "unknown_intent"
        if event.state in {"done", "failed"}:
            return "duplicate"
        if event.state != "dispatched" or not fence_ok(generation, event.fencing_generation):
            return "stale"
        if event.event_type != "research.reconcile" or not isinstance(event.payload, dict):
            return "invalid_intent"
        try:
            run_id = uuid.UUID(event.payload["run_id"])
            operation_id = uuid.UUID(event.payload["operation_id"])
            query_id = event.payload["query_id"]
        except (KeyError, ValueError, TypeError):
            return "invalid_intent"
        run = (await session.execute(select(SearchRun).where(
            SearchRun.workspace_id == workspace_id, SearchRun.id == run_id,
        ))).scalar_one_or_none()
        operation = (await session.execute(select(ProviderOperation).where(
            ProviderOperation.workspace_id == workspace_id,
            ProviderOperation.id == operation_id,
        ))).scalar_one_or_none()
        if (run is None or operation is None or operation.status != "unknown" or
                operation.intent_key != f"research:{run_id}:{query_id}" or
                run.execution_snapshot.get("capability", {}).get("price_version") != adapter.price_version):
            return "invalid_operation"
        queries = run.execution_snapshot.get("query_plan", {}).get("queries", [])
        query = next((item for item in queries if item.get("id") == query_id), None)
        if query is None:
            return "invalid_plan"
        prepared = PreparedQuery("status", run.id, operation.id, query, operation.intent_key,
            max(0, run.limits["max_results"] - (run.usage_counters or {}).get("raw_results", 0)))
    try:
        batch = await adapter.status(prepared.intent_key)
    except Exception:
        batch = None
    if batch is None:
        async with tenant_session(engine, workspace_id) as session:
            event = (await session.execute(select(OutboxEvent).where(
                OutboxEvent.workspace_id == workspace_id,
                OutboxEvent.intent_key == reconcile_intent,
            ).with_for_update())).scalar_one_or_none()
            if event is None or event.state != "dispatched" or not fence_ok(generation, event.fencing_generation):
                return "stale"
            event.attempts += 1
            event.state = "failed" if event.attempts >= 3 else "ready"
            event.lease_owner = None
            event.lease_expires_at = None
        return "manual_review" if event.attempts >= 3 else "pending"
    try:
        return await _finalize(engine, workspace_id, prepared, reconcile_intent,
                               generation, batch, adapter)
    except Exception:
        # An ambiguous finalize never releases the original reservation.
        return await _mark_unknown(engine, workspace_id, prepared, reconcile_intent,
                                   generation, "reconciliation_finalize_unverified")
