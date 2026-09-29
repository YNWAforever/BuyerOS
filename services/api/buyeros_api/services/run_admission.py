"""Atomic admission of an approved, budgeted research run.

The returned queued state means durable intent only. No provider call occurs in
this transaction. The production capability resolver currently returns none.
"""

from datetime import datetime, timezone
from decimal import Decimal
import uuid

from sqlalchemy import select

from ..api.errors import ApiError
from ..api.schemas import RunCreate
from ..settings import get_settings
from ..db.icp import IcpVersion, Project, canonical_hash
from ..db.outbox import OutboxEvent
from ..db.runs import RunEvent, SearchRun
from .budget_service import ZERO, account_snapshot, ensure_period_accounts
from .outbox_service import build_intent
from .policy_service import evaluate_current_policy
from .query_plan import build_query_plan


def _money(value: Decimal) -> dict:
    return {"amount": format(value, ".6f"), "currency": "USD"}


def run_data(run: SearchRun) -> dict:
    return {
        "id": str(run.id), "workspace_id": str(run.workspace_id),
        "project_id": str(run.project_id), "icp_version_id": str(run.icp_version_id),
        "version": run.version, "created_at": run.created_at.isoformat(),
        "updated_at": run.updated_at.isoformat(), "data_mode": "live",
        "status": run.status, "stage": run.stage,
        "target_companies": run.target_companies, "raw_count": run.raw_result_count, "company_count": 0, "assessed_count": 0,
        "last_event_sequence": 1, "max_cost": _money(run.max_cost),
        "spent": _money(ZERO), "reserved": _money(ZERO),
        "limits": run.limits, "attempt": run.attempt,
    }


async def admit_run(session, actor_id: uuid.UUID, project_id: uuid.UUID, request: RunCreate,
                    *, workspace_id: uuid.UUID, capabilities: dict | None,
                    environment: str = "production") -> dict:
    """Insert run, first event, run ceiling and one outbox row in caller transaction."""
    if environment != "test" and not get_settings().paid_admission_enabled:
        raise ApiError(503, "CAPABILITY_DISABLED", "new paid research admission is disabled")
    if capabilities is None:
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "verified search capability is not selected")
    if capabilities.get("provider") == "fixture" and environment != "test":
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "fixture capability is test-only")
    if not capabilities.get("verified") or not capabilities.get("price_version"):
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "verified bounded pricing and filters are required")
    project = (await session.execute(select(Project).where(
        Project.workspace_id == workspace_id, Project.id == project_id,
    ).with_for_update())).scalar_one_or_none()
    if project is None:
        raise ApiError(404, "NOT_FOUND", "project not found")
    if project.status != "active":
        raise ApiError(409, "INVALID_STATE", "archived project cannot start research")
    icp = (await session.execute(select(IcpVersion).where(
        IcpVersion.workspace_id == workspace_id, IcpVersion.project_id == project_id,
        IcpVersion.id == request.icp_version_id,
    ))).scalar_one_or_none()
    if icp is None:
        raise ApiError(404, "NOT_FOUND", "profile not found")
    if (project.active_icp_version_id != icp.id or icp.approved_at is None
            or icp.approved_by is None or icp.superseded_at is not None
            or icp.basis_offer_revision != project.offer_revision
            or icp.content_hash != canonical_hash(icp.content)):
        raise ApiError(412, "STALE_REVISION", "current approved profile is required")
    if not set(icp.content.get("markets") or []).issubset(set(project.markets or [])):
        raise ApiError(422, "INVALID_REQUEST", "ICP market is outside current project scope")
    limits = request.limits.model_dump(mode="json")
    try:
        plan = build_query_plan(icp.content, capabilities, limits)
    except (ValueError, TypeError) as exc:
        raise ApiError(422, "INVALID_REQUEST", str(exc)) from exc
    policy = await evaluate_current_policy(
        session, {"workspace_id": workspace_id, "project_id": project_id},
        "account_research", datetime.now(timezone.utc),
    )
    if not policy["allowed"]:
        raise ApiError(409, "POLICY_BLOCKED", "current account research policy is required")
    max_cost = Decimal(request.max_cost.amount)
    if max_cost <= ZERO:
        raise ApiError(409, "BUDGET_LIMIT", "a positive run ceiling is required")
    accounts = await account_snapshot(session, workspace_id, project_id, None, "discovery")
    if any(Decimal(account["remaining"]["amount"]) < max_cost or
           account["effective_state"] != "active" for account in accounts):
        raise ApiError(409, "BUDGET_LIMIT", "approved budget does not cover run ceiling")

    snapshot = {
        "icp_content_hash": icp.content_hash,
        "icp_number": icp.number,
        "offer_revision": project.offer_revision,
        "capability": {
            "provider": capabilities["provider"],
            "price_version": capabilities["price_version"],
            "verified_filters": sorted(set(capabilities["verified_filters"])),
            "markets": sorted(set(capabilities["markets"])),
            "languages": sorted(set(capabilities["languages"])),
        },
        "query_plan": plan,
        "actor_id": str(actor_id),
    }
    counters = {name: 0 for name in
                ("rounds", "queries", "raw_results", "pages", "model_tokens", "in_flight")}
    run = SearchRun(workspace_id=workspace_id, project_id=project_id,
                    icp_version_id=icp.id, status="queued", stage="queued",
                    limits=limits, target_companies=request.target_companies,
                    max_cost=max_cost, execution_snapshot=snapshot,
                    usage_counters=counters)
    session.add(run)
    await session.flush()
    run_accounts = await ensure_period_accounts(session, workspace_id, project_id, run.id, None)
    run_account = next(account for account in run_accounts if account.scope == "run")
    run_account.approved_limit = max_cost
    session.add(RunEvent(workspace_id=workspace_id, run_id=run.id, sequence=1,
                         event_type="run.queued", payload={"stage": "queued", "version": 1}))
    intent_key = build_intent("run.discover", {"run_id": str(run.id)}, 0)
    session.add(OutboxEvent(workspace_id=workspace_id, intent_key=intent_key,
                            event_type="run.discover", payload={"run_id": str(run.id)}))
    await session.flush()
    await session.refresh(run)
    return run_data(run)
