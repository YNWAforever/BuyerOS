import pytest

from buyeros_api.services.fit import InventedEvidence, needs_review_if_uncited, validate_assessment


def test_rejects_invented_evidence_id():
    assessment = {"verdict": "match", "evidence_ids": ["ev1", "ghost"]}
    with pytest.raises(InventedEvidence):
        validate_assessment(assessment, {"ev1"})


def test_rejects_unknown_verdict():
    with pytest.raises(ValueError):
        validate_assessment({"verdict": "probably", "evidence_ids": []}, set())


def test_accepts_scoped_ids():
    assert validate_assessment({"verdict": "needs_review", "evidence_ids": ["ev1"]}, {"ev1"})["verdict"] == "needs_review"


def test_uncited_match_needs_review():
    assert needs_review_if_uncited({"verdict": "match", "evidence_ids": []}) is True
    assert needs_review_if_uncited({"verdict": "match", "evidence_ids": ["ev1"]}) is False
