---
task_id: "BO-020"
title: "Reconcile provider results, callback replay and in-flight cancellation"
phase: "P4"
status: "BLOCKED"
priority: "P1"
source_requirements: ["REQ-RECONCILE","REQ-POLICY","REQ-BUDGET"]
depends_on: ["BO-019"]
blocked_by: ["B-PROVIDERS","B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "backend"
files_to_read: ["features/workspace.tsx","features/buyers/detail.tsx","services/contracts.ts","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: ["features/workspace.tsx","features/buyers/detail.tsx"]
dependency_output_files_to_modify: ["services/api/buyeros_api/main.py", "services/live/client.ts", "services/worker/buyeros_worker/tasks.py"]
proposed_files_to_create: ["services/api/buyeros_api/routes/enrichment_jobs.py","services/api/buyeros_api/routes/provider_callbacks.py","services/worker/buyeros_worker/enrichment/reconcile.py","services/api/tests/test_enrichment_reconciliation.py"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["contracts/openapi.proposed.yaml","03_DATA_API_AND_STATE_CONTRACTS.md"]
migration_impact: "none; if current source requires an unlisted migration stop and revise task"
external_capabilities: []
external_spend_authorized: false
acceptance_tests: ["TEST-BO-020-01","TEST-BO-020-02","TEST-BO-020-03"]
verification_commands: [{"command":"uv run python -m pytest tests/test_enrichment_reconciliation.py","working_directory":"services/api","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"Callback signature/replay, polling, ledger and late-policy tests pass"}]
rollback_or_rollforward: "Disable result exposure/callback consumer if compromised; retain signed receipt/audit metadata, process known events after fix idempotently. Financial correction uses compensating entries."
effort_range_hours: [24,40]
---

# BO-020 — Reconcile provider results, callback replay and in-flight cancellation

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

Late, duplicate or out-of-order provider results settle cost once and expose permitted contact data accurately while cancelled/suppressed records stay protected.

## Source requirement and present-state evidence

Source requirements: `REQ-RECONCILE`, `REQ-POLICY`, `REQ-BUDGET`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). Existing UI has immediate local lookup success and labels valid/catch-all/unavailable, but no asynchronous pending/unknown/reconciliation or callback flow.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **backend**; phase **P4**.
- Required predecessor evidence: `BO-019`.
- Blockers: `B-PROVIDERS`, `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **EXISTING, inspected:** `features/workspace.tsx`
- **EXISTING, inspected:** `features/buyers/detail.tsx`

- **PROPOSED new file:** `services/api/buyeros_api/routes/enrichment_jobs.py`
- **PROPOSED new file:** `services/api/buyeros_api/routes/provider_callbacks.py`
- **PROPOSED new file:** `services/worker/buyeros_worker/enrichment/reconcile.py`
- **PROPOSED new file:** `services/api/tests/test_enrichment_reconciliation.py`

**PROPOSED predecessor outputs to modify after their creating task completes** (not existing at the audited commit):

- `services/api/buyeros_api/main.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/live/client.ts` — inspect producer-task result first; modify only this task's required wiring.
- `services/worker/buyeros_worker/tasks.py` — inspect producer-task result first; modify only this task's required wiring.

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Implement provider callback verification only if BO-002 verified signature/event timestamp/replay contract; otherwise documented authenticated polling with bounded rate/cost. Correlate server-held provider ID, never trust callback tenant IDs.

2. Deduplicate provider event IDs/body hashes, enforce state monotonicity and reject invalid signatures/replays outside policy. Store receipt metadata and process through durable outbox.

3. Fetch authoritative status/invoice/credit where supported; reconcile per-operation actual cost and batch partials with unique cost events. Release unused upper bound only on conclusive result/no-charge evidence.

4. Recheck current purpose/suppression/retention gates before writing/exposing personal contact result; quarantine/discard late prohibited data while still settling financial facts.

5. Map found validity precisely: public remains unverified, catch-all distinct, provider-marked-valid records provenance/check time, absent identity stays unknown. Never infer outreach permission.

6. Expose job GET/cancel/reconcile controls with permission; cancel_requested cannot erase provider accepted charge. Surface aged unknowns and bounded manual review queue, not perpetual silent loading.

## API, schema and state changes

GET enrichment-jobs/{id}; POST cancel/reconcile; verified callback route in OpenAPI. pending/unknown→reconciled with independent contact validity and cost outcome.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`event found arrives after suppression` settles the verified bill once but withholds/quarantines personal result; replay of the same provider event has no second cost effect.

## Failure and concurrency cases

Webhook replay/out-of-order terminal status, duplicate invoice line, provider credits discrepancy, late success after suppression and missing results remain auditable. Manual reconciliation requires evidence/role and cannot fabricate a refund.

- Scenario 1: Repeated/out-of-order callbacks cannot double-settle or regress terminal state.
- Scenario 2: Late found result after suppression is withheld while charge settles once.
- Scenario 3: Unknown→no-charge releases funds only with authoritative evidence; catch-all never appears provider-marked valid.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-020-01:** Repeated/out-of-order callbacks cannot double-settle or regress terminal state.
- **TEST-BO-020-02:** Late found result after suppression is withheld while charge settles once.
- **TEST-BO-020-03:** Unknown→no-charge releases funds only with authoritative evidence; catch-all never appears provider-marked valid.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `uv run python -m pytest tests/test_enrichment_reconciliation.py` | `services/api` | PROPOSED_AFTER_TASK / NOT RUN | Callback signature/replay, polling, ledger and late-policy tests pass |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Disable result exposure/callback consumer if compromised; retain signed receipt/audit metadata, process known events after fix idempotently. Financial correction uses compensating entries.

## Effort assumptions

**24–40 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-020 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-020-reconcile-provider-results-callback-replay-and-in-flight-cancellation.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; the audited source is imported at commit b804ba8d1514a1049b7202c861278dd72c473a75 (tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), merged into main via 72fef7da785624a35bb6701f1451ebcf0184a089), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: Late, duplicate or out-of-order provider results settle cost once and expose permitted contact data accurately while cancelled/suppressed records stay protected. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

