"""T09 buyer lists and actor-scoped saved filters on the existing domain API."""
import uuid

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from ..auth import Principal, get_principal
from ..deps import load_membership, permission_for_roles, tenant_scoped
from ..errors import ApiError, envelope
from ..idempotency import begin_idempotency, complete_idempotency, if_match_version
from ..schemas import ListMembershipRequest, ListWrite, OwnerAssignRequest, PresetWrite
from ...db.buyers import BuyerList, FilterPreset
from ...db.icp import Project
from ...services.buyer_review import _resolve_items
from ...services.bulk_service import create_bulk_job, job_data
from ...services.buyer_management import (
    assign_owners, buyer_list_data, change_memberships, get_list, preset_data, validate_preset_filters,
)

router = APIRouter(prefix="/v1/workspaces/{workspace_id}", tags=["buyer-management"])


async def _member(session, principal, workspace_id, operation):
    member = await load_membership(session, principal=principal, workspace_id=workspace_id)
    if not permission_for_roles(member["roles"], operation):
        raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
    return member


async def _project(session, workspace_id, project_id):
    row = (await session.execute(select(Project.id).where(
        Project.workspace_id == workspace_id, Project.id == project_id,
    ))).scalar_one_or_none()
    if row is None:
        raise ApiError(404, "NOT_FOUND", "project not found")


def _replayed_bulk(outcome, response):
    stored = outcome.response
    if stored.get("http_status") == 202:
        response.status_code = 202
        return stored["data"]
    return stored


def _key(value):
    if not value:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    return value


@router.post("/projects/{project_id}/buyer-owner-assignments")
async def assign_buyer_owners(
    workspace_id: uuid.UUID, project_id: uuid.UUID, payload: OwnerAssignRequest,
    request: Request, response: Response, principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    body = payload.model_dump(mode="json")
    async with tenant_scoped(workspace_id) as session:
        member = await _member(session, principal, workspace_id, "assignBuyerOwners")
        await _project(session, workspace_id, project_id)
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=member["user_id"],
            operation_id="assignBuyerOwners", key=_key(idempotency_key), body=body,
            target={"project_id": str(project_id)},
        )
        if outcome.replay and outcome.response is not None:
            return envelope(_replayed_bulk(outcome, response), request.state.request_id)
        pairs = await _resolve_items(session, workspace_id=workspace_id, project_id=project_id,
                                     actor_user_id=member["user_id"], selection=body["selection"])
        if len(pairs) > 100:
            job = await create_bulk_job(
                session, workspace_id=workspace_id, project_id=project_id,
                actor_user_id=member["user_id"], operation="assignBuyerOwners",
                selection=body["selection"], command={
                    "owner_membership_id": body["owner_membership_id"], "reason": body["reason"],
                },
            )
            data = job_data(job)
            response.status_code = 202
            complete_idempotency(outcome, str(job.id), response={"http_status": 202, "data": data})
        else:
            data = await assign_owners(
                session, workspace_id=workspace_id, project_id=project_id,
                actor_user_id=member["user_id"], selection=body["selection"],
                owner_membership_id=payload.owner_membership_id, reason=payload.reason,
            )
            complete_idempotency(outcome, str(project_id), response=data)
    return envelope(data, request.state.request_id)


@router.get("/projects/{project_id}/lists")
async def list_buyer_lists(
    workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request,
    offset: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=100),
    principal: Principal = Depends(get_principal),
):
    async with tenant_scoped(workspace_id) as session:
        await _member(session, principal, workspace_id, "listBuyerLists")
        await _project(session, workspace_id, project_id)
        base = (BuyerList.workspace_id == workspace_id, BuyerList.project_id == project_id)
        total = (await session.execute(select(func.count()).select_from(BuyerList).where(*base))).scalar_one()
        rows = (await session.execute(
            select(BuyerList).where(*base).order_by(BuyerList.created_at.desc(), BuyerList.id.desc())
            .offset(offset).limit(limit)
        )).scalars().all()
        items = [await buyer_list_data(session, row) for row in rows]
    return envelope({"items": items, "offset": offset, "limit": limit, "total": total}, request.state.request_id)


