import uuid

from fastapi import APIRouter, Depends, Header, Query, Request, Response

from ..auth import Principal, get_principal
from ..errors import ApiError, envelope
from ..schemas import ArchiveRequest, ProjectCreate, ProjectUpdate

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/projects", tags=["projects"])


def _sender_data(sender) -> dict | None:
    if sender is None:
        return None
    return {
        "id": str(sender.id), "workspace_id": str(sender.workspace_id),
        "project_id": str(sender.project_id), "version_key": sender.version_key,
        "display_name": sender.display_name, "role_title": sender.role,
        "organization": sender.organization, "business_email": sender.business_email,
        "country": sender.country, "status": "retired" if sender.retired else "approved",
        "reviewed_by": str(sender.reviewed_by), "reviewed_at": sender.reviewed_at.isoformat(),
    }


async def _sender_map(session, projects) -> dict:
    from sqlalchemy import select
    from ...db.drafts import SenderIdentityVersion

    ids = [p.active_sender_identity_version_id for p in projects if p.active_sender_identity_version_id]
    if not ids:
        return {}
    rows = (await session.execute(select(SenderIdentityVersion).where(
        SenderIdentityVersion.workspace_id == projects[0].workspace_id,
        SenderIdentityVersion.id.in_(ids),
    ))).scalars().all()
    return {row.id: row for row in rows}


def _project_data(project, sender=None) -> dict:
    return {
        "id": str(project.id),
        "workspace_id": str(project.workspace_id),
        "version": project.version,
        "offer_revision": project.offer_revision,
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
        "sender_identity": _sender_data(sender),
    }


@router.get("")
async def list_projects(
    workspace_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal),
    offset: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    from sqlalchemy import func, select

    from ...db.icp import Project
    from ..deps import load_membership, permission_for_roles, tenant_scoped

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "listProjects"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        predicate = Project.workspace_id == workspace_id
        total = (await session.execute(select(func.count()).select_from(Project).where(predicate))).scalar_one()
        rows = (
            await session.execute(
                select(Project).where(predicate).order_by(Project.created_at, Project.id)
                .offset(offset).limit(limit)
            )
        ).scalars().all()
        senders = await _sender_map(session, rows)
        items = [_project_data(p, senders.get(p.active_sender_identity_version_id)) for p in rows]
    return envelope({"items": items, "offset": offset, "limit": limit, "total": total}, request.state.request_id)


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
            target={"workspace_id": str(workspace_id)}, precondition=None,
        )
        if outcome.replay:
            if outcome.response is None:
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "legacy replay requires a new key")
            response.headers["ETag"] = f'"{outcome.response["version"]}"'
            return envelope(outcome.response["data"], request.state.request_id)
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
        # Every new project begins with zero approved spend in every constrained scope.
        from ...services.budget_service import CATEGORIES, ensure_period_accounts, lock_budget_workspace
        await lock_budget_workspace(session, workspace_id)
        await ensure_period_accounts(session, workspace_id, project.id, None, None)
        for category in sorted(CATEGORIES):
            await ensure_period_accounts(session, workspace_id, project.id, None, category)
        data = _project_data(project)
        complete_idempotency(outcome, str(project.id), response={"http_status": 201, "version": project.version, "data": data})
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
        senders = await _sender_map(session, [project])
        data = _project_data(project, senders.get(project.active_sender_identity_version_id))
    return envelope(data, request.state.request_id)


