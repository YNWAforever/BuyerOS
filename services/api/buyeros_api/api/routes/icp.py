import uuid

from fastapi import APIRouter, Depends, Header, Request

from ..auth import Principal, get_principal
from ..errors import ApiError, envelope

router = APIRouter(prefix="/v1/workspaces/{workspace_id}", tags=["icp"])

_CONTENT_KEYS = (
    "offer_document_ids", "offer_facts", "requirements", "markets",
    "buyer_types", "languages", "desired_roles",
)


def _icp_data(row) -> dict:
    content = row.content or {}
    return {
        "id": str(row.id),
        "workspace_id": str(row.workspace_id),
        "project_id": str(row.project_id),
        "number": row.number,
        "content_hash": row.content_hash,
        "status": "superseded" if row.superseded_at else ("approved" if row.approved_at else "saved"),
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "approved_by": str(row.approved_by) if row.approved_by else None,
        "requirements": content.get("requirements", []),
        "markets": content.get("markets", []),
        "buyer_types": content.get("buyer_types", []),
        "languages": content.get("languages", []),
        "offer_facts": content.get("offer_facts", []),
    }


@router.get("/projects/{project_id}/icp-versions")
async def list_icp_versions(
    workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)
) -> dict:
    from sqlalchemy import select

    from ...db.icp import IcpVersion
    from ..deps import load_membership, permission_for_roles, tenant_scoped

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "listICPVersions"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        rows = (
            await session.execute(
                select(IcpVersion).where(
                    IcpVersion.workspace_id == workspace_id, IcpVersion.project_id == project_id
                )
            )
        ).scalars().all()
        items = [_icp_data(v) for v in rows]
    return envelope({"items": items, "offset": 0, "limit": len(items), "total": len(items)}, request.state.request_id)


@router.post("/projects/{project_id}/icp-versions", status_code=201)
async def save_icp_version(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    from sqlalchemy import func, select

    from ...db.icp import IcpVersion, Project, canonical_hash
    from ..deps import load_membership, permission_for_roles, tenant_scoped

    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    body = await request.json()
    content = {key: body[key] for key in _CONTENT_KEYS if key in body}

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "saveICPVersion"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        project = (
            await session.execute(
                select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id)
            )
        ).scalar_one_or_none()
        if project is None:
            raise ApiError(404, "NOT_FOUND", "project not found")
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
            content=content,
            content_hash=canonical_hash(content),
        )
        session.add(row)
        await session.flush()
        data = _icp_data(row)
    return envelope(data, request.state.request_id)


@router.post("/icp-versions/{icp_version_id}/approve")
async def approve_icp_version(
    workspace_id: uuid.UUID,
    icp_version_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> dict:
    from datetime import datetime, timezone

    from sqlalchemy import select

    from ...db.icp import IcpVersion, Project
    from ...services.icp_service import StaleRevision, verify_approval_hash
    from ..deps import load_membership, permission_for_roles, tenant_scoped
    from ..idempotency import if_match_version

    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    # Contract `IfMatch`: strong version ETag ("4"); missing is 400, stale is 412.
    expected_version = if_match_version(if_match)

    body = await request.json()
    if body.get("confirmation") is not True:
        raise ApiError(400, "INVALID_REQUEST", "confirmation must be true")
    expected_hash = body.get("content_hash", "")

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "approveICPVersion"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        row = (
            await session.execute(
                select(IcpVersion)
                .where(IcpVersion.workspace_id == workspace_id, IcpVersion.id == icp_version_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            raise ApiError(404, "NOT_FOUND", "profile version not found")
        if row.number != expected_version:
            raise ApiError(412, "STALE_REVISION", "profile version changed; reload the profile")
        try:
            verify_approval_hash(row, expected_hash)
        except StaleRevision as exc:
            raise ApiError(412, "STALE_REVISION", str(exc)) from exc
        if row.approved_at is not None:
            return envelope(_icp_data(row), request.state.request_id)
        row.approved_at = datetime.now(timezone.utc)
        row.approved_by = membership["user_id"]
        project = (
            await session.execute(
                select(Project).where(Project.workspace_id == workspace_id, Project.id == row.project_id).with_for_update()
            )
        ).scalar_one_or_none()
        if project is None:
            raise ApiError(404, "NOT_FOUND", "project not found")
        project.active_icp_version_id = row.id
        data = _icp_data(row)
    return envelope(data, request.state.request_id)
