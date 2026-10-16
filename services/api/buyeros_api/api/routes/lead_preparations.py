"""Read only preparation views; all mutations use the durable local intent boundary."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request

from ..auth import Principal, get_principal
from ..deps import tenant_scoped
from ..errors import envelope
from ..lead_schemas import LeadEnvelope, LeadPreparationView, LeadPreparationPage, LeadPreparationRevisionPage
from ...services.lead_evidence_service import resolve_lead_scope
from ...services.lead_preparation_service import get_preparation, list_preparations, list_preparation_revisions

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/projects/{project_id}", tags=["lead-preparations"])


@router.get("/buyers/{buyer_id}/lead-preparations", name="listLeadPreparations",
            operation_id="listLeadPreparations", response_model=LeadEnvelope[LeadPreparationPage])
async def list_preparations_route(
    workspace_id: uuid.UUID, project_id: uuid.UUID, buyer_id: uuid.UUID, request: Request,
    offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
    principal: Principal = Depends(get_principal),
):
    async with tenant_scoped(workspace_id) as session:
        scope = await resolve_lead_scope(session, workspace_id=workspace_id, project_id=project_id,
                                         buyer_id=buyer_id, principal=principal)
        data = await list_preparations(session, scope=scope, offset=offset, limit=limit, now=datetime.now(timezone.utc))
    return envelope(data, request.state.request_id)


@router.get("/lead-preparations/{preparation_id}", name="getLeadPreparation",
            operation_id="getLeadPreparation", response_model=LeadEnvelope[LeadPreparationView])
async def get_preparation_route(
    workspace_id: uuid.UUID, project_id: uuid.UUID, preparation_id: uuid.UUID, request: Request,
    principal: Principal = Depends(get_principal),
):
    async with tenant_scoped(workspace_id) as session:
        scope = await resolve_lead_scope(session, workspace_id=workspace_id, project_id=project_id,
                                         buyer_id=None, principal=principal)
        data = await get_preparation(session, scope=scope, preparation_id=preparation_id, now=datetime.now(timezone.utc))
    return envelope(data, request.state.request_id)


@router.get("/lead-preparations/{preparation_id}/revisions", name="listLeadPreparationRevisions",
            operation_id="listLeadPreparationRevisions", response_model=LeadEnvelope[LeadPreparationRevisionPage])
async def list_preparation_revisions_route(
    workspace_id: uuid.UUID, project_id: uuid.UUID, preparation_id: uuid.UUID, request: Request,
    offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
    principal: Principal = Depends(get_principal),
):
    async with tenant_scoped(workspace_id) as session:
        scope = await resolve_lead_scope(session, workspace_id=workspace_id, project_id=project_id,
                                         buyer_id=None, principal=principal)
        data = await list_preparation_revisions(session, scope=scope, preparation_id=preparation_id,
                                                offset=offset, limit=limit, now=datetime.now(timezone.utc))
    return envelope(data, request.state.request_id)
