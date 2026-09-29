"""Redacted, paged tenant audit trail for current workspace admins."""
import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select

from ..auth import Principal, get_principal
from ..deps import load_membership, tenant_scoped
from ..errors import ApiError, envelope
from ...db.outcomes import AuditEvent
from ...services.audit_service import append_audit, audit_data

router = APIRouter(prefix="/v1/workspaces/{workspace_id}", tags=["audit"])


@router.get("/audit-events")
async def list_audit_events(workspace_id: uuid.UUID, request: Request,
                            offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                            action: str | None = Query(None, max_length=64),
                            principal: Principal = Depends(get_principal)):
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if "workspace_admin" not in member["roles"]:
            raise ApiError(403, "PERMISSION_DENIED", "workspace admin required")
        conditions = [AuditEvent.workspace_id == workspace_id]
        if action:
            conditions.append(AuditEvent.action == action)
        total = (await session.execute(select(func.count()).select_from(AuditEvent).where(*conditions))).scalar_one()
        rows = (await session.execute(select(AuditEvent).where(*conditions)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .offset(offset).limit(limit))).scalars().all()
        data = {"items": [audit_data(row) for row in rows],
                "offset": offset, "limit": limit, "total": total}
        append_audit(session, workspace_id=workspace_id, actor_id=member["user_id"],
                     action="audit.viewed", entity_type="workspace", entity_id=workspace_id,
                     request_id=request.state.request_id)
    return envelope(data, request.state.request_id)
