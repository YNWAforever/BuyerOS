"""T19 deterministic fixture evaluation is never live-provider accuracy proof."""

import json
from pathlib import Path

from buyeros_api.services.fit import evaluate_evidence_fit


def test_research_eval_fixture_verdicts_and_citation_support():
    fixture = json.loads((Path(__file__).resolve().parents[3] / "tests/fixtures/research-eval.json").read_text(encoding="utf-8"))
    assert fixture["schema"] == "research-eval.v1"
    confusion = {}
    unsupported = 0
    for case in fixture["cases"]:
        result = evaluate_evidence_fit(case["requirements"], case["evidence"])
        confusion[(case["expected"], result["verdict"])] = confusion.get((case["expected"], result["verdict"]), 0) + 1
        allowed = {item["id"] for item in case["evidence"] if item["current"] and not item["is_inference"]}
        unsupported += len(set(result["evidence_ids"]) - allowed)
    assert len(fixture["cases"]) == 6
    assert all(expected == actual for expected, actual in confusion)
    assert unsupported == 0
