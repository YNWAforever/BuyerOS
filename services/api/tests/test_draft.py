import pytest

from buyeros_api.services.draft_service import UncitedClaim, validate_grounding


def test_uncited_claim_rejected():
    revision = {"body": "We cut costs 40%", "evidence_ids": [], "offer_fact_ids": []}
    with pytest.raises(UncitedClaim):
        validate_grounding(revision, allowed_evidence=set(), allowed_facts=set())


def test_grounded_revision_ok():
    revision = {"body": "We supply sensors", "evidence_ids": ["ev1"], "offer_fact_ids": ["f1"]}
    out = validate_grounding(revision, allowed_evidence={"ev1"}, allowed_facts={"f1"})
    assert out["evidence_ids"] == ["ev1"]


def test_foreign_evidence_rejected():
    revision = {"body": "x", "evidence_ids": ["ghost"], "offer_fact_ids": []}
    with pytest.raises(UncitedClaim):
        validate_grounding(revision, allowed_evidence={"ev1"}, allowed_facts=set())


def test_foreign_offer_fact_rejected():
    revision = {"body": "x", "evidence_ids": [], "offer_fact_ids": ["ghost"]}
    with pytest.raises(UncitedClaim):
        validate_grounding(revision, allowed_evidence=set(), allowed_facts={"f1"})


@pytest.mark.parametrize("language", ["en", "zh-HK"])
def test_fixed_template_preserves_sources_and_metadata_without_style_promises(language):
    from buyeros_api.execution.handlers.draft_generate import render_grounded_template, validate_grounded_output
    facts = [{"id": "e1000000-0000-4000-8000-000000000001", "value": "Industrial sensors", "approved": True}]
    evidence = [{"id": "e2000000-0000-4000-8000-000000000001", "version": 1, "stance": "supports",
                 "excerpt": "English public catalog excerpt."}]
    common = dict(facts=facts, evidence=evidence, language=language, kind="initial")
    first = render_grounded_template(**common, objective="Request a demonstration", tone="professional")
    second = render_grounded_template(**common, objective="Discuss procurement", tone="warm")
    assert first["subject"] == second["subject"] and first["body"] == second["body"]
    assert first["objective"] != second["objective"] and first["tone"] != second["tone"]
    assert 'English public catalog excerpt.' in first["body"]
    assert '[evidence:e2000000-0000-4000-8000-000000000001:v1]' in first["body"] and '[offer_fact:e1000000-0000-4000-8000-000000000001]' in first["body"]
    assert first["body"].startswith("你好，" if language == "zh-HK" else "Hello,")
    assert first["route"] == "grounded-template.v1"
    assert validate_grounded_output(first, facts=facts, evidence=evidence) == first
