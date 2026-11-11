"""Turn-first conversation transport; all authority is server derived.

`POST /conversation-turns` is the normal entry point for a discussion: when
`thread_id` is absent the server creates the thread and the first user message in
one transaction. A separate authenticated decision executes one inline proposal
through the existing typed sales-task / sales-output services.
"""
import asyncio
import json
import time
import uuid

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import StreamingResponse

from ..auth import Principal, get_principal
from ..deps import get_rate_engine
from ..errors import ApiError, envelope
from ..idempotency import if_match_version
from ...sales.contracts import Scope
from ...sales.turn_contracts import TurnDecisionRequest, TurnRequest
from ...services.conversation_access import access
from ...services import conversation_metrics
from ...services import conversation_turns as service
from ...services import turn_rate_limit
from ...services.conversation_turn_events import read_turn_events
from ...services.conversation_proposal_read import decorate_turn_payload
from .conversation_threads import data as thread_data

# Bounded streaming window; the client reconnects with its last seq.
STREAM_POLL_SECONDS = 0.25
STREAM_HEARTBEAT_SECONDS = 5.0
STREAM_DEADLINE_SECONDS = 20.0
TERMINAL_STATUSES = frozenset({'completed', 'failed', 'needs_input',
    'needs_approval', 'cancelled', 'outcome_unknown'})


def _sse(row) -> str:
    data = json.dumps({'seq': row.seq, 'turn_id': str(row.turn_id),
        'kind': row.kind, 'payload': row.payload}, separators=(',', ':'),
        ensure_ascii=False)
    return f'event: {row.kind}\ndata: {data}\n\n'


async def _stream_events(workspace_id, project_id, actor_id, turn_id, after):
    from ...api.deps import get_engine
    from ...db.session import tenant_session
    scope = Scope(workspace_id=workspace_id, project_id=project_id, actor_id=actor_id)
    cursor = after
    deadline = time.monotonic() + STREAM_DEADLINE_SECONDS
    last_heartbeat = time.monotonic()
    while True:
        async with tenant_session(get_engine(), workspace_id) as session:
            rows = await read_turn_events(session, scope, turn_id, cursor)
            status = await service.turn_status(session, scope, turn_id)
        terminal = False
        for row in rows:
            yield _sse(row)
            cursor = row.seq
            terminal = terminal or row.kind == 'turn.final'
        if terminal:
            return
        if not rows and status in TERMINAL_STATUSES:
            # Legacy/terminal turn without persisted events: refetch instead of tailing.
            return
        now = time.monotonic()
        if now >= deadline:
            return
        if now - last_heartbeat >= STREAM_HEARTBEAT_SECONDS:
            yield ': heartbeat\n\n'
            last_heartbeat = now
        await asyncio.sleep(STREAM_POLL_SECONDS)

router = APIRouter(prefix='/v1/workspaces/{workspace_id}/projects/{project_id}/conversation-turns',
    tags=['conversation-turns'])


def _key(request: Request) -> str:
    value = request.headers.get('Idempotency-Key', '')
    if not 8 <= len(value) <= 200:
        raise ApiError(400, 'INVALID_REQUEST', 'Idempotency-Key must be 8..200 characters')
    return value


def _body(payload, precondition) -> None:
    expected = getattr(payload, 'expected_thread_version', None)
    if expected is not None and expected != precondition:
        raise ApiError(422, 'INVALID_REQUEST', 'body and If-Match thread version differ')


@router.post('', status_code=200, operation_id='createConversationTurn')
async def create(workspace_id: uuid.UUID, project_id: uuid.UUID, payload: TurnRequest,
    request: Request, response: Response, principal: Principal = Depends(get_principal),
    precondition: str | None = Header(default=None, alias='If-Match')):
    key = _key(request)
    response.headers['Cache-Control'] = 'no-store'
    async with access(workspace_id, project_id, principal) as (session, actor):
        scope = Scope(workspace_id=workspace_id, project_id=project_id, actor_id=actor)
        if payload.thread_id is not None:
            # Existing discussion: the strong native precondition is mandatory.
            expected = if_match_version(precondition)
            _body(payload, expected)
            payload = payload.model_copy(update={'expected_thread_version': expected})
        thread, role, turn = await service.create_turn(session, scope, payload, key,
            admit=lambda: turn_rate_limit.enforce_turn_rate_limit(
                get_rate_engine(), workspace_id))
        turn_payload = turn.model_dump(mode='json')
        await decorate_turn_payload(session, scope.workspace_id, scope.project_id,
            thread.id, turn.id, turn_payload, actor)
        result = {'thread': await thread_data(session, thread, role, viewer=actor),
                  'turn': turn_payload}
        response.headers['ETag'] = f'"{thread.version}"'
    return envelope(result, request.state.request_id)


