"""Durable, derived conversation-turn events for SSE replay and recovery.

The append path is the *only* writer. Events are always written inside the
transaction that changes the turn/part/proposal state they describe; the
terminal ``turn.final`` event is therefore committed atomically with
``conversation_turns.status``.

``seq`` allocation flushes pending rows before computing the next value: the
same defect that previously produced ``UniqueViolation`` on the message
sequence must not recur for events (the caller already holds the discussion row
lock, so concurrent appends serialize).
"""
import json
from datetime import timezone

from sqlalchemy import func, select

from ..db.conversation_turn_events import EVENT_KINDS, ConversationTurnEvent
from ..sales.turn_contracts import (NoticeEventPayload, PartEventPayload,
    ProposalEventPayload, ToolEventPayload, TurnFinalPayload, TurnStartedPayload)

EVENT_PAYLOAD_MODELS = {
    'turn.started': TurnStartedPayload,
    'part': PartEventPayload,
    'tool': ToolEventPayload,
    'proposal': ProposalEventPayload,
    'notice': NoticeEventPayload,
    'turn.final': TurnFinalPayload,
}
# Bounds: a part event embeds one MessagePart (itself <= 16 KiB validated).
MAX_EVENT_PAYLOAD_BYTES = 32768
TERMINAL_KIND = 'turn.final'


def validate_event_payload(kind: str, payload: dict) -> dict:
    if kind not in EVENT_PAYLOAD_MODELS:
        raise ValueError('unknown turn event kind')
    model = EVENT_PAYLOAD_MODELS[kind].model_validate(payload)
    data = model.model_dump(mode='json')
    if len(json.dumps(data, sort_keys=True, separators=(',', ':'),
            ensure_ascii=False).encode('utf-8')) > MAX_EVENT_PAYLOAD_BYTES:
        raise ValueError('turn event payload exceeds its bound')
    return data



async def next_turn_event_seq(session, workspace_id, turn_id) -> int:
    """Flush pending rows, then allocate the next per-turn sequence."""
    await session.flush()
    current = (await session.execute(select(func.coalesce(
        func.max(ConversationTurnEvent.seq), 0)).where(
        ConversationTurnEvent.workspace_id == workspace_id,
        ConversationTurnEvent.turn_id == turn_id))).scalar_one()
    return current + 1


def _instant(value) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def build_turn_events(parts, notices, status, *, started_at=None,
                      finished_at=None) -> list[tuple[str, dict]]:
    """Deterministic event sequence for one persisted turn.

    ``turn.started`` first, then for each persisted assistant part a ``part``
    event plus its typed ``tool``/``proposal``/``notice`` transition, turn-level
    notices, and exactly one terminal ``turn.final`` last.

    ``started_at``/``finished_at`` are application-observed boundary instants:
    every event row of one turn shares the transaction timestamp, so latency
    must come from these payloads (they are optional for historical events).
    """
    events: list[tuple[str, dict]] = [('turn.started', {
        'status': 'running', 'started_at': _instant(started_at)})]
    for index, part in enumerate(parts):
        data = part.model_dump(mode='json') if hasattr(part, 'model_dump') else dict(part)
        events.append(('part', {'index': index, 'part': data}))
        if data.get('kind') == 'tool_activity':
            events.append(('tool', {
                'call_id': data['call_id'], 'capability': data['capability'],
                'state': data['state'], 'summary': data.get('summary'),
                'error_code': data.get('error_code')}))
        elif data.get('kind') == 'proposal':
            events.append(('proposal', {
                'proposal_id': data['proposal_id'], 'capability': data['capability'],
                'requires_approval': data['requires_approval']}))
        elif data.get('kind') == 'notice':
            events.append(('notice', {'code': data['code'], 'message': data['message']}))
    for notice in notices:
        data = notice.model_dump(mode='json') if hasattr(notice, 'model_dump') else dict(notice)
        events.append(('notice', {'code': data['code'], 'message': data['message']}))
    events.append(('turn.final', {'status': status,
                                 'finished_at': _instant(finished_at)}))
    return events


async def append_turn_events(session, scope, turn, parts, notices, status, *,
                             started_at=None, finished_at=None):
    """Append all events for one turn inside the caller's transaction."""
    rows = []
    for kind, payload in build_turn_events(parts, notices, status,
            started_at=started_at, finished_at=finished_at):
        payload = validate_event_payload(kind, payload)
        seq = await next_turn_event_seq(session, scope.workspace_id, turn.id)
        row = ConversationTurnEvent(workspace_id=scope.workspace_id,
            project_id=scope.project_id, thread_id=turn.thread_id, turn_id=turn.id,
            seq=seq, kind=kind, payload=payload)
        session.add(row)
        rows.append(row)
    await session.flush()
    return rows


async def read_turn_events(session, scope, turn_id, after: int = 0, limit: int = 100):
    return (await session.execute(select(ConversationTurnEvent).where(
        ConversationTurnEvent.workspace_id == scope.workspace_id,
        ConversationTurnEvent.project_id == scope.project_id,
        ConversationTurnEvent.turn_id == turn_id,
        ConversationTurnEvent.seq > after).order_by(
            ConversationTurnEvent.seq).limit(limit))).scalars().all()


def event_payload(row) -> dict:
    return {'seq': row.seq, 'kind': row.kind, 'payload': row.payload}
