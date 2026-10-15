"""Manual evidence and durable local intentions, with current server authority."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Query, Request

from ..auth import Principal, get_principal
from ..deps import tenant_scoped
from ..errors import envelope
from ..lead_schemas import (
    EmptyLeadBody, LeadEnvelope, LeadEvidencePage, LeadIntentInput,
    LeadIntentPage, LeadIntentReceipt, LeadIntentView,
)
from ...services.lead_evidence_service import resolve_lead_scope, list_observations
from ...services.lead_intent_service import (
    prepare_intent, read_intent, list_intents, apply_intent, acknowledge_intent, cancel_intent,
)

router = APIRouter(
    prefix="/v1/workspaces/{workspace_id}/projects/{project_id}", tags=["lead-workflow"],
)


@router.get("/buyers/{buyer_id}/lead-evidence", operation_id="listLeadEvidence",
            name="listLeadEvidence", response_model=LeadEnvelope[LeadEvidencePage])
async def list_lead_evidence(
    workspace_id: uuid.UUID, project_id: uuid.UUID, buyer_id: uuid.UUID, request: Request,
    offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
    principal: Principal = Depends(get_principal),
):
    async with tenant_scoped(workspace_id) as session:
        scope = await resolve_lead_scope(session, workspace_id=workspace_id, project_id=project_id,
                                         buyer_id=buyer_id, principal=principal)
        result = await list_observations(session, scope, offset=offset, limit=limit, now=datetime.now(timezone.utc))
    return envelope(result, request.state.request_id)


@router.post("/lead-intents", status_code=201, operation_id="prepareLeadIntent",
             name="prepareLeadIntent", response_model=LeadEnvelope[LeadIntentView])
async def prepare_lead_intent(
    workspace_id: uuid.UUID, project_id: uuid.UUID, payload: LeadIntentInput, request: Request,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    principal: Principal = Depends(get_principal),
):
    async with tenant_scoped(workspace_id) as session:
        scope = await resolve_lead_scope(session, workspace_id=workspace_id, project_id=project_id,
                                         buyer_id=payload.buyer_id, principal=principal)
        result = await prepare_intent(session, scope=scope, data=payload, key=idempotency_key)
    return envelope(result, request.state.request_id)


@router.get("/lead-intents", operation_id="listLeadIntents", name="listLeadIntents",
            response_model=LeadEnvelope[LeadIntentPage])
async def list_lead_intents(
    workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request,
    offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
    principal: Principal = Depends(get_principal),
):
    async with tenant_scoped(workspace_id) as session:
        scope = await resolve_lead_scope(session, workspace_id=workspace_id, project_id=project_id,
                                         buyer_id=None, principal=principal)
        result = await list_intents(session, scope=scope, offset=offset, limit=limit, now=datetime.now(timezone.utc))
    return envelope(result, request.state.request_id)


@router.get("/lead-intents/{intent_id}", operation_id="getLeadIntent", name="getLeadIntent",
            response_model=LeadEnvelope[LeadIntentView])
async def get_lead_intent(
    workspace_id: uuid.UUID, project_id: uuid.UUID, intent_id: uuid.UUID, request: Request,
    principal: Principal = Depends(get_principal),
):
    async with tenant_scoped(workspace_id) as session:
        scope = await resolve_lead_scope(session, workspace_id=workspace_id, project_id=project_id,
                                         buyer_id=None, principal=principal)
        result = await read_intent(session, scope=scope, intent_id=intent_id, now=datetime.now(timezone.utc))
    return envelope(result, request.state.request_id)


@router.post("/lead-intents/{intent_id}/apply", operation_id="applyLeadIntent",
             name="applyLeadIntent", response_model=LeadEnvelope[LeadIntentReceipt])
async def apply_lead_intent(
    workspace_id: uuid.UUID, project_id: uuid.UUID, intent_id: uuid.UUID,
    payload: EmptyLeadBody, request: Request,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    if_match: str | None = Header(None, alias="If-Match"),
    principal: Principal = Depends(get_principal),
):
    async with tenant_scoped(workspace_id) as session:
        scope = await resolve_lead_scope(session, workspace_id=workspace_id, project_id=project_id,
                                         buyer_id=None, principal=principal)
        result = await apply_intent(session, scope=scope, intent_id=intent_id, key=idempotency_key,
                                   if_match=if_match, now=datetime.now(timezone.utc))
    return envelope(result, request.state.request_id)


@router.post("/lead-intents/{intent_id}/acknowledgements", operation_id="acknowledgeLeadIntent",
             name="acknowledgeLeadIntent", response_model=LeadEnvelope[LeadIntentView])
async def acknowledge_lead_intent(
    workspace_id: uuid.UUID, project_id: uuid.UUID, intent_id: uuid.UUID,
    payload: EmptyLeadBody, request: Request,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    principal: Principal = Depends(get_principal),
):
    async with tenant_scoped(workspace_id) as session:
        scope = await resolve_lead_scope(session, workspace_id=workspace_id, project_id=project_id,
                                         buyer_id=None, principal=principal)
        result = await acknowledge_intent(session, scope=scope, intent_id=intent_id,
                                          key=idempotency_key, now=datetime.now(timezone.utc))
    return envelope(result, request.state.request_id)


@router.post("/lead-intents/{intent_id}/cancel", operation_id="cancelLeadIntent",
             name="cancelLeadIntent", response_model=LeadEnvelope[LeadIntentView])
async def cancel_lead_intent(
    workspace_id: uuid.UUID, project_id: uuid.UUID, intent_id: uuid.UUID,
    payload: EmptyLeadBody, request: Request,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    principal: Principal = Depends(get_principal),
):
    async with tenant_scoped(workspace_id) as session:
        scope = await resolve_lead_scope(session, workspace_id=workspace_id, project_id=project_id,
                                         buyer_id=None, principal=principal)
        result = await cancel_intent(session, scope=scope, intent_id=intent_id,
                                    key=idempotency_key, now=datetime.now(timezone.utc))
    return envelope(result, request.state.request_id)
