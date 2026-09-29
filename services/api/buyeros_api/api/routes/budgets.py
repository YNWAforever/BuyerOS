"""Budget read model and explicitly authorized, versioned limit changes."""
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import func, select

from ..auth import Principal, get_principal
from ..deps import load_membership, permission_for_roles, tenant_scoped
from ..errors import ApiError, envelope
from ..idempotency import begin_idempotency, complete_idempotency, if_match_version
from ..schemas import BudgetUpdate
from ...db.budget import BudgetAccount
from ...db.icp import Project
from ...services.audit_service import append_audit
from ...services.budget_service import (CATEGORIES, _money, _held, budget_data,
                                        ensure_period_accounts, lock_budget_workspace)

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/budgets", tags=["budgets"])


@router.get("")
async def list_budgets(workspace_id: uuid.UUID, request: Request,
                       offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                       principal: Principal = Depends(get_principal)):
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "listBudgets"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        await lock_budget_workspace(session, workspace_id)
        projects = (await session.execute(select(Project.id).where(Project.workspace_id == workspace_id))).scalars().all()
        await ensure_period_accounts(session, workspace_id, None, None, None)
        for project_id in projects:
            await ensure_period_accounts(session, workspace_id, project_id, None, None)
            for category in sorted(CATEGORIES):
                await ensure_period_accounts(session, workspace_id, project_id, None, category)
        rows = (await session.execute(select(BudgetAccount).where(BudgetAccount.workspace_id == workspace_id)
            .order_by(BudgetAccount.period_start.desc(), BudgetAccount.scope, BudgetAccount.scope_id,
                      BudgetAccount.category, BudgetAccount.id)
            .offset(offset).limit(limit))).scalars().all()
        total = (await session.execute(select(func.count()).select_from(BudgetAccount).where(
            BudgetAccount.workspace_id == workspace_id))).scalar_one()
        items = [await budget_data(session, row) for row in rows]
    return envelope({"items": items, "offset": offset, "limit": limit, "total": total}, request.state.request_id)


@router.patch("/{budget_id}")
async def update_budget(workspace_id: uuid.UUID, budget_id: uuid.UUID, payload: BudgetUpdate,
                        request: Request, response: Response, principal: Principal = Depends(get_principal),
                        if_match: str | None = Header(None, alias="If-Match"),
                        idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "updateBudget"):
            raise ApiError(403, "PERMISSION_DENIED", "workspace admin required")
        version = if_match_version(if_match)
        if not idempotency_key:
            raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
        await lock_budget_workspace(session, workspace_id)
        row = (await session.execute(select(BudgetAccount).where(
            BudgetAccount.workspace_id == workspace_id, BudgetAccount.id == budget_id
        ).with_for_update())).scalar_one_or_none()
        if row is None:
            raise ApiError(404, "NOT_FOUND", "budget account not found")
        outcome = await begin_idempotency(session, workspace_id=workspace_id, actor_id=member["user_id"],
            operation_id="updateBudget", key=idempotency_key, body=payload.model_dump(mode="json"),
            target={"budget_id": str(budget_id)}, precondition=if_match)
        if outcome.replay:
            if outcome.response is None:
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "legacy replay requires a new key")
            response.headers["ETag"] = f'"{outcome.response["version"]}"'
            return envelope(outcome.response["data"], request.state.request_id)
        if row.version != version:
            raise ApiError(412, "STALE_REVISION", "budget version changed")
        new_limit = _money(Decimal(payload.approved_limit.amount))
        held, _ = await _held(session, row)
        if new_limit < row.settled_spend + held:
            raise ApiError(409, "BUDGET_LIMIT", "limit cannot fall below settled plus held cost")
        if row.approved_limit != new_limit:
            row.approved_limit = new_limit
            row.version += 1
            await session.flush()
            await session.refresh(row)
            append_audit(session, workspace_id=workspace_id, actor_id=member["user_id"],
                         action="budget.limit_updated", entity_type="budget_account", entity_id=row.id,
                         request_id=request.state.request_id, reason=payload.reason)
        data = await budget_data(session, row)
        complete_idempotency(outcome, str(row.id),
                             response={"version": row.version, "data": data})
        response.headers["ETag"] = f'"{row.version}"'
    return envelope(data, request.state.request_id)
