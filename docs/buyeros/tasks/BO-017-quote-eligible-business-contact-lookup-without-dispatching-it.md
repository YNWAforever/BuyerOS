---
task_id: "BO-017"
title: "Quote eligible business-contact lookup without dispatching it"
phase: "P4"
status: "BLOCKED"
priority: "P1"
source_requirements: ["REQ-QUOTE","REQ-POLICY","REQ-BUDGET"]
depends_on: ["BO-002","BO-008","BO-009","BO-010","BO-016"]
blocked_by: ["B-PROVIDERS","B-POLICY","B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "backend"
files_to_read: ["services/mock-client.ts","features/workspace.tsx","features/buyers/detail.tsx","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: ["features/workspace.tsx","features/buyers/detail.tsx"]
dependency_output_files_to_modify: ["services/api/buyeros_api/main.py", "services/api/buyeros_api/models/core.py", "services/live/client.ts"]
proposed_files_to_create: ["services/api/buyeros_api/routes/enrichment_quotes.py","services/api/buyeros_api/services/contact_eligibility.py","services/api/alembic/versions/0006_enrichment.py","services/api/tests/test_lookup_quote.py"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["contracts/openapi.proposed.yaml","03_DATA_API_AND_STATE_CONTRACTS.md"]
migration_impact: "PROPOSED additive migration; serialize through sole Alembic owner; execution only on approved disposable/staging DB"
external_capabilities: []
external_spend_authorized: false
acceptance_tests: ["TEST-BO-017-01","TEST-BO-017-02","TEST-BO-017-03"]
verification_commands: [{"command":"uv run python -m pytest tests/test_lookup_quote.py","working_directory":"services/api","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"Eligibility, quote-binding, zero-dispatch and price-version tests pass"}]
rollback_or_rollforward: "Disable quote capability and invalidate unconfirmed affected quotes; no reservation to refund for quote-only records."
effort_range_hours: [18,30]
---

# BO-017 — Quote eligible business-contact lookup without dispatching it

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

The existing dialog displays a server-priced immutable quote, eligible/skipped companies and reasons, expiry and maximum cost; opening or closing it does not purchase contacts.

## Source requirement and present-state evidence

Source requirements: `REQ-QUOTE`, `REQ-POLICY`, `REQ-BUDGET`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). Workspace:action('lookup') calls mock-client:quote and marks a local quote Reserved immediately; closeModal cancels that demo reservation. Actual live quote must be unreserved until explicit confirmation.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **backend**; phase **P4**.
- Required predecessor evidence: `BO-002`, `BO-008`, `BO-009`, `BO-010`, `BO-016`.
- Blockers: `B-PROVIDERS`, `B-POLICY`, `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **EXISTING, inspected:** `features/workspace.tsx`
- **EXISTING, inspected:** `features/buyers/detail.tsx`

- **PROPOSED new file:** `services/api/buyeros_api/routes/enrichment_quotes.py`
- **PROPOSED new file:** `services/api/buyeros_api/services/contact_eligibility.py`
- **PROPOSED new file:** `services/api/alembic/versions/0006_enrichment.py`
- **PROPOSED new file:** `services/api/tests/test_lookup_quote.py`

**PROPOSED predecessor outputs to modify after their creating task completes** (not existing at the audited commit):

- `services/api/buyeros_api/main.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/api/buyeros_api/models/core.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/live/client.ts` — inspect producer-task result first; modify only this task's required wiring.

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Resolve explicit buyer IDs/server selection snapshot under tenant/project scope and evaluate accepted+current Match+research policy+no suppression+appropriate not-researched state for each company.

2. Bind quote to sorted IDs, normalized request hash, requested roles/business-email purpose, actor/tenant, profile/eligibility versions, provider/price version, currency, upper bound and server expiry.

3. Validate provider bounded pricing and quote capability from BO-002; phone and waterfall options are absent. Returning a quote may use cached verified pricing only; no paid contact call.

4. Persist quoted state without spend reservation; expose eligible/blocked rows and stable reason codes. Show available budget as informational because it is rechecked atomically at confirm.

5. Adapt existing lookup dialog and closeModal so closing unconfirmed quote merely dismisses/expires it. Do not reuse demo Reserved label for an unreserved live quote.

## API, schema and state changes

POST /projects/{project_id}/enrichment-quotes; response quoted state, line eligibility, hash/version/currency/max_cost/expires_at. Migration adds quotes/jobs; no provider dispatch.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`quoteLookup` binds selection/purpose=contact_research/roles/contact_type; `quote.status=quoted` and `reservation_id=null`. Opening/closing the quote creates no provider operation or reserved amount.

## Failure and concurrency cases

Expired selection, stale profile, policy unknown, unsupported provider price bound or all-ineligible returns explicit reasons. Price changes invalidate confirmation, not hidden extra charges.

- Scenario 1: Open/close dialog creates zero provider calls and zero budget reservation.
- Scenario 2: Mixed accepted/review/suppressed/policy-unknown batch returns correct per-company reasons.
- Scenario 3: Quote hash covers purpose/roles/IDs/price/actor; tampered IDs or stale profile cannot be confirmed later.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-017-01:** Open/close dialog creates zero provider calls and zero budget reservation.
- **TEST-BO-017-02:** Mixed accepted/review/suppressed/policy-unknown batch returns correct per-company reasons.
- **TEST-BO-017-03:** Quote hash covers purpose/roles/IDs/price/actor; tampered IDs or stale profile cannot be confirmed later.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `uv run python -m pytest tests/test_lookup_quote.py` | `services/api` | PROPOSED_AFTER_TASK / NOT RUN | Eligibility, quote-binding, zero-dispatch and price-version tests pass |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Disable quote capability and invalidate unconfirmed affected quotes; no reservation to refund for quote-only records.

## Effort assumptions

**18–30 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-017 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-017-quote-eligible-business-contact-lookup-without-dispatching-it.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; the audited source is imported at commit b804ba8d1514a1049b7202c861278dd72c473a75 (tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), merged into main via 72fef7da785624a35bb6701f1451ebcf0184a089), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: The existing dialog displays a server-priced immutable quote, eligible/skipped companies and reasons, expiry and maximum cost; opening or closing it does not purchase contacts. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

