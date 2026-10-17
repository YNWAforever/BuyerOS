"""Existing research requires explicit provider and result-source authorization."""
from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from buyeros_api.api.policy_activation_schemas import PolicyTerms, PolicyUseContext
from buyeros_api.services.policy_activation_terms import match_policy_use
from tests.test_policy_activation_contract import terms_body, P

NOW = datetime(2026, 10, 18, tzinfo=timezone.utc)


def research_terms():
    binding = {"provider_name": "fixture", "account_reference": "owned-research-account", "contract_sha256": "a" * 64}
    return {**terms_body(), "purpose": "account_research", "template_version": "provider-research.v1",
            "allowed_actions": ["research.search", "research.model", "research.read", "research.persist", "research.fetch"],
            "research_scope": {"search": binding, "model": {**binding, "contract_sha256": "b" * 64}}}


def context(action, **changes):
    return PolicyUseContext.model_validate({"project_id": P, "action": action, **changes})


def test_research_search_requires_exact_declared_binding_even_before_sources_are_known():
    terms = PolicyTerms.model_validate(research_terms())
    use = context("research.search", provider_name="fixture", account_reference="owned-research-account",
                  contract_sha256="a" * 64)
    assert match_policy_use(terms, use, NOW)
    for changes in ({"provider_name": "other"}, {"account_reference": None}, {"contract_sha256": "c" * 64},
                    {"project_id": UUID("a0000000-0000-4000-8000-000000000002")}):
        assert not match_policy_use(terms, use.model_copy(update=changes), NOW)
    assert not match_policy_use(PolicyTerms.model_validate(terms_body()), use, NOW)


def test_research_model_and_result_operations_enforce_sources_and_separate_model_identity():
    terms = PolicyTerms.model_validate(research_terms())
    use = context("research.model", source_domains=["rice.example.test"], provider_name="fixture",
                  account_reference="owned-research-account", contract_sha256="b" * 64)
    assert match_policy_use(terms, use, NOW)
    assert not match_policy_use(terms, use.model_copy(update={"contract_sha256": "a" * 64}), NOW)
    assert not match_policy_use(terms, use.model_copy(update={"source_domains": ()}), NOW)
    for action in ("research.read", "research.persist", "research.fetch"):
        assert match_policy_use(terms, context(action, source_domains=["rice.example.test"]), NOW)
        for domains in ([], ["rice.example.test.evil.test"]):
            assert not match_policy_use(terms, context(action, source_domains=domains), NOW)


def test_research_grant_does_not_enable_contact_send_or_undeclared_provider_actions():
    body = research_terms()
    terms = PolicyTerms.model_validate(body)
    for action in ("contact.enrich", "contact.read", "delivery.send", "provider.any"):
        assert not match_policy_use(terms, context(action, source_domains=["rice.example.test"]), NOW)
    for change in ({"research_scope": {}}, {"provider_scope": {"provider_name": "fixture",
                    "account_reference": "owned", "contract_sha256": "a" * 64}},
                   {"research_scope": {"search": body["research_scope"]["search"]}},
                   {"purpose": "contact_research"}):
        with pytest.raises(ValidationError):
            PolicyTerms.model_validate({**body, **change})
