"""Deterministic turn orchestration: planning, parts and replay identity.

No database and no provider: these tests pin the code-owned registry boundary,
the bounded plan ceiling, the strict citation adapter and the canonical durable
references built for a later approved execution.
"""
import uuid
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from buyeros_api.api.errors import ApiError
from buyeros_api.sales import turn_contracts
from buyeros_api.sales.registry import load_skill
from buyeros_api.services import conversation_turns as engine
from buyeros_api.services.conversation_reply import Grounding, reply_from_grounding

PROFILE = 'c5000000-0000-4000-8000-000000000001'
DOCUMENT = 'c3000000-0000-4000-8000-000000000001'
FACT = 'c4000000-0000-4000-8000-000000000001'
FACT_SOURCE = f'fact:profile:{PROFILE}:{FACT}'
DOCUMENT_SOURCE = f'document:{DOCUMENT}'


def grounding(*, with_document=True):
    citations = [{'id': FACT_SOURCE, 'label': 'Approved offer fact',
                  'locator': {'surface': 'profile', 'id': PROFILE}}]
    if with_document:
        citations.append({'id': DOCUMENT_SOURCE, 'label': 'Offer document',
                          'locator': {'surface': 'document', 'id': DOCUMENT}})
    return Grounding(citations=citations, excerpts=['Industrial sensors'],
        sources=[], profile_id=PROFILE, profile_hash='a' * 64, offer_revision=1,
        document_ids=[DOCUMENT] if with_document else [])


def thread(template_id='custom'):
    return SimpleNamespace(id=uuid.uuid4(), template_id=template_id)


def project(languages=('en',)):
    return SimpleNamespace(language_preferences=list(languages))


def request(**changes):
    values = {'client_message_id': uuid.uuid4(), 'language': 'en',
              'text': 'Summarise the selected documents'}
    values.update(changes)
    return turn_contracts.TurnRequest(**values)


def test_turn_first_plan_is_deterministic_and_registry_derived():
    payload = request()
    thread_row = thread('understand-documents')
    first, staged = engine.build_plan(thread_row, payload,
        engine.skill_for(thread_row, payload), project(), grounding(), True, True)
    second, staged_again = engine.build_plan(thread_row, payload,
        engine.skill_for(thread_row, payload), project(), grounding(), True, True)
    assert first.steps == ('answer', 'propose') == second.steps
    assert first.proposal == second.proposal
    assert first.proposal.capability == 'documents.read'
    skill = load_skill('understand-documents', '1')
    assert first.proposal.capability in skill.allowed_actions
    assert first.proposal.requires_approval is True
    assert staged['capability'] == 'documents.read'
    assert staged['arguments']['document_ids'] == [DOCUMENT]
    assert first.proposal not in second.notices


def test_request_skill_override_is_validated_against_the_registry():
    payload = request(skill_id='invented-skill')
    with pytest.raises(ApiError) as caught:
        engine.skill_for(thread(), payload)
    assert caught.value.code == 'INVALID_REQUEST'


def test_plan_ceiling_is_bounded_and_capabilities_are_registered():
    payload = request()
    thread_row = thread('understand-documents')
    plan, staged = engine.build_plan(thread_row, payload,
        engine.skill_for(thread_row, payload), project(), grounding(), True, True)
    assert len(plan.steps) == len(set(plan.steps)) <= turn_contracts.MAX_TURN_STEPS
    assert set(engine.EXECUTORS) == {'documents.read', 'research.read'}
    assert plan.proposal.capability in engine.EXECUTORS
    assert engine.skill_for(thread_row, request(skill_id=None)).id == 'understand-documents'
    assert engine.skill_for(thread('custom'), request()).id == 'sales-prospect'


@pytest.mark.parametrize('sales_ok,language_ok,code', [
    (False, True, 'SALES_ADMISSION_DISABLED'),
    (True, False, 'LANGUAGE_UNAVAILABLE'),
])
def test_admission_and_language_never_propose_an_action(sales_ok, language_ok, code):
    payload = request()
    thread_row = thread('understand-documents')
    plan, staged = engine.build_plan(thread_row, payload,
        engine.skill_for(thread_row, payload), project(('en',) if language_ok else ('zh-HK',)),
        grounding(), sales_ok, language_ok)
    assert plan.proposal is None and staged is None
    assert code in {notice.code for notice in plan.notices}


def test_missing_selected_document_does_not_propose_document_work():
    payload = request()
    thread_row = thread('understand-documents')
    plan, staged = engine.build_plan(thread_row, payload,
        engine.skill_for(thread_row, payload), project(), grounding(with_document=False),
        True, True)
    assert plan.proposal is None and staged is None
    assert 'NEEDS_SELECTED_DOCUMENT' in {notice.code for notice in plan.notices}


def test_unavailable_capability_for_skill_is_surfaced_not_invented():
    payload = request()
    thread_row = thread('custom')  # sales-prospect has no nonbillable executor here
    plan, staged = engine.build_plan(thread_row, payload,
        engine.skill_for(thread_row, payload), project(), grounding(), True, True)
    assert plan.proposal is None and staged is None
    assert 'CAPABILITY_NOT_AVAILABLE' in {notice.code for notice in plan.notices}


def test_missing_grounding_requires_selected_sources():
    parts, notices = engine.answer_parts(Grounding([], []), 'en')
    assert isinstance(parts[0], turn_contracts.TextPart)
    assert notices[0].code == 'SOURCES_REQUIRED'
    assert engine._execution_refs(Grounding([], [])) == []


