"""Contact job controls; the provider is never called from HTTP."""

import uuid

from fastapi import APIRouter, Depends, Header, Request, Response

from ..auth import Principal, get_principal
from ..deps import load_membership, permission_for_roles, tenant_scoped
from ..errors import ApiError, envelope
from ..idempotency import begin_idempotency, complete_idempotency, if_match_version
from ..schemas import ArchiveRequest, ReconcileRequest
from ...services.enrichment_service import cancel_job, job_data, require_job, queue_reconciliation

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/enrichment-jobs", tags=["contact jobs"])


@router.get("/{job_id}", name="getEnrichmentJob")
async def get_enrichment_job(workspace_id: uuid.UUID, job_id: uuid.UUID, request: Request,
                             response: Response, principal: Principal = Depends(get_principal)):
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "getEnrichmentJob"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        job, quote = await require_job(session, workspace_id, job_id,
                                       actor_id=member["user_id"],
                                       is_admin="workspace_admin" in member["roles"])
        data = await job_data(session, job, quote)
    response.headers["ETag"] = f'"{data["version"]}"'
    return envelope(data, request.state.request_id)


@router.post("/{job_id}/cancel", status_code=202, name="cancelEnrichmentJob")
async def cancel_enrichment_job(workspace_id: uuid.UUID, job_id: uuid.UUID,
                                payload: ArchiveRequest, request: Request, response: Response,
                                principal: Principal = Depends(get_principal),
                                idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                                if_match: str | None = Header(default=None, alias="If-Match")):
    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    version = if_match_version(if_match)
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "cancelEnrichmentJob"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=member["user_id"],
            operation_id=f"cancelEnrichmentJob:{job_id}", key=idempotency_key,
            body=payload.model_dump(), target={"job_id": str(job_id)}, precondition=if_match,
        )
        if outcome.replay and outcome.response is not None:
            data = outcome.response["data"]
        else:
            data = await cancel_job(session, workspace_id, job_id, member["user_id"],
                                    version=version, reason=payload.reason,
                                    is_admin="workspace_admin" in member["roles"])
            complete_idempotency(outcome, str(job_id),
                                 response={"http_status": 202, "data": data})
    response.headers["ETag"] = f'"{data["version"]}"'
    return envelope(data, request.state.request_id)


def selected_contact_status_capability():
    """No live provider has verified nonbillable status semantics."""
    return None, "production", False


@router.post("/{job_id}/reconcile", status_code=202, name="reconcileEnrichmentJob")
async def reconcile_enrichment_job(workspace_id: uuid.UUID, job_id: uuid.UUID,
                                   payload: ReconcileRequest, request: Request,
                                   principal: Principal = Depends(get_principal),
                                   idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                                   selection=Depends(selected_contact_status_capability)):
    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "reconcileEnrichmentJob"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=member["user_id"],
            operation_id=f"reconcileEnrichmentJob:{job_id}", key=idempotency_key,
            body=payload.model_dump(), target={"job_id": str(job_id)},
        )
        if outcome.replay and outcome.response is not None:
            data = outcome.response["data"]
        else:
            capability, environment, status_nonbillable = selection
            data = await queue_reconciliation(
                session, workspace_id, job_id, member["user_id"],
                reason=payload.reason, capability=capability,
                environment=environment, status_nonbillable=status_nonbillable,
            )
            complete_idempotency(outcome, data["id"], response={"http_status": 202, "data": data})
    return envelope(data, request.state.request_id)
