---
task_id: "BO-018"
title: "Confirm a contact quote once with atomic reservation and durable job creation"
phase: "P4"
status: "BLOCKED"
priority: "P1"
source_requirements: ["REQ-CONFIRM","REQ-BUDGET","REQ-POLICY"]
depends_on: ["BO-011","BO-017"]
blocked_by: ["B-PROVIDERS","B-POLICY","B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "backend"
files_to_read: ["services/mock-client.ts","features/workspace.tsx","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: ["features/workspace.tsx"]
dependency_output_files_to_modify: ["services/api/buyeros_api/routes/enrichment_quotes.py", "services/live/client.ts"]
proposed_files_to_create: ["services/api/buyeros_api/services/confirm_lookup.py","services/api/tests/test_lookup_confirmation.py"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["contracts/openapi.proposed.yaml","03_DATA_API_AND_STATE_CONTRACTS.md"]
migration_impact: "none; if current source requires an unlisted migration stop and revise task"
external_capabilities: []
external_spend_authorized: false
acceptance_tests: ["TEST-BO-018-01","TEST-BO-018-02","TEST-BO-018-03"]
verification_commands: [{"command":"uv run python -m pytest tests/test_lookup_confirmation.py","working_directory":"services/api","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"Multi-connection PostgreSQL race, atomicity and idempotency tests pass"}]
rollback_or_rollforward: "Pause dispatch while investigating; release only conclusively never-submitted jobs through audited transition. Preserve ambiguous reservations."
effort_range_hours: [22,36]
---

# BO-018 — Confirm a contact quote once with atomic reservation and durable job creation

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

Double-clicks or concurrent confirmations create one durable lookup job/reservation and no request can reserve beyond the available budget.

## Source requirement and present-state evidence

Source requirements: `REQ-CONFIRM`, `REQ-BUDGET`, `REQ-POLICY`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). mock-client:confirm synchronously assigns deterministic contacts and cost in browser memory. Production confirmation must separate reservation/job acceptance from external submission/result.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **backend**; phase **P4**.
- Required predecessor evidence: `BO-011`, `BO-017`.
- Blockers: `B-PROVIDERS`, `B-POLICY`, `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **EXISTING, inspected:** `features/workspace.tsx`

- **PROPOSED new file:** `services/api/buyeros_api/services/confirm_lookup.py`
- **PROPOSED new file:** `services/api/tests/test_lookup_confirmation.py`

**PROPOSED predecessor outputs to modify after their creating task completes** (not existing at the audited commit):

- `services/api/buyeros_api/routes/enrichment_quotes.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/live/client.ts` — inspect producer-task result first; modify only this task's required wiring.

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Require scoped Idempotency-Key and hash over quote ID/version/request; authenticate actor and verify quote binding/expiry/provider price validity and project ownership.

2. Lock quote and budget rows in deterministic order; revalidate every buyer's acceptance/current fit/research permission/suppression under the transaction. Reject quote where eligibility changed; require new explicit quote for changed priced selection.

3. Atomically create enrichment job, reservation upper bound, provider-operation intents and outbox event; quote becomes consumed, its separate reservation becomes reserved, and return 202 only after commit.

4. Same key+same request returns original status/job; same key+different payload returns IDEMPOTENCY_CONFLICT. Different keys for same quote still converge via unique confirmed quote constraint.

5. Render confirmation loading/accepted/job progress separately from found contacts; unknown HTTP response allows safe retry with original key, never generate a new charge intent.

6. Do not dispatch provider within the database transaction or confirmation request. Grant dispatcher only the committed operation ID, not client-provided emails/provider settings.

## API, schema and state changes

POST /enrichment-quotes/{quote_id}/confirm; 202 enrichment_job/reservation. No contact found implied. Atomic quote quoted→consumed plus separate reserved budget/job rows; transaction is all-or-nothing.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`confirmLookup` with `quote_hash=<exact hash>, confirm_eligible_only=true` and original Idempotency-Key atomically moves quote `quoted→consumed`, creates one reservation and returns one durable job. Repeated identical confirmation returns that job.

## Failure and concurrency cases

Quote expires at boundary, two budget confirmations race, DB rollback, duplicate browser retry and response loss after commit are explicit. A client timeout does not cancel reserved job.

- Scenario 1: 20 simultaneous same-quote confirmations create one job/reservation/outbox effect.
- Scenario 2: Two quotes competing for remaining budget cannot over-reserve across all applicable ceilings.
- Scenario 3: Expired/stale/suppressed quote returns error with zero new reservation; lost HTTP response recovered with same key returns original job.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-018-01:** 20 simultaneous same-quote confirmations create one job/reservation/outbox effect.
- **TEST-BO-018-02:** Two quotes competing for remaining budget cannot over-reserve across all applicable ceilings.
- **TEST-BO-018-03:** Expired/stale/suppressed quote returns error with zero new reservation; lost HTTP response recovered with same key returns original job.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `uv run python -m pytest tests/test_lookup_confirmation.py` | `services/api` | PROPOSED_AFTER_TASK / NOT RUN | Multi-connection PostgreSQL race, atomicity and idempotency tests pass |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Pause dispatch while investigating; release only conclusively never-submitted jobs through audited transition. Preserve ambiguous reservations.

## Effort assumptions

**22–36 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-018 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-018-confirm-a-contact-quote-once-with-atomic-reservation-and-durable-job-creation.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; the audited source is imported at commit b804ba8d1514a1049b7202c861278dd72c473a75 (tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), merged into main via 72fef7da785624a35bb6701f1451ebcf0184a089), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: Double-clicks or concurrent confirmations create one durable lookup job/reservation and no request can reserve beyond the available budget. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

