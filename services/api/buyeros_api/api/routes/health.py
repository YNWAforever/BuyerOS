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

    The route only reaches this builder after a successful tenant-scoped query, so it
    passes `database="ready"`; the queue and the worker stay `unavailable` because no
    broker or worker is wired or observed in this phase. `ready` is therefore still
    false, which is the honest answer.
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
        }
        for name in CAPABILITY_NAMES
    ]
    return {"items": items, "offset": 0, "limit": len(items), "total": len(items)}


@router.get("/health/live")
async def live() -> dict:
    """Non-contract liveness probe only: no auth and no dependency or secret disclosure."""
    return {
        "data": {"status": "ok", "service": "buyeros-api", "timestamp": _now()},
        "request_id": "",
        "data_mode": "live",
    }


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

    await _authorize(principal, workspace_id, "getReadiness")
    return envelope(readiness_payload(database="ready"), request.state.request_id)


@router.get("/v1/workspaces/{workspace_id}/capabilities")
async def capabilities(workspace_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)) -> dict:
    from ..errors import envelope

    await _authorize(principal, workspace_id, "getCapabilities")
    return envelope(capabilities_payload(), request.state.request_id)
