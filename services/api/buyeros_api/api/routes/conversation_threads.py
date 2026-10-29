"""Flag-gated private notes. ACL is resolved before every read, write and replay."""
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, field_validator, model_validator
from sqlalchemy import exists, func, or_, select

from ..auth import Principal, get_principal
from ..deps import load_membership, permission_for_roles, tenant_scoped
from ..errors import ApiError, envelope
from ..idempotency import begin_idempotency, complete_idempotency, if_match_version
from ...db.conversation_threads import ConversationThread as Thread, ConversationThreadMessage as Message, ConversationThreadShare as Share
from ...db.icp import Project
from ...db.models import Membership, User
from ...services.audit_service import append_audit
from ...services.membership_directory import directory_search, member_display_name
from ...settings import get_settings
from ...services.conversation_connections import approved_sources, SOURCE as DRIVE_SOURCE

router = APIRouter(prefix='/v1/workspaces/{workspace_id}/projects/{project_id}/conversation-threads', tags=['conversation-threads'])
LABELS = {'drive': {'Google Drive item'}, 'document': {'Offer document'}, 'fact': {'Offer fact', 'Approved offer fact', 'Candidate offer fact'}, 'run': {'Research run'}, 'results': {'Results summary'}}
TEMPLATES = {'first-project','understand-documents','research-market','review-buyers','check-company','prepare-follow-up','custom'}
STATUSES = {'draft','queued','running','partial','paused_budget','cancel_requested','cancelled','failed','completed','awaiting_reconciliation'}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Note(StrictModel):
    text: StrictStr = Field(min_length=1, max_length=4000, pattern=r'\S')

    @field_validator('text')
    @classmethod
    def local_text_bound(cls, value):
        if '\x00' in value or len(value.encode('utf-16-le')) > 8000:
            raise ValueError('note exceeds device character bound')
        return value


class Source(StrictModel):
    id: StrictStr = Field(max_length=200, pattern=r'^(document|fact|run|results|drive):[A-Za-z0-9][A-Za-z0-9._:-]*$')
    label: StrictStr

    @model_validator(mode='after')
    def generic_label(self):
        if self.label not in LABELS[self.id.split(':', 1)[0]]:
            raise ValueError('generic source label required')
        if self.id.startswith('drive:') and not DRIVE_SOURCE.fullmatch(self.id):
            raise ValueError('invalid Drive reference')
        return self


class RunRef(StrictModel):
    id: StrictStr = Field(pattern=r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')
    label: Literal['Research run']
    status: StrictStr

    @field_validator('status')
    @classmethod
    def known_status(cls, value):
        if value not in STATUSES:
            raise ValueError('unknown run status')
        return value


class Sources(StrictModel):
    sources: list[Source] = Field(max_length=100)

    @field_validator('sources')
    @classmethod
    def unique(cls, value):
        if len({item.id for item in value}) != len(value):
            raise ValueError('duplicate reference')
        return value


class Rename(StrictModel):
    title: StrictStr = Field(min_length=1, max_length=80, pattern=r'\S')

    @field_validator('title')
    @classmethod
    def local_title_bound(cls, value):
        if '\x00' in value or len(value.encode('utf-16-le')) > 160:
            raise ValueError('title exceeds device character bound')
        return value


class ImportThread(Sources, Rename):
    confirmed: StrictBool
    template_id: StrictStr
    messages: list[Note] = Field(min_length=1, max_length=100)
    runs: list[RunRef] = Field(default_factory=list, max_length=100)

    @model_validator(mode='after')
    def valid_import(self):
        if not self.confirmed or self.template_id not in TEMPLATES or len({r.id for r in self.runs}) != len(self.runs):
            raise ValueError('confirmation, known template and unique references required')
        return self


class Grant(StrictModel):
    role: Literal['viewer', 'editor']


def not_found():
    return ApiError(404, 'NOT_FOUND', 'discussion not found')


@asynccontextmanager
async def access(workspace_id, project_id, principal, *, lock_project=False):
    if os.environ.get('NEXT_PUBLIC_CONVERSATION_HOME') != 'true':
        raise not_found()
    if not get_settings().live_read_enabled:
        raise ApiError(503, 'READ_DISABLED', 'live reads are temporarily disabled')
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member['roles'], 'getProject'):
            raise not_found()
        query = select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id)
        if lock_project:
            query = query.with_for_update()
        if (await session.execute(query)).scalar_one_or_none() is None:
            raise not_found()
        yield session, member['user_id']


