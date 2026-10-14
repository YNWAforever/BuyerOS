"""Resumable private attachments with actor-bound reconciliation and atomic completion."""
import base64
import hashlib
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import func, select, text

from ...db.document_uploads import DocumentSlide, DocumentUpload, DocumentUploadChunk
from ...db.ingestion import OfferDocument
from ...db.models import Membership
from ...db.outbox import OutboxEvent
from ...execution.pdf_parser import PdfParserTimeout
from ...execution.pptx_parser import PptxParserTimeout
from ...services import document_upload_service as service
from ...services.ingestion_service import document_candidate_facts
from ...services.object_store import PostgresPrivateStore, StoreUnavailable, get_private_store
from ..auth import Principal, get_principal
from ..deps import permission_for_roles, tenant_scoped
from ..errors import ApiError, envelope
from ..idempotency import begin_idempotency, complete_idempotency
from ..schemas import DocumentUploadComplete, DocumentUploadStart
from .documents import RETENTION_SECONDS, _authorize, _data, _project

router = APIRouter(prefix='/v1/workspaces/{workspace_id}', tags=['offer-documents'])


def _key(key):
    if not key or not 8 <= len(key) <= 200:
        raise ApiError(400, 'INVALID_REQUEST', 'Idempotency-Key must be 8..200 characters')


def _store(workspace_id):
    try:
        store = get_private_store(workspace_id)
        if not isinstance(store, PostgresPrivateStore):
            raise StoreUnavailable('resumable attachments require private PostgreSQL storage')
        return store
    except StoreUnavailable as exc:
        raise ApiError(503, 'PROVIDER_UNAVAILABLE', str(exc), retryable=True) from exc