_MATERIAL_FIELDS = ("offer", "website", "markets", "language_preferences")


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
    from ...db.drafts import Approval, OutreachDraft, SenderIdentityVersion
    from ...services.audit_service import append_audit
    from ..deps import load_membership, permission_for_roles, tenant_scoped
    from ..idempotency import begin_idempotency, complete_idempotency, if_match_version
    from datetime import datetime, timezone
    from sqlalchemy import update

    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    expected_version = if_match_version(if_match)
    changes = payload.model_dump(exclude_unset=True, mode="json")
    sender_change = changes.pop("sender_identity", None)
    if not changes and sender_change is None:
        raise ApiError(422, "INVALID_REQUEST", "at least one field is required")

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "updateProject"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        if sender_change is not None and not set(membership["roles"]).intersection({"reviewer", "workspace_admin"}):
            raise ApiError(403, "PERMISSION_DENIED", "sender configuration requires reviewer or admin")
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=membership["user_id"],
            operation_id="updateProject", key=idempotency_key,
            body={**changes, **({"sender_identity": sender_change} if sender_change else {})},
            target={"workspace_id": str(workspace_id), "project_id": str(project_id)},
            precondition=if_match,
        )
        if outcome.replay:
            if outcome.response is None:
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "legacy replay requires a new key")
            response.headers["ETag"] = f'"{outcome.response["version"]}"'
            return envelope(outcome.response["data"], request.state.request_id)
        project = (
            await session.execute(
                select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id).with_for_update()
            )
        ).scalar_one_or_none()
        if project is None:
            raise ApiError(404, "NOT_FOUND", "project not found")
        if project.version != expected_version:
            raise ApiError(412, "STALE_REVISION", "project changed; reload it")
        material = False
        for field, value in changes.items():
            if field in _MATERIAL_FIELDS and getattr(project, field) != value:
                material = True
            setattr(project, field, value)
        project.version += 1
        if material:
            project.offer_revision += 1
        if material and project.active_icp_version_id is not None:
            # Contract: a material offer/market change supersedes the active profile.
            await session.execute(
                IcpVersion.__table__.update()
                .where(IcpVersion.workspace_id == workspace_id, IcpVersion.id == project.active_icp_version_id)
                .values(superseded_at=func.now())
            )
            project.active_icp_version_id = None
        sender = None
        if sender_change is not None:
            previous_id = project.active_sender_identity_version_id
            project.sender_identity_epoch += 1
            sender = SenderIdentityVersion(
                id=uuid.uuid4(), workspace_id=workspace_id, project_id=project_id,
                version_key="", display_name=sender_change["display_name"],
                role=sender_change.get("role_title"),
                organization=sender_change["organization"],
                business_email=sender_change["business_email"],
                country=sender_change["country"], reviewed_by=membership["user_id"],
                reviewed_at=datetime.now(timezone.utc), review_reason=sender_change["reason"],
            )
            sender.version_key = f"sender:{sender.id}:{project.sender_identity_epoch}"
            session.add(sender)
            await session.flush()
            if previous_id:
                await session.execute(update(SenderIdentityVersion).where(
                    SenderIdentityVersion.workspace_id == workspace_id,
                    SenderIdentityVersion.id == previous_id,
                ).values(retired=True))
            project.active_sender_identity_version_id = sender.id
            draft_ids = select(OutreachDraft.id).where(
                OutreachDraft.workspace_id == workspace_id,
                OutreachDraft.project_id == project_id,
            )
            await session.execute(update(Approval).where(
                Approval.workspace_id == workspace_id, Approval.draft_id.in_(draft_ids),
                Approval.invalidated_reason.is_(None),
            ).values(invalidated_reason="sender_changed", invalidated_at=datetime.now(timezone.utc)))
            await session.execute(update(OutreachDraft).where(
                OutreachDraft.workspace_id == workspace_id,
                OutreachDraft.project_id == project_id,
                OutreachDraft.state == "approved",
            ).values(state="stale"))
            append_audit(session, workspace_id=workspace_id, actor_id=membership["user_id"],
                         action="sender_identity.reviewed", entity_type="project", entity_id=project_id,
                         request_id=request.state.request_id, reason=sender_change["reason"])
        await session.flush()
        await session.refresh(project)
        if sender is None:
            senders = await _sender_map(session, [project])
            sender = senders.get(project.active_sender_identity_version_id)
        data = _project_data(project, sender)
        complete_idempotency(outcome, str(project.id), response={"http_status": 200, "version": project.version, "data": data})
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
            target={"workspace_id": str(workspace_id), "project_id": str(project_id)},
            precondition=if_match,
        )
        if outcome.replay:
            if outcome.response is None:
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "legacy replay requires a new key")
            response.headers["ETag"] = f'"{outcome.response["version"]}"'
            return envelope(outcome.response["data"], request.state.request_id)
        project = (
            await session.execute(
                select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id).with_for_update()
            )
        ).scalar_one_or_none()
        if project is None:
            raise ApiError(404, "NOT_FOUND", "project not found")
        if project.version != expected_version:
            raise ApiError(412, "STALE_REVISION", "project changed; reload it")
        if project.status != "active":
            raise ApiError(409, "INVALID_STATE", "project already archived")
        project.status = "archived"
        project.version += 1
        # Preserve only a digest of the free-text reason in the same transaction.
        import hashlib
        from ...services.audit_service import append_audit

        append_audit(session, workspace_id=workspace_id, actor_id=membership["user_id"],
            action="project.archived", entity_type="project", entity_id=project.id,
            request_id=request.state.request_id, reason=payload.reason,
            detail_digest="sha256:" + hashlib.sha256(payload.reason.encode("utf-8")).hexdigest())
        await session.flush()
        await session.refresh(project)
        data = _project_data(project)
        complete_idempotency(outcome, str(project.id), response={"http_status": 200, "version": project.version, "data": data})
        response.headers["ETag"] = f'"{project.version}"'
    return envelope(data, request.state.request_id)
