"""Real typed policy boundaries; no DB, Auth client, network or real data."""
from copy import deepcopy
from datetime import datetime, timezone
import importlib
import importlib.util
from uuid import UUID

import pytest
from pydantic import ValidationError

W = "11111111-1111-4111-8111-111111111111"
P = "a0000000-0000-4000-8000-000000000001"
CATEGORIES = [
    "professional_identity", "employment", "procurement_scope", "business_channel",
    "evidence_excerpt", "review_note", "preparation_content",
]


def modules():
    name = "buyeros_api.api.policy_activation_schemas"
    assert importlib.util.find_spec(name) is not None, "controlled policy contract is not implemented"
    return importlib.import_module(name), importlib.import_module("buyeros_api.services.policy_activation_terms")


def terms_body():
    return {
        "workspace_id": W, "controller_scope_id": W, "project_id": P,
        "purpose": "contact_research", "template_version": "manual-native.v1",
        "allowed_data_categories": CATEGORIES.copy(),
        "allowed_sources": {"domains": ["rice.example.test"], "document_ids": []},
        "allowed_actions": ["observation.append", "lead.review", "lead.evidence.read"],
        "valid_from": "2026-10-17T00:00:00Z", "expires_at": "2026-11-17T00:00:00Z",
        "retention_days": 30,
        "deletion_plan": {
            "method": "redact_private_payload", "audit": "retain_non_content",
            "backup": "expiry_and_replay", "reference": "fixture://controller/deletion",
        },
        "countries": ["GB"], "policy_version": "fixture-v1",
        "basis_reference": "fixture://basis/no-real-consent",
        "provenance": "  合成證據—not a real consent record  ",
        "owner_evidence_reference": "fixture://owner/designation",
        "owner_evidence_sha256": "a" * 64,
    }


@pytest.mark.parametrize("change", [
    {"actor_id": W}, {"approved_by": W}, {"status": "permitted"},
    {"purpose": "outreach"}, {"template_version": "arbitrary.v1"},
    {"allowed_actions": ["provider.search"]},
    {"allowed_data_categories": ["employment"]},
    {"retention_days": True}, {"retention_days": 0},
    {"expires_at": "2026-11-17T00:00:00"},
    {"valid_from": "2026-11-17T00:00:00Z"},
    {"controller_scope_id": "22222222-2222-4222-8222-222222222222"},
])
def test_rejects_actor_fields_unknown_purpose_and_unenforceable_scope(change):
    schema, _ = modules()
    with pytest.raises(ValidationError):
        schema.PolicyTerms.model_validate({**terms_body(), **change})


def test_canonical_terms_are_stable_without_rewriting_evidence():
    schema, service = modules()
    raw = terms_body()
    left, left_hash = service.canonicalize_terms(schema.PolicyTerms.model_validate(raw))
    reordered = dict(reversed(list(raw.items())))
    reordered["expires_at"] = "2026-11-17T08:00:00+08:00"
    right, right_hash = service.canonicalize_terms(schema.PolicyTerms.model_validate(reordered))
    assert left_hash == right_hash
    assert len(left_hash) == 64
    assert left.provenance == right.provenance == "  合成證據—not a real consent record  "
    changed = {**raw, "provenance": raw["provenance"] + "!"}
    assert service.canonicalize_terms(schema.PolicyTerms.model_validate(changed))[1] != left_hash
    with pytest.raises(ValidationError):
        left.retention_days = 365


@pytest.mark.parametrize("domains", [
    [], ["https://rice.example.test/"], ["user@rice.example.test"],
    ["rice.example.test:443"], ["*.example.test"], ["127.0.0.1"],
    ["rice.example.test", "rice.example.test"],
])
def test_source_scope_rejects_empty_or_ambiguous_domains(domains):
    schema, _ = modules()
    raw = terms_body()
    raw["allowed_sources"]["domains"] = domains
    with pytest.raises(ValidationError):
        schema.PolicyTerms.model_validate(raw)


def test_match_policy_use_is_bound_to_time_project_action_data_and_sources():
    schema, service = modules()
    terms = schema.PolicyTerms.model_validate(terms_body())
    ctx = dict(action="observation.append", project_id=UUID(P), source_ids=(),
               source_domains=("rice.example.test",), data_categories=frozenset({"employment"}))
    now = datetime(2026, 10, 18, tzinfo=timezone.utc)
    assert service.match_policy_use(terms, schema.PolicyUseContext(**ctx), now)
    for changed in [
        {"project_id": UUID(W)}, {"action": "provider.search"},
        {"source_domains": ("rice.example.test.evil.test",)},
        {"data_categories": frozenset({"private_address"})},
        {"source_domains": ()},
    ]:
        assert not service.match_policy_use(terms, schema.PolicyUseContext(**{**ctx, **changed}), now)
    assert not service.match_policy_use(terms, schema.PolicyUseContext(**ctx), terms.expires_at)
    assert not service.match_policy_use(terms, schema.PolicyUseContext(**ctx),
                                        datetime(2026, 10, 16, tzinfo=timezone.utc))


def test_request_requires_paired_prior_head_and_owner_binding():
    schema, _ = modules()
    raw = {
        "client_request_id": "33333333-3333-4333-8333-333333333333",
        "authority_id": "44444444-4444-4444-8444-444444444444", "authority_version": 1,
        "expected_policy_id": None, "expected_policy_version": None,
        "terms": terms_body(), "request_deadline": "2026-10-20T00:00:00Z",
    }
    assert schema.ActivationSubmit.model_validate(raw).authority_version == 1
    for change in [
        {"authority_version": 0}, {"actor_id": W}, {"expected_policy_version": 1},
        {"request_deadline": "2026-12-20T00:00:00Z"},
    ]:
        with pytest.raises(ValidationError):
            schema.ActivationSubmit.model_validate({**deepcopy(raw), **change})
