import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from ..auth import Principal, get_principal

router = APIRouter(tags=["health"])

CAPABILITY_NAMES = ("research", "contact_enrichment", "draft_generation", "mailbox", "crm")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def readiness_payload(*, database: str = "unavailable", queue: str = "unavailable", worker: str = "unavailable") -> dict:
    """Contract `Readiness` shape. No credential, DSN or provider detail is ever included.

    The route reaches this builder after a tenant-scoped DB query. Queue and worker
    become ready only with a recent committed heartbeat from a broker-delivered
    sweep task; absence and expiry fail closed.
    """
    return {
        "ready": database == "ready" and queue == "ready" and worker == "ready",
        "database": database,
        "queue": queue,
        "worker": worker,
        "checked_at": _now(),
    }


def capabilities_payload() -> dict:
    """Contract `CapabilityPage` shape; live providers stay disabled in this phase."""
    now = _now()
    items = [
        {
            "name": name,
            "status": "disabled" if name in {"mailbox", "crm"} else "unconfigured",
            "reason_codes": ["live_providers_not_activated"],
            "checked_at": now,
            "billable": False,
            "owner_role": "Release owner",
            "next_action": (
                "Keep delivery disabled. Use authorized exports and manual outcomes."
                if name in {"mailbox", "crm"}
                else "Select a provider and complete bounded verification before activation."
            ),
        }
        for name in CAPABILITY_NAMES
    ]
    return {"items": items, "offset": 0, "limit": len(items), "total": len(items)}


@router.get("/health/live")
async def live(request: Request) -> dict:
    """Minimal unauthenticated liveness with a contract-valid correlation ID."""
    from ..errors import envelope

    return envelope({"status": "ok", "service": "buyeros-api", "timestamp": _now()},
                    request.state.request_id)


async def _authorize(principal: Principal, workspace_id: uuid.UUID, operation_id: str) -> None:
    """Membership-check the caller for `operation_id` before any state is reported."""
    from ..deps import load_membership, permission_for_roles, tenant_scoped
    from ..errors import ApiError

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], operation_id):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")


@router.get("/v1/workspaces/{workspace_id}/readiness")
async def readiness(workspace_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)) -> dict:
    from ..errors import envelope

    from sqlalchemy import select
    from ...db.worker import WorkerHeartbeat
    from ..deps import load_membership, permission_for_roles, tenant_scoped
    from ..errors import ApiError
    from ...settings import get_settings

    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "getReadiness"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        from ...db.worker_execution import WorkerRuntimeControl
        backend, enabled = (await session.execute(select(WorkerRuntimeControl.backend, WorkerRuntimeControl.enabled))).one()
        heartbeat = (await session.execute(select(WorkerHeartbeat)
            .order_by(WorkerHeartbeat.observed_at.desc()).limit(1))).scalar_one_or_none() if backend == 'celery' and enabled else None
        worker, queue = "unavailable", "unavailable"
        if backend == 'cloudflare':
            from ...services.worker_recovery import read_execution_health
            health = await read_execution_health(session, now=datetime.now(timezone.utc))
            worker, queue = health['worker'], health['queue']
        elif heartbeat is not None:
            age = (datetime.now(timezone.utc) - heartbeat.observed_at).total_seconds()
            if 0 <= age <= get_settings().worker_heartbeat_max_age_seconds:
                worker, queue = "ready", heartbeat.broker_state
            else:
                worker = "stale"
    return envelope(readiness_payload(database="ready", queue=queue, worker=worker), request.state.request_id)


@router.get("/v1/workspaces/{workspace_id}/capabilities")
async def capabilities(workspace_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)) -> dict:
    from ..errors import envelope

    await _authorize(principal, workspace_id, "getCapabilities")
    return envelope(capabilities_payload(), request.state.request_id)
