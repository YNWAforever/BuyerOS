"""Evidence-bound fit assessment validation (BO-015)."""

VERDICTS = ("match", "needs_review", "not_a_match")


class InventedEvidence(Exception):
    pass


def validate_assessment(assessment: dict, allowed_evidence_ids: set[str]) -> dict:
    if assessment.get("verdict") not in VERDICTS:
        raise ValueError("unknown verdict")
    for evidence_id in assessment.get("evidence_ids", []):
        if evidence_id not in allowed_evidence_ids:
            raise InventedEvidence(evidence_id)
    return assessment


def needs_review_if_uncited(assessment: dict) -> bool:
    return assessment.get("verdict") == "match" and not assessment.get("evidence_ids")
