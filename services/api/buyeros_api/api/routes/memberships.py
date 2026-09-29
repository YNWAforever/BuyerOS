"""Versioned management of existing verified tenant memberships only."""
import uuid
from hashlib import sha256

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import func, select

from ..auth import Principal, get_principal
from ..deps import load_membership, tenant_scoped
from ..errors import ApiError, envelope
from ..idempotency import begin_idempotency, complete_idempotency, if_match_version
from ..schemas import MembershipUpdate
from ...db.models import Membership
from ...services.audit_service import append_audit

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/memberships", tags=["memberships"])


def _data(row: Membership) -> dict:
    return {"id": str(row.id), "workspace_id": str(row.workspace_id),
            "user_id": str(row.user_id), "roles": list(row.roles),
            "active": row.active, "version": row.version}


async def _admin(session, principal, workspace_id):
    member = await load_membership(session, principal=principal, workspace_id=workspace_id)
    if "workspace_admin" not in member["roles"]:
        raise ApiError(403, "PERMISSION_DENIED", "workspace admin required")
    return member


@router.get("")
async def list_memberships(workspace_id: uuid.UUID, request: Request,
                           offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                           principal: Principal = Depends(get_principal)):
    async with tenant_scoped(workspace_id) as session:
        await _admin(session, principal, workspace_id)
        total = (await session.execute(select(func.count()).select_from(Membership).where(
            Membership.workspace_id == workspace_id))).scalar_one()
        rows = (await session.execute(select(Membership).where(Membership.workspace_id == workspace_id)
            .order_by(Membership.id).offset(offset).limit(limit))).scalars().all()
        data = {"items": [_data(row) for row in rows], "offset": offset, "limit": limit, "total": total}
    return envelope(data, request.state.request_id)


@router.patch("/{membership_id}")
async def update_membership(workspace_id: uuid.UUID, membership_id: uuid.UUID, payload: MembershipUpdate,
                            request: Request, response: Response,
                            principal: Principal = Depends(get_principal),
                            if_match: str | None = Header(None, alias="If-Match"),
                            idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    expected = if_match_version(if_match)
    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    body = payload.model_dump(mode="json")
    async with tenant_scoped(workspace_id) as session:
        member = await _admin(session, principal, workspace_id)
        # Serialize admin changes without requiring UPDATE privilege on workspaces.
        lock_id = int.from_bytes(sha256(f"membership-admin:{workspace_id}".encode()).digest()[:8], "big", signed=True)
        await session.execute(select(func.pg_advisory_xact_lock(lock_id)))
        row = (await session.execute(select(Membership).where(Membership.workspace_id == workspace_id,
            Membership.id == membership_id).with_for_update())).scalar_one_or_none()
        if row is None:
            raise ApiError(404, "NOT_FOUND", "membership not found")
        outcome = await begin_idempotency(session, workspace_id=workspace_id, actor_id=member["user_id"],
            operation_id="updateMembership", key=idempotency_key, body=body,
            target={"membership_id": str(membership_id)}, precondition=if_match)
        if outcome.replay and outcome.response is not None:
            response.headers["ETag"] = f'"{outcome.response["version"]}"'
            return envelope(outcome.response, request.state.request_id)
        if row.version != expected:
            raise ApiError(412, "STALE_REVISION", "membership version changed")
        new_roles = list(payload.roles)
        # At least one active admin must remain after this transaction.
        if row.active and "workspace_admin" in row.roles and (not payload.active or "workspace_admin" not in new_roles):
            count = (await session.execute(select(func.count()).select_from(Membership).where(
                Membership.workspace_id == workspace_id, Membership.active.is_(True),
                Membership.roles.any("workspace_admin")))).scalar_one()
            if count <= 1:
                raise ApiError(409, "LAST_ADMIN", "cannot remove the last active workspace admin")
        changed = row.roles != new_roles or row.active != payload.active
        if changed:
            row.roles = new_roles
            row.active = payload.active
            row.version += 1
            append_audit(session, workspace_id=workspace_id, actor_id=member["user_id"],
                         action="membership.updated", entity_type="membership", entity_id=row.id,
                         request_id=request.state.request_id, reason=payload.reason)
        data = _data(row)
        complete_idempotency(outcome, str(row.id), response=data)
        response.headers["ETag"] = f'"{row.version}"'
    return envelope(data, request.state.request_id)