@router.post("/projects/{project_id}/lists", status_code=201)
async def create_buyer_list(
    workspace_id: uuid.UUID, project_id: uuid.UUID, payload: ListWrite, request: Request,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    body = payload.model_dump(mode="json")
    async with tenant_scoped(workspace_id) as session:
        member = await _member(session, principal, workspace_id, "createBuyerList")
        await _project(session, workspace_id, project_id)
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=member["user_id"],
            operation_id="createBuyerList", key=_key(idempotency_key), body=body,
            target={"project_id": str(project_id)},
        )
        if outcome.replay and outcome.response is not None:
            return envelope(outcome.response, request.state.request_id)
        item = BuyerList(workspace_id=workspace_id, project_id=project_id, name=payload.name, version=1)
        session.add(item)
        await session.flush()
        await session.refresh(item)
        data = await buyer_list_data(session, item)
        complete_idempotency(outcome, str(item.id), response=data)
    return envelope(data, request.state.request_id)


@router.get("/lists/{list_id}")
async def get_buyer_list(
    workspace_id: uuid.UUID, list_id: uuid.UUID, request: Request,
    principal: Principal = Depends(get_principal),
):
    async with tenant_scoped(workspace_id) as session:
        await _member(session, principal, workspace_id, "getBuyerList")
        item = await get_list(session, workspace_id=workspace_id, list_id=list_id)
        data = await buyer_list_data(session, item)
    return envelope(data, request.state.request_id)


@router.patch("/lists/{list_id}")
async def rename_buyer_list(
    workspace_id: uuid.UUID, list_id: uuid.UUID, payload: ListWrite, request: Request, response: Response,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
):
    expected = if_match_version(if_match)
    body = payload.model_dump(mode="json")
    async with tenant_scoped(workspace_id) as session:
        member = await _member(session, principal, workspace_id, "renameBuyerList")
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=member["user_id"],
            operation_id="renameBuyerList", key=_key(idempotency_key), body=body,
            target={"list_id": str(list_id)}, precondition=if_match,
        )
        if outcome.replay and outcome.response is not None:
            response.headers["ETag"] = f'"{outcome.response["version"]}"'
            return envelope(outcome.response, request.state.request_id)
        item = await get_list(session, workspace_id=workspace_id, list_id=list_id, lock=True)
        if item.version != expected:
            raise ApiError(412, "STALE_REVISION", "buyer list changed; reload it")
        item.name = payload.name
        item.version += 1
        await session.flush()
        await session.refresh(item)
        data = await buyer_list_data(session, item)
        complete_idempotency(outcome, str(item.id), response=data)
        response.headers["ETag"] = f'"{item.version}"'
    return envelope(data, request.state.request_id)


@router.post("/lists/{list_id}/memberships")
async def change_list_memberships(
    workspace_id: uuid.UUID, list_id: uuid.UUID, payload: ListMembershipRequest, request: Request,
    response: Response, principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
):
    expected = if_match_version(if_match)
    body = payload.model_dump(mode="json")
    async with tenant_scoped(workspace_id) as session:
        member = await _member(session, principal, workspace_id, "changeListMemberships")
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=member["user_id"],
            operation_id="changeListMemberships", key=_key(idempotency_key), body=body,
            target={"list_id": str(list_id)}, precondition=if_match,
        )
        if outcome.replay and outcome.response is not None:
            return envelope(_replayed_bulk(outcome, response), request.state.request_id)
        item = await get_list(session, workspace_id=workspace_id, list_id=list_id, lock=True)
        if item.version != expected:
            raise ApiError(412, "STALE_REVISION", "buyer list changed; reload it")
        pairs = await _resolve_items(session, workspace_id=workspace_id, project_id=item.project_id,
                                     actor_user_id=member["user_id"], selection=body["selection"])
        if len(pairs) > 100:
            job = await create_bulk_job(
                session, workspace_id=workspace_id, project_id=item.project_id,
                actor_user_id=member["user_id"], operation="changeListMemberships",
                selection=body["selection"],
                command={"list_id": str(item.id), "operation": body["operation"]},
            )
            data = job_data(job)
            response.status_code = 202
            complete_idempotency(outcome, str(job.id), response={"http_status": 202, "data": data})
        else:
            data = await change_memberships(
                session, item=item, actor_user_id=member["user_id"],
                selection=body["selection"], operation=body["operation"],
            )
            complete_idempotency(outcome, str(item.id), response=data)
    return envelope(data, request.state.request_id)


