"""Public run admission on the declared domain API path."""

import json
import re
import uuid

from sqlalchemy import func, select
from fastapi import Query
from fastapi.responses import StreamingResponse

from ...db.icp import Project
from ...db.runs import SearchRun
from ...services.run_control import cancel_run, retry_run
from ...services.run_events import event_page, require_run, run_snapshot
from ..schemas import ArchiveRequest, RunRetryRequest

from fastapi import APIRouter, Depends, Header, Request

from ..auth import Principal, get_principal
from ..deps import load_membership, permission_for_roles, tenant_scoped
from ..errors import ApiError, envelope
from ..idempotency import begin_idempotency, complete_idempotency
from ..schemas import RunCreate
from ...services.run_admission import admit_run

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/projects/{project_id}/runs", tags=["runs"])


def selected_run_capability() -> tuple[dict | None, str]:
    """No production provider is selected; tests override this dependency explicitly."""
    return None, "production"


@router.post("", status_code=202, name="startRun")
async def start_run(
    workspace_id: uuid.UUID, project_id: uuid.UUID, payload: RunCreate,
    request: Request, principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    selection: tuple[dict | None, str] = Depends(selected_run_capability),
) -> dict:
    if idempotency_key is None:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "startRun"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        body = payload.model_dump(mode="json")
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=member["user_id"],
            operation_id="startRun", key=idempotency_key, body=body,
            target={"workspace_id": str(workspace_id), "project_id": str(project_id)},
        )
        if outcome.replay:
            if outcome.response is None:
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "legacy replay requires a new key")
            return envelope(outcome.response["data"], request.state.request_id)
        capability, environment = selection
        data = await admit_run(session, member["user_id"], project_id, payload,
                               workspace_id=workspace_id, capabilities=capability,
                               environment=environment)
        complete_idempotency(outcome, data["id"], response={"http_status": 202, "data": data})
    return envelope(data, request.state.request_id)


# The declared detail paths are workspace-scoped, unlike project run admission.
detail_router = APIRouter(prefix="/v1/workspaces/{workspace_id}/runs", tags=["runs"])


def _version_header(value: str | None) -> int:
    if value is None:
        raise ApiError(400, "INVALID_REQUEST", "If-Match header is required")
    if not re.fullmatch(r'"[1-9][0-9]*"', value):
        raise ApiError(400, "INVALID_REQUEST", "If-Match must be a strong numeric version")
    return int(value[1:-1])


@router.get("", name="listRuns")
async def list_runs(
    workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request,
    offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
    principal: Principal = Depends(get_principal),
):
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "listRuns"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        project = (await session.execute(select(Project.id).where(
            Project.workspace_id == workspace_id, Project.id == project_id))).scalar_one_or_none()
        if project is None:
            raise ApiError(404, "NOT_FOUND", "project not found")
        conditions = (SearchRun.workspace_id == workspace_id, SearchRun.project_id == project_id)
        total = (await session.execute(select(func.count()).select_from(SearchRun).where(*conditions))).scalar_one()
        rows = (await session.execute(select(SearchRun).where(*conditions)
            .order_by(SearchRun.created_at.desc(), SearchRun.id.desc()).offset(offset).limit(limit))).scalars().all()
        items = [await run_snapshot(session, row) for row in rows]
    return envelope({"items": items, "offset": offset, "limit": limit, "total": total}, request.state.request_id)


@detail_router.get("/{run_id}", name="getRun")
async def get_run(workspace_id: uuid.UUID, run_id: uuid.UUID, request: Request,
                  principal: Principal = Depends(get_principal)):
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "getRun"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        data = await run_snapshot(session, await require_run(session, workspace_id, run_id))
    return envelope(data, request.state.request_id)


@detail_router.get("/{run_id}/events", name="getRunEvents")
async def get_run_events(
    workspace_id: uuid.UUID, run_id: uuid.UUID, request: Request,
    after_sequence: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200),
    principal: Principal = Depends(get_principal),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
):
    if last_event_id is not None:
        if not re.fullmatch(r"[0-9]+", last_event_id):
            raise ApiError(400, "INVALID_REQUEST", "invalid Last-Event-ID")
        after_sequence = max(after_sequence, int(last_event_id))
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "getRunEvents"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        data = await event_page(session, await require_run(session, workspace_id, run_id),
                                after_sequence, limit)
    if after_sequence > data["latest_sequence"]:
        raise ApiError(409, "EVENT_CURSOR_EXPIRED", "refresh the run snapshot before reconnecting")
    if "text/event-stream" in request.headers.get("Accept", ""):
        frames = [f'id: {item["sequence"]}\nevent: {item["type"]}\ndata: '
                  + json.dumps(item, separators=(",", ":")) + "\n\n" for item in data["items"]]
        return StreamingResponse(iter(frames or [": replay complete\n\n"]),
                                 media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
    return envelope(data, request.state.request_id)


@detail_router.post("/{run_id}/cancel", status_code=202, name="cancelRun")
async def cancel_run_http(
    workspace_id: uuid.UUID, run_id: uuid.UUID, payload: ArchiveRequest,
    request: Request, principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
):
    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    version = _version_header(if_match)
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "cancelRun"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        outcome = await begin_idempotency(session, workspace_id=workspace_id,
            actor_id=member["user_id"], operation_id=f"cancelRun:{run_id}",
            key=idempotency_key, body=payload.model_dump(), target={"run_id": str(run_id)},
            precondition=if_match)
        if outcome.replay and outcome.response is not None:
            return envelope(outcome.response["data"], request.state.request_id)
        run = await cancel_run(session, workspace_id, run_id, payload.reason,
                               expected_version=version)
        await session.flush()
        await session.refresh(run)
        data = await run_snapshot(session, run)
        complete_idempotency(outcome, str(run_id), response={"http_status": 202, "data": data})
    return envelope(data, request.state.request_id)


@detail_router.post("/{run_id}/retry", status_code=202, name="retryRun")
async def retry_run_http(
    workspace_id: uuid.UUID, run_id: uuid.UUID, payload: RunRetryRequest,
    request: Request, principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
):
    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    version = _version_header(if_match)
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "retryRun"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        outcome = await begin_idempotency(session, workspace_id=workspace_id,
            actor_id=member["user_id"], operation_id=f"retryRun:{run_id}",
            key=idempotency_key, body=payload.model_dump(), target={"run_id": str(run_id)},
            precondition=if_match)
        if outcome.replay and outcome.response is not None:
            return envelope(outcome.response["data"], request.state.request_id)
        run = await retry_run(session, workspace_id, run_id, payload.reason,
                              expected_version=version)
        await session.flush()
        await session.refresh(run)
        data = await run_snapshot(session, run)
        complete_idempotency(outcome, str(run_id), response={"http_status": 202, "data": data})
    return envelope(data, request.state.request_id)
