"""Authenticated export creation, status and revocable content endpoints."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Request, Response

from ..auth import Principal, get_principal
from ..deps import load_membership, permission_for_roles, tenant_scoped
from ..errors import ApiError, envelope
from ..idempotency import begin_idempotency, complete_idempotency, if_match_version
from ..schemas import BuyerExportRequest, DraftExportRequest
from ...services.audit_service import append_audit
from ...services.export_service import (authorize_export_content, create_buyer_export,
                                        create_bulk_failure_export, create_draft_export, job_data,
                                        load_actor_export)

router = APIRouter(prefix="/v1/workspaces/{workspace_id}", tags=["exports"])


@router.post("/projects/{project_id}/exports", status_code=202)
async def export_buyers(workspace_id: uuid.UUID, project_id: uuid.UUID,
                        payload: BuyerExportRequest, request: Request,
                        principal: Principal = Depends(get_principal),
                        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> dict:
    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "exportBuyers"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        outcome = await begin_idempotency(session, workspace_id=workspace_id,
            actor_id=member["user_id"], operation_id="exportBuyers", key=idempotency_key,
            body=payload.model_dump(mode="json"),
            target={"workspace_id": str(workspace_id), "project_id": str(project_id)})
        if outcome.replay:
            if not outcome.record.resource_id:
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "legacy replay requires a new key")
            current = await authorize_export_content(session, workspace_id=workspace_id,
                actor_id=member["user_id"], export_id=uuid.UUID(outcome.record.resource_id))
            return envelope(job_data(current["job"]), request.state.request_id)
        job = await create_buyer_export(session, workspace_id=workspace_id,
            project_id=project_id, actor_id=member["user_id"], request=payload)
        data = job_data(job)
        complete_idempotency(outcome, str(job.id), response={"http_status": 202, "data": data})
    return envelope(data, request.state.request_id)


@router.post("/drafts/{draft_id}/exports", status_code=202)
async def export_draft(workspace_id: uuid.UUID, draft_id: uuid.UUID,
                       payload: DraftExportRequest, request: Request,
                       principal: Principal = Depends(get_principal),
                       idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                       if_match: str | None = Header(default=None, alias="If-Match")) -> dict:
    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    expected_version = if_match_version(if_match)
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "exportDraft"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        outcome = await begin_idempotency(session, workspace_id=workspace_id,
            actor_id=member["user_id"], operation_id="exportDraft", key=idempotency_key,
            body=payload.model_dump(mode="json"),
            target={"workspace_id": str(workspace_id), "draft_id": str(draft_id)},
            precondition=if_match)
        if outcome.replay:
            if not outcome.record.resource_id:
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "legacy replay requires a new key")
            current = await authorize_export_content(session, workspace_id=workspace_id,
                actor_id=member["user_id"], export_id=uuid.UUID(outcome.record.resource_id))
            return envelope(job_data(current["job"]), request.state.request_id)
        job = await create_draft_export(session, workspace_id=workspace_id,
            draft_id=draft_id, actor_id=member["user_id"], request=payload,
            expected_version=expected_version)
        data = job_data(job)
        complete_idempotency(outcome, str(job.id), response={"http_status": 202, "data": data})
    return envelope(data, request.state.request_id)


@router.post("/jobs/{job_id}/exports", status_code=202)
async def export_bulk_failures(workspace_id: uuid.UUID, job_id: uuid.UUID, request: Request,
                               principal: Principal = Depends(get_principal),
                               idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> dict:
    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "exportBulkFailures"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        outcome = await begin_idempotency(session, workspace_id=workspace_id,
            actor_id=member["user_id"], operation_id="exportBulkFailures", key=idempotency_key,
            body={}, target={"workspace_id": str(workspace_id), "job_id": str(job_id)})
        if outcome.replay:
            if not outcome.record.resource_id:
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "legacy replay requires a new key")
            current = await authorize_export_content(session, workspace_id=workspace_id,
                actor_id=member["user_id"], export_id=uuid.UUID(outcome.record.resource_id))
            return envelope(job_data(current["job"]), request.state.request_id)
        job = await create_bulk_failure_export(session, workspace_id=workspace_id,
            source_job_id=job_id, actor_id=member["user_id"])
        data = job_data(job)
        complete_idempotency(outcome, str(job.id), response={"http_status": 202, "data": data})
    return envelope(data, request.state.request_id)


@router.get("/exports/{export_id}")
async def get_export(workspace_id: uuid.UUID, export_id: uuid.UUID, request: Request,
                     principal: Principal = Depends(get_principal)) -> dict:
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "getExport"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        job = await load_actor_export(session, workspace_id=workspace_id,
            actor_id=member["user_id"], export_id=export_id)
        data = job_data(job)
        if job.expires_at and job.expires_at <= datetime.now(timezone.utc):
            data["status"] = "expired"
    return envelope(data, request.state.request_id)


@router.get("/exports/{export_id}/content")
async def download_export(workspace_id: uuid.UUID, export_id: uuid.UUID, request: Request,
                          principal: Principal = Depends(get_principal)) -> Response:
    failure = None
    content = None
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "downloadExport"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        job = await load_actor_export(session, workspace_id=workspace_id,
            actor_id=member["user_id"], export_id=export_id)
        try:
            content = await authorize_export_content(session, workspace_id=workspace_id,
                actor_id=member["user_id"], export_id=export_id)
        except ApiError as exc:
            if exc.status_code not in {403, 412}:
                raise
            job.state = "expired" if "expired" in exc.message else "revoked"
            job.version += 1
            append_audit(session, workspace_id=workspace_id, actor_id=member["user_id"],
                         action="export.revoked", entity_type="export_job", entity_id=job.id,
                         reason="expired" if job.state == "expired" else "current_gate_changed")
            failure = exc
        else:
            append_audit(session, workspace_id=workspace_id, actor_id=member["user_id"],
                         action="export.copied" if job.format == "clipboard" else "export.downloaded",
                         entity_type="export_job", entity_id=job.id)
    if failure is not None:
        raise failure
    assert content is not None
    headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
               "X-Request-ID": request.state.request_id}
    if content["filename"]:
        headers["Content-Disposition"] = f'attachment; filename="{content["filename"]}"'
    return Response(content["body"], media_type=content["media_type"], headers=headers)
