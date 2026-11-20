"""Bounded readable history and additive conversation-basis contracts."""
import hashlib
import uuid

import pytest

from buyeros_api.providers import conversation_model
from buyeros_api.services import conversation_admission
from buyeros_api.services.conversation_context import (
    MAX_HISTORY_BYTES, MAX_HISTORY_MESSAGES, _assistant_body_is_safe,
    bounded_history, readable_items)


def test_bounded_history_is_chronological_and_capped_at_twelve():
    # Callers supply newest-first rows; the bounded window is returned oldest-first.
    items = [('user', f'message {index}') for index in reversed(range(15))]
    result = bounded_history(items)
    assert len(result) == MAX_HISTORY_MESSAGES
    assert [item['text'] for item in result] == [
        f'message {index}' for index in range(3, 15)]
    assert {item['role'] for item in result} == {'user'}


def test_bounded_history_is_a_newest_contiguous_suffix_on_byte_overflow():
    # Newest-first input. Once an oversized message no longer fits, older complete
    # messages behind it are not selected: the window is the newest contiguous
    # suffix, and the oversized message itself is never truncated.
    items = [('assistant', 'newest complete'),
             ('assistant', 'x' * (MAX_HISTORY_BYTES + 1)),
             ('user', 'older complete')]
    result = bounded_history(items)
    assert result == [{'role': 'assistant', 'text': 'newest complete'}]
    assert sum(len(item['text'].encode()) for item in result) <= MAX_HISTORY_BYTES


def test_bounded_history_twelve_users_survive_interleaved_cited_assistants():
    # readable_items filters cited assistant rows before the bound; the scan is
    # newest-first and the final window keeps twelve readable user messages.
    cited = [{'kind': 'citations', 'items': [{'id': 'document:stale'}]}]
    rows = []
    for index in reversed(range(20)):
        rows.append(('user', f'buyer {index}', []))
        rows.append(('assistant', 'cited body', cited))
    result = readable_items(rows)
    assert len(result) == MAX_HISTORY_MESSAGES
    assert [item['text'] for item in result] == [
        f'buyer {index}' for index in range(8, 20)]


def test_bounded_history_rejects_unknown_roles_and_empty_text():
    with pytest.raises(ValueError):
        bounded_history([('system', 'x')])
    assert bounded_history([('user', '   ')]) == []


def test_assistant_bodies_with_citations_are_never_replayed():
    assert _assistant_body_is_safe([])
    assert _assistant_body_is_safe([{'kind': 'notice', 'code': 'SOURCES_REQUIRED'}])
    # An ID-only citation cannot prove the reviewed content/revision unchanged.
    assert not _assistant_body_is_safe([{'kind': 'citations', 'items': [
        {'id': 'document:not-authorized-to-replay'}]}])


PROFILE_ID = str(uuid.uuid4())
FACT_ID = str(uuid.uuid4())
FACT_SOURCE = f'fact:profile:{PROFILE_ID}:{FACT_ID}'
_CITATION = {'id': FACT_SOURCE, 'label': 'Approved offer fact',
             'locator': {'surface': 'profile', 'id': PROFILE_ID}}


class _Grounding:
    profile_id = PROFILE_ID
    profile_hash = 'sha256:' + 'a' * 64
    offer_revision = 1
    sources = [{'citation': _CITATION, 'excerpts': ['Approved source excerpt']}]
    document_ids = []
    citations = [_CITATION]


def _basis(history=None, thread_id=None, thread_version=None):
    return conversation_admission.make_basis(_Grounding(),
        workspace_id=uuid.uuid4(), project_id=uuid.uuid4(), actor_id=uuid.uuid4(),
        question='Which buyer came second?', history=history,
        thread_id=thread_id, thread_version=thread_version)


def test_fit_history_drops_oldest_messages_to_the_real_transport_budget():
    from buyeros_api.services.conversation_reply import ROUTE
    history = [{'role': 'user', 'text': 'old ' + 'x' * 2600},
               {'role': 'user', 'text': 'new ' + 'y' * 2600}]
    fitted, basis = conversation_admission.fit_history(_Grounding(), history=history,
        route=ROUTE, model_id='synthetic-model', workspace_id=uuid.uuid4(),
        project_id=uuid.uuid4(), actor_id=uuid.uuid4(),
        question='Which buyer came second?')
    assert fitted == history[-1:]
    assert basis['history'] == fitted


def test_question_that_cannot_fit_returns_no_dispatch_condition():
    from buyeros_api.services.conversation_reply import ROUTE
    from buyeros_api.api.errors import ApiError
    with pytest.raises(ApiError) as error:
        conversation_admission.fit_history(_Grounding(), history=[],
            route=ROUTE, model_id='synthetic-model', workspace_id=uuid.uuid4(),
            project_id=uuid.uuid4(), actor_id=uuid.uuid4(),
            question='q' * 7000)
    assert error.value.code == 'CONVERSATION_CONTEXT_TOO_LARGE'


def test_legacy_basis_without_history_or_thread_stays_compatible():
    legacy = _basis()
    assert 'history' not in legacy and 'thread_id' not in legacy
    conversation_model.validate_basis(legacy)
    assert legacy['basis_hash'] == hashlib.sha256(
        conversation_admission.canonical_json(
            {key: value for key, value in legacy.items() if key != 'basis_hash'})
    ).hexdigest()


def test_basis_history_and_thread_identity_are_optional_and_validated():
    history = [{'role': 'user', 'text': 'The first buyer was Acme.'},
               {'role': 'user', 'text': 'The second buyer was Beta.'}]
    basis = _basis(history=history, thread_id=uuid.uuid4(), thread_version=3)
    conversation_model.validate_basis(basis)
    assert basis['history'] == history
    assert basis['thread_version'] == 3

    bad_role = {**basis, 'history': [{'role': 'system', 'text': 'x'}]}
    with pytest.raises(ValueError):
        conversation_model.validate_basis(bad_role)
    too_much = {**basis, 'history': [{'role': 'user', 'text': 'x' * 4097}]}
    with pytest.raises(ValueError):
        conversation_model.validate_basis(too_much)
    with pytest.raises(ValueError):
        conversation_model.validate_basis({**basis, 'thread_version': 0})
