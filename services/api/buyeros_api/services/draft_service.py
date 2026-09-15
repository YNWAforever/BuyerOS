"""Grounded draft revision validation (BO-021)."""


class UncitedClaim(Exception):
    pass


def validate_grounding(revision: dict, allowed_evidence: set[str], allowed_facts: set[str]) -> dict:
    evidence = revision.get("evidence_ids", [])
    facts = revision.get("offer_fact_ids", [])
    if not evidence and not facts:
        raise UncitedClaim("revision has no cited evidence or offer facts")
    if any(e not in allowed_evidence for e in evidence):
        raise UncitedClaim("unknown evidence id")
    if any(f not in allowed_facts for f in facts):
        raise UncitedClaim("unknown offer fact id")
    return revision
