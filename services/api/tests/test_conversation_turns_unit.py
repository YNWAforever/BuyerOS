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
        engine.skill_for(thread_row, payload), project(), grounding(), buyer=None,
        drive_ids=(), sales_ok=True, language_ok=True)
    second, staged_again = engine.build_plan(thread_row, payload,
        engine.skill_for(thread_row, payload), project(), grounding(), buyer=None,
        drive_ids=(), sales_ok=True, language_ok=True)
    assert first.steps == ('answer', 'propose') == second.steps
    assert first.proposals == second.proposals
    assert first.proposals[0].capability == 'documents.read'
    skill = load_skill('understand-documents', '1')
    assert first.proposals[0].capability in skill.allowed_actions
    assert first.proposals[0].requires_approval is True
    assert staged[0]['capability'] == 'documents.read'
    assert staged[0]['arguments']['document_ids'] == [DOCUMENT]
    assert first.proposals[0] not in second.notices


def test_request_skill_override_is_validated_against_the_registry():
    payload = request(skill_id='invented-skill')
    with pytest.raises(ApiError) as caught:
        engine.skill_for(thread(), payload)
    assert caught.value.code == 'INVALID_REQUEST'


def test_plan_ceiling_is_bounded_and_capabilities_are_registered():
    payload = request()
    thread_row = thread('understand-documents')
    plan, staged = engine.build_plan(thread_row, payload,
        engine.skill_for(thread_row, payload), project(), grounding(), buyer=None,
        drive_ids=(), sales_ok=True, language_ok=True)
    assert len(plan.steps) == len(set(plan.steps)) <= turn_contracts.MAX_TURN_STEPS
    assert set(engine.EXECUTORS) == {'documents.read', 'research.read',
        'xverum.enrich_company', 'drive.read'}
    assert plan.proposals[0].capability in engine.EXECUTORS
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
        grounding(), buyer=None, drive_ids=(), sales_ok=sales_ok, language_ok=language_ok)
    assert plan.proposals == () and staged == []
    assert code in {notice.code for notice in plan.notices}


def test_missing_selected_document_does_not_propose_document_work():
    payload = request()
    thread_row = thread('understand-documents')
    plan, staged = engine.build_plan(thread_row, payload,
        engine.skill_for(thread_row, payload), project(), grounding(with_document=False),
        buyer=None, drive_ids=(), sales_ok=True, language_ok=True)
    assert plan.proposals == () and staged == []
    assert 'NEEDS_SELECTED_DOCUMENT' in {notice.code for notice in plan.notices}


def test_unavailable_capability_for_skill_is_surfaced_not_invented():
    payload = request()
    thread_row = thread('custom')  # sales-prospect has no nonbillable executor here
    plan, staged = engine.build_plan(thread_row, payload,
        engine.skill_for(thread_row, payload), project(), grounding(), buyer=None,
        drive_ids=(), sales_ok=True, language_ok=True)
    assert plan.proposals == () and staged == []
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
    # Decision continuation identity includes the expected version: a decision
    # resumed after a blocked (needs_input) decision must create a new result.
    proposal_id, turn_id = uuid.uuid4(), uuid.uuid4()

    def decision(version):
        return turn_contracts.TurnDecisionRequest(proposal_id=proposal_id,
            decision='approve', expected_thread_version=version)

    blocked = engine.decision_fingerprint(scope, thread_id, turn_id, decision(2))
    assert blocked != engine.decision_fingerprint(scope, thread_id, turn_id, decision(3))
    assert blocked == engine.decision_fingerprint(scope, thread_id, turn_id, decision(2))


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


def test_integrity_errors_are_only_mapped_to_idempotency_when_expected():
    """Finding 2 regression: unrelated constraint failures are never masked as 409.

    The turn/decision handlers used to map every IntegrityError to
    IDEMPOTENCY_CONFLICT, hiding the real constraint (this masked the 0067
    validator failure as a bogus concurrent request).
    """
    from types import SimpleNamespace
    from buyeros_api.api.errors import ApiError
    from buyeros_api.services import conversation_turns as engine

    class FakeIntegrity(Exception):
        def __init__(self, constraint):
            self.orig = SimpleNamespace(diag=SimpleNamespace(constraint_name=constraint))

    def failure(constraint):
        return FakeIntegrity(constraint)

    assert engine.is_expected_conflict(
        failure('uq_conversation_turns_actor_client'), engine.TURN_CONFLICT_CONSTRAINTS)
    assert engine.is_expected_conflict(
        failure('uq_conversation_turn_decisions_workspace_id_proposal_id'),
        engine.DECISION_CONFLICT_CONSTRAINTS)
    unrelated = failure('fk_conversation_threads_buyer')
    assert not engine.is_expected_conflict(unrelated, engine.TURN_CONFLICT_CONSTRAINTS)
    with pytest.raises(ApiError) as caught:
        engine.raise_unexpected_integrity(unrelated, 'unit-test')
    assert caught.value.status_code == 500
    assert caught.value.code == 'INTERNAL_ERROR'
    assert caught.value.code != 'IDEMPOTENCY_CONFLICT'


