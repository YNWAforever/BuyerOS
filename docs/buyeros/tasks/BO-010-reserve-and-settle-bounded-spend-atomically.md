---
task_id: "BO-010"
title: "Reserve and settle bounded spend atomically"
phase: "P2"
status: "BLOCKED"
priority: "P0"
source_requirements: ["REQ-BUDGET","REQ-PROVIDER"]
depends_on: ["BO-005","BO-009"]
blocked_by: ["B-PROVIDERS","B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "backend"
files_to_read: ["services/mock-client.ts","services/run-engine.ts","services/contracts.ts","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: []
dependency_output_files_to_modify: ["services/api/buyeros_api/db.py", "services/api/buyeros_api/models/core.py", "services/api/buyeros_api/main.py"]
proposed_files_to_create: ["services/api/buyeros_api/services/budgets.py", "services/api/buyeros_api/models/budget.py", "services/api/alembic/versions/0003_budget.py", "services/api/tests/test_budget_atomicity.py", "services/api/buyeros_api/routes/budgets.py"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["03_DATA_API_AND_STATE_CONTRACTS.md"]
migration_impact: "PROPOSED additive migration; serialize through sole Alembic owner; execution only on approved disposable/staging DB"
external_capabilities: ["Verified provider contracts and deterministic fixtures; no live calls authorized"]
external_spend_authorized: false
acceptance_tests: ["TEST-BO-010-01", "TEST-BO-010-02", "TEST-BO-010-03", "TEST-BO-010-04", "TEST-BO-010-05"]
verification_commands: [{"command":"uv run python -m pytest tests/test_budget_atomicity.py","working_directory":"services/api","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"Concurrency tests pass on local PostgreSQL with independent connections; ledger reconciles exactly"}]
rollback_or_rollforward: "Pause all paid dispatch, preserve immutable ledger, repair by compensating entries. Never delete or rewrite settled cost history."
effort_range_hours: [24,40]
---

# BO-010 — Reserve and settle bounded spend atomically

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

Concurrent paid-operation authorization cannot exceed approved workspace/project/run/category limits, and uncertain provider charges retain their reservation.

## Source requirement and present-state evidence

Source requirements: `REQ-BUDGET`, `REQ-PROVIDER`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). mock-client:usage sums JavaScript numbers and excludes expired demo quote reservations; confirm does a local budget check. These browser semantics must not be copied as a production financial guarantee.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **backend**; phase **P2**.
- Required predecessor evidence: `BO-005`, `BO-009`.
- Blockers: `B-PROVIDERS`, `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **Existing application files to modify: none.** New backend/planning files are explicitly proposed below; this is not a claim that those services already exist.

- **PROPOSED new file:** `services/api/buyeros_api/services/budgets.py`
- **PROPOSED new file:** `services/api/buyeros_api/models/budget.py`
- **PROPOSED new file:** `services/api/alembic/versions/0003_budget.py`
- **PROPOSED new file:** `services/api/tests/test_budget_atomicity.py`

**PROPOSED predecessor outputs to modify after their creating task completes** (not existing at the audited commit):

- `services/api/buyeros_api/db.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/api/buyeros_api/models/core.py` — inspect producer-task result first; modify only this task's required wiring.

- **PROPOSED new file:** `services/api/buyeros_api/routes/budgets.py`

- **PROPOSED predecessor output to modify:** `services/api/buyeros_api/main.py`

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Represent money as Python Decimal and PostgreSQL NUMERIC(20,6) plus explicit currency and price-version snapshot; API amount strings never binary float totals. Six decimal places preserve sub-cent provider metering. Separate operation charges/provider credits/subscription allocation/infra overhead.

2. Create budget accounts, reservations, immutable cost events and provider-operation correlation. Define bound <= each applicable active budget; lock accounts in deterministic workspace→project→run→category order.

3. Within one transaction, insert scoped idempotency key+normalized hash, check every applicable remaining ceiling, reserve the operation upper bound and update reserved totals. Same key+same payload returns original; different payload returns conflict.

4. Implement transitions reserve→committed/settled/released/reconciled/reversed with unique operation/event constraints. Settled invoice adjustments may exceed estimate only under explicit exception incident flow; unbounded provider calls are disabled.

5. Expiry releases only never-submitted reservations with conclusive non-dispatch. submitted/unknown operations keep funds reserved until authoritative reconciliation; never release on request/worker timeout.

6. Implement budget reduction rules for existing reservations; prevent negative availability and pause new dispatch without retroactively cancelling charges. Wire audit reasons and metrics for aged unknown reservations.

**Additional authority/concurrency step:** Use explicit half-open UTC budget periods [period_start, period_end) with period IDs on reservations and immutable cost events. Evaluate operation time/price snapshot server-side. At rollover, outstanding submitted/unknown holds remain active and are conservatively carried into new-period admission limits until authoritative settlement; a calendar boundary never releases them. Settlement/refund/reversal is attributed to the original reservation/operation period with provenance, not moved to manufacture new-period capacity. Reject lowering a cap below settled plus all applicable active/rolled holds; budget updates use version/row locking.

## API, schema and state changes

Budget read/update and ledger service; additive budget_accounts/reservations/cost_events/provider_operations schema. Invariant settled_spend + active_reserved_upper_bounds + proposed_reservation <= approved_budget at authorization.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`budget=10.000000 USD; reserve A=6.000000; reserve B=6.000000 concurrently` yields one reservation and one BUDGET_LIMIT. If provider acceptance for A is uncertain, 6.000000 remains reserved.

## Failure and concurrency cases

Parallel reserve races, lock deadlock/retry, currency mismatch, duplicate event, timeout-after-acceptance and budget reduction are explicit cases. Reservation cannot disappear due merely to quote expiry after dispatch.

- Scenario 1: Two concurrent 6.00 reservations under 10.00 approve exactly one; balance equals ledger.
- Scenario 2: Same idempotency key repeated settles once; different payload conflicts.
- Scenario 3: Provider accepted then client timeout leaves reservation active until confirmed cost/no-charge reconciliation; cancellation does not release unknown spend.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-010-01:** Two concurrent 6.00 reservations under 10.00 approve exactly one; balance equals ledger.
- **TEST-BO-010-02:** Same idempotency key repeated settles once; different payload conflicts.
- **TEST-BO-010-03:** Provider accepted then client timeout leaves reservation active until confirmed cost/no-charge reconciliation; cancellation does not release unknown spend.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `uv run python -m pytest tests/test_budget_atomicity.py` | `services/api` | PROPOSED_AFTER_TASK / NOT RUN | Concurrency tests pass on local PostgreSQL with independent connections; ledger reconciles exactly |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

Additional required negative tests:

- **TEST-BO-010-04:** At UTC period rollover, submitted/unknown reservations remain held and constrain new-period admission; concurrent boundary requests cannot exceed either applicable limit.
- **TEST-BO-010-05:** Refunds/reversals remain attributed to the original operation period; lowering a cap below settled plus active/carried reservations returns a versioned conflict without altering the ledger.

## Rollback or roll-forward

Pause all paid dispatch, preserve immutable ledger, repair by compensating entries. Never delete or rewrite settled cost history.

## Effort assumptions

**24–40 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-010 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-010-reserve-and-settle-bounded-spend-atomically.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; currently empty until the exact audited import lands, expected tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: Concurrent paid-operation authorization cannot exceed approved workspace/project/run/category limits, and uncertain provider charges retain their reservation. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

