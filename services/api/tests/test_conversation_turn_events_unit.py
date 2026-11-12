"""Unit: deterministic event ordering, payload validation, flush-first allocator."""
import asyncio
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from buyeros_api.sales import turn_contracts
from buyeros_api.services import conversation_turn_events as events


def text_part(text='hello'):
    return turn_contracts.TextPart(text=text, language='en')


def tool_part(state='completed', error_code=None):
    return turn_contracts.ToolActivityPart(call_id=uuid.uuid4(),
        capability='documents.read', title='Saved output', state=state,
        started_at=datetime.now(timezone.utc), finished_at=datetime.now(timezone.utc),
        summary='summary', error_code=error_code)


def proposal_part():
    return turn_contracts.ProposalPart(proposal_id=uuid.uuid4(), capability='documents.read',
        title='Summarise', rationale='rationale', arguments_preview={'a': 1},
        cost=turn_contracts.ProposalCost(kind='nonbillable', amount=0, unit='USD'))


def test_event_sequence_is_ordered_and_terminal_last():
    parts = [text_part(), tool_part(state='failed', error_code='OUTPUT_NEEDS_REVIEW'),
             proposal_part(), text_part('second')]
    notices = [turn_contracts.TurnNotice(code='SALES_ADMISSION_DISABLED', message='disabled')]
    sequence = events.build_turn_events(parts, notices, 'failed')
    kinds = [kind for kind, _ in sequence]
    assert kinds[0] == 'turn.started'
    assert kinds[-1] == 'turn.final'
    assert kinds.count('turn.final') == 1
    assert 'turn.final' not in kinds[:-1]
    part_events = [payload for kind, payload in sequence if kind == 'part']
    assert [payload['index'] for payload in part_events] == [0, 1, 2, 3]
    assert part_events[0]['part']['kind'] == 'text'
    tool = next(payload for kind, payload in sequence if kind == 'tool')
    assert tool['state'] == 'failed' and tool['error_code'] == 'OUTPUT_NEEDS_REVIEW'
    proposal = next(payload for kind, payload in sequence if kind == 'proposal')
    assert proposal['requires_approval'] is True
    notice_codes = [payload['code'] for kind, payload in sequence if kind == 'notice']
    assert 'SALES_ADMISSION_DISABLED' in notice_codes
    # Every emitted payload passes the same validator the database uses.
    for kind, payload in sequence:
        events.validate_event_payload(kind, payload)


def test_event_payload_validation_rejects_unknown_or_malformed_shapes():
    with pytest.raises(ValueError):
        events.validate_event_payload('turn.delta', {'text': 'x'})
    with pytest.raises(ValidationError):
        events.validate_event_payload('turn.final', {'status': 'running'})
    with pytest.raises(ValidationError):
        events.validate_event_payload('tool', {'call_id': 'not-a-uuid',
            'capability': 'documents.read', 'state': 'completed'})
    with pytest.raises(ValidationError):
        events.validate_event_payload('proposal', {'proposal_id': str(uuid.uuid4()),
            'capability': 'documents.read', 'requires_approval': False})
    oversized = text_part('x' * 4000)
    # A part event embeds one bounded MessagePart; injecting an extra field is
    # rejected by the same strict part model, never silently persisted.
    with pytest.raises((ValidationError, ValueError)):
        events.validate_event_payload('part', {'index': 0, 'part': {
            **oversized.model_dump(mode='json'), 'tenant_id': str(uuid.uuid4())}})


def test_event_allocator_flushes_pending_rows_before_reading_max():
    class FakeSession:
        def __init__(self):
            self.calls = []

        async def flush(self):
            self.calls.append('flush')

        async def execute(self, statement):
            self.calls.append('execute')
            return SimpleNamespace(scalar_one=lambda: 5)

    session = FakeSession()
    value = asyncio.run(events.next_turn_event_seq(session,
        uuid.uuid4(), uuid.uuid4()))
    assert session.calls == ['flush', 'execute']
    assert value == 6
