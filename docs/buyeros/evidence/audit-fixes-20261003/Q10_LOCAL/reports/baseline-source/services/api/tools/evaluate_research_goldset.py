"""Evaluate supplied research labels offline; no provider, DB or approval calls.

Declared labels do not verify human independence or live provider results.
Three repeats retain separate company-level intervals.
"""
import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StrictBool

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.quality_metrics import proportion, provenance, write_new_report

Verdict = Literal["match", "not_match"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Annotation(StrictModel):
    annotator_id: str = Field(min_length=1)
    verdict: Verdict


class Adjudication(Annotation):
    reason: str = Field(min_length=1)


class Source(StrictModel):
    id: str = Field(min_length=1)
    company_id: UUID
    workspace_id: UUID
    url: HttpUrl
    date: date
    current: StrictBool
    is_inference: StrictBool


class GoldRow(StrictModel):
    company_id: UUID
    workspace_id: UUID
    market: str = Field(min_length=1)
    language: str = Field(min_length=1)
    company_type: str = Field(min_length=1)
    split: Literal["train", "holdout"]
    reference_verdict: Verdict
    annotations: list[Annotation] = Field(min_length=2, max_length=2)
    adjudication: Adjudication | None = None
    sources: list[Source]


class Goldset(StrictModel):
    schema_version: Literal["buyeros.research-goldset.v1"] = Field(alias="schema")
    evidence_mode: Literal["fixture", "declared_human_labels"]
    owner: str = Field(min_length=1)
    rows: list[GoldRow] = Field(min_length=1)


class Prediction(StrictModel):
    company_id: UUID
    predicted_company_id: UUID
    workspace_id: UUID
    verdict: Literal["match", "not_match", "needs_review"]
    evidence_ids: list[str]


class Run(StrictModel):
    run_id: str = Field(min_length=1)
    rows: list[Prediction]


class Predictions(StrictModel):
    schema_version: Literal["buyeros.research-predictions.v1"] = Field(alias="schema")
    runs: list[Run] = Field(min_length=3, max_length=3)


def evaluate(goldset: dict, predictions: dict) -> dict:
    gold, pred = Goldset.model_validate(goldset), Predictions.model_validate(predictions)
    ids = [r.company_id for r in gold.rows]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate company across goldset/splits")
    if gold.evidence_mode == "declared_human_labels" and len(ids) < 200:
        raise ValueError("declared human goldset requires at least 200 companies")
    for row in gold.rows:
        annotators = {a.annotator_id.strip() for a in row.annotations}
        if "" in annotators or len(annotators) != 2:
            raise ValueError("two distinct declared annotators required")
        verdicts = {a.verdict for a in row.annotations}
        if row.adjudication:
            if not row.adjudication.annotator_id.strip() or row.adjudication.annotator_id.strip() in annotators or not row.adjudication.reason.strip():
                raise ValueError("separate adjudicator and reason required")
            reference = row.adjudication.verdict
        elif len(verdicts) != 1:
            raise ValueError("disagreement requires adjudication")
        else:
            reference = next(iter(verdicts))
        if row.reference_verdict != reference:
            raise ValueError("reference disagrees with labels/adjudication")
        if len({s.id for s in row.sources}) != len(row.sources):
            raise ValueError("duplicate source identifier")
    holdout = {r.company_id: r for r in gold.rows if r.split == "holdout"}
    if not holdout:
        raise ValueError("holdout companies required")
    if len({r.run_id for r in pred.runs}) != 3:
        raise ValueError("three distinct run ids required")
    violations, reports = [], []
    for run in pred.runs:
        predicted_ids = [r.company_id for r in run.rows]
        if len(set(predicted_ids)) != len(predicted_ids) or set(predicted_ids) != set(holdout):
            raise ValueError("each run must cover exactly the fixed holdout companies")
        counts = dict(tp=0, fp=0, tn=0, fn=0, needs_review=0)
        for item in run.rows:
            row = holdout[item.company_id]
            def violation(code):
                violations.append(dict(run_id=run.run_id, company_id=str(item.company_id), code=code))
            if item.predicted_company_id != row.company_id:
                violation("wrong_company")
            if item.workspace_id != row.workspace_id:
                violation("wrong_workspace")
            qualified = {s.id for s in row.sources if s.company_id == row.company_id and s.workspace_id == row.workspace_id and s.current and not s.is_inference}
            if set(item.evidence_ids) - qualified:
                violation("unsupported_evidence")
            if item.verdict == "match" and not (set(item.evidence_ids) & qualified):
                violation("match_without_qualified_evidence")
            positive = row.reference_verdict == "match"
            if item.verdict == "match":
                counts["tp" if positive else "fp"] += 1
            elif positive:
                counts["fn"] += 1  # positive abstentions reduce recall
            elif item.verdict == "not_match":
                counts["tn"] += 1
            if item.verdict == "needs_review":
                counts["needs_review"] += 1
        n = len(holdout)
        reports.append({"run_id": run.run_id, "confusion": counts,
                        "precision": proportion(counts["tp"], counts["tp"] + counts["fp"]),
                        "recall": proportion(counts["tp"], sum(r.reference_verdict == "match" for r in holdout.values())),
                        "coverage": proportion(n-counts["needs_review"], n),
                        "needs_review": proportion(counts["needs_review"], n)})
    threshold_met = not violations and all(r["precision"]["estimate"] is not None and r["precision"]["estimate"] >= .95 for r in reports)
    return {"schema": "buyeros.research-goldset-evaluation.v1", "evidence_mode": gold.evidence_mode,
            "label_verification": "supplied declarations only; independence not authenticated",
            "owner": gold.owner, "total_companies": len(ids), "holdout_companies": len(holdout),
            "runs": reports, "safety_violations": violations, "quality_thresholds_met": threshold_met,
            "thresholds": {"match_precision_estimate": .95, "safety_violations": 0, "minimum_declared_human_companies": 200},
            "repeat_policy": "separate per-run intervals; no pooled 3n sample", "ci_method": "Wilson 95%, per run/company",
            "live_verified": False, "provider_calls": 0, "release_accepted": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--goldset", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output.resolve() in (args.goldset.resolve(), args.predictions.resolve()) or args.output.exists():
            raise ValueError("output must be new and cannot alias inputs")
        inputs = [p.read_bytes() for p in (args.goldset, args.predictions)]
        report = evaluate(*(json.loads(value) for value in inputs))
        root = Path(__file__).resolve().parents[3]
        report.update(provenance(root, [Path(__file__).resolve(), Path(__file__).with_name("quality_metrics.py")]))
        report["input_hashes"] = dict(zip(("goldset", "predictions"), (hashlib.sha256(value).hexdigest() for value in inputs)))
        write_new_report(args.output, report, (args.goldset, args.predictions))
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Offline {report['evidence_mode']} report written; live_verified=false; provider_calls=0")
    # Fixture correctness can pass without claiming actual provider accuracy.
    return 1 if report["safety_violations"] or (report["evidence_mode"] != "fixture" and not report["quality_thresholds_met"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
