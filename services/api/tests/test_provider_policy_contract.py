"""Provider policy opt-in; no DB client, network, secret or runtime flag changes."""
from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from buyeros_api.api.policy_activation_schemas import PolicyTerms, PolicyUseContext
from buyeros_api.services.policy_activation_terms import canonicalize_terms, match_policy_use
from tests.test_policy_activation_contract import terms_body, P

NOW = datetime(2026, 10, 18, tzinfo=timezone.utc)
SENDER = "50000000-0000-4000-8000-000000000001"
RECIPIENT = "60000000-0000-4000-8000-000000000001"


def provider_terms(purpose="contact_research"):
    return {**terms_body(), "template_version": "provider-native.v1", "purpose": purpose,
            "allowed_actions": {
                "contact_research": ["contact.enrich"],
                "draft_preparation": ["draft.generate"],
                "outreach": ["delivery.review", "delivery.send"],
            }[purpose],
            "provider_scope": {
                "provider_name": "synthetic", "account_reference": "owned-test-account",
                "contract_sha256": "b" * 64,
                **({"sender_identity_id": SENDER, "recipient_refs": [RECIPIENT]}
                   if purpose != "contact_research" else {}),
            }}


def provider_context(**changes):
    return PolicyUseContext.model_validate({
        "action": "contact.enrich", "project_id": P, "source_domains": ["rice.example.test"],
        "provider_name": "synthetic", "account_reference": "owned-test-account",
        "contract_sha256": "b" * 64, **changes,
    })


def test_exact_provider_scope_matches_but_manual_grant_never_does():
    terms = PolicyTerms.model_validate(provider_terms())
    assert match_policy_use(terms, provider_context(), NOW)
    assert not match_policy_use(PolicyTerms.model_validate(terms_body()), provider_context(), NOW)
    assert not match_policy_use(terms, PolicyUseContext(action="contact.enrich", project_id=UUID(P),
                                                       source_domains=("rice.example.test",)), NOW)


@pytest.mark.parametrize("change", [
    {"provider_name": "other"}, {"account_reference": "other"}, {"contract_sha256": "c" * 64},
    {"project_id": "a0000000-0000-4000-8000-000000000002"}, {"action": "delivery.send"},
    {"source_domains": ["rice.example.test.evil.test"]},
])
def test_provider_or_scope_drift_fails_closed(change):
    assert not match_policy_use(PolicyTerms.model_validate(provider_terms()), provider_context(**change), NOW)


@pytest.mark.parametrize("change", [
    {"provider_scope": None}, {"purpose": "account_research"}, {"allowed_actions": ["lead.review"]},
    {"provider_scope": {"provider_name": "*", "account_reference": "*", "contract_sha256": "b" * 64}},
])
def test_incomplete_or_manual_provider_scope_is_rejected(change):
    with pytest.raises(ValidationError):
        PolicyTerms.model_validate({**provider_terms(), **change})


def test_send_requires_exact_recipient_sender_and_provider_while_review_cannot_send():
    terms = PolicyTerms.model_validate(provider_terms("outreach"))
    ctx = provider_context(action="delivery.send", sender_identity_id=SENDER, recipient_ref=RECIPIENT)
    assert match_policy_use(terms, ctx, NOW)
    for changes in ({"sender_identity_id": None}, {"recipient_ref": None},
                    {"recipient_ref": UUID("60000000-0000-4000-8000-000000000002")},
                    {"provider_name": None}, {"contract_sha256": "c" * 64}):
        assert not match_policy_use(terms, ctx.model_copy(update=changes), NOW)
    reviewed = terms.model_copy(update={"allowed_actions": ("delivery.review",)})
    assert not match_policy_use(reviewed, ctx, NOW)
    assert match_policy_use(reviewed, ctx.model_copy(update={"action": "delivery.review",
                            "provider_name": None, "account_reference": None, "contract_sha256": None}), NOW)


def test_manual_wire_and_canonical_hash_remain_unchanged():
    raw = terms_body()
    terms, digest = canonicalize_terms(PolicyTerms.model_validate(raw))
    from buyeros_api.db.icp import canonical_hash
    assert "provider_scope" not in terms.model_dump(mode="json")
    assert digest == canonical_hash(terms.model_dump(mode="json")).removeprefix("sha256:")


def test_provider_policy_can_explicitly_retain_manual_actions_without_automatic_expansion():
    base = PolicyTerms.model_validate(provider_terms())
    manual = PolicyUseContext(action="lead.evidence.read", project_id=UUID(P), source_domains=("rice.example.test",))
    assert not match_policy_use(base, manual, NOW)
    combined = PolicyTerms.model_validate({**provider_terms(), "allowed_actions": ["contact.enrich", "lead.evidence.read"]})
    assert match_policy_use(combined, manual, NOW)
    assert match_policy_use(combined, provider_context(), NOW)


def test_contact_read_needs_explicit_contact_reference_and_never_inherits_enrichment():
    raw = {**provider_terms(), "allowed_actions": ["contact.read"]}
    raw["provider_scope"] = {**raw["provider_scope"], "recipient_refs": [RECIPIENT]}
    terms = PolicyTerms.model_validate(raw)
    use = provider_context(action="contact.read", recipient_ref=RECIPIENT)
    assert match_policy_use(terms, use, NOW)
    assert not match_policy_use(terms, use.model_copy(update={"recipient_ref": None}), NOW)
    assert not match_policy_use(PolicyTerms.model_validate(provider_terms()), use, NOW)
    with pytest.raises(ValidationError):
        PolicyTerms.model_validate({**raw, "provider_scope": provider_terms()["provider_scope"]})