async def _member(session, principal, workspace_id):
    member = await _authorize(session, principal, workspace_id, 'uploadOfferDocument')
    # Hold current authority until this short mutation commits. A revocation or
    # role edit that wins first is observed here, including after extraction.
    row = (await session.execute(select(Membership).where(
        Membership.workspace_id == workspace_id, Membership.user_id == member['user_id'])
        .with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    if row is None or not row.active:
        raise ApiError(404, 'NOT_FOUND', 'workspace not found')
    if not permission_for_roles(row.roles, 'uploadOfferDocument'):
        raise ApiError(403, 'PERMISSION_DENIED', 'insufficient role')
    return member


async def _stage(session, workspace_id, upload_id, actor_id, *, lock=False):
    query = select(DocumentUpload).where(DocumentUpload.workspace_id == workspace_id,
        DocumentUpload.id == upload_id, DocumentUpload.actor_user_id == actor_id)
    if lock:
        query = query.with_for_update()
    row = (await session.execute(query)).scalar_one_or_none()
    if row is None:
        raise ApiError(404, 'NOT_FOUND', 'upload not found')
    return row


def _active(row):
    if row.status != 'uploading' or row.expires_at <= service._now():
        raise ApiError(409, 'INVALID_REQUEST', 'upload is terminal or expired; read its status')


async def _ready_doc(session, workspace_id, document_id):
    row = (await session.execute(select(OfferDocument).where(
        OfferDocument.workspace_id == workspace_id, OfferDocument.id == document_id,
        OfferDocument.status == 'ready', OfferDocument.retention_until > service._now())
        .with_for_update(read=True))).scalar_one_or_none()
    if row is None:
        raise ApiError(404, 'NOT_FOUND', 'document not available')
    return row


async def _matching_doc(session, workspace_id, project_id, manifest):
    return (await session.execute(select(OfferDocument).where(
        OfferDocument.workspace_id == workspace_id, OfferDocument.project_id == project_id,
        OfferDocument.filename == manifest['filename'], OfferDocument.media_type == manifest['media_type'],
        OfferDocument.sha256 == manifest['source_sha256'], OfferDocument.status == 'ready',
        OfferDocument.retention_until > service._now(), OfferDocument.object_key.is_not(None))
        .order_by(OfferDocument.created_at, OfferDocument.id).limit(1))).scalar_one_or_none()


@router.post('/projects/{project_id}/offer-document-uploads', status_code=201)
async def start_document_upload(workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request,
        payload: DocumentUploadStart, principal: Principal = Depends(get_principal),
        idempotency_key: str | None = Header(default=None, alias='Idempotency-Key')):
    _key(idempotency_key)
    manifest = payload.model_dump()
    service.validate_manifest(manifest)
    _store(workspace_id)
    async with tenant_scoped(workspace_id) as session:
        member = await _member(session, principal, workspace_id)
        # The runtime role cannot UPDATE workspace rows. A namespaced stable
        # transaction advisory lock serializes quotas without widening that ACL.
        lock_id = int.from_bytes(hashlib.sha256(b'offer-upload-quota:' + workspace_id.bytes).digest()[:8], signed=True)
        await session.execute(text('SELECT pg_advisory_xact_lock(:lock_id)'), {'lock_id': lock_id})
        await _project(session, workspace_id, project_id, lock=True)
        await service.purge_staging(session, workspace_id)
        outcome = await begin_idempotency(session, workspace_id=workspace_id, actor_id=member['user_id'],
            operation_id='startOfferDocumentUpload', key=idempotency_key, body=manifest,
            target={'workspace_id': str(workspace_id), 'project_id': str(project_id)})
        if outcome.replay:
            row = await _stage(session, workspace_id, uuid.UUID(outcome.record.resource_id), member['user_id'])
        else:
            row = (await session.execute(select(DocumentUpload).where(
                DocumentUpload.workspace_id == workspace_id, DocumentUpload.project_id == project_id,
                DocumentUpload.actor_user_id == member['user_id'], DocumentUpload.status == 'uploading',
                DocumentUpload.expires_at > service._now(),
                *[getattr(DocumentUpload, key) == value for key, value in manifest.items()]))).scalar_one_or_none()
            if row is None:
                doc = await _matching_doc(session, workspace_id, project_id, manifest)
                if doc is None:
                    scope = (DocumentUpload.workspace_id == workspace_id, DocumentUpload.status == 'uploading', DocumentUpload.expires_at > service._now())
                    total = (await session.execute(select(func.count()).select_from(DocumentUpload).where(*scope))).scalar_one()
                    actor_total = (await session.execute(select(func.count()).select_from(DocumentUpload).where(*scope, DocumentUpload.actor_user_id == member['user_id']))).scalar_one()
                    if total >= 8 or actor_total >= 2:
                        raise ApiError(429, 'RATE_LIMITED', 'active attachment upload limit reached', retryable=True)
                now = service._now()
                row = DocumentUpload(workspace_id=workspace_id, project_id=project_id, actor_user_id=member['user_id'],
                    **manifest, chunk_size=service.CHUNK_BYTES, chunk_count=(payload.byte_length + service.CHUNK_BYTES - 1) // service.CHUNK_BYTES,
                    status='completed' if doc else 'uploading', document_id=doc.id if doc else None,
                    created_at=now, expires_at=now + timedelta(hours=1))
                session.add(row)
                await session.flush()
            data = await service.upload_data(session, row)
            complete_idempotency(outcome, str(row.id), response=data)
        data = await service.upload_data(session, row)
    return envelope(data, request.state.request_id)


@router.get('/offer-document-uploads/{upload_id}')
async def get_document_upload(workspace_id: uuid.UUID, upload_id: uuid.UUID, request: Request,
        principal: Principal = Depends(get_principal)):
    async with tenant_scoped(workspace_id) as session:
        member = await _member(session, principal, workspace_id)
        await service.purge_staging(session, workspace_id)
        row = await _stage(session, workspace_id, upload_id, member['user_id'])
        data = await service.upload_data(session, row)
    return envelope(data, request.state.request_id)


@router.put('/offer-document-uploads/{upload_id}/chunks/{index}')
async def put_document_chunk(workspace_id: uuid.UUID, upload_id: uuid.UUID, index: int, request: Request,
        principal: Principal = Depends(get_principal), chunk_sha256: str | None = Header(default=None, alias='X-Chunk-Sha256')):
    # Authorize before reading untrusted bytes, then again at the immutable write.
    async with tenant_scoped(workspace_id) as session:
        member = await _authorize(session, principal, workspace_id, 'uploadOfferDocument')
        row = await _stage(session, workspace_id, upload_id, member['user_id'])
        _active(row)
    if request.headers.get('content-type') != 'application/octet-stream':
        raise ApiError(400, 'INVALID_REQUEST', 'chunk must use application/octet-stream')
    parts, size = [], 0
    async for part in request.stream():
        size += len(part)
        if size > service.CHUNK_BYTES:
            raise ApiError(400, 'INVALID_REQUEST', 'chunk too large')
        parts.append(part)
    body = b''.join(parts)
    if not body or hashlib.sha256(body).hexdigest() != chunk_sha256:
        raise ApiError(400, 'INVALID_REQUEST', 'chunk digest mismatch')
    async with tenant_scoped(workspace_id) as session:
        member = await _member(session, principal, workspace_id)
        row = await _stage(session, workspace_id, upload_id, member['user_id'])
        await _project(session, workspace_id, row.project_id, lock=True)
        row = await _stage(session, workspace_id, upload_id, member['user_id'], lock=True)
        _active(row)
        if not 0 <= index < row.chunk_count or len(body) != min(row.chunk_size, row.byte_length - index * row.chunk_size):
            raise ApiError(400, 'INVALID_REQUEST', 'chunk position or length mismatch')
        existing = (await session.execute(select(DocumentUploadChunk).where(
            DocumentUploadChunk.workspace_id == workspace_id, DocumentUploadChunk.upload_id == upload_id,
            DocumentUploadChunk.chunk_index == index))).scalar_one_or_none()
        if existing is not None and (existing.sha256 != chunk_sha256 or bytes(existing.body) != body):
            raise ApiError(409, 'IDEMPOTENCY_CONFLICT', 'different bytes already exist at this position')
        if existing is None:
            session.add(DocumentUploadChunk(workspace_id=workspace_id, upload_id=upload_id, chunk_index=index, body=body, sha256=chunk_sha256))
            await session.flush()
        data = await service.upload_data(session, row)
    return envelope(data, request.state.request_id)


@router.post('/offer-document-uploads/{upload_id}/complete', status_code=202)
async def complete_document_upload(workspace_id: uuid.UUID, upload_id: uuid.UUID, request: Request, response: Response,
        payload: DocumentUploadComplete, principal: Principal = Depends(get_principal), idempotency_key: str | None = Header(default=None, alias='Idempotency-Key')):
    _key(idempotency_key)
    store = _store(workspace_id)
    async with tenant_scoped(workspace_id) as session:
        member = await _member(session, principal, workspace_id)
        stage = await _stage(session, workspace_id, upload_id, member['user_id'])
        if stage.status == 'completed':
            data = _data(await _ready_doc(session, workspace_id, stage.document_id))
            outcome = await begin_idempotency(session, workspace_id=workspace_id, actor_id=member['user_id'],
                operation_id='completeOfferDocumentUpload', key=idempotency_key, body=payload.model_dump(),
                target={'workspace_id': str(workspace_id), 'upload_id': str(upload_id)})
            if not outcome.replay:
                complete_idempotency(outcome, str(stage.document_id), response={'version': data['version'], 'data': data})
            response.headers['ETag'] = f'"{data["version"]}"'
            return envelope(data, request.state.request_id)
        _active(stage)
        await _project(session, workspace_id, stage.project_id)
        chunks = (await session.execute(select(DocumentUploadChunk).where(
            DocumentUploadChunk.workspace_id == workspace_id, DocumentUploadChunk.upload_id == upload_id)
            .order_by(DocumentUploadChunk.chunk_index))).scalars().all()
        if [c.chunk_index for c in chunks] != list(range(stage.chunk_count)):
            raise ApiError(409, 'INVALID_REQUEST', 'upload is missing chunks')
        body = b''.join(bytes(c.body) for c in chunks)
    # No transaction is held across the isolated, resource-capped parser.
    failure = None
    try:
        parsed = await service.parse_document(stage, body)
    except (PptxParserTimeout, PdfParserTimeout):
        failure = 'PARSER_TIMEOUT'
    except ValueError:
        failure = 'INVALID_DOCUMENT'
    async with tenant_scoped(workspace_id) as session:
        member = await _member(session, principal, workspace_id)
        await _project(session, workspace_id, stage.project_id, lock=True)
        row = await _stage(session, workspace_id, upload_id, member['user_id'], lock=True)
        if row.status == 'completed':
            data = _data(await _ready_doc(session, workspace_id, row.document_id))
            failure = None
        else:
            _active(row)
            if failure:
                row.status, row.failure_code, row.version = 'failed', failure, row.version + 1
                await service.clear_chunks(session, row)
            else:
                outcome = await begin_idempotency(session, workspace_id=workspace_id, actor_id=member['user_id'],
                    operation_id='completeOfferDocumentUpload', key=idempotency_key, body={},
                    target={'workspace_id': str(workspace_id), 'upload_id': str(upload_id)})
                manifest = dict(filename=row.filename, media_type=row.media_type, source_sha256=row.source_sha256)
                doc = await _matching_doc(session, workspace_id, row.project_id, manifest)
                if doc is None:
                    object_key = await store.put_private(body, digest=row.source_sha256, retention_seconds=RETENTION_SECONDS, session=session)
                    doc = OfferDocument(workspace_id=workspace_id, project_id=row.project_id, kind='upload',
                        filename=row.filename, media_type=row.media_type, sha256=row.source_sha256, status='ready',
                        object_key=object_key, retention_until=service._now() + timedelta(seconds=RETENTION_SECONDS),
                        fact_candidates=[], extraction_metadata={**parsed['metadata'], 'byte_length': row.byte_length, 'chunk_size': service.CHUNK_BYTES})
                    session.add(doc)
                    await session.flush()
                    doc.fact_candidates = document_candidate_facts(doc.id, parsed['facts'])
                    for slide in parsed['slides']:
                        session.add(DocumentSlide(workspace_id=workspace_id, project_id=row.project_id, document_id=doc.id,
                            slide_number=slide['number'], text=slide['text'], classification=slide['classification']))
                    session.add(OutboxEvent(workspace_id=workspace_id, intent_key=f'offer.parse:{doc.id}', event_type='offer.parse',
                        payload={'document_id': str(doc.id), 'actor_user_id': str(member['user_id']), 'processing_mode': 'inline_deterministic'}, state='done'))
                    await session.flush()
                    await session.refresh(doc)
                row.status, row.document_id, row.version = 'completed', doc.id, row.version + 1
                await service.clear_chunks(session, row)
                data = _data(doc)
                complete_idempotency(outcome, str(doc.id), response={'version': doc.version, 'data': data})
    if failure:
        raise ApiError(400, 'INVALID_REQUEST', failure + '; upload failed, staged bytes removed')
    response.headers['ETag'] = f'"{data["version"]}"'
    return envelope(data, request.state.request_id)


@router.get('/offer-documents/{document_id}/slides')
async def document_slides(workspace_id: uuid.UUID, document_id: uuid.UUID, request: Request,
        offset: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=20),
        principal: Principal = Depends(get_principal)):
    async with tenant_scoped(workspace_id) as session:
        await _authorize(session, principal, workspace_id, 'getOfferDocument')
        doc = await _ready_doc(session, workspace_id, document_id)
        scope = (DocumentSlide.workspace_id == workspace_id, DocumentSlide.document_id == doc.id)
        total = (await session.execute(select(func.count()).select_from(DocumentSlide).where(*scope))).scalar_one()
        slides = (await session.execute(select(DocumentSlide).where(*scope).order_by(DocumentSlide.slide_number).offset(offset).limit(limit))).scalars().all()
        data = dict(items=[dict(number=s.slide_number, text=s.text, classification=s.classification) for s in slides], offset=offset, limit=limit, total=total)
    return envelope(data, request.state.request_id)


@router.get('/offer-documents/{document_id}/content-chunks/{index}')
async def document_content_chunk(workspace_id: uuid.UUID, document_id: uuid.UUID, index: int, request: Request,
        principal: Principal = Depends(get_principal)):
    async with tenant_scoped(workspace_id) as session:
        await _authorize(session, principal, workspace_id, 'getOfferDocument')
        doc = await _ready_doc(session, workspace_id, document_id)
        length = doc.extraction_metadata.get('byte_length', 0)
        chunk_count = (length + service.CHUNK_BYTES - 1) // service.CHUNK_BYTES
        if not 0 <= index < chunk_count or not doc.object_key or not doc.object_key.startswith('postgres/tenants/'):
            raise ApiError(404, 'NOT_FOUND', 'original content not available')
        try:
            body = await PostgresPrivateStore(workspace_id).get_private_chunk(doc.object_key, offset=index * service.CHUNK_BYTES,
                length=min(service.CHUNK_BYTES, length - index * service.CHUNK_BYTES), expected_sha256=doc.sha256)
        except ValueError as exc:
            raise ApiError(404, 'NOT_FOUND', 'original content not available') from exc
        data = dict(index=index, offset=index * service.CHUNK_BYTES, byte_length=len(body), chunk_count=chunk_count,
            source_byte_length=length, chunk_sha256=hashlib.sha256(body).hexdigest(), source_sha256=doc.sha256,
            filename=doc.filename, media_type=doc.media_type, body_base64=base64.b64encode(body).decode('ascii'))
    return envelope(data, request.state.request_id)
