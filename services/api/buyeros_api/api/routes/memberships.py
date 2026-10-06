"""Versioned management of existing verified tenant memberships only."""
import uuid

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import func, select

from ..auth import Principal, get_principal
from ..deps import load_membership, permission_for_roles, tenant_scoped
from ..errors import ApiError, envelope
from ..idempotency import begin_idempotency, complete_idempotency, if_match_version
from ..schemas import EligibleAssignee, MembershipRead, MembershipUpdate
from ...db.models import Membership, User
from ...services.membership_directory import directory_search, eligible_owner_predicate, member_display_name
from ...services.membership_admin import require_workspace_admin, lock_membership_admin, apply_membership_update

router = APIRouter(prefix="/v1/workspaces/{workspace_id}", tags=["memberships"])


def _data(row: Membership, name: str | None) -> dict:
    return MembershipRead(id=row.id, workspace_id=row.workspace_id, user_id=row.user_id,
        display_name=member_display_name(name,row.user_id), roles=row.roles,
        active=row.active, version=row.version).model_dump(mode="json")


async def _admin(session, principal, workspace_id):
    return await require_workspace_admin(session, principal, workspace_id)


async def _directory(session, workspace_id, q, offset, limit, *, eligible=False):
    query=select(Membership,User.display_name).join(User,User.id==Membership.user_id).where(
        Membership.workspace_id==workspace_id, directory_search(q))
    if eligible:
        query=query.where(eligible_owner_predicate(workspace_id))
    total=(await session.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows=(await session.execute(query.order_by(Membership.id).offset(offset).limit(limit))).all()
    items=[EligibleAssignee(membership_id=row.id,user_id=row.user_id,
        display_name=member_display_name(name,row.user_id),version=row.version).model_dump(mode="json")
        if eligible else _data(row,name) for row,name in rows]
    return {"items":items,"offset":offset,"limit":limit,"total":total}


@router.get("/memberships")
async def list_memberships(workspace_id: uuid.UUID, request: Request,
                           q: str = Query("",max_length=200),
                           offset: int = Query(0,ge=0), limit: int = Query(20,ge=1,le=100),
                           principal: Principal = Depends(get_principal)):
    async with tenant_scoped(workspace_id) as session:
        await _admin(session,principal,workspace_id)
        data=await _directory(session,workspace_id,q,offset,limit)
    return envelope(data,request.state.request_id)


@router.get("/eligible-assignees")
async def list_eligible_assignees(workspace_id: uuid.UUID, request: Request,
                                q: str = Query("",max_length=200),
                                offset: int = Query(0,ge=0), limit: int = Query(20,ge=1,le=100),
                                principal: Principal = Depends(get_principal)):
    async with tenant_scoped(workspace_id) as session:
        member=await load_membership(session,principal=principal,workspace_id=workspace_id)
        if not permission_for_roles(member["roles"],"assignBuyerOwners"):
            raise ApiError(403,"PERMISSION_DENIED","insufficient role")
        data=await _directory(session,workspace_id,q,offset,limit,eligible=True)
    return envelope(data,request.state.request_id)


@router.patch("/memberships/{membership_id}")
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
        await lock_membership_admin(session, workspace_id)
        member = await _admin(session, principal, workspace_id)
        row = (await session.execute(select(Membership).where(Membership.workspace_id == workspace_id,
            Membership.id == membership_id).with_for_update())).scalar_one_or_none()
        if row is None:
            raise ApiError(404, "NOT_FOUND", "membership not found")
        outcome = await begin_idempotency(session, workspace_id=workspace_id, actor_id=member["user_id"],
            operation_id="updateMembership", key=idempotency_key, body=body,
            target={"membership_id": str(membership_id)}, precondition=if_match)
        if outcome.replay and outcome.response is not None:
            data = dict(outcome.response)
            # Old durable responses retain their business result. Add only the new
            # read projection; do not rewrite historical idempotency records.
            if "display_name" not in data:
                name = (await session.execute(select(User.display_name).where(User.id == row.user_id))).scalar_one_or_none()
                data["display_name"] = member_display_name(name, row.user_id)
            response.headers["ETag"] = f'"{data["version"]}"'
            return envelope(data, request.state.request_id)
        if row.version != expected:
            raise ApiError(412, "STALE_REVISION", "membership version changed")
        await apply_membership_update(session, row, workspace_id=workspace_id,
            actor_id=member['user_id'], roles=list(payload.roles), active=payload.active,
            reason=payload.reason, request_id=request.state.request_id)
        name = (await session.execute(select(User.display_name).where(User.id == row.user_id))).scalar_one_or_none()
        data = _data(row, name)
        complete_idempotency(outcome, str(row.id), response=data)
        response.headers["ETag"] = f'"{row.version}"'
    return envelope(data, request.state.request_id)
