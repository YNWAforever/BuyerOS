"""Turn-first conversation transport; all authority is server derived.

`POST /conversation-turns` is the normal entry point for a discussion: when
`thread_id` is absent the server creates the thread and the first user message in
one transaction. A separate authenticated decision executes one inline proposal
through the existing typed sales-task / sales-output services.
"""
import uuid

from fastapi import APIRouter, Depends, Header, Request, Response

from ..auth import Principal, get_principal
from ..errors import ApiError, envelope
from ..idempotency import if_match_version
from ...sales.contracts import Scope
from ...sales.turn_contracts import TurnDecisionRequest, TurnRequest
from ...services.conversation_access import access
from ...services import conversation_turns as service
from .conversation_threads import data as thread_data

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
        thread, role, turn = await service.create_turn(session, scope, payload, key)
        result = {'thread': await thread_data(session, thread, role),
                  'turn': turn.model_dump(mode='json')}
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
        result = {'thread': await thread_data(session, thread, role),
                  'turn': turn.model_dump(mode='json')}
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
        result = {'thread': await thread_data(session, thread, role),
                  'turn': turn.model_dump(mode='json')}
        response.headers['ETag'] = f'"{thread.version}"'
    return envelope(result, request.state.request_id)