def test_default_model_path_is_honest_advisory_with_citations():
    parts, notices = engine.answer_parts(grounding(), 'en')
    assert notices[0].code == 'CONVERSATION_MODEL_UNAVAILABLE'
    assert isinstance(parts[1], turn_contracts.CitationsPart)
    assert [item.id for item in parts[1].items] == [FACT_SOURCE, DOCUMENT_SOURCE]
    assert 'not configured' in parts[0].text
    assert 'Industrial sensors' not in parts[0].text  # no source body is echoed


def test_deterministic_fixture_adapter_can_only_return_selected_citations(monkeypatch):
    selected = grounding()

    def fixture_adapter(value):
        return reply_from_grounding(value, fixture_candidate={
            'text': 'Review the cited approved source.', 'status': 'needs_review',
            'fixture': True, 'citations': [selected.citations[0]]})

    monkeypatch.setattr(engine, 'model_answer', fixture_adapter)
    parts, notices = engine.answer_parts(selected, 'en')
    assert notices == []
    assert parts[0].text == 'Review the cited approved source.'
    assert [item.id for item in parts[1].items] == [FACT_SOURCE]

    def invented(value):
        return reply_from_grounding(value, fixture_candidate={
            'text': 'Invented answer.', 'status': 'needs_review', 'fixture': True,
            'citations': [{'id': f'document:{uuid.uuid4()}', 'label': 'Offer document',
                           'locator': {'surface': 'document', 'id': str(uuid.uuid4())}}]})

    monkeypatch.setattr(engine, 'model_answer', invented)
    with pytest.raises(ApiError) as caught:
        engine.answer_parts(selected, 'en')
    assert caught.value.code == 'CONVERSATION_REPLY_UNVERIFIED'


def test_execution_refs_are_canonical_current_and_durable():
    refs = engine._execution_refs(grounding())
    assert {(ref['kind'], ref['version']) for ref in refs} == {
        ('project_fact', 1), ('document', 1)}
    assert {ref['locator'] for ref in refs} == {FACT_SOURCE, DOCUMENT_SOURCE}
    assert all(ref['retention_class'] == 'durable' for ref in refs)
    drive = Grounding([{'id': 'drive:abc', 'label': 'Google Drive item',
                        'locator': {'surface': 'drive', 'id': 'abc'}}], [], sources=[],
        profile_id='', profile_hash='', offer_revision=1)
    assert engine._execution_refs(drive) == []


def test_replay_fingerprint_binds_scope_client_message_and_thread():
    scope = SimpleNamespace(workspace_id=uuid.uuid4(), project_id=uuid.uuid4(),
        actor_id=uuid.uuid4())
    payload = request()
    thread_id = uuid.uuid4()
    baseline = engine.request_fingerprint(scope, payload, thread_id)
    assert baseline == engine.request_fingerprint(scope, payload, thread_id)
    assert baseline != engine.request_fingerprint(scope, payload, uuid.uuid4())
    assert baseline != engine.request_fingerprint(scope, request(
        client_message_id=payload.client_message_id, text='different'), thread_id)
    other_scope = SimpleNamespace(workspace_id=scope.workspace_id,
        project_id=scope.project_id, actor_id=uuid.uuid4())
    assert baseline != engine.request_fingerprint(other_scope, payload, thread_id)


def test_title_rules_are_bounded_and_client_safe():
    assert engine.thread_title('   Research   this buyer  ') == 'Research this buyer'
    assert len(engine.thread_title('x' * 200)) == engine.TITLE_LIMIT
    assert engine.thread_title('\x00') == 'New discussion'


@pytest.mark.parametrize('payload', [
    {'kind': 'unknown_part', 'text': 'x'},
    {'kind': 'text', 'text': 'x', 'language': 'en', 'tenant_id': str(uuid.uuid4())},
])
def test_injected_parts_cannot_be_persisted(payload):
    with pytest.raises(ValidationError):
        turn_contracts.validate_part_list([payload])


def test_notices_reject_unknown_fields_and_oversized_lists():
    with pytest.raises(ValidationError):
        turn_contracts.validate_notices([{'code': 'CODE', 'message': 'm', 'actor_id': 'x'}])
    with pytest.raises((ValidationError, ValueError)):
        turn_contracts.validate_notices([{'code': 'CODE', 'message': 'm'}] * 9)


def test_registered_tables_match_the_readiness_contract():
    from buyeros_api.db.base import Base
    from buyeros_api.services.schema_readiness import sales_requirements
    required = sales_requirements()
    assert required['compatible_heads'] == ['0066_conversation_turns']
    for name in ('conversation_turns', 'conversation_turn_proposals',
                 'conversation_turn_decisions', 'conversation_thread_messages'):
        columns = required['required_relations'][f'public.{name}']
        assert set(columns) == set(Base.metadata.tables[name].columns.keys())
    assert {'public.conversation_turns', 'public.conversation_turn_proposals',
            'public.conversation_turn_decisions'} <= set(required['required_rls'])
    updates = [item for item in required['required_privileges']
        if item['relation'] == 'public.conversation_turn_proposals' and item['privilege'] == 'UPDATE']
    assert updates and set(updates[0]['columns']) == {'status', 'revision', 'result', 'updated_at'}


def test_turn_routes_register_only_with_conversation_home(monkeypatch):
    from buyeros_api.api.app import create_app
    monkeypatch.setenv('NEXT_PUBLIC_CONVERSATION_HOME', 'true')
    enabled_paths = [path for path in create_app().openapi()['paths']
        if 'conversation-turns' in path]
    assert len(enabled_paths) == 3
    monkeypatch.delenv('NEXT_PUBLIC_CONVERSATION_HOME')
    disabled_paths = [path for path in create_app().openapi()['paths']
        if 'conversation-turns' in path]
    assert disabled_paths == []