def thread_scope(workspace_id, project_id):
    return (Thread.workspace_id == workspace_id, Thread.project_id == project_id)


def shared(actor):
    return exists(select(Share.id).where(Share.workspace_id == Thread.workspace_id, Share.thread_id == Thread.id, Share.grantee_user_id == actor))


async def load(session, workspace_id, project_id, thread_id, actor, *, owner=False, edit=False, lock=False):
    query = select(Thread).where(*thread_scope(workspace_id, project_id), Thread.id == thread_id,
        Thread.owner_user_id == actor if owner else or_(Thread.owner_user_id == actor, shared(actor)))
    if lock:
        query = query.with_for_update()
    row = (await session.execute(query)).scalar_one_or_none()
    if row is None:
        raise not_found()
    role = 'owner' if row.owner_user_id == actor else (await session.execute(select(Share.role).where(
        Share.workspace_id == workspace_id, Share.thread_id == row.id, Share.grantee_user_id == actor))).scalar_one_or_none()
    if role is None or (owner and role != 'owner') or (edit and role not in {'owner','editor'}):
        raise not_found()
    return row, role


async def data(session, row, role, *, full=True):
    result = {'id': str(row.id), 'version': row.version, 'templateId': row.template_id, 'title': row.title,
        'createdAt': int(row.created_at.timestamp()*1000), 'updatedAt': int(row.updated_at.timestamp()*1000), 'access': role,
        'shareCount': (await session.execute(select(func.count()).select_from(Share).where(Share.workspace_id == row.workspace_id, Share.thread_id == row.id))).scalar_one() if role == 'owner' else 0}
    if full:
        messages = (await session.execute(select(Message).where(Message.workspace_id == row.workspace_id, Message.thread_id == row.id).order_by(Message.created_at, Message.id))).scalars().all()
        result.update(messages=[{'id': str(m.id), 'text': m.text} for m in messages], sources=row.sources, runs=row.runs)
    return result


def audit(session, row, actor, action, entity_id=None):
    append_audit(session, workspace_id=row.workspace_id, actor_id=actor, action='conversation_thread.'+action,
        entity_type='conversation_thread', entity_id=entity_id or row.id)


async def intent(session, request, actor, operation, body):
    key = request.headers.get('Idempotency-Key')
    if not key:
        raise ApiError(400, 'INVALID_REQUEST', 'Idempotency-Key header is required')
    return await begin_idempotency(session, workspace_id=request.path_params['workspace_id'], actor_id=actor,
        operation_id=operation, key=key, body=body,
        target={k:str(v) for k,v in request.path_params.items()}, precondition=request.headers.get('If-Match'))


def bump(row, request):
    if row.version != if_match_version(request.headers.get('If-Match')):
        raise ApiError(409, 'STALE_REVISION', 'discussion changed; copy unsaved text and reload')
    row.version += 1
    row.updated_at = datetime.now(timezone.utc)


