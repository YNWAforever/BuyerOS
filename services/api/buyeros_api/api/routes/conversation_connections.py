"""Flag-gated, project-scoped Drive control plane. All Drive calls are reads."""
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator
from sqlalchemy import select
from ..auth import Principal, get_principal
from ..deps import load_membership, permission_for_roles, tenant_scoped
from ..errors import ApiError, envelope
from ..idempotency import begin_idempotency, complete_idempotency, if_match_version
from ...db.icp import Project
from ...db.conversation_connections import DriveConnection
from ...services import drive_mcp
from ...services.conversation_connections import load
from ...services.audit_service import append_audit
from ...settings import get_settings

router = APIRouter(prefix='/v1/workspaces/{workspace_id}/projects/{project_id}/conversation-connections/google-drive', tags=['conversation-connections'])


class Empty(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ApproveFolders(Empty):
    folder_ids: list[StrictStr] = Field(max_length=20)

    @field_validator('folder_ids')
    @classmethod
    def valid_ids(cls, values):
        if not all(drive_mcp.identifier(value) for value in values) or len(set(values)) != len(values):
            raise ValueError('unique folder IDs required')
        return values


def not_found():
    return ApiError(404, 'NOT_FOUND', 'connection not found')


@asynccontextmanager
async def access(workspace_id, project_id, principal, *, admin=False, write=False):
    if os.environ.get('NEXT_PUBLIC_CONVERSATION_HOME') != 'true':
        raise not_found()
    if not get_settings().live_read_enabled:
        raise ApiError(503, 'READ_DISABLED', 'live reads are temporarily disabled')
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        operation = 'connectConversationDrive' if admin else 'getConversationDrive'
        if not permission_for_roles(member['roles'], operation):
            raise not_found()
        query = select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id, Project.status == 'active')
        # Serializes first connect as well as updates; members only acquire a shared lock.
        query = query.with_for_update() if write else query.with_for_update(read=True)
        if (await session.execute(query)).scalar_one_or_none() is None:
            raise not_found()
        yield session, member


def data(row, member):
    return {'version': row.version if row else 1, 'connected': bool(row and row.connected),
            'available': drive_mcp.configured(), 'can_manage': 'workspace_admin' in member['roles'],
            'folders': row.folders if row else [], 'residency_preference': 'HK', 'metadata_cache_seconds': 0}


@router.get('', operation_id='getConversationDrive')
async def status(workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)):
    async with access(workspace_id, project_id, principal) as (session, member):
        row = await load(session, workspace_id, project_id)
        result = data(row, member)
        if row and row.connected:
            try:
                await drive_mcp.adapter().status(workspace_id, project_id)
            except ApiError as error:
                if error.code != 'DRIVE_UNAVAILABLE':
                    raise
                # Keep local disconnect available during external outages.
                result['available'] = False
    return envelope(result, request.state.request_id)


@router.get('/folders', operation_id='listConversationDriveFolders')
async def folders(workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)):
    async with access(workspace_id, project_id, principal, admin=True) as (session, member):
        row = await load(session, workspace_id, project_id)
        if row is None or not row.connected:
            raise not_found()
        result = {'items': [{'id': ident, 'label': 'Google Drive folder'} for ident in await drive_mcp.adapter().folders(workspace_id, project_id)]}
    return envelope(result, request.state.request_id)


@router.get('/items', operation_id='listConversationDriveItems')
async def items(workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)):
    async with access(workspace_id, project_id, principal) as (session, member):
        row = await load(session, workspace_id, project_id)
        result = {'items': []}
        if row and row.connected and row.folders:
            result['items'] = [{'id': f'drive:{row.generation}:{item["id"]}', 'label': 'Google Drive item'}
                for item in await drive_mcp.adapter().items(workspace_id, project_id, [folder['id'] for folder in row.folders])]
    return envelope(result, request.state.request_id)


async def mutate(workspace_id, project_id, request, principal, operation, payload):
    async with access(workspace_id, project_id, principal, admin=True, write=True) as (session, member):
        row = await load(session, workspace_id, project_id, lock=True)
        key = request.headers.get('Idempotency-Key')
        if not key:
            raise ApiError(400, 'INVALID_REQUEST', 'Idempotency-Key header is required')
        outcome = await begin_idempotency(session, workspace_id=workspace_id, actor_id=member['user_id'],
            operation_id=operation, key=key, body=payload, target={'project_id': str(project_id)},
            precondition=request.headers.get('If-Match'))
        if not outcome.replay:
            if if_match_version(request.headers.get('If-Match')) != (row.version if row else 1):
                raise ApiError(409, 'STALE_REVISION', 'connection changed; reload before trying again')
            if operation == 'connectConversationDrive':
                if row and row.connected:
                    raise ApiError(409, 'ALREADY_CONNECTED', 'Google Drive is already connected')
                await drive_mcp.adapter().status(workspace_id, project_id)
            elif operation == 'approveConversationDriveFolders':
                if row is None or not row.connected:
                    raise not_found()
                candidates = await drive_mcp.adapter().folders(workspace_id, project_id)
                if any(ident not in candidates for ident in payload['folder_ids']):
                    raise not_found()
            if row is None:
                row = DriveConnection(workspace_id=workspace_id, project_id=project_id,
                    configured_by=member['user_id'], version=1, folders=[], connected=False)
                session.add(row)
            row.version += 1
            row.configured_by = member['user_id']
            row.updated_at = datetime.now(timezone.utc)
            row.generation = uuid.uuid4()  # Reconnect/approval cannot revive stale selections.
            row.connected = operation != 'disconnectConversationDrive'
            row.folders = [{'id': ident, 'label': 'Google Drive folder'} for ident in payload.get('folder_ids', [])]
            await session.flush()
            append_audit(session, workspace_id=workspace_id, actor_id=member['user_id'],
                action='conversation_drive.' + operation, entity_type='conversation_drive', entity_id=row.id)
            complete_idempotency(outcome, str(row.id))
        result = data(row, member)
    return envelope(result, request.state.request_id)


@router.post('', operation_id='connectConversationDrive')
async def connect(workspace_id: uuid.UUID, project_id: uuid.UUID, payload: Empty, request: Request, principal: Principal = Depends(get_principal)):
    return await mutate(workspace_id, project_id, request, principal, 'connectConversationDrive', payload.model_dump())


@router.put('/folders', operation_id='approveConversationDriveFolders')
async def approve(workspace_id: uuid.UUID, project_id: uuid.UUID, payload: ApproveFolders, request: Request, principal: Principal = Depends(get_principal)):
    return await mutate(workspace_id, project_id, request, principal, 'approveConversationDriveFolders', payload.model_dump())


@router.delete('', operation_id='disconnectConversationDrive')
async def disconnect(workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)):
    # Local authorization is revoked even when the external gateway is down.
    return await mutate(workspace_id, project_id, request, principal, 'disconnectConversationDrive', {})
