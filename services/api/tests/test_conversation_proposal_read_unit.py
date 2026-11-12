"""Unit: coarse/privacy-preserving, containment-scoped decision decoration."""
import json
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

from buyeros_api.services.conversation_proposal_read import (coarse_actor_label,
    decorate_parts, decision_payload)

VIEWER = uuid.uuid4()
OTHER = uuid.uuid4()
TURN = uuid.uuid4()


def proposal(proposal_id=None):
    return {'kind': 'proposal', 'proposal_id': str(proposal_id or uuid.uuid4()),
        'capability': 'documents.read', 'title': 'Summarise',
        'rationale': 'Rationale', 'arguments_preview': {'a': 1},
        'cost': {'kind': 'nonbillable', 'amount': '0', 'unit': 'USD',
                 'may_incur_provider_charges': False, 'known': True},
        'requires_approval': True}


def decision_row(actor=VIEWER, choice='approve', turn_id=TURN, proposal_id=None):
    return SimpleNamespace(proposal_id=proposal_id, turn_id=turn_id,
        actor_id=actor, decision=choice,
        created_at=datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc))


def test_coarse_actor_label_is_you_or_a_workspace_member_only():
    assert coarse_actor_label(VIEWER, VIEWER) == 'you'
    assert coarse_actor_label(OTHER, VIEWER) == 'a workspace member'
    assert coarse_actor_label(None, VIEWER) == 'a workspace member'
    assert coarse_actor_label(VIEWER, None) == 'a workspace member'
    for label in ('you', 'a workspace member'):
        assert str(VIEWER) not in label and str(OTHER) not in label


def test_decision_payload_carries_no_raw_identity():
    row = decision_row(actor=OTHER, choice='reject')
    payload = decision_payload(row, VIEWER)
    assert payload['choice'] == 'reject'
    assert payload['decided_by'] == 'a workspace member'
    assert datetime.fromisoformat(payload['decided_at']) == row.created_at
    encoded = json.dumps(payload)
    assert str(OTHER) not in encoded and str(VIEWER) not in encoded


def test_decision_payload_allowlist_degrades_malformed_rows_to_absent():
    for bad in ('compromised', 'APPROVE', None, 1):
        assert decision_payload(decision_row(choice=bad), VIEWER) is None
    assert decision_payload(SimpleNamespace(decision='approve', created_at=None,
        actor_id=VIEWER), VIEWER) is None


def test_decorate_parts_is_a_copy_and_requires_containing_turn():
    target = str(uuid.uuid4())
    stored = [proposal(target), {'kind': 'text', 'text': 'hello', 'language': 'en'}]
    original = deepcopy(stored)
    row = decision_row(actor=VIEWER, turn_id=TURN, proposal_id=uuid.UUID(target))
    decorated = decorate_parts([dict(stored[0])], {target: row}, VIEWER, turn_id=TURN)
    assert decorated[0]['decision'] == {'choice': 'approve',
        'decided_at': row.created_at.isoformat(), 'decided_by': 'you'}
    assert stored == original  # stored parts unchanged
    assert 'decision' not in json.dumps(stored)
    # A decision whose persisted turn does not contain the part is not used.
    foreign = decision_row(actor=VIEWER, turn_id=uuid.uuid4(),
        proposal_id=uuid.UUID(target))
    assert 'decision' not in decorate_parts(stored, {target: foreign}, VIEWER,
        turn_id=TURN)[0]
    # Without a proven containing turn no decoration is possible.
    assert 'decision' not in decorate_parts(stored, {target: row}, VIEWER,
        turn_id=None)[0]
    same = decorate_parts([dict(stored[0])], {target: row}, OTHER, turn_id=TURN)
    assert same[0]['decision']['decided_by'] == 'a workspace member'


def test_absent_decision_adds_no_field():
    stored = [proposal()]
    assert 'decision' not in decorate_parts(stored, {}, VIEWER, turn_id=TURN)[0]