@router.get('', operation_id='listConversationThreads')
async def list_threads(workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal), offset: int = Query(0, ge=0, le=10000), limit: int = Query(50, ge=1, le=100)):
    async with access(workspace_id, project_id, principal) as (session, actor):
        predicate = (*thread_scope(workspace_id, project_id), or_(Thread.owner_user_id == actor, shared(actor)))
        total = (await session.execute(select(func.count()).select_from(Thread).where(*predicate))).scalar_one()
        rows = (await session.execute(select(Thread).where(*predicate).order_by(Thread.updated_at.desc(), Thread.id).offset(offset).limit(limit))).scalars().all()
        items = []
        for row in rows:
            _, role = await load(session, workspace_id, project_id, row.id, actor)
            items.append(await data(session, row, role, full=False))
    return envelope({'items': items, 'total': total, 'offset': offset, 'limit': limit}, request.state.request_id)


@router.post('', status_code=201, operation_id='createConversationThread')
async def create_thread(workspace_id: uuid.UUID, project_id: uuid.UUID, payload: ImportThread, request: Request, principal: Principal = Depends(get_principal)):
    async with access(workspace_id, project_id, principal, lock_project=True) as (session, actor):
        drive_ids = [source.id for source in payload.sources if source.id.startswith('drive:')]
        if drive_ids:
            await approved_sources(session, workspace_id, project_id, drive_ids)
        outcome = await intent(session, request, actor, 'createConversationThread', payload.model_dump())
        if outcome.replay:
            row, role = await load(session, workspace_id, project_id, uuid.UUID(outcome.record.resource_id), actor, owner=True)
        else:
            count = (await session.execute(select(func.count()).select_from(Thread).where(*thread_scope(workspace_id, project_id), Thread.owner_user_id == actor))).scalar_one()
            if count >= 200:
                raise ApiError(409, 'THREAD_LIMIT', 'owned discussion limit reached')
            row = Thread(workspace_id=workspace_id, project_id=project_id, owner_user_id=actor,
                template_id=payload.template_id, title=payload.title, sources=[s.model_dump() for s in payload.sources], runs=[r.model_dump() for r in payload.runs], version=1)
            session.add(row)
            await session.flush()
            now = datetime.now(timezone.utc)
            for index, note in enumerate(payload.messages):
                session.add(Message(workspace_id=workspace_id, project_id=project_id, thread_id=row.id,
                    owner_user_id=actor, author_user_id=actor, text=note.text, created_at=now+timedelta(microseconds=index)))
            audit(session, row, actor, 'imported')
            complete_idempotency(outcome, str(row.id))  # No note/title copies in idempotency responses.
            await session.flush()
            role = 'owner'
        result = await data(session, row, role)
    return envelope(result, request.state.request_id)


@router.get('/{thread_id}', operation_id='getConversationThread')
async def get_thread(workspace_id: uuid.UUID, project_id: uuid.UUID, thread_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)):
    async with access(workspace_id, project_id, principal) as (session, actor):
        row, role = await load(session, workspace_id, project_id, thread_id, actor)
        result = await data(session, row, role)
    return envelope(result, request.state.request_id)


@router.patch('/{thread_id}', operation_id='renameConversationThread')
async def rename(workspace_id: uuid.UUID, project_id: uuid.UUID, thread_id: uuid.UUID, payload: Rename, request: Request, principal: Principal = Depends(get_principal)):
    async with access(workspace_id, project_id, principal) as (session, actor):
        row, role = await load(session, workspace_id, project_id, thread_id, actor, owner=True, lock=True)
        bump(row, request)
        row.title = payload.title
        await session.flush()
        result = await data(session, row, role)
    return envelope(result, request.state.request_id)


@router.post('/{thread_id}/messages', operation_id='appendConversationThreadMessage')
async def append(workspace_id: uuid.UUID, project_id: uuid.UUID, thread_id: uuid.UUID, payload: Note, request: Request, principal: Principal = Depends(get_principal)):
    async with access(workspace_id, project_id, principal) as (session, actor):
        row, role = await load(session, workspace_id, project_id, thread_id, actor, edit=True, lock=True)
        outcome = await intent(session, request, actor, 'appendConversationThreadMessage', payload.model_dump())
        if not outcome.replay:
            bump(row, request)
            count = (await session.execute(select(func.count()).select_from(Message).where(Message.workspace_id == workspace_id, Message.thread_id == row.id))).scalar_one()
            if count >= 100:
                raise ApiError(409, 'MESSAGE_LIMIT', 'discussion message limit reached')
            session.add(Message(workspace_id=workspace_id, project_id=project_id, thread_id=row.id, owner_user_id=row.owner_user_id, author_user_id=actor, text=payload.text))
            complete_idempotency(outcome, str(row.id))
            await session.flush()
        result = await data(session, row, role)
    return envelope(result, request.state.request_id)


