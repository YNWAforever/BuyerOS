---
task_id: "BO-024"
title: "Persist manual outcomes and reconcile every displayed usage metric"
phase: "P5"
status: "BLOCKED"
priority: "P1"
source_requirements: ["REQ-OUTCOME","REQ-USAGE","REQ-BUDGET"]
depends_on: ["BO-016","BO-020","BO-022","BO-023"]
blocked_by: ["B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "backend"
files_to_read: ["features/workspace.tsx","services/mock-client.ts","services/contracts.ts","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: ["features/workspace.tsx"]
dependency_output_files_to_modify: ["services/api/buyeros_api/main.py", "services/api/buyeros_api/models/core.py", "services/live/client.ts"]
proposed_files_to_create: ["services/api/buyeros_api/routes/outcomes.py","services/api/buyeros_api/routes/usage.py","services/api/alembic/versions/0008_outcomes.py","services/api/tests/test_usage_outcomes.py"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["contracts/openapi.proposed.yaml","03_DATA_API_AND_STATE_CONTRACTS.md"]
migration_impact: "PROPOSED additive migration; serialize through sole Alembic owner; execution only on approved disposable/staging DB"
external_capabilities: []
external_spend_authorized: false
acceptance_tests: ["TEST-BO-024-01","TEST-BO-024-02","TEST-BO-024-03"]
verification_commands: [{"command":"uv run python -m pytest tests/test_usage_outcomes.py","working_directory":"services/api","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"Distinct-company, date-scope, ledger and manual provenance tests pass"}]
rollback_or_rollforward: "Disable affected metric or show unavailable with incident reference; recompute derived values from immutable ledger/events, not manual dashboard patch."
effort_range_hours: [18,30]
---

# BO-024 — Persist manual outcomes and reconcile every displayed usage metric

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

Overview/Results/Usage agree with persisted ledger and distinct company counts, and user-recorded outcomes are transparently manual.

## Source requirement and present-state evidence

Source requirements: `REQ-OUTCOME`, `REQ-USAGE`, `REQ-BUDGET`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). mock-client:usage derives local spent/contactSpent/reserved/accepted/valid; Workspace Results inline callbacks add fictional manual outcomes. Static sample timestamps/prices and in-memory per-project scope are not live analytics.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **backend**; phase **P5**.
- Required predecessor evidence: `BO-016`, `BO-020`, `BO-022`, `BO-023`.
- Blockers: `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **EXISTING, inspected:** `features/workspace.tsx`

- **PROPOSED new file:** `services/api/buyeros_api/routes/outcomes.py`
- **PROPOSED new file:** `services/api/buyeros_api/routes/usage.py`
- **PROPOSED new file:** `services/api/alembic/versions/0008_outcomes.py`
- **PROPOSED new file:** `services/api/tests/test_usage_outcomes.py`

**PROPOSED predecessor outputs to modify after their creating task completes** (not existing at the audited commit):

- `services/api/buyeros_api/main.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/api/buyeros_api/models/core.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/live/client.ts` — inspect producer-task result first; modify only this task's required wiring.

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Persist outcome append/correction events with actor, source=manual, server creation time, user reported occurrence time, notes/provenance and buyer/project; do not imply inbox sync or real sent status.

2. Implement explicit date/project/workspace filters and metric definitions: eligible distinct accepted companies, accepted companies with >=1 valid policy-eligible unsuppressed contact, attributed settled discovery/extraction/assessment/contact charges and active reservations.

3. Cost per accepted company uses declared scope and denominator; no mixing all-time acceptance with filtered costs without label. Return null for zero denominator, rendered as em dash.

4. Keep quoted estimates/reserved upper bounds/settled provider cost/credits/subscription/infra separately labelled; unknown provider outcomes count reserved pending reconciliation.

5. Wire Overview cards, Results tabs, manual stage menus and budget settings to authorized API; read-only viewer cannot record outcomes or change budget.

6. Expose data mode and source for every metric and manual stage; copied/approved draft never increments sent/reply/meeting automatically.

## API, schema and state changes

GET usage/budgets; POST project outcome-events; metrics response documents scope/denominators/currency. Manual event correction is append-only supersession, not silent historical rewrite.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`spent=12.000000 USD, accepted_distinct_companies=3` yields cost/accepted=4.000000 USD; three contact rows for one company add one to the contactable-company denominator. Outcomes carry `source=manual`.

## Failure and concurrency cases

Concurrent manual edits/idempotency retries cannot duplicate stage count; stale budget forms use version conflicts. Partial run and unknown charge remain visible in totals.

- Scenario 1: Ledger sum reconciles all visible figures; three contacts at one company count one contactable company.
- Scenario 2: Zero denominator renders em dash and mixed currencies are never summed without explicit conversion policy.
- Scenario 3: Manual outcome includes actor/source/time and no inbox/delivery claim; viewer/cross-tenant mutation denied.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-024-01:** Ledger sum reconciles all visible figures; three contacts at one company count one contactable company.
- **TEST-BO-024-02:** Zero denominator renders em dash and mixed currencies are never summed without explicit conversion policy.
- **TEST-BO-024-03:** Manual outcome includes actor/source/time and no inbox/delivery claim; viewer/cross-tenant mutation denied.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `uv run python -m pytest tests/test_usage_outcomes.py` | `services/api` | PROPOSED_AFTER_TASK / NOT RUN | Distinct-company, date-scope, ledger and manual provenance tests pass |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Disable affected metric or show unavailable with incident reference; recompute derived values from immutable ledger/events, not manual dashboard patch.

## Effort assumptions

**18–30 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-024 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-024-persist-manual-outcomes-and-reconcile-every-displayed-usage-metric.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; planning pack committed at 1512d4c17d4f792e14598d524fdac3c9c37d27e7; a source import of the audited content baseline is still expected, importing tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: Overview/Results/Usage agree with persisted ledger and distinct company counts, and user-recorded outcomes are transparently manual. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

