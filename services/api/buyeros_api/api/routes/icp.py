import uuid

from fastapi import APIRouter, Depends, Header, Query, Request

from ..auth import Principal, get_principal
from ..errors import ApiError, envelope
from ..schemas import ICPSaveRequest, ICPApproveRequest

router = APIRouter(prefix="/v1/workspaces/{workspace_id}", tags=["icp"])

_CONTENT_KEYS = (
    "offer_document_ids", "offer_facts", "requirements", "markets",
    "buyer_types", "languages", "desired_roles",
)


from ...services.icp_service import icp_data as _icp_data


@router.get("/projects/{project_id}/icp-versions")
async def list_icp_versions(
    workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request,
    principal: Principal = Depends(get_principal),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    from sqlalchemy import func, select

    from ...db.icp import IcpVersion
    from ..deps import load_membership, permission_for_roles, tenant_scoped

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "listICPVersions"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        from ...db.icp import Project
        project = (
            await session.execute(
                select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id)
            )
        ).scalar_one_or_none()
        if project is None:
            raise ApiError(404, "NOT_FOUND", "project not found")
        predicate = (IcpVersion.workspace_id == workspace_id, IcpVersion.project_id == project_id)
        total = (await session.execute(select(func.count()).select_from(IcpVersion).where(*predicate))).scalar_one()
        rows = (
            await session.execute(
                select(IcpVersion).where(*predicate).order_by(IcpVersion.number, IcpVersion.id)
                .offset(offset).limit(limit)
            )
        ).scalars().all()
        items = [_icp_data(v, project=project) for v in rows]
    return envelope({"items": items, "offset": offset, "limit": limit, "total": total}, request.state.request_id)


@router.post("/projects/{project_id}/icp-versions", status_code=201)
async def save_icp_version(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    payload: ICPSaveRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    from sqlalchemy import func, select

    from ...db.icp import IcpVersion, Project, canonical_hash
    from ...services.offer_document_refs import validate_offer_document_refs
    from ..deps import load_membership, permission_for_roles, tenant_scoped
    from ..idempotency import begin_idempotency, complete_idempotency

    if idempotency_key is None or not (8 <= len(idempotency_key) <= 200):
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key must be 8..200 characters")
    body = payload.model_dump(mode="json", exclude_unset=True)
    content = {key: body[key] for key in _CONTENT_KEYS if key in body}
    content["basis_offer_revision"] = payload.basis_offer_revision
    if payload.parent_icp_version_id is not None:
        content["parent_icp_version_id"] = str(payload.parent_icp_version_id)
    # Caller-supplied flags never approve facts. The reviewer approves the immutable version later.
    for fact in content["offer_facts"]:
        fact["approved"] = False

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "saveICPVersion"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=membership["user_id"],
            operation_id="saveICPVersion", key=idempotency_key, body=body,
            target={"workspace_id": str(workspace_id), "project_id": str(project_id)},
        )
        if outcome.replay:
            if outcome.response is None:
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "legacy replay requires a new key")
            return envelope(outcome.response["data"], request.state.request_id)
        project = (
            await session.execute(
                select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id).with_for_update()
            )
        ).scalar_one_or_none()
        if project is None:
            raise ApiError(404, "NOT_FOUND", "project not found")
        if project.status != "active":
            raise ApiError(409, "INVALID_REQUEST", "archived project cannot save profiles")
        if payload.basis_offer_revision != project.offer_revision:
            raise ApiError(412, "STALE_REVISION", "offer basis changed; reload project")
        await validate_offer_document_refs(
            session, workspace_id=workspace_id, project_id=project_id,
            document_ids=payload.offer_document_ids, facts=payload.offer_facts,
        )
        if payload.parent_icp_version_id is not None:
            parent = (
                await session.execute(
                    select(IcpVersion.id).where(
                        IcpVersion.workspace_id == workspace_id,
                        IcpVersion.project_id == project_id,
                        IcpVersion.id == payload.parent_icp_version_id,
                    )
                )
            ).scalar_one_or_none()
            if parent is None:
                raise ApiError(404, "NOT_FOUND", "parent profile not found")
        highest = (
            await session.execute(
                select(func.max(IcpVersion.number)).where(
                    IcpVersion.workspace_id == workspace_id, IcpVersion.project_id == project_id
                )
            )
        ).scalar()
        row = IcpVersion(
            workspace_id=workspace_id,
            project_id=project_id,
            number=(highest or 0) + 1,
            basis_offer_revision=payload.basis_offer_revision,
            parent_id=payload.parent_icp_version_id,
            content=content,
            content_hash=canonical_hash(content),
        )
        session.add(row)
        await session.flush()
        data = _icp_data(row, project=project)
        complete_idempotency(
            outcome, str(row.id), response={"http_status": 201, "version": row.number, "data": data}
        )
    return envelope(data, request.state.request_id)


@router.post("/icp-versions/{icp_version_id}/approve")
async def approve_icp_version(
    workspace_id: uuid.UUID,
    icp_version_id: uuid.UUID,
    payload: ICPApproveRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> dict:
    from sqlalchemy import select

    from ...db.icp import IcpVersion
    from ...services.icp_service import approve_icp
    from ..deps import load_membership, permission_for_roles, tenant_scoped
    from ..idempotency import begin_idempotency, complete_idempotency, if_match_version

    if idempotency_key is None or not (8 <= len(idempotency_key) <= 200):
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key must be 8..200 characters")
    expected_number = if_match_version(if_match)
    body = payload.model_dump(mode="json")

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "approveICPVersion"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=membership["user_id"],
            operation_id="approveICPVersion", key=idempotency_key, body=body,
            target={"workspace_id": str(workspace_id), "icp_version_id": str(icp_version_id)},
            precondition=if_match,
        )
        if outcome.replay:
            if outcome.response is None:
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "legacy replay requires a new key")
            return envelope(outcome.response["data"], request.state.request_id)
        project_id = (
            await session.execute(
                select(IcpVersion.project_id).where(
                    IcpVersion.workspace_id == workspace_id, IcpVersion.id == icp_version_id
                )
            )
        ).scalar_one_or_none()
        if project_id is None:
            raise ApiError(404, "NOT_FOUND", "profile version not found")
        data = await approve_icp(
            session, project_id, icp_version_id, payload.expected_project_version,
            payload.content_hash, membership["user_id"], workspace_id=workspace_id,
            expected_number=expected_number,
        )
        complete_idempotency(
            outcome, str(icp_version_id), response={"http_status": 200, "version": expected_number, "data": data}
        )
    return envelope(data, request.state.request_id)
