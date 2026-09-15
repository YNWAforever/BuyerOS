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