@router.put('/{thread_id}/sources', operation_id='setConversationThreadSources')
async def sources(workspace_id: uuid.UUID, project_id: uuid.UUID, thread_id: uuid.UUID, payload: Sources, request: Request, principal: Principal = Depends(get_principal)):
    async with access(workspace_id, project_id, principal) as (session, actor):
        row, role = await load(session, workspace_id, project_id, thread_id, actor, edit=True, lock=True)
        drive_ids = [source.id for source in payload.sources if source.id.startswith('drive:')]
        if drive_ids:
            await approved_sources(session, workspace_id, project_id, drive_ids)
        outcome = await intent(session, request, actor, 'setConversationThreadSources', payload.model_dump())
        if not outcome.replay:
            bump(row, request)
            row.sources = [s.model_dump() for s in payload.sources]
            complete_idempotency(outcome, str(row.id))
            audit(session, row, actor, 'sources_changed')
            await session.flush()
        result = await data(session, row, role)
    return envelope(result, request.state.request_id)


@router.post('/{thread_id}/runs', operation_id='appendConversationThreadRun')
async def runs(workspace_id: uuid.UUID, project_id: uuid.UUID, thread_id: uuid.UUID, payload: RunRef, request: Request, principal: Principal = Depends(get_principal)):
    async with access(workspace_id, project_id, principal) as (session, actor):
        row, role = await load(session, workspace_id, project_id, thread_id, actor, edit=True, lock=True)
        outcome = await intent(session, request, actor, 'appendConversationThreadRun', payload.model_dump())
        if not outcome.replay:
            bump(row, request)
            refs = [r for r in row.runs if r['id'] != payload.id]
            if len(refs) >= 100:
                raise ApiError(409, 'RUN_LIMIT', 'discussion run limit reached')
            row.runs = refs + [payload.model_dump()]
            complete_idempotency(outcome, str(row.id))
            await session.flush()
        result = await data(session, row, role)
    return envelope(result, request.state.request_id)


@router.delete('/{thread_id}', operation_id='deleteConversationThread')
async def delete(workspace_id: uuid.UUID, project_id: uuid.UUID, thread_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)):
    async with access(workspace_id, project_id, principal) as (session, actor):
        row, _ = await load(session, workspace_id, project_id, thread_id, actor, owner=True, lock=True)
        bump(row, request)
        audit(session, row, actor, 'deleted')
        await session.delete(row)
    return envelope({'id': str(thread_id)}, request.state.request_id)


@router.get('/{thread_id}/share-recipients', operation_id='searchConversationThreadRecipients')
async def recipients(workspace_id: uuid.UUID, project_id: uuid.UUID, thread_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal), q: str = Query('', max_length=80), offset: int = Query(0, ge=0, le=10000), limit: int = Query(25, ge=1, le=25)):
    async with access(workspace_id, project_id, principal) as (session, actor):
        await load(session, workspace_id, project_id, thread_id, actor, owner=True)
        rows = (await session.execute(select(Membership, User.display_name).join(User, User.id == Membership.user_id).where(
            Membership.workspace_id == workspace_id, Membership.active.is_(True), Membership.user_id != actor,
            Membership.roles.overlap(['viewer','operator','reviewer','workspace_admin']), directory_search(q)).order_by(Membership.id).offset(offset).limit(limit))).all()
        result = [{'member_id': str(m.id), 'display_name': member_display_name(name, m.user_id)} for m, name in rows]
    return envelope({'items': result, 'offset': offset, 'limit': limit}, request.state.request_id)


