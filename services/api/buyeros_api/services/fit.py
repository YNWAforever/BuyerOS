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



def evaluate_evidence_fit(requirements: list[dict], evidence: list[dict]) -> dict:
    """Classify a scoped evidence set without consuming untrusted source prose.

    Callers must first load evidence under the tenant/run/company and current
    permission context. Stale or inferred claims cannot support a Match.
    This deterministic path spends no model tokens and never acts on page text.
    """
    if not isinstance(requirements, list) or not requirements or not isinstance(evidence, list):
        raise ValueError("requirements and evidence are required")
    required = {}
    for item in requirements:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
            raise ValueError("invalid requirement ID")
        if item.get("category") not in {"must", "nice", "exclude"} or not isinstance(item.get("hard_exclusion"), bool):
            raise ValueError("invalid requirement kind")
        if item["id"] in required:
            raise ValueError("duplicate requirement ID")
        required[item["id"]] = item
    claims: dict[str, dict[str, set[str]]] = {
        key: {"supports": set(), "contradicts": set(), "qualifies": set()}
        for key in required
    }
    seen: dict[str, tuple] = {}
    cited: list[str] = []
    evidence_refs: list[dict] = []
    contradictory_evidence_ids: list[str] = []
    for item in evidence:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
            raise ValueError("invalid evidence ID")
        requirement_id = item.get("requirement_id")
        if requirement_id not in required:
            raise InventedEvidence(requirement_id)
        stance = item.get("stance")
        if stance not in {"supports", "contradicts", "qualifies"}:
            raise ValueError("invalid evidence stance")
        version = item.get("version")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ValueError("invalid evidence version")
        signature = (requirement_id, stance, version, item.get("current"), item.get("is_inference"))
        previous = seen.setdefault(item["id"], signature)
        if previous != signature:
            raise ValueError("conflicting evidence ID")
        if item.get("current") is not True or item.get("is_inference") is not False:
            continue
        if item["id"] not in cited:
            cited.append(item["id"])
            evidence_refs.append({"id": item["id"], "version": version})
            if stance == "contradicts":
                contradictory_evidence_ids.append(item["id"])
        claims[requirement_id][stance].add(item["id"])
    supported = []
    contradicted = []
    unknown = []
    hard_reject = False
    ambiguity = not any(item["category"] == "must" for item in required.values())
    for requirement_id, requirement in required.items():
        positive = bool(claims[requirement_id]["supports"])
        negative = bool(claims[requirement_id]["contradicts"])
        qualified = bool(claims[requirement_id]["qualifies"])
        if positive:
            supported.append(requirement_id)
        if negative:
            contradicted.append(requirement_id)
        if not positive and not negative or qualified:
            unknown.append(requirement_id)
        conflict = positive and negative
        if conflict or qualified:
            ambiguity = True
        proven_reject = (requirement["hard_exclusion"] and not conflict and not qualified and
                         ((requirement["category"] == "exclude" and positive) or
                          (requirement["category"] == "must" and negative)))
        hard_reject = hard_reject or proven_reject
        if requirement["category"] == "must" and not positive and not proven_reject:
            ambiguity = True
        if (requirement["category"] == "exclude" and requirement["hard_exclusion"]
                and not negative and not proven_reject):
            ambiguity = True
    verdict = "not_a_match" if hard_reject else "needs_review" if ambiguity else "match"
    rationale = (f"Evidence review: {len(supported)} supported, {len(contradicted)} "
                 f"contradicted, {len(unknown)} unknown requirement(s).")
    return {
        "verdict": verdict,
        "supported_requirement_ids": supported,
        "contradicted_requirement_ids": contradicted,
        "unknown_requirement_ids": unknown,
        "evidence_ids": cited,
        "contradictory_evidence_ids": contradictory_evidence_ids,
        "evidence_refs": evidence_refs,
        "rationale": rationale,
        "next_action": "human_review",
    }
