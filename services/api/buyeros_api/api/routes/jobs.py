"""Actor-bound durable job status and result pages."""
import uuid
from typing import Literal

from sqlalchemy import func, select

from fastapi import APIRouter, Depends, Header, Query, Request, Response

from ..auth import Principal, get_principal
from ..deps import load_membership, permission_for_roles, tenant_scoped
from ..errors import ApiError, envelope
from ..idempotency import begin_idempotency, complete_idempotency
from ...services.bulk_service import cancel_bulk_job, job_data, read_job_page, retry_failed_only
from ...db.outbox import AsyncJob

router = APIRouter(prefix="/v1/workspaces/{workspace_id}", tags=["jobs"])


@router.get("/jobs")
async def list_async_jobs(
    workspace_id: uuid.UUID, request: Request,
    offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
    status: Literal["queued", "running", "cancel_requested", "cancelled", "completed", "failed"] | None = None,
    project_id: uuid.UUID | None = None,
    principal: Principal = Depends(get_principal),
):
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "listAsyncJobs"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        conditions = [AsyncJob.workspace_id == workspace_id]
        if "workspace_admin" not in member["roles"]:
            conditions.append(AsyncJob.actor_user_id == member["user_id"])
        if status is not None:
            conditions.append(AsyncJob.status == status)
        if project_id is not None:
            conditions.append(AsyncJob.project_id == project_id)
        total = (await session.execute(select(func.count()).select_from(AsyncJob).where(*conditions))).scalar_one()
        rows = (await session.execute(select(AsyncJob).where(*conditions)
            .order_by(AsyncJob.created_at.desc(), AsyncJob.id.desc())
            .offset(offset).limit(limit))).scalars().all()
        data = {"items": [job_data(row) for row in rows], "offset": offset, "limit": limit, "total": total}
    return envelope(data, request.state.request_id)


@router.get("/jobs/{job_id}")
async def get_async_job(
    workspace_id: uuid.UUID, job_id: uuid.UUID, request: Request,
    offset: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=100),
    principal: Principal = Depends(get_principal),
):
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "getAsyncJob"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        data = await read_job_page(
            session, workspace_id=workspace_id, job_id=job_id,
            actor_user_id=member["user_id"], is_admin="workspace_admin" in member["roles"],
            offset=offset, limit=limit,
        )
    return envelope(data, request.state.request_id)


@router.post("/jobs/{job_id}/retry-failed")
async def retry_failed_async_job(
    workspace_id: uuid.UUID, job_id: uuid.UUID, request: Request, response: Response,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=member["user_id"],
            operation_id=f"retryFailedAsyncJob:{job_id}", key=idempotency_key,
            body={}, target={"job_id": str(job_id)},
        )
        if outcome.replay and outcome.response is not None:
            response.status_code = outcome.response["http_status"]
            return envelope(outcome.response["data"], request.state.request_id)
        status, data = await retry_failed_only(
            session, workspace_id=workspace_id, job_id=job_id,
            actor_user_id=member["user_id"], roles=member["roles"],
        )
        complete_idempotency(outcome, str(data.get("id", job_id)),
                             response={"http_status": status, "data": data})
        response.status_code = status
    return envelope(data, request.state.request_id)


@router.post("/jobs/{job_id}/cancel")
async def cancel_async_job(
    workspace_id: uuid.UUID, job_id: uuid.UUID, request: Request,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=member["user_id"],
            operation_id=f"cancelAsyncJob:{job_id}", key=idempotency_key,
            body={}, target={"job_id": str(job_id)},
        )
        if outcome.replay and outcome.response is not None:
            return envelope(outcome.response, request.state.request_id)
        data = await cancel_bulk_job(session, workspace_id=workspace_id, job_id=job_id,
                                     actor_user_id=member["user_id"])
        complete_idempotency(outcome, str(job_id), response=data)
    return envelope(data, request.state.request_id)