def test_migration_0067_validator_is_plain_sql_and_accepts_reviewed_cost_metadata():
    """The copied validator must not keep f-string brace escapes or reject cost.known."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / 'alembic' / 'versions'
        / '0067_conversation_buyer.py').read_text(encoding='utf-8')
    assert '{{' not in source and '}}' not in source
    assert "ARRAY['kind','amount','unit','may_incur_provider_charges','known']" in source
    assert "'buyer'" in source


def test_registered_tables_match_the_readiness_contract():
    from buyeros_api.db.base import Base
    from buyeros_api.services.schema_readiness import sales_requirements
    required = sales_requirements()
    assert required['compatible_heads'] == ['0071_conversation_retention']
    for name in ('conversation_turns', 'conversation_turn_proposals',
                 'conversation_turn_decisions', 'conversation_thread_messages',
                 'conversation_turn_events', 'conversation_turn_reconciliations',
                 'conversation_turn_rate_windows'):
        columns = required['required_relations'][f'public.{name}']
        assert set(columns) == set(Base.metadata.tables[name].columns.keys())
    assert {'public.conversation_turns', 'public.conversation_turn_proposals',
            'public.conversation_turn_decisions'} <= set(required['required_rls'])
    updates = [item for item in required['required_privileges']
        if item['relation'] == 'public.conversation_turn_proposals' and item['privilege'] == 'UPDATE']
    assert updates and set(updates[0]['columns']) == {'status', 'revision', 'result', 'updated_at'}
    worker = sales_requirements(worker=True)
    for name in ('public.conversation_thread_messages', 'public.conversation_turns',
                 'public.conversation_turn_proposals', 'public.conversation_turn_decisions',
                 'public.conversation_turn_events', 'public.conversation_turn_reconciliations',
                 'public.conversation_turn_rate_windows'):
        assert name not in worker['required_relations']
        assert not [item for item in worker['required_privileges'] if item['relation'] == name]


def test_turn_routes_register_only_with_conversation_home(monkeypatch):
    from buyeros_api.api.app import create_app
    monkeypatch.setenv('NEXT_PUBLIC_CONVERSATION_HOME', 'true')
    enabled_paths = [path for path in create_app().openapi()['paths']
        if 'conversation-turns' in path]
    assert len(enabled_paths) == 6
    monkeypatch.delenv('NEXT_PUBLIC_CONVERSATION_HOME')
    disabled_paths = [path for path in create_app().openapi()['paths']
        if 'conversation-turns' in path]
    assert disabled_paths == []


# --- task-6: linked buyer + proposal-only approved MCP capabilities ----------

def buyer_projection():
    return {'id': uuid.uuid4(), 'version': 2, 'company_id': uuid.uuid4(),
            'name': 'DeltaGrid', 'domain': 'deltagrid.example',
            'review_state': 'accepted'}


def test_linked_buyer_produces_proposal_only_enrichment():
    thread_row = thread('custom')
    payload = request(text='Enrich the linked company')
    buyer = buyer_projection()
    plan, staged = engine.build_plan(thread_row, payload,
        engine.skill_for(thread_row, payload), project(), grounding(),
        buyer=buyer, drive_ids=(), sales_ok=True, language_ok=True)
    proposals = {proposal.capability: proposal for proposal in plan.proposals}
    assert 'xverum.enrich_company' in proposals
    enrichment = proposals['xverum.enrich_company']
    assert enrichment.requires_approval is True
    assert enrichment.cost.kind == 'provider_credits'
    assert enrichment.cost.unit == 'credits'
    assert enrichment.cost.may_incur_provider_charges is True
    assert enrichment.cost.known is False  # reviewed tariff not available yet
    staged_enrichment = next(item for item in staged
        if item['capability'] == 'xverum.enrich_company')
    assert staged_enrichment['arguments']['buyer_id'] == str(buyer['id'])
    assert staged_enrichment['arguments']['company_id'] == str(buyer['company_id'])
    assert staged_enrichment['source_refs'] == [engine._buyer_source_ref(buyer)]
    assert staged_enrichment['source_refs'][0]['kind'] == 'buyer'
    assert engine._buyer_citation(buyer)['id'] == f"buyer:{buyer['id']}"
    # Serializer must not downgrade a buyer citation to a document citation.
    assert engine._citation_item(f"buyer:{buyer['id']}", 'DeltaGrid').kind == 'buyer'
    assert engine._citation_item('document:' + str(uuid.uuid4()), 'Offer document').kind == 'document'
    assert 'xverum.enrich_company' in engine.PROPOSAL_ONLY
    assert engine._executor('xverum.enrich_company') is not None


def test_drive_source_produces_proposal_only_read():
    drive_id = 'drive:' + str(uuid.uuid4()) + ':' + 'a' * 32
    payload = request(text='Read the selected Drive evidence')
    plan, staged = engine.build_plan(thread('custom'), payload,
        load_skill('sales-prospect', '1'), project(), grounding(),
        buyer=None, drive_ids=(drive_id,), sales_ok=True, language_ok=True)
    assert [proposal.capability for proposal in plan.proposals] == ['drive.read']
    proposal = plan.proposals[0]
    assert proposal.cost.kind == 'nonbillable'
    assert proposal.cost.may_incur_provider_charges is False
    assert proposal.requires_approval is True
    assert staged[0]['arguments']['source_ids'] == [drive_id]
    assert 'drive.read' in engine.PROPOSAL_ONLY


def test_enrichment_intent_is_deterministic_and_text_only():
    assert engine._enrichment_intent('Please verify this company')
    assert engine._enrichment_intent('請查證這間公司')
    assert not engine._enrichment_intent('Summarise the selected documents')
    # The buyer link, not free text, grants tool permission: no buyer -> no proposal.
    plan, staged = engine.build_plan(thread('custom'),
        request(text='Please verify this company'), load_skill('sales-prospect', '1'),
        project(), grounding(), buyer=None, drive_ids=(), sales_ok=True,
        language_ok=True)
    assert 'xverum.enrich_company' not in {p.capability for p in plan.proposals}


def test_proposal_only_executors_are_terminal_and_never_dispatch(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from buyeros_api.settings import get_settings
    from buyeros_api.providers import xverum_mcp
    from buyeros_api.services import conversation_connections

    monkeypatch.setattr(xverum_mcp, 'XverumTransport',
        lambda *args, **kwargs: pytest.fail('provider transport must not be constructed'))
    monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED', 'false')

    class _NoAccessSession:
        async def execute(self, *args, **kwargs):
            pytest.fail('no database work is required when admission is disabled')

    scope = SimpleNamespace(workspace_id=uuid.uuid4(), project_id=uuid.uuid4(), actor_id=uuid.uuid4())
    outcome = asyncio.run(engine._execute_xverum_proposal_only(
        _NoAccessSession(), scope, None, None, SimpleNamespace(arguments={})))
    assert (outcome.kind, outcome.code) == ('failed', 'SALES_ADMISSION_DISABLED')

    async def not_connected(*args, **kwargs):
        return None

    monkeypatch.setattr(conversation_connections, 'load', not_connected)
    drive = asyncio.run(engine._execute_drive_proposal_only(
        object(), scope, None, None, SimpleNamespace(arguments={'source_ids': []})))
    assert (drive.kind, drive.code) == ('failed', 'DRIVE_NOT_CONFIGURED')

    monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED', 'true')
    monkeypatch.setenv('BUYEROS_SALES_WORKSPACE_IDS', str(scope.workspace_id))
    monkeypatch.setenv('BUYEROS_PAID_ADMISSION_ENABLED', 'false')
    get_settings.cache_clear()
    try:
        paid = asyncio.run(engine._execute_xverum_proposal_only(
            _NoAccessSession(), scope, None, None, SimpleNamespace(arguments={})))
        assert (paid.kind, paid.code) == ('failed', 'PAID_ADMISSION_DISABLED')
    finally:
        monkeypatch.delenv('BUYEROS_PAID_ADMISSION_ENABLED', raising=False)
        get_settings.cache_clear()


def test_plan_ceiling_caps_proposals_so_step_count_stays_bounded():
    """A turn may never exceed MAX_TURN_STEPS persisted steps (DB CHECK 0..3)."""
    drive_id = 'drive:' + str(uuid.uuid4()) + ':' + 'a' * 32
    thread_row = thread('understand-documents')
    payload = request(text='Enrich the linked company and read the Drive evidence')
    plan, staged = engine.build_plan(thread_row, payload,
        engine.skill_for(thread_row, payload), project(), grounding(),
        buyer=buyer_projection(), drive_ids=(drive_id,), sales_ok=True,
        language_ok=True)
    assert len(plan.steps) == turn_contracts.MAX_TURN_STEPS
    assert len(plan.proposals) == turn_contracts.MAX_TURN_STEPS - 1
    assert len(staged) == len(plan.proposals)
    assert {proposal.capability for proposal in plan.proposals} == {
        'documents.read', 'xverum.enrich_company'}

