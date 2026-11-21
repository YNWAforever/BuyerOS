"""Code-owned conversation route registration and disabled-by-default opt-in."""
import inspect
from copy import replace
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from buyeros_api.providers import base
from buyeros_api.providers.base import Money
from buyeros_api.providers import conversation_route
from buyeros_api.providers.conversation_route import (
    MAX_QA_CALL_LIABILITY, ReviewedConversationRoute, registration_for_facts)
from buyeros_api.services import conversation_admission
from buyeros_api.settings import get_settings
from buyeros_api.execution.config import get_settings as dispatch_settings

WS = '10000000-0000-4000-8000-000000000001'
PROJECT = '20000000-0000-4000-8000-000000000001'
OTHER_WS = '10000000-0000-4000-8000-000000000002'
OTHER_PROJECT = '20000000-0000-4000-8000-000000000002'


def reviewed_facts(**overrides):
    """Synthetic reviewed facts; the hash is computed only in this test fixture."""
    fields = dict(workspace_id=WS, project_id=PROJECT,
        model_id='synthetic-conversation-model',
        pricing_version='synthetic-conversation-price-v1',
        policy_account_reference='synthetic-conversation-account',
        max_liability=Money(Decimal('0.100000')), markets=frozenset({'US'}),
        languages=frozenset({'en'}), verified_at=datetime(2026, 11, 21, tzinfo=timezone.utc),
        source_urls=('https://opencode.ai/',), contract_sha256='0' * 64,
        retention='0 days; reviewed ZDR terms expire 2026-11-30',
        evidence_expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        account_verified=True)
    fields.update(overrides)
    unhashed = ReviewedConversationRoute(**fields)
    return replace(unhashed, contract_sha256=registration_for_facts(unhashed).contract_hash)


@pytest.fixture
def route_env(monkeypatch):
    monkeypatch.setenv('NEXT_PUBLIC_CONVERSATION_HOME', 'true')
    monkeypatch.setenv('BUYEROS_PAID_ADMISSION_ENABLED', 'true')
    monkeypatch.setenv('BUYEROS_PAID_DISPATCH_ENABLED', 'true')
    monkeypatch.setenv(conversation_route.ENABLED_ENV, 'true')
    monkeypatch.setenv(conversation_route.WORKSPACE_ENV, WS)
    monkeypatch.setenv(conversation_route.PROJECT_ENV, PROJECT)
    monkeypatch.setenv(conversation_route.CREDENTIAL_ENV, 'synthetic-conversation-no-real-key')
    get_settings.cache_clear(); dispatch_settings.cache_clear()
    # The dedicated conversation credential must not require or populate the
    # global research provider selection.
    monkeypatch.setattr(base, 'SELECTED_LIVE_PROVIDERS', frozenset())
    monkeypatch.setattr(conversation_admission, 'REGISTRATION', None)
    yield
    get_settings.cache_clear(); dispatch_settings.cache_clear()


def test_registration_absent_and_selection_disabled_by_default(monkeypatch):
    for name in (conversation_route.ENABLED_ENV, conversation_route.WORKSPACE_ENV,
                 conversation_route.PROJECT_ENV):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(conversation_route, 'REVIEWED_ROUTES', ())
    assert conversation_route.REVIEWED_ROUTES == ()
    assert conversation_route.CONVERSATION_ROUTE.route_id == 'opencode-go-conversation.v1'
    assert not conversation_route.CONVERSATION_ROUTE.permitted_tools
    assert conversation_route.CONVERSATION_TEST_EVIDENCE == (
        'services/api/tests/test_conversation_admission_db.py',
        'services/api/tests/test_discussion_context_recall.py',
        'services/api/tests/test_conversation_route_registration.py')
    assert all('test_exa_opencode_providers.py' not in path
               for path in conversation_route.CONVERSATION_TEST_EVIDENCE)
    assert conversation_route.preflight() is None
    assert conversation_route.conversation_registration() is None
    assert conversation_admission.selected_configuration('US', 'en',
        workspace_id=WS, project_id=PROJECT) is None


def test_exact_reviewed_scope_builds_the_registration_and_matching_policy_hash(route_env, monkeypatch):
    facts = reviewed_facts()
    monkeypatch.setattr(conversation_route, 'REVIEWED_ROUTES', (facts,))
    item = conversation_route.preflight()
    assert item is not None
    assert item.model_id == 'synthetic-conversation-model'
    assert item.model_route == conversation_route.CONVERSATION_ROUTE
    assert item.capability.provider == 'opencode-go'
    assert item.capability.max_liability == facts.max_liability
    assert item.capability.verified_at == facts.verified_at
    assert item.contract_hash == facts.contract_sha256
    snapshot = item.snapshot()
    assert snapshot['retention'] == facts.retention
    assert snapshot['verified_at'] == facts.verified_at.isoformat()
    assert snapshot['source_urls'] == list(facts.source_urls)
    assert conversation_route.registration_for_facts(
        replace(facts, retention='changed retention review')).contract_hash != facts.contract_sha256
    assert item.policy_binding.account_reference == facts.policy_account_reference
    assert item.policy_binding.contract_sha256 == facts.contract_sha256
    selected = conversation_admission.selected_configuration('US', 'en',
        workspace_id=WS, project_id=PROJECT)
    assert selected is not None and selected.model_id == item.model_id
    with pytest.raises(RuntimeError):
        item.factory()


