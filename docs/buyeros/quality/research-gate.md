# C61-24 research capture and release gate

Original Q10 evaluator and the `buyeros.research-goldset.v1` / `buyeros.research-predictions.v1` contracts come from `7eb0ed5`; Q10 guards/tests include `fd97c90`. Current capture adds a separate `buyeros.research-capture-manifest.v1` input and `buyeros.research-capture-provenance.v1` sidecar. Historical audit results remain unchanged.

## Read-only capture

Create a manifest with dataset marker, exact database/workspace/project/canonical actor IDs, exactly three distinct original run IDs, a fixed company/buyer holdout, timezone-aware `frozen_at`, and paths plus SHA256 for the original goldset and threshold files. Threshold file schema is `buyeros.research-thresholds.v1` and its `frozen_at` must match. No threshold or label files are created from predictions. Declared timestamps/hashes bind supplied artifacts; they do not authenticate human independence, historical threshold adoption or real run independence.

Use only an authorized target. The `owned-fixture` target requires a loopback `buyeros_test_` database. `authorized-readonly` is a code path for a separately authorized external read; its presence is not operational authorization. Both require the exact `buyeros_api` login and server role with no superuser/BYPASSRLS, READ ONLY/REPEATABLE READ, current DB membership, active project and current account_research policy. Set `C61_RESEARCH_CAPTURE_DATABASE_URL` privately; inherited application/test/worker DSNs are not selected.

```text
python services/api/tools/capture_research_predictions.py --manifest artifacts/c61-capture-manifest.json --output artifacts/c61-predictions-new.json
python services/api/tools/evaluate_research_goldset.py --goldset artifacts/c61-goldset.json --predictions artifacts/c61-predictions-new.json --output artifacts/c61-quality-new.json
```

Capture reads saved data; it never admits work, calls a supplier, decrypts private contact prose or settles a cost/hold. Every expected company appears in every original run. Failed/partial/missing/ambiguous/unqualified data remain needs_review and stay in recall/coverage/abstention denominators. Wrong company IDs and blocker metadata remain visible. Receipt erasure/expiry, original hash/scope and evidence revisions fail closed. Not_match uses qualified counterevidence; counterevidence cannot become Match. New output and sidecar must both be absent; input aliases and existing evidence are refused. After a partial filesystem failure, reconcile both local paths and choose a new output instead of overwriting evidence.

## Acceptance still pending

At least200 distinct real companies, fixed holdout, two independently authenticated reviewers and separate adjudication, strata for homonyms/subsidiaries/regions/languages/stale or contradictory/injection cases, three independent authorized supplier runs, real company/contact/source inspection and billing evidence are required. Report each run independently with Wilson95% intervals; never pool3n. Precision estimate>=95% and safety violations0 remain proposed starting points; product must adopt recall/coverage/cost ceilings before measurement. Current per-stratum/frozen declared cost gate tooling is implemented locally; real receipts, authenticated billing, raw live cost capture and adopted product thresholds remain pending. Small strata must be marked insufficient, and all-abstention precision is unavailable.

Offline reports always remain live_verified=false/release_accepted=false. Original received/unknown saved receipt or zero local Cost events cannot establish billing settlement. Current owned PG/CLI evidence and one synthetic native receipt metadata test are fixtures; the latter explicitly sets a terminal metadata state and adds two failed empty runs, not three real provider runs. No current built preview, provider accuracy, production readback or human UAT is established. Release A, Neon-only and native send remain NOT_ACCEPTED.

Rollback: stop capture, revert only these offline tool/discovery files and retain input/report/provenance/failure artifacts. No schema or provider mutation occurs. Keep canonical UUID/FK, original holds/receipts and0047 privacy erasure.


## Frozen declared strata and cost CLI

```text
python services/api/tools/evaluate_frozen_research.py --goldset artifacts/c61-goldset.json --predictions artifacts/c61-predictions-new.json --thresholds artifacts/c61-thresholds.json --capture artifacts/c61-predictions-new-provenance.json --costs artifacts/c61-cost-observations.json --output artifacts/c61-frozen-quality-new.json
```

Threshold schema remains buyeros.research-thresholds.v1 with a nonblank owner, adopted boolean, aware frozen_at, precision_min>=0.95, recall_min/coverage_min/abstention_max between0and1, maximum_cost as an unsigned decimal string(max6places), currency, minimum_companies>=200, minimum_stratum_companies and integer safety_violations=0. Preliminary null/unadopted budgets do not become default passing ceilings. Freeze and raw goldset/threshold hashes must match the original capture; prediction binding uses the canonical JSON hash supplied by capture, so indentation does not change its identity. Output still records exact input file hashes.

Each run/market/language/company_type stratum reports separate denominators and Wilson95% intervals; insufficient configured counts and unavailable precision/recall are explicit blockers. Capture observations and cost rows cover the exact original company/run set, no omission or duplicated repeats. Cost schema buyeros.research-cost-observations.v1 has exactly3run rows: run_id,currency,settled_amount,active_hold,unknown_hold,billing_complete,evidence_sha256. All monetary values are unsigned decimal strings. Active and unknown buckets are disjoint; per-run maximum liability=settled+active+unknown. Remaining holds, unsettled or absent billing evidence, currency mismatch or exceeded ceiling block the gate. Numeric fields and opaque invoice hashes are supplied declarations, not authenticated supplier accounting or permission to release a hold.

CLI exit0 means the supplied frozen declarations meet the numerical/structural gate; exit1 is a written blocked gate report; exit2 refuses malformed/changed input or existing/aliased evidence. Every report keeps live_verified=false,release_accepted=false,provider_calls=0,database_calls=0 and false authentication flags. Actual three independent provider runs, at least200 real company labels, source/contact review, real billing/cost capture and product/human adoption are separate gates. Synthetic clear/unknown examples in artifacts/c61/C61-24-frozen-quality-synthetic-* are fictional fixtures and never enter production.
