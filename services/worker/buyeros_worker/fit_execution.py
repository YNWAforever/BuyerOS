"""Consume one durable run.fit intent through the tenant-scoped LangGraph."""

import uuid

from sqlalchemy import select

from buyeros_api.db.buyers import FitAssessment, ProjectBuyer
from buyeros_api.db.outbox import OutboxEvent
from buyeros_api.db.runs import RawCandidate, SearchRun
from buyeros_api.db.session import tenant_session

from .checkpoints import open_checkpoint_saver
from .fit_runner import FitDomainRunner
from .leases import fence_ok
from .research_graph import build_research_graph, checkpoint_config
from .run_emitter import emit_run_event


async def _partial(engine, workspace_id, intent_key, generation, reason: str) -> str:
    async with tenant_session(engine, workspace_id) as session:
        event = (await session.execute(select(OutboxEvent).where(
            OutboxEvent.workspace_id == workspace_id,
            OutboxEvent.intent_key == intent_key,
        ).with_for_update())).scalar_one_or_none()
        if event is None or event.state != "dispatched" or not fence_ok(generation, event.fencing_generation):
            return "stale"
        run_id = uuid.UUID(event.payload["run_id"])
        run = (await session.execute(select(SearchRun).where(
            SearchRun.workspace_id == workspace_id, SearchRun.id == run_id,
        ).with_for_update())).scalar_one()
        if run.status == "cancel_requested":
            event.state = "done"
            event.lease_owner = None
            event.lease_expires_at = None
            return "cancel_requested"
        run.status = "partial"
        run.stage = "fit_review_required"
        run.terminal_reason = reason
        run.version += 1
        await emit_run_event(session, run.id, "run.partial", payload={"reason": reason})
        event.state = "done"
        event.lease_owner = None
        event.lease_expires_at = None
    return "partial"


async def execute_fit(engine, workspace_id: uuid.UUID, intent_key: str, generation: int,
                      *, checkpoint_dsn: str) -> str:
    """Process bounded buyer IDs; domain rows, not graph checkpoints, remain truth."""
    async with tenant_session(engine, workspace_id) as session:
        event = (await session.execute(select(OutboxEvent).where(
            OutboxEvent.workspace_id == workspace_id,
            OutboxEvent.intent_key == intent_key,
        ).with_for_update())).scalar_one_or_none()
        if event is None:
            return "unknown_intent"
        if event.state in {"done", "failed"}:
            return "duplicate"
        if event.state != "dispatched" or not fence_ok(generation, event.fencing_generation):
            return "stale"
        if event.event_type != "run.fit" or not isinstance(event.payload, dict):
            return "invalid_intent"
        try:
            run_id = uuid.UUID(event.payload["run_id"])
        except (KeyError, TypeError, ValueError):
            return "invalid_intent"
        run = (await session.execute(select(SearchRun).where(
            SearchRun.workspace_id == workspace_id, SearchRun.id == run_id,
        ))).scalar_one_or_none()
        if run is None or run.status not in {"queued", "running"} or run.stage != "fit":
            return "invalid_run"
        buyer_ids = (await session.execute(select(ProjectBuyer.id).join(
            RawCandidate,
            (RawCandidate.workspace_id == ProjectBuyer.workspace_id) &
            (RawCandidate.canonical_company_id == ProjectBuyer.company_id) &
            (RawCandidate.run_id == run.id),
        ).where(ProjectBuyer.workspace_id == workspace_id,
                ProjectBuyer.project_id == run.project_id).distinct().order_by(ProjectBuyer.id))).scalars().all()
        if len(buyer_ids) > run.target_companies or len(buyer_ids) > 100:
            return "invalid_target"
        attempt = run.attempt
        if run.status == "queued":
            run.status = "running"
            run.version += 1
            await emit_run_event(session, run.id, "run.started", payload={"stage": "fit"})

    assessment_ids = []
    try:
        async with open_checkpoint_saver(checkpoint_dsn, workspace_id) as saver:
            for buyer_id in buyer_ids:
                runner = FitDomainRunner(engine, workspace_id, run_id, buyer_id)
                graph = build_research_graph(saver, runner)
                config = checkpoint_config(workspace_id, run_id, "fit-v1", attempt, buyer_id)
                initial = {"workspace_id": str(workspace_id), "run_id": str(run_id),
                           "buyer_id": str(buyer_id), "workflow_version": "fit-v1",
                           "attempt": attempt}
                saved = await graph.aget_state(config)
                result = await graph.ainvoke(None if saved.values else initial, config)
                assessment_ids.append(uuid.UUID(result["assessment_id"]))
    except ValueError as exc:
        return await _partial(engine, workspace_id, intent_key, generation, str(exc)[:200])

    async with tenant_session(engine, workspace_id) as session:
        event = (await session.execute(select(OutboxEvent).where(
            OutboxEvent.workspace_id == workspace_id,
            OutboxEvent.intent_key == intent_key,
        ).with_for_update())).scalar_one_or_none()
        if event is None or event.state != "dispatched" or not fence_ok(generation, event.fencing_generation):
            return "stale"
        run = (await session.execute(select(SearchRun).where(
            SearchRun.workspace_id == workspace_id, SearchRun.id == run_id,
        ).with_for_update())).scalar_one()
        if run.status != "running" or run.stage != "fit":
            return "invalid_run"
        if assessment_ids:
            persisted = (await session.execute(select(FitAssessment.id).where(
                FitAssessment.workspace_id == workspace_id,
                FitAssessment.run_id == run_id,
                FitAssessment.id.in_(assessment_ids),
            ))).scalars().all()
            if len(persisted) != len(assessment_ids):
                raise ValueError("fit graph output is not durable")
        await emit_run_event(session, run.id, "run.completed", transition="complete",
                             payload={"fit_assessments": len(assessment_ids),
                                      "next_action": "human_review"})
        run.stage = "review"
        run.version += 1
        event.state = "done"
        event.lease_owner = None
        event.lease_expires_at = None
    return "done"