@router.get('/{thread_id}/shares', operation_id='listConversationThreadShares')
async def shares(workspace_id: uuid.UUID, project_id: uuid.UUID, thread_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)):
    async with access(workspace_id, project_id, principal) as (session, actor):
        row, _ = await load(session, workspace_id, project_id, thread_id, actor, owner=True)
        rows = (await session.execute(select(Share, Membership, User.display_name).join(Membership, (Membership.workspace_id == Share.workspace_id) & (Membership.user_id == Share.grantee_user_id)).join(User, User.id == Share.grantee_user_id).where(Share.workspace_id == workspace_id, Share.thread_id == thread_id).order_by(Share.id))).all()
        result = {'version': row.version, 'items': [{'member_id':str(m.id), 'display_name':member_display_name(name, m.user_id), 'role':s.role, 'active':m.active and permission_for_roles(m.roles,'getProject')} for s,m,name in rows]}
    return envelope(result, request.state.request_id)


@router.put('/{thread_id}/shares/{member_id}', operation_id='putConversationThreadShare')
async def grant(workspace_id: uuid.UUID, project_id: uuid.UUID, thread_id: uuid.UUID, member_id: uuid.UUID, payload: Grant, request: Request, principal: Principal = Depends(get_principal)):
    async with access(workspace_id, project_id, principal) as (session, actor):
        row, role = await load(session, workspace_id, project_id, thread_id, actor, owner=True, lock=True)
        member = (await session.execute(select(Membership).where(Membership.workspace_id == workspace_id, Membership.id == member_id, Membership.active.is_(True)))).scalar_one_or_none()
        if member is None or member.user_id == actor or not permission_for_roles(member.roles, 'getProject'):
            raise not_found()
        outcome = await intent(session, request, actor, 'putConversationThreadShare', payload.model_dump())
        if not outcome.replay:
            bump(row, request)
            share = (await session.execute(select(Share).where(Share.workspace_id == workspace_id, Share.thread_id == thread_id, Share.grantee_user_id == member.user_id))).scalar_one_or_none()
            if share is None:
                count = (await session.execute(select(func.count()).select_from(Share).where(Share.workspace_id == workspace_id, Share.thread_id == thread_id))).scalar_one()
                if count >= 25:
                    raise ApiError(409, 'SHARE_LIMIT', 'discussion share limit reached')
                share = Share(workspace_id=workspace_id, project_id=project_id, thread_id=thread_id, owner_user_id=actor, grantee_user_id=member.user_id, granted_by=actor, role=payload.role)
                session.add(share)
                action = 'shared'
            else:
                share.role = payload.role
                share.version += 1
                action = 'role_changed'
            await session.flush()
            audit(session, row, actor, action, share.id)
            complete_idempotency(outcome, str(row.id))
        result = await data(session, row, role)
    return envelope(result, request.state.request_id)


@router.delete('/{thread_id}/shares/{member_id}', operation_id='revokeConversationThreadShare')
async def revoke(workspace_id: uuid.UUID, project_id: uuid.UUID, thread_id: uuid.UUID, member_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)):
    async with access(workspace_id, project_id, principal) as (session, actor):
        row, role = await load(session, workspace_id, project_id, thread_id, actor, owner=True, lock=True)
        bump(row, request)
        share = (await session.execute(select(Share).join(Membership, (Membership.workspace_id == Share.workspace_id) & (Membership.user_id == Share.grantee_user_id)).where(Share.workspace_id == workspace_id, Share.thread_id == thread_id, Membership.id == member_id))).scalar_one_or_none()
        if share is None:
            raise not_found()
        audit(session, row, actor, 'revoked', share.id)
        await session.delete(share)
        await session.flush()
        result = await data(session, row, role)
    return envelope(result, request.state.request_id)
