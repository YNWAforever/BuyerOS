import uuid

from fastapi import APIRouter, Depends, Header, Request, Response

from ..auth import Principal, get_principal
from ..errors import ApiError, envelope
from ..schemas import ArchiveRequest, ProjectCreate, ProjectUpdate

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/projects", tags=["projects"])


def _project_data(project) -> dict:
    return {
        "id": str(project.id),
        "workspace_id": str(project.workspace_id),
        "version": project.version,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
        "data_mode": "live",
        "name": project.name,
        "company_name": project.company_name,
        "offer": project.offer,
        "website": project.website,
        "markets": list(project.markets),
        "language_preferences": list(project.language_preferences),
        "status": project.status,
        "active_icp_version_id": str(project.active_icp_version_id) if project.active_icp_version_id else None,
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
    response: Response,
    payload: ProjectCreate,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    from sqlalchemy import select

    from ...db.icp import Project
    from ..deps import load_membership, permission_for_roles, tenant_scoped
    from ..idempotency import begin_idempotency, complete_idempotency

    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "createProject"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=membership["user_id"],
            operation_id="createProject", key=idempotency_key, body=payload.model_dump(mode="json"),
        )
        if outcome.replay:
            project = (
                await session.execute(
                    select(Project).where(
                        Project.workspace_id == workspace_id, Project.id == uuid.UUID(str(outcome.record.resource_id))
                    )
                )
            ).scalar_one_or_none()
            if project is None:
                raise ApiError(404, "NOT_FOUND", "project not found")
            response.headers["ETag"] = f'"{project.version}"'
            return envelope(_project_data(project), request.state.request_id)
        project = Project(
            workspace_id=workspace_id,
            name=payload.name,
            company_name=payload.company_name,
            offer=payload.offer,
            website=payload.website,
            markets=payload.markets,
            language_preferences=payload.language_preferences,
        )
        session.add(project)
        await session.flush()
        complete_idempotency(outcome, str(project.id))
        data = _project_data(project)
        response.headers["ETag"] = f'"{project.version}"'
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


_MATERIAL_FIELDS = ("offer", "markets")


@router.patch("/{project_id}")
async def update_project(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    request: Request,
    response: Response,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> dict:
    from sqlalchemy import func, select

    from ...db.icp import IcpVersion, Project
    from ..deps import load_membership, permission_for_roles, tenant_scoped
    from ..idempotency import begin_idempotency, complete_idempotency, if_match_version

    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    expected_version = if_match_version(if_match)
    changes = payload.model_dump(exclude_unset=True, mode="json")
    if not changes:
        raise ApiError(422, "INVALID_REQUEST", "at least one field is required")

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "updateProject"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=membership["user_id"],
            operation_id="updateProject", key=idempotency_key, body=changes,
        )
        project = (
            await session.execute(
                select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id).with_for_update()
            )
        ).scalar_one_or_none()
        if project is None:
            raise ApiError(404, "NOT_FOUND", "project not found")
        if outcome.replay:
            response.headers["ETag"] = f'"{project.version}"'
            return envelope(_project_data(project), request.state.request_id)
        if project.version != expected_version:
            raise ApiError(412, "STALE_REVISION", "project changed; reload it")
        material = False
        for field, value in changes.items():
            if field in _MATERIAL_FIELDS and getattr(project, field) != value:
                material = True
            setattr(project, field, value)
        project.version += 1
        if material and project.active_icp_version_id is not None:
            # Contract: a material offer/market change supersedes the active profile.
            await session.execute(
                IcpVersion.__table__.update()
                .where(IcpVersion.workspace_id == workspace_id, IcpVersion.id == project.active_icp_version_id)
                .values(superseded_at=func.now())
            )
            project.active_icp_version_id = None
        await session.flush()
        await session.refresh(project)
        complete_idempotency(outcome, str(project.id))
        data = _project_data(project)
        response.headers["ETag"] = f'"{project.version}"'
    return envelope(data, request.state.request_id)


@router.delete("/{project_id}")
async def archive_project(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    payload: ArchiveRequest,
    request: Request,
    response: Response,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> dict:
    from sqlalchemy import select

    from ...db.icp import Project
    from ..deps import load_membership, permission_for_roles, tenant_scoped
    from ..idempotency import begin_idempotency, complete_idempotency, if_match_version

    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    expected_version = if_match_version(if_match)
    body = payload.model_dump(mode="json")

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "archiveProject"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=membership["user_id"],
            operation_id="archiveProject", key=idempotency_key, body=body,
        )
        project = (
            await session.execute(
                select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id).with_for_update()
            )
        ).scalar_one_or_none()
        if project is None:
            raise ApiError(404, "NOT_FOUND", "project not found")
        if outcome.replay:
            response.headers["ETag"] = f'"{project.version}"'
            return envelope(_project_data(project), request.state.request_id)
        if project.version != expected_version:
            raise ApiError(412, "STALE_REVISION", "project changed; reload it")
        project.status = "archived"
        project.version += 1
        await session.flush()
        await session.refresh(project)
        complete_idempotency(outcome, str(project.id))
        data = _project_data(project)
        response.headers["ETag"] = f'"{project.version}"'
    return envelope(data, request.state.request_id)