def test_wrong_or_malformed_scope_fails_closed(route_env, monkeypatch):
    monkeypatch.setattr(conversation_route, 'REVIEWED_ROUTES', (reviewed_facts(),))
    assert conversation_route.preflight() is not None
    monkeypatch.setenv(conversation_route.PROJECT_ENV, OTHER_PROJECT)
    assert conversation_route.preflight() is None
    assert conversation_admission.selected_configuration('US', 'en',
        workspace_id=WS, project_id=OTHER_PROJECT) is None
    monkeypatch.setenv(conversation_route.PROJECT_ENV, 'not-a-uuid')
    assert conversation_route.preflight() is None
    monkeypatch.setenv(conversation_route.ENABLED_ENV, '1')
    assert conversation_route.preflight() is None


def test_pending_account_model_hash_or_facts_never_claim_verified(route_env, monkeypatch):
    pending = reviewed_facts(account_verified=False)
    monkeypatch.setattr(conversation_route, 'REVIEWED_ROUTES', (pending,))
    assert conversation_route.preflight() is None
    assert conversation_admission.selected_configuration('US', 'en',
        workspace_id=WS, project_id=PROJECT) is None

    bad_hash = replace(reviewed_facts(), contract_sha256='f' * 64)
    monkeypatch.setattr(conversation_route, 'REVIEWED_ROUTES', (bad_hash,))
    assert conversation_route.preflight() is None

    duplicate = reviewed_facts()
    monkeypatch.setattr(conversation_route, 'REVIEWED_ROUTES', (duplicate, duplicate))
    assert conversation_route.preflight() is None


def test_dedicated_credential_is_required_and_global_research_key_cannot_select(route_env, monkeypatch):
    facts = reviewed_facts()
    monkeypatch.setattr(conversation_route, 'REVIEWED_ROUTES', (facts,))
    assert conversation_admission.selected_configuration('US', 'en',
        workspace_id=WS, project_id=PROJECT) is not None
    admission_source = inspect.getsource(conversation_admission)
    assert 'BUYEROS_OPENCODE_API_KEY' not in admission_source
    assert 'conversation_route.CREDENTIAL_ENV' in admission_source
    monkeypatch.delenv(conversation_route.CREDENTIAL_ENV)
    monkeypatch.setenv('BUYEROS_OPENCODE_API_KEY', 'synthetic-global-research-key')
    assert conversation_route.preflight() is None
    assert conversation_admission.selected_configuration('US', 'en',
        workspace_id=WS, project_id=PROJECT) is None


def test_expired_reviewed_evidence_fails_closed(route_env, monkeypatch):
    expired = reviewed_facts(evidence_expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
    monkeypatch.setattr(conversation_route, 'REVIEWED_ROUTES', (expired,))
    assert conversation_route.preflight() is None
    assert conversation_admission.selected_configuration('US', 'en',
        workspace_id=WS, project_id=PROJECT) is None


def test_unreviewed_environment_model_pricing_liability_are_ignored(route_env, monkeypatch):
    monkeypatch.setenv('BUYEROS_CONVERSATION_MODEL_ID', 'arbitrary-env-model')
    monkeypatch.setenv('BUYEROS_CONVERSATION_MODEL_PRICING_VERSION', 'arbitrary-price')
    monkeypatch.setenv('BUYEROS_CONVERSATION_POLICY_ACCOUNT_REFERENCE', 'arbitrary-account')
    facts = reviewed_facts()
    monkeypatch.setattr(conversation_route, 'REVIEWED_ROUTES', (facts,))
    item = conversation_route.preflight()
    assert item is not None
    assert item.model_id == facts.model_id
    assert item.capability.pricing_version == facts.pricing_version
    assert item.policy_binding.account_reference == facts.policy_account_reference
    assert item.capability.max_liability == facts.max_liability


@pytest.mark.parametrize('field,value', [
    ('model_id', ''), ('pricing_version', ''), ('policy_account_reference', ''),
    ('max_liability', Money(Decimal('1.000001'))),
    ('verified_at', datetime(2026, 11, 21)),
    ('source_urls', ()), ('markets', frozenset()), ('languages', frozenset()),
    ('contract_sha256', 'not-a-hash'), ('retention', ''),
    ('evidence_expires_at', datetime(2026, 11, 21)),
    ('evidence', ('synthetic-not-a-test.py',)),
])
def test_reviewed_facts_reject_missing_or_unbounded_evidence(field, value):
    with pytest.raises(ValueError):
        reviewed_facts(**{field: value})


def test_selection_keeps_all_existing_paid_and_dispatch_gates(route_env, monkeypatch):
    facts = reviewed_facts()
    monkeypatch.setattr(conversation_route, 'REVIEWED_ROUTES', (facts,))
    assert conversation_admission.selected_configuration('US', 'en',
        workspace_id=WS, project_id=PROJECT) is not None
    get_settings.cache_clear()
    monkeypatch.setenv('BUYEROS_PAID_ADMISSION_ENABLED', 'false')
    get_settings.cache_clear(); dispatch_settings.cache_clear()
    assert conversation_admission.selected_configuration('US', 'en',
        workspace_id=WS, project_id=PROJECT) is None
    monkeypatch.setenv('BUYEROS_PAID_ADMISSION_ENABLED', 'true')
    monkeypatch.setenv('NEXT_PUBLIC_CONVERSATION_HOME', 'false')
    get_settings.cache_clear(); dispatch_settings.cache_clear()
    assert conversation_admission.selected_configuration('US', 'en',
        workspace_id=WS, project_id=PROJECT) is None
    assert conversation_admission.selected_configuration('GB', 'en',
        workspace_id=WS, project_id=PROJECT) is None
    assert conversation_admission.selected_configuration('US', 'zh-HK',
        workspace_id=WS, project_id=PROJECT) is None
    assert MAX_QA_CALL_LIABILITY.amount == Decimal('1.000000')