@router.get("/projects/{project_id}/filter-presets")
async def list_filter_presets(
    workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request,
    offset: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=100),
    principal: Principal = Depends(get_principal),
):
    async with tenant_scoped(workspace_id) as session:
        member = await _member(session, principal, workspace_id, "listFilterPresets")
        await _project(session, workspace_id, project_id)
        scope = (FilterPreset.workspace_id == workspace_id, FilterPreset.project_id == project_id,
                 FilterPreset.actor_user_id == member["user_id"])
        total = (await session.execute(select(func.count()).select_from(FilterPreset).where(*scope))).scalar_one()
        rows = (await session.execute(
            select(FilterPreset).where(*scope).order_by(FilterPreset.created_at.desc(), FilterPreset.id.desc())
            .offset(offset).limit(limit)
        )).scalars().all()
        items = [preset_data(item) for item in rows]
    return envelope({"items": items, "offset": offset, "limit": limit, "total": total}, request.state.request_id)


@router.post("/projects/{project_id}/filter-presets", status_code=201)
async def save_filter_preset(
    workspace_id: uuid.UUID, project_id: uuid.UUID, payload: PresetWrite, request: Request,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    filters = payload.filters.model_dump(mode="json", exclude_none=True)
    validate_preset_filters(filters)
    body = {"name": payload.name, "filters": filters, "sort": payload.sort}
    async with tenant_scoped(workspace_id) as session:
        member = await _member(session, principal, workspace_id, "saveFilterPreset")
        await _project(session, workspace_id, project_id)
        if filters.get("list_id"):
            try:
                parsed_list_id = uuid.UUID(filters["list_id"])
            except (ValueError, TypeError, AttributeError) as exc:
                raise ApiError(422, "INVALID_REQUEST", "list_id must be a UUID") from exc
            chosen_list = await get_list(session, workspace_id=workspace_id, list_id=parsed_list_id)
            if chosen_list.project_id != project_id:
                raise ApiError(404, "NOT_FOUND", "buyer list not found")
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=member["user_id"],
            operation_id="saveFilterPreset", key=_key(idempotency_key), body=body,
            target={"project_id": str(project_id)},
        )
        if outcome.replay and outcome.response is not None:
            return envelope(outcome.response, request.state.request_id)
        statement = insert(FilterPreset).values(
            id=uuid.uuid4(), workspace_id=workspace_id, project_id=project_id,
            actor_user_id=member["user_id"], name=payload.name,
            filters=filters, sort=payload.sort, version=1,
        ).on_conflict_do_update(
            constraint="uq_filter_presets_actor_name",
            set_={"filters": filters, "sort": payload.sort,
                  "version": FilterPreset.version + 1, "updated_at": func.now()},
        ).returning(FilterPreset.id)
        preset_id = (await session.execute(statement)).scalar_one()
        item = (await session.execute(select(FilterPreset).where(
            FilterPreset.workspace_id == workspace_id, FilterPreset.id == preset_id,
        ))).scalar_one()
        data = preset_data(item)
        complete_idempotency(outcome, str(item.id), response=data)
    return envelope(data, request.state.request_id)
