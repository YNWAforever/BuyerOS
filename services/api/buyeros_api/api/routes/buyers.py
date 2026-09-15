import uuid

from fastapi import APIRouter, Depends, Request

from ..auth import Principal, get_principal
from ..errors import ApiError, envelope

router = APIRouter(prefix="/v1/workspaces/{workspace_id}", tags=["buyers"])


def _buyer_data(buyer, company) -> dict:
    return {"id": str(buyer.id), "project_id": str(buyer.project_id), "company": company.display_name, "note": buyer.note}


@router.get("/projects/{project_id}/buyers")
async def list_buyers(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(get_principal),
) -> dict:
    from sqlalchemy import select

    from ...db.buyers import BuyerSnapshot, BuyerSnapshotItem, Company, ProjectBuyer
    from ..deps import load_membership, permission_for_roles, tenant_scoped

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
        items = [_buyer_data(buyer, company) for buyer, company in rows]
        data = {
            "items": items,
            "snapshot_id": str(snapshot_id),
            "offset": 0,
            "limit": len(items),
            "total": len(items),
            "expires_at": snapshot.expires_at.isoformat() if snapshot.expires_at else None,
        }
    return envelope(data, request.state.request_id)


@router.get("/buyers/{buyer_id}")
async def get_buyer(
    workspace_id: uuid.UUID, buyer_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)
) -> dict:
    from sqlalchemy import select

    from ...db.buyers import Company, ProjectBuyer
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
        data = _buyer_data(buyer, company)
    return envelope(data, request.state.request_id)
