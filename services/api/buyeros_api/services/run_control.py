"""Safe run cancellation and bounded retry within one domain transaction."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from ..api.errors import ApiError
from ..api.deps import permission_for_roles
from ..db.contact import ProviderOperation
from ..db.icp import IcpVersion, Project, canonical_hash
from ..db.models import Membership
from .policy_service import evaluate_current_policy
from ..db.outbox import OutboxEvent
from ..db.worker_execution import WorkerRuntimeControl
from ..db.runs import SearchRun
from .outbox_service import build_intent
from .run_events import append_event, require_run


async def cancel_run(session, workspace_id: uuid.UUID, run_id: uuid.UUID, reason: str,
                     *, expected_version: int) -> SearchRun:
    # Worker lock order is outbox -> run. Follow it so a dispatch cannot slip
    # between proving a ready intent and committing cancellation.
    events = (await session.execute(select(OutboxEvent).where(
        OutboxEvent.workspace_id == workspace_id,
        OutboxEvent.payload["run_id"].astext == str(run_id),
    ).order_by(OutboxEvent.id).with_for_update())).scalars().all()
    run = await require_run(session, workspace_id, run_id, lock=True)
    if run.version != expected_version:
        raise ApiError(412, "STALE_REVISION", "run version changed")
    if run.status in {"completed", "cancelled"}:
        raise ApiError(409, "INVALID_STATE", "terminal run cannot be cancelled")
    if run.status == "cancel_requested":
        return run
    prior_status = run.status
    for event in events:
        if event.state == "ready" and event.event_type != "research.reconcile":
            event.state = "done"
    unresolved = (await session.execute(select(ProviderOperation.id).where(
        ProviderOperation.workspace_id == workspace_id,
        ProviderOperation.intent_key.like(f"research:{run_id}:%"),
        ProviderOperation.status.in_(["submitting", "unknown", "accepted"]),
    ).limit(1))).scalar_one_or_none()
    dispatched = any(event.state == "dispatched" for event in events)
    proven_undispatched = prior_status == "queued" and not dispatched and unresolved is None
    run.status = "cancelled" if proven_undispatched else "cancel_requested"
    run.stage = "cancelled" if proven_undispatched else "reconciling_cancellation"
    run.version += 1
    await append_event(session, run, "run.cancelled" if proven_undispatched else "run.cancel_requested",
                       payload={"reason": reason, "version": run.version, "stage": run.stage,
                                "company_count": (run.usage_counters or {}).get("companies", 0),
                                "raw_count": run.raw_result_count})
    return run


async def retry_run(session, workspace_id: uuid.UUID, run_id: uuid.UUID, reason: str,
                    *, expected_version: int) -> SearchRun:
    """Resume only a fit checkpoint whose provider work has fully settled.

    Discovery failures need a per-query settlement proof and a stable resume
    cursor before requeueing. Until then the API rejects them rather than
    buying the same unknown provider operation again.
    """
    run = await require_run(session, workspace_id, run_id, lock=True)
    if run.version != expected_version:
        raise ApiError(412, "STALE_REVISION", "run version changed")
    if run.status not in {"failed", "partial", "paused_budget"}:
        raise ApiError(409, "INVALID_STATE", "run is not retryable")
    if run.stage not in {"fit_review_required", "fit"}:
        raise ApiError(409, "RETRY_UNSAFE", "discovery resume needs authoritative reconciliation")
    runtime = await _retry_preconditions(session, run)
    run.attempt += 1
    run.version += 1
    run.status = "queued"
    run.stage = "fit"
    run.terminal_reason = None
    payload = {"run_id": str(run.id)}
    session.add(OutboxEvent(workspace_id=workspace_id,
                            intent_key=build_intent("run.fit", payload, run.attempt),
                            event_type="run.fit", payload=payload,
                            runtime_backend=runtime.backend, runtime_epoch=runtime.epoch))
    await append_event(session, run, "run.queued", payload={
        "reason": reason, "version": run.version, "stage": run.stage,
        "company_count": (run.usage_counters or {}).get("companies", 0),
        "raw_count": run.raw_result_count,
    })
    return run


async def _retry_preconditions(session, run):
    """Shared read-only basis; retry_run holds the existing run lock."""
    workspace_id, run_id = run.workspace_id, run.id
    project = (await session.execute(select(Project).where(
        Project.workspace_id == workspace_id, Project.id == run.project_id,
    ))).scalar_one_or_none()
    icp = (await session.execute(select(IcpVersion).where(
        IcpVersion.workspace_id == workspace_id, IcpVersion.project_id == run.project_id,
        IcpVersion.id == run.icp_version_id,
    ))).scalar_one_or_none()
    snapshot = run.execution_snapshot or {}
    if (project is None or project.status != "active" or icp is None or
            project.active_icp_version_id != icp.id or icp.approved_at is None or
            icp.superseded_at is not None or icp.content_hash != canonical_hash(icp.content) or
            icp.content_hash != snapshot.get("icp_content_hash") or
            project.offer_revision != snapshot.get("offer_revision")):
        raise ApiError(412, "STALE_REVISION", "run profile basis changed")
    try:
        actor_id = uuid.UUID(snapshot["actor_id"])
    except (KeyError, ValueError, TypeError) as exc:
        raise ApiError(409, "RETRY_UNSAFE", "original run actor is absent") from exc
    actor = (await session.execute(select(Membership).where(
        Membership.workspace_id == workspace_id, Membership.user_id == actor_id,
        Membership.active.is_(True),
    ))).scalar_one_or_none()
    if actor is None or not permission_for_roles(actor.roles, "startRun"):
        raise ApiError(409, "RETRY_UNSAFE", "original run actor is no longer authorized")
    policy = await evaluate_current_policy(session, {
        "workspace_id": workspace_id, "project_id": run.project_id,
    }, "account_research", datetime.now(timezone.utc))
    if not policy["allowed"]:
        raise ApiError(409, "POLICY_BLOCKED", "current account research policy is required")
    from buyeros_api.execution.provider_context import pending_run_work
    if await pending_run_work(session, workspace_id, run_id):
        raise ApiError(409, "RETRY_UNSAFE", "original run provider work requires reconciliation before checkpoint retry")
    runtime = (await session.execute(select(WorkerRuntimeControl.backend, WorkerRuntimeControl.epoch))).one_or_none()
    if (runtime is None or runtime.backend not in {'celery', 'cloudflare'} or
            type(runtime.epoch) is not int or not 1 <= runtime.epoch <= 9007199254740991):
        raise ApiError(503, "CAPABILITY_DISABLED", "current worker selector is unavailable")
    return runtime


async def run_retryable(session, run):
    if run.status not in {"failed", "partial", "paused_budget"} or run.stage not in {"fit_review_required", "fit"}:
        return False
    try:
        await _retry_preconditions(session, run)
    except ApiError:
        return False
    return True
