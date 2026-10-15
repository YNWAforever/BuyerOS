"""Read-only planning/accounting views. Local writes use the existing lead intent boundary."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, Request

from ..auth import Principal, get_principal
from ..deps import tenant_scoped
from ..errors import envelope
from ..lead_schemas import LeadEnvelope, PilotBudgetView, PilotCostPage
from ...services.lead_evidence_service import resolve_lead_scope
from ...services.pilot_budget_service import project_pilot_budget, list_pilot_cost_events

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/projects/{project_id}", tags=["pilot-budget"])


@router.get("/pilot-budget", name="getPilotBudget", operation_id="getPilotBudget",
            response_model=LeadEnvelope[PilotBudgetView])
async def pilot_budget(
    workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request,
    principal: Principal = Depends(get_principal),
):
    async with tenant_scoped(workspace_id) as session:
        scope = await resolve_lead_scope(session, workspace_id=workspace_id, project_id=project_id,
                                         buyer_id=None, principal=principal)
        data = await project_pilot_budget(session, scope=scope, now=datetime.now(timezone.utc))
    return envelope(data, request.state.request_id)


@router.get("/pilot-cost-events", name="listPilotCostEvents", operation_id="listPilotCostEvents",
            response_model=LeadEnvelope[PilotCostPage])
async def pilot_cost_events(
    workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request,
    offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
    principal: Principal = Depends(get_principal),
):
    async with tenant_scoped(workspace_id) as session:
        scope = await resolve_lead_scope(session, workspace_id=workspace_id, project_id=project_id,
                                         buyer_id=None, principal=principal)
        data = await list_pilot_cost_events(session, scope=scope, offset=offset, limit=limit, now=datetime.now(timezone.utc))
    return envelope(data, request.state.request_id)
