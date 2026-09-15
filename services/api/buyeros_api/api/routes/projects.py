import uuid

from fastapi import APIRouter, Depends, Header, Request

from ..auth import Principal, get_principal
from ..errors import ApiError, envelope

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/projects", tags=["projects"])


def _project_data(project) -> dict:
    return {
        "id": str(project.id),
        "workspace_id": str(project.workspace_id),
        "name": project.name,
        "status": project.status,
    }


@router.get("")
async def list_projects(workspace_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)) -> dict:
    from sqlalchemy import select

    from ...db.icp import Project
    from ..deps import load_membership, permission_for_roles, tenant_scoped

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "listProjects"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        rows = (await session.execute(select(Project).where(Project.workspace_id == workspace_id))).scalars().all()
        items = [_project_data(p) for p in rows]
    return envelope({"items": items, "offset": 0, "limit": len(items), "total": len(items)}, request.state.request_id)


@router.post("", status_code=201)
async def create_project(
    workspace_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    from ...db.icp import Project
    from ..deps import load_membership, permission_for_roles, tenant_scoped

    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    body = await request.json()
    name = body.get("name")
    if not isinstance(name, str) or not (2 <= len(name) <= 160):
        raise ApiError(422, "INVALID_REQUEST", "name must be 2..160 characters")

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "createProject"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        project = Project(workspace_id=workspace_id, name=name)
        session.add(project)
        await session.flush()
        data = _project_data(project)
    return envelope(data, request.state.request_id)


@router.get("/{project_id}")
async def get_project(
    workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)
) -> dict:
    from sqlalchemy import select

    from ...db.icp import Project
    from ..deps import load_membership, permission_for_roles, tenant_scoped

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "getProject"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        project = (
            await session.execute(
                select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id)
            )
        ).scalar_one_or_none()
        if project is None:
            raise ApiError(404, "NOT_FOUND", "project not found")
        data = _project_data(project)
    return envelope(data, request.state.request_id)
