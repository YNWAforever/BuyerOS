import uuid

from fastapi import APIRouter, Depends, Header, Query, Request, Response

from ..auth import Principal, get_principal
from ..errors import ApiError, envelope
from ..schemas import SnapshotCreate

router = APIRouter(prefix="/v1/workspaces/{workspace_id}", tags=["buyers"])


@router.get("/projects/{project_id}/buyers")
async def list_buyers(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    request: Request,
    offset: int = Query(default=0, ge=0),
    limit: int = 20,
    principal: Principal = Depends(get_principal),
) -> dict:
    from datetime import datetime, timezone

    from sqlalchemy import select

    from ...db.buyers import BuyerSnapshot, BuyerSnapshotItem, Company, ProjectBuyer
    from ...services.buyer_read import view
    from ..deps import load_membership, permission_for_roles, tenant_scoped

    limit = max(1, min(100, limit))
    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "listBuyers"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        # The contract reads a page from a server-owned immutable snapshot, not a live query.
        snapshot = (
            await session.execute(
                select(BuyerSnapshot).where(
                    BuyerSnapshot.workspace_id == workspace_id,
                    BuyerSnapshot.project_id == project_id,
                    BuyerSnapshot.id == snapshot_id,
                )
            )
        ).scalar_one_or_none()
        if snapshot is None:
            raise ApiError(404, "NOT_FOUND", "buyer snapshot not found")
        if snapshot.expires_at is not None and snapshot.expires_at <= datetime.now(timezone.utc):
            raise ApiError(404, "NOT_FOUND", "buyer snapshot not found")
        rows = (
            await session.execute(
                select(ProjectBuyer, Company)
                .join(Company, (Company.workspace_id == ProjectBuyer.workspace_id) & (Company.id == ProjectBuyer.company_id))
                .join(
                    BuyerSnapshotItem,
                    (BuyerSnapshotItem.workspace_id == ProjectBuyer.workspace_id)
                    & (BuyerSnapshotItem.buyer_id == ProjectBuyer.id),
                )
                .where(
                    BuyerSnapshotItem.workspace_id == workspace_id,
                    BuyerSnapshotItem.snapshot_id == snapshot_id,
                )
                .order_by(BuyerSnapshotItem.ordinal)
            )
        ).all()
        total = len(rows)
        page = rows[offset : offset + limit]
        items = [
            await view(session, workspace_id=workspace_id, buyer=buyer, company=company)
            for buyer, company in page
        ]
        data = {
            "items": items,
            "snapshot_id": str(snapshot_id),
            "offset": offset,
            "limit": limit,
            "total": total,
            "expires_at": snapshot.expires_at.isoformat() if snapshot.expires_at else None,
        }
    return envelope(data, request.state.request_id)


@router.get("/buyers/{buyer_id}")
async def get_buyer(
    workspace_id: uuid.UUID, buyer_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)
) -> dict:
    from sqlalchemy import select

    from ...db.buyers import Company, ProjectBuyer
    from ...services.buyer_read import view
    from ..deps import load_membership, permission_for_roles, tenant_scoped

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "getBuyer"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        row = (
            await session.execute(
                select(ProjectBuyer, Company)
                .join(
                    Company,
                    (Company.workspace_id == ProjectBuyer.workspace_id) & (Company.id == ProjectBuyer.company_id),
                )
                .where(ProjectBuyer.workspace_id == workspace_id, ProjectBuyer.id == buyer_id)
            )
        ).one_or_none()
        if row is None:
            raise ApiError(404, "NOT_FOUND", "buyer not found")
        buyer, company = row
        data = await view(session, workspace_id=workspace_id, buyer=buyer, company=company)
    return envelope(data, request.state.request_id)


@router.post("/projects/{project_id}/buyer-snapshots", status_code=201)
async def create_buyer_snapshot(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    payload: SnapshotCreate,
    request: Request,
    response: Response,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    from ...db.buyers import BuyerSnapshot, BuyerSnapshotItem
    from ...db.icp import Project
    from ...services.buyer_selection import filters_hash, materialize
    from ...services.buyer_view import snapshot_data
    from ..deps import load_membership, permission_for_roles, tenant_scoped
    from ..idempotency import begin_idempotency, complete_idempotency

    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    body = payload.model_dump(mode="json")

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "createBuyerSnapshot"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        project = (
            await session.execute(
                select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id)
            )
        ).scalar_one_or_none()
        if project is None:
            raise ApiError(404, "NOT_FOUND", "project not found")
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=membership["user_id"],
            operation_id="createBuyerSnapshot", key=idempotency_key, body=body,
        )
        if outcome.replay and outcome.response is not None:
            return envelope(outcome.response, request.state.request_id)
        ordered, matched, clipped = await materialize(
            session, workspace_id=workspace_id, project_id=project_id,
            filters=body["filters"], sort=body["sort"], limit=body["requested_limit"],
        )
        snapshot = BuyerSnapshot(
            workspace_id=workspace_id, project_id=project_id,
            filter_hash=filters_hash(body["filters"], body["sort"]),
            actor_user_id=membership["user_id"],
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        )
        session.add(snapshot)
        await session.flush()
        for ordinal, (buyer_id, buyer_version) in enumerate(ordered):
            session.add(
                BuyerSnapshotItem(
                    workspace_id=workspace_id, snapshot_id=snapshot.id,
                    ordinal=ordinal, buyer_id=buyer_id, buyer_version=buyer_version,
                )
            )
        await session.flush()
        data = snapshot_data(snapshot, sort=body["sort"], total=len(ordered), result_limit_reached=clipped)
        complete_idempotency(outcome, str(snapshot.id), response=data)
    return envelope(data, request.state.request_id)
