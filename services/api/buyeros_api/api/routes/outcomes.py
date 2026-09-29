"""Current-membership manual outcomes; corrections append immutable history."""
import uuid

from fastapi import APIRouter, Depends, Header, Query, Request, Response

from ..auth import Principal, get_principal
from ..deps import load_membership, permission_for_roles, tenant_scoped
from ..errors import ApiError, envelope
from ..idempotency import begin_idempotency, complete_idempotency, if_match_version
from ..schemas import OutcomeCreateRequest, OutcomeCorrectionRequest
from ...services.outcome_service import (correct_outcome, list_outcomes, load_outcome,
                                         outcome_data, record_outcome)

router = APIRouter(prefix="/v1/workspaces/{workspace_id}", tags=["outcomes"])


@router.get("/projects/{project_id}/outcomes")
async def list_project_outcomes(workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request,
                                offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                                principal: Principal = Depends(get_principal)):
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "listOutcomes"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        data = await list_outcomes(session, workspace_id=workspace_id, project_id=project_id,
                                   offset=offset, limit=limit)
    return envelope(data, request.state.request_id)


@router.post("/projects/{project_id}/outcomes", status_code=201)
async def record_manual_outcome(workspace_id: uuid.UUID, project_id: uuid.UUID,
                                payload: OutcomeCreateRequest, request: Request, response: Response,
                                principal: Principal = Depends(get_principal),
                                idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "recordOutcome"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        outcome = await begin_idempotency(session, workspace_id=workspace_id,
            actor_id=member["user_id"], operation_id="recordOutcome", key=idempotency_key,
            body=payload.model_dump(mode="json"),
            target={"workspace_id": str(workspace_id), "project_id": str(project_id)})
        if outcome.replay:
            if not outcome.record.resource_id:
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "legacy replay requires a new key")
            event = await load_outcome(session, workspace_id=workspace_id,
                outcome_id=uuid.UUID(outcome.record.resource_id), project_id=project_id)
        else:
            event = await record_outcome(session, workspace_id=workspace_id,
                project_id=project_id, actor_id=member["user_id"], request=payload)
            complete_idempotency(outcome, str(event.id))
        data = outcome_data(event)
        response.headers["ETag"] = f'"{event.version}"'
    return envelope(data, request.state.request_id)


@router.post("/outcomes/{outcome_id}/corrections", status_code=201)
async def correct_manual_outcome(workspace_id: uuid.UUID, outcome_id: uuid.UUID,
                                 payload: OutcomeCorrectionRequest, request: Request, response: Response,
                                 principal: Principal = Depends(get_principal),
                                 idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                                 if_match: str | None = Header(default=None, alias="If-Match")):
    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    expected_version = if_match_version(if_match)
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "correctOutcome"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        outcome = await begin_idempotency(session, workspace_id=workspace_id,
            actor_id=member["user_id"], operation_id="correctOutcome", key=idempotency_key,
            body=payload.model_dump(mode="json"),
            target={"workspace_id": str(workspace_id), "outcome_id": str(outcome_id)},
            precondition=if_match)
        if outcome.replay:
            if not outcome.record.resource_id:
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "legacy replay requires a new key")
            event = await load_outcome(session, workspace_id=workspace_id,
                outcome_id=uuid.UUID(outcome.record.resource_id))
        else:
            event = await correct_outcome(session, workspace_id=workspace_id,
                outcome_id=outcome_id, actor_id=member["user_id"], request=payload,
                expected_version=expected_version)
            complete_idempotency(outcome, str(event.id))
        data = outcome_data(event)
        response.headers["ETag"] = f'"{event.version}"'
    return envelope(data, request.state.request_id)
