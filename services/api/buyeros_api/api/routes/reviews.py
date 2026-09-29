import uuid

from fastapi import APIRouter, Depends, Header, Request, Response

from ..auth import Principal, get_principal
from ..errors import ApiError, envelope
from ..schemas import ReviewRequest

router = APIRouter(prefix="/v1/workspaces/{workspace_id}", tags=["buyer-reviews"])


@router.post("/projects/{project_id}/buyer-reviews")
async def review_buyers(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    payload: ReviewRequest,
    request: Request,
    response: Response,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    from sqlalchemy import select

    from ...db.icp import Project
    from ...services.buyer_review import _resolve_items, apply
    from ...services.bulk_service import create_bulk_job, job_data
    from ..deps import load_membership, permission_for_roles, tenant_scoped
    from ..idempotency import begin_idempotency, complete_idempotency

    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    body = payload.model_dump(mode="json")

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "reviewBuyers"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        project = (
            await session.execute(select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id).with_for_update())
        ).scalar_one_or_none()
        if project is None:
            raise ApiError(404, "NOT_FOUND", "project not found")
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=membership["user_id"],
            operation_id=f"reviewBuyers:{project_id}", key=idempotency_key, body=body,
        )
        if outcome.replay and outcome.response is not None:
            stored = outcome.response
            if stored.get("http_status") == 202:
                response.status_code = 202
                stored = stored["data"]
            return envelope(stored, request.state.request_id)
        pairs = await _resolve_items(session, workspace_id=workspace_id, project_id=project_id,
                                     actor_user_id=membership["user_id"], selection=body["selection"])
        if len(pairs) > 100:
            job = await create_bulk_job(
                session, workspace_id=workspace_id, project_id=project_id,
                actor_user_id=membership["user_id"], operation="reviewBuyers",
                selection=body["selection"],
                command={"status": body["status"], "reason": body["reason"]},
            )
            data = job_data(job)
            response.status_code = 202
            complete_idempotency(outcome, str(job.id), response={"http_status": 202, "data": data})
        else:
            data = await apply(
                session, workspace_id=workspace_id, project_id=project_id,
                actor_user_id=membership["user_id"], active_icp_version_id=project.active_icp_version_id,
                selection=body["selection"], status=body["status"], reason=body["reason"],
            )
            complete_idempotency(outcome, str(project_id), response=data)
    return envelope(data, request.state.request_id)
