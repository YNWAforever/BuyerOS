"""Bounded native staging primitives; no provider jobs or long parse transactions."""
import asyncio
import hashlib
import re
from datetime import datetime, timezone

from sqlalchemy import delete, select

from ..db.document_uploads import DocumentUpload, DocumentUploadChunk
from ..execution.pptx_parser import parse_pptx
from ..services.ingestion_service import parse_upload_candidates, validate_upload
from ..api.errors import ApiError

CHUNK_BYTES = 2 * 1024 * 1024
PPTX_MIME = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
FORMATS = {'.pptx': PPTX_MIME, '.pdf': 'application/pdf', '.txt': 'text/plain', '.md': 'text/markdown'}


def _now():
    return datetime.now(timezone.utc)


def validate_manifest(manifest):
    name, mime, size, digest = (manifest[k] for k in ('filename', 'media_type', 'byte_length', 'source_sha256'))
    expected = next((value for suffix, value in FORMATS.items() if name.lower().endswith(suffix)), None)
    if (not name or len(name) > 255 or any(c in name for c in '/\\')
            or any(ord(c) < 32 for c in name) or expected != mime
            or type(size) is not int or not 1 <= size <= (20 if mime == PPTX_MIME else 5) * 1024 * 1024
            or not re.fullmatch('[a-f0-9]{64}', digest)):
        raise ApiError(400, 'INVALID_REQUEST', 'invalid upload manifest or unsupported format')


async def clear_chunks(session, row):
    await session.execute(delete(DocumentUploadChunk).where(
        DocumentUploadChunk.workspace_id == row.workspace_id, DocumentUploadChunk.upload_id == row.id))


async def purge_staging(session, workspace_id):
    rows = (await session.execute(select(DocumentUpload).where(
        DocumentUpload.workspace_id == workspace_id, DocumentUpload.status == 'uploading',
        DocumentUpload.expires_at <= _now()).order_by(DocumentUpload.expires_at, DocumentUpload.id)
        .limit(64).with_for_update(skip_locked=True))).scalars().all()
    for row in rows:
        await clear_chunks(session, row)
        row.status, row.failure_code, row.version = 'expired', 'UPLOAD_EXPIRED', row.version + 1
    await session.flush()


async def upload_data(session, row):
    chunks = (await session.execute(select(DocumentUploadChunk.chunk_index, DocumentUploadChunk.sha256).where(
        DocumentUploadChunk.workspace_id == row.workspace_id, DocumentUploadChunk.upload_id == row.id)
        .order_by(DocumentUploadChunk.chunk_index))).all()
    data = dict(id=str(row.id), workspace_id=str(row.workspace_id), project_id=str(row.project_id),
                filename=row.filename, media_type=row.media_type, byte_length=row.byte_length,
                source_sha256=row.source_sha256, chunk_size=row.chunk_size, chunk_count=row.chunk_count,
                status=row.status, expires_at=row.expires_at.isoformat(), version=row.version,
                received_chunks=[dict(index=index, sha256=digest) for index, digest in chunks])
    if row.document_id:
        data['document_id'] = str(row.document_id)
    if row.failure_code:
        data['failure_code'] = row.failure_code
    return data


async def parse_document(stage, body):
    if hashlib.sha256(body).hexdigest() != stage.source_sha256 or len(body) != stage.byte_length:
        raise ValueError('original digest or length mismatch')
    if stage.media_type == PPTX_MIME:
        return await asyncio.to_thread(parse_pptx, body)
    validated = validate_upload(stage.filename, stage.media_type, body, stage.source_sha256)
    return dict(facts=await parse_upload_candidates(validated), slides=[], metadata={'format': validated.kind})