@router.post('/{turn_id}/decisions', operation_id='decideConversationTurnProposal')
async def decide(workspace_id: uuid.UUID, project_id: uuid.UUID, turn_id: uuid.UUID,
    payload: TurnDecisionRequest, request: Request, response: Response,
    principal: Principal = Depends(get_principal),
    precondition: str | None = Header(default=None, alias='If-Match')):
    key = _key(request)
    response.headers['Cache-Control'] = 'no-store'
    _body(payload, if_match_version(precondition))
    # Mutation path: current membership, policy and budget gates stay serialized.
    async with access(workspace_id, project_id, principal, sales=True,
                      admission=False) as (session, actor):
        scope = Scope(workspace_id=workspace_id, project_id=project_id, actor_id=actor)
        thread, role, turn, _replayed = await service.decide(session, scope, turn_id,
            payload, key)
        turn_payload = turn.model_dump(mode='json')
        await decorate_turn_payload(session, scope.workspace_id, scope.project_id,
            thread.id, turn.id, turn_payload, actor)
        result = {'thread': await thread_data(session, thread, role, viewer=actor),
                  'turn': turn_payload}
        response.headers['ETag'] = f'"{thread.version}"'
    return envelope(result, request.state.request_id)


@router.post('/{turn_id}/cancel', operation_id='cancelConversationTurn')
async def cancel(workspace_id: uuid.UUID, project_id: uuid.UUID, turn_id: uuid.UUID,
    request: Request, response: Response, principal: Principal = Depends(get_principal),
    precondition: str | None = Header(default=None, alias='If-Match')):
    key = _key(request)
    response.headers['Cache-Control'] = 'no-store'
    expected = if_match_version(precondition)
    if await request.body():
        raise ApiError(400, 'INVALID_REQUEST', 'cancel takes no request body')
    async with access(workspace_id, project_id, principal, sales=True,
                      admission=False) as (session, actor):
        scope = Scope(workspace_id=workspace_id, project_id=project_id, actor_id=actor)
        thread, role, turn = await service.cancel_turn(session, scope, turn_id, expected, key)
        turn_payload = turn.model_dump(mode='json')
        await decorate_turn_payload(session, scope.workspace_id, scope.project_id,
            thread.id, turn.id, turn_payload, actor)
        result = {'thread': await thread_data(session, thread, role, viewer=actor),
                  'turn': turn_payload}
        response.headers['ETag'] = f'"{thread.version}"'
    return envelope(result, request.state.request_id)


@router.get('/{turn_id}/events', operation_id='streamConversationTurnEvents')
async def stream_events(workspace_id: uuid.UUID, project_id: uuid.UUID,
    turn_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal),
    after: int = Query(0, ge=0)):
    """Persisted turn events as Server-Sent Events; never re-runs a turn."""
    async with access(workspace_id, project_id, principal) as (session, actor):
        scope = Scope(workspace_id=workspace_id, project_id=project_id, actor_id=actor)
        await service.stream_turn(session, scope, turn_id)
    return StreamingResponse(_stream_events(workspace_id, project_id, actor, turn_id, after),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})


@router.get('/metrics', operation_id='readConversationTurnMetrics')
async def metrics(workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request,
    response: Response, principal: Principal = Depends(get_principal),
    window_days: int = Query(conversation_metrics.DEFAULT_WINDOW_DAYS, ge=1,
        le=conversation_metrics.MAX_WINDOW_DAYS)):
    """Bounded aggregate turn/proposal/budget metrics for this project."""
    response.headers['Cache-Control'] = 'no-store'
    async with access(workspace_id, project_id, principal) as (session, actor):
        scope = Scope(workspace_id=workspace_id, project_id=project_id, actor_id=actor)
        data = await conversation_metrics.turn_metrics(session, scope,
            window_days=window_days)
    return envelope(data, request.state.request_id)


@router.post('/{turn_id}/reconcile', operation_id='reconcileConversationTurn')
async def reconcile(workspace_id: uuid.UUID, project_id: uuid.UUID,
    turn_id: uuid.UUID, request: Request, response: Response,
    principal: Principal = Depends(get_principal)):
    """Resolve an outcome_unknown turn from persisted evidence; never dispatches."""
    key = _key(request)
    if await request.body():
        raise ApiError(400, 'INVALID_REQUEST', 'reconcile takes no request body')
    response.headers['Cache-Control'] = 'no-store'
    async with access(workspace_id, project_id, principal, sales=True,
                      admission=False) as (session, actor):
        scope = Scope(workspace_id=workspace_id, project_id=project_id, actor_id=actor)
        thread, role, turn = await service.reconcile_turn(session, scope, turn_id, key)
        turn_payload = turn.model_dump(mode='json')
        await decorate_turn_payload(session, scope.workspace_id, scope.project_id,
            thread.id, turn.id, turn_payload, actor)
        result = {'thread': await thread_data(session, thread, role, viewer=actor),
                  'turn': turn_payload}
        response.headers['ETag'] = f'"{thread.version}"'
    return envelope(result, request.state.request_id)
