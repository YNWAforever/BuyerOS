"""Tenant-authorized offer document ingestion and lifecycle."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, Header, Query, Request, Response, UploadFile
from sqlalchemy import func, select

from ...db.contact import IdempotencyRecord
from ...db.icp import IcpVersion, Project
from ...db.ingestion import OfferDocument
from ...db.outbox import AsyncJob, OutboxEvent
from ...services.ingestion_service import MAX_UPLOAD_BYTES, validate_upload
from ...services.bulk_service import job_data
from ...services.offer_source_policy import canonical_source_url, current_offer_source_permission
from ...services.object_store import StoreUnavailable, get_private_store
from ...services.confirm_service import IdempotencyConflict, same_request
from ..auth import Principal, get_principal
from ..deps import load_membership, permission_for_roles, tenant_scoped
from ..errors import ApiError, envelope
from ..idempotency import begin_idempotency, complete_idempotency, if_match_version, request_fingerprint
from ..schemas import ArchiveRequest, OfferIngestRequest

router = APIRouter(prefix="/v1/workspaces/{workspace_id}", tags=["offer-documents"])
RETENTION_SECONDS = 30 * 86400


def _data(row: OfferDocument) -> dict:
    data = {
        "id": str(row.id), "workspace_id": str(row.workspace_id),
        "project_id": str(row.project_id), "version": row.version,
        "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat(),
        "data_mode": "live", "filename": row.filename, "media_type": row.media_type,
        "status": row.status, "fact_candidates": list(row.fact_candidates),
    }
    if row.sha256 is not None:
        data["sha256"] = row.sha256
    if row.failure_code is not None:
        data["failure_code"] = row.failure_code
    if row.retention_until is not None:
        data["retention_until"] = row.retention_until.isoformat()
    return data


async def _authorize(session, principal, workspace_id, operation):
    member = await load_membership(session, principal=principal, workspace_id=workspace_id)
    if not permission_for_roles(member["roles"], operation):
        raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
    return member


async def _project(session, workspace_id, project_id):
    row = (await session.execute(select(Project).where(
        Project.workspace_id == workspace_id, Project.id == project_id,
    ))).scalar_one_or_none()
    if row is None or row.status != "active":
        raise ApiError(404, "NOT_FOUND", "project not found")
    return row


async def _preflight_replay(session, *, workspace_id, actor_id, key, operation, target, body):
    if not 8 <= len(key) <= 200:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key must be 8..200 characters")
    existing = (await session.execute(select(IdempotencyRecord).where(
        IdempotencyRecord.workspace_id == workspace_id,
        IdempotencyRecord.actor_id == actor_id,
        IdempotencyRecord.operation_id == operation,
        IdempotencyRecord.key == key,
    ))).scalar_one_or_none()
    if existing is None:
        return None
    expected = request_fingerprint(operation, target, None, body)
    try:
        same_request(existing.key, existing.request_hash, key, expected, raise_on_conflict=True)
    except IdempotencyConflict as exc:
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", str(exc)) from exc
    if existing.status != "completed" or existing.response is None:
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", "request is still in progress")
    return existing.response


@router.post("/projects/{project_id}/offer-documents", status_code=202)
async def upload_offer_document(
    workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request, response: Response,
    file: UploadFile = File(...), declared_sha256: str = Form(...),
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    body = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        upload = validate_upload(file.filename or "", file.content_type or "", body, declared_sha256)
    except ValueError as exc:
        raise ApiError(400, "INVALID_REQUEST", str(exc)) from exc
    identity = {"filename": upload.filename, "media_type": upload.media_type,
                "sha256": upload.sha256, "size": upload.size}
    target = {"workspace_id": str(workspace_id), "project_id": str(project_id)}
    async with tenant_scoped(workspace_id) as session:
        member = await _authorize(session, principal, workspace_id, "uploadOfferDocument")
        await _project(session, workspace_id, project_id)
        replay = await _preflight_replay(
            session, workspace_id=workspace_id, actor_id=member["user_id"],
            key=idempotency_key, operation="uploadOfferDocument", target=target, body=identity,
        )
        if replay is not None:
            response.headers["ETag"] = f'"{replay["version"]}"'
            return envelope(replay["data"], request.state.request_id)
    try:
        store = get_private_store(workspace_id)
        object_key = await store.put_private(
            upload.body, digest=upload.sha256, retention_seconds=RETENTION_SECONDS,
        )
    except StoreUnavailable as exc:
        raise ApiError(503, "PROVIDER_UNAVAILABLE", str(exc), retryable=True) from exc
    except Exception as exc:
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "private object storage failed", retryable=True) from exc
    try:
        async with tenant_scoped(workspace_id) as session:
            member = await _authorize(session, principal, workspace_id, "uploadOfferDocument")
            await _project(session, workspace_id, project_id)
            outcome = await begin_idempotency(
                session, workspace_id=workspace_id, actor_id=member["user_id"],
                operation_id="uploadOfferDocument", key=idempotency_key,
                body=identity, target=target,
            )
            if outcome.replay:
                if outcome.response is None:
                    raise ApiError(409, "IDEMPOTENCY_CONFLICT", "legacy replay requires a new key")
                data = outcome.response["data"]
            else:
                row = OfferDocument(
                    workspace_id=workspace_id, project_id=project_id, kind="upload",
                    filename=upload.filename, media_type=upload.media_type,
                    sha256=upload.sha256, status="quarantined", object_key=object_key,
                    retention_until=datetime.now(timezone.utc) + timedelta(seconds=RETENTION_SECONDS),
                    fact_candidates=[],
                )
                session.add(row)
                await session.flush()
                session.add(OutboxEvent(
                    workspace_id=workspace_id, intent_key=f"offer.parse:{row.id}",
                    event_type="offer.parse", payload={"document_id": str(row.id)},
                ))
                data = _data(row)
                complete_idempotency(outcome, str(row.id), response={"version": row.version, "data": data})
        if outcome.replay:
            await store.delete_private(object_key)
    except Exception:
        try:
            await store.delete_private(object_key)
        except Exception:
            pass  # Orphan lifecycle policy is an explicit activation prerequisite.
        raise
    response.headers["ETag"] = f'"{data["version"]}"'
    return envelope(data, request.state.request_id)


@router.get("/offer-documents/{document_id}")
async def get_offer_document(
    workspace_id: uuid.UUID, document_id: uuid.UUID, request: Request, response: Response,
    principal: Principal = Depends(get_principal),
) -> dict:
    async with tenant_scoped(workspace_id) as session:
        await _authorize(session, principal, workspace_id, "getOfferDocument")
        row = (await session.execute(select(OfferDocument).where(
            OfferDocument.workspace_id == workspace_id, OfferDocument.id == document_id,
            OfferDocument.status != "deleted",
        ))).scalar_one_or_none()
        if row is None:
            raise ApiError(404, "NOT_FOUND", "document not found")
        data = _data(row)
    response.headers["ETag"] = f'"{data["version"]}"'
    return envelope(data, request.state.request_id)


@router.delete("/offer-documents/{document_id}", status_code=202)
async def delete_offer_document(
    workspace_id: uuid.UUID, document_id: uuid.UUID, request: Request, response: Response,
    payload: ArchiveRequest, principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> dict:
    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    version = if_match_version(if_match)
    async with tenant_scoped(workspace_id) as session:
        member = await _authorize(session, principal, workspace_id, "deleteOfferDocument")
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=member["user_id"],
            operation_id="deleteOfferDocument", key=idempotency_key,
            body=payload.model_dump(mode="json"),
            target={"workspace_id": str(workspace_id), "document_id": str(document_id)},
            precondition=if_match,
        )
        if outcome.replay:
            if outcome.response is None:
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "legacy replay requires a new key")
            data = outcome.response["data"]
        else:
            project_id = (await session.execute(select(OfferDocument.project_id).where(
                OfferDocument.workspace_id == workspace_id, OfferDocument.id == document_id,
                OfferDocument.status != "deleted",
            ))).scalar_one_or_none()
            if project_id is None:
                raise ApiError(404, "NOT_FOUND", "document not found")
            project = (await session.execute(select(Project).where(
                Project.workspace_id == workspace_id, Project.id == project_id,
            ).with_for_update())).scalar_one()
            row = (await session.execute(select(OfferDocument).where(
                OfferDocument.workspace_id == workspace_id, OfferDocument.id == document_id,
                OfferDocument.status != "deleted",
            ).with_for_update())).scalar_one_or_none()
            if row is None:
                raise ApiError(404, "NOT_FOUND", "document not found")
            if row.version != version:
                raise ApiError(412, "STALE_REVISION", "document version changed")
            referenced = (await session.execute(select(IcpVersion).where(
                IcpVersion.workspace_id == workspace_id,
                IcpVersion.project_id == project.id,
                IcpVersion.content["offer_document_ids"].contains([str(document_id)]),
            ).with_for_update())).scalars().all()
            if referenced:
                project.offer_revision += 1
                project.version += 1
                active = next((item for item in referenced if item.id == project.active_icp_version_id), None)
                if active is not None:
                    active.superseded_at = datetime.now(timezone.utc)
                    project.active_icp_version_id = None
            row.status = "deleted"
            row.deleted_at = datetime.now(timezone.utc)
            row.fact_candidates = []
            row.version += 1
            await session.flush()
            await session.refresh(row)
            session.add(OutboxEvent(
                workspace_id=workspace_id, intent_key=f"offer.delete:{row.id}",
                event_type="offer.delete", payload={"document_id": str(row.id)},
            ))
            data = _data(row)
            complete_idempotency(outcome, str(row.id), response={"version": row.version, "data": data})
    response.headers["ETag"] = f'"{data["version"]}"'
    return envelope(data, request.state.request_id)


@router.post("/projects/{project_id}/offer-ingestions", status_code=202)
async def ingest_offer_url(
    workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request,
    payload: OfferIngestRequest, principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    try:
        source_url = canonical_source_url(payload.source_url)
    except ValueError as exc:
        raise ApiError(422, "INVALID_REQUEST", str(exc)) from exc
    body = {**payload.model_dump(mode="json"), "source_url": source_url}
    async with tenant_scoped(workspace_id) as session:
        member = await _authorize(session, principal, workspace_id, "ingestOfferUrl")
        await _project(session, workspace_id, project_id)
        decision = await current_offer_source_permission(
            session, workspace_id=workspace_id, project_id=project_id,
            source_url=source_url,
        )
        if decision is None:
            raise ApiError(403, "POLICY_BLOCKED", "source is not currently permitted")
        try:
            get_private_store(workspace_id)
        except StoreUnavailable as exc:
            raise ApiError(503, "PROVIDER_UNAVAILABLE", str(exc), retryable=True) from exc
        outcome = await begin_idempotency(
            session, workspace_id=workspace_id, actor_id=member["user_id"],
            operation_id="ingestOfferUrl", key=idempotency_key, body=body,
            target={"workspace_id": str(workspace_id), "project_id": str(project_id)},
        )
        if outcome.replay:
            if outcome.response is None:
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "legacy replay requires a new key")
            data = outcome.response
        else:
            retention_until = min(
                decision.expires_at,
                datetime.now(timezone.utc) + timedelta(days=decision.retention_days),
            )
            document = OfferDocument(
                workspace_id=workspace_id, project_id=project_id, kind="url",
                filename="pending-url-fetch", media_type="application/octet-stream",
                sha256=None, status="queued", source_url=source_url,
                retention_until=retention_until, fact_candidates=[],
            )
            session.add(document)
            await session.flush()
            job = AsyncJob(
                workspace_id=workspace_id, project_id=project_id,
                actor_user_id=member["user_id"], kind="offer_ingestion",
                operation="ingestOfferUrl", status="queued", requested=1,
                command={"document_id": str(document.id), "source_url": source_url,
                         "policy_decision_id": str(decision.id), "max_cost": body["max_cost"]},
            )
            session.add(job)
            await session.flush()
            session.add(OutboxEvent(
                workspace_id=workspace_id, intent_key=f"offer.fetch:{job.id}",
                event_type="offer.fetch",
                payload={"document_id": str(document.id), "job_id": str(job.id)},
            ))
            data = job_data(job)
            complete_idempotency(outcome, str(job.id), response=data)
    return envelope(data, request.state.request_id)


@router.get("/projects/{project_id}/offer-documents")
async def list_offer_documents(
    workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    principal: Principal = Depends(get_principal),
) -> dict:
    async with tenant_scoped(workspace_id) as session:
        await _authorize(session, principal, workspace_id, "listOfferDocuments")
        exists = (await session.execute(select(Project.id).where(
            Project.workspace_id == workspace_id, Project.id == project_id,
        ))).scalar_one_or_none()
        if exists is None:
            raise ApiError(404, "NOT_FOUND", "project not found")
        scope = (OfferDocument.workspace_id == workspace_id,
                 OfferDocument.project_id == project_id)
        total = (await session.execute(
            select(func.count()).select_from(OfferDocument).where(*scope)
        )).scalar_one()
        rows = (await session.execute(
            select(OfferDocument).where(*scope)
            .order_by(OfferDocument.created_at.desc(), OfferDocument.id.desc())
            .offset(offset).limit(limit)
        )).scalars().all()
        data = {"items": [_data(row) for row in rows],
                "offset": offset, "limit": limit, "total": total}
    return envelope(data, request.state.request_id)
