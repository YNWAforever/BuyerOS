"""Reconciled project usage for one explicit UTC period."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request

from ..auth import Principal, get_principal
from ..deps import load_membership, permission_for_roles, tenant_scoped
from ..errors import ApiError, envelope
from ...services.usage import get_usage

router=APIRouter(prefix="/v1/workspaces/{workspace_id}",tags=["usage"])


@router.get("/projects/{project_id}/usage")
async def get_project_usage(workspace_id:uuid.UUID,project_id:uuid.UUID,request:Request,
                            from_utc:datetime=Query(alias="from"),to_utc:datetime=Query(alias="to"),
                            principal:Principal=Depends(get_principal)):
    async with tenant_scoped(workspace_id) as session:
        member=await load_membership(session,principal=principal,workspace_id=workspace_id)
        if not permission_for_roles(member["roles"],"getUsage"):
            raise ApiError(403,"PERMISSION_DENIED","insufficient role")
        data=await get_usage(session,workspace_id=workspace_id,project_id=project_id,
            from_utc=from_utc,to_utc=to_utc,as_of=datetime.now(timezone.utc))
    return envelope(data,request.state.request_id)
