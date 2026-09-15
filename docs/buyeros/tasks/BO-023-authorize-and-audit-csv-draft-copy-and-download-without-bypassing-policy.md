---
task_id: "BO-023"
title: "Authorize and audit CSV, draft copy and download without bypassing policy"
phase: "P5"
status: "BLOCKED"
priority: "P1"
source_requirements: ["REQ-EXPORT","REQ-POLICY","REQ-APPROVAL"]
depends_on: ["BO-008","BO-009","BO-022"]
blocked_by: ["B-POLICY","B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "backend"
files_to_read: ["services/mock-client.ts","features/workspace.tsx","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: ["features/workspace.tsx"]
dependency_output_files_to_modify: ["services/api/buyeros_api/main.py", "services/live/client.ts"]
proposed_files_to_create: ["services/api/buyeros_api/routes/exports.py","services/api/buyeros_api/services/export_policy.py","services/api/tests/test_authorized_exports.py","tests/frontend/export-download.spec.ts"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["contracts/openapi.proposed.yaml","03_DATA_API_AND_STATE_CONTRACTS.md"]
migration_impact: "none; if current source requires an unlisted migration stop and revise task"
external_capabilities: []
external_spend_authorized: false
acceptance_tests: ["TEST-BO-023-01","TEST-BO-023-02","TEST-BO-023-03"]
verification_commands: [{"command":"uv run python -m pytest tests/test_authorized_exports.py","working_directory":"services/api","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"Scope, formula, current approval and retention checks pass"},{"command":"pnpm exec playwright test tests/frontend/export-download.spec.ts","working_directory":"repo","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"Real browser download event and artifact content verified"}]
rollback_or_rollforward: "Disable export capability, expire affected links and retain audit. Prior downloads cannot be recalled; follow incident/deletion process for any leak."
effort_range_hours: [16,28]
---

# BO-023 — Authorize and audit CSV, draft copy and download without bypassing policy

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

Real data export and addressed draft copy/download require current scope/purpose/approval checks, produce auditable artifacts, and never create Sent or expose blocked contact data.

## Source requirement and present-state evidence

Source requirements: `REQ-EXPORT`, `REQ-POLICY`, `REQ-APPROVAL`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). mock-client:csv neutralizes formulas and marks data_mode=demo; download creates a Blob. Workspace copy/download callbacks operate client-side and are not authorization boundaries. Historical download capture was unverified.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **backend**; phase **P5**.
- Required predecessor evidence: `BO-008`, `BO-009`, `BO-022`.
- Blockers: `B-POLICY`, `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **EXISTING, inspected:** `features/workspace.tsx`

- **PROPOSED new file:** `services/api/buyeros_api/routes/exports.py`
- **PROPOSED new file:** `services/api/buyeros_api/services/export_policy.py`
- **PROPOSED new file:** `services/api/tests/test_authorized_exports.py`
- **PROPOSED new file:** `tests/frontend/export-download.spec.ts`

**PROPOSED predecessor outputs to modify after their creating task completes** (not existing at the audited commit):

- `services/api/buyeros_api/main.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/live/client.ts` — inspect producer-task result first; modify only this task's required wiring.

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Implement scoped export request resolving explicit IDs/server snapshot and per-record export-purpose/suppression decisions. Include only authorized fields; plain company intelligence export must not sneak contact fields into notes/evidence.

2. Require current revision/context approval for addressed outreach draft copy/download under approved policy; unapproved review-only export, if allowed, is visibly watermarked and excludes prohibited contact data.

3. Perform authorization before payload is returned to browser; copy button fetches authorized exact revision rather than dumping cached stale text. Previously accessed data cannot be technically recalled; rely on minimization and access controls.

4. Neutralize spreadsheet formula prefixes including leading whitespace, quote commas/newlines/Unicode safely; prevent secret/person-data leakage through columns and filenames.

5. Generate private bounded-lifetime artifact or bounded synchronous payload with data_mode=live, source IDs, scoped count and audit event; signed URL scoped and expiry checked. Demo exports retain DEMO_ and synthetic marker.

6. Record export/copy/download audit separately from manual outcomes and delivery. No mailto/send shortcut.

## API, schema and state changes

Project buyer export and /drafts/{draft_id}/exports operations; require Idempotency-Key/version/context as specified. Export queued→running→ready/failed/revoked/expired under the contract. A policy-blocked request returns its structured error without creating an export, or an existing job fails/revokes with a reason; blocked is not an invented stored status. No delivery transition.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`exportDraft` for revision 4 after suppression returns POLICY_BLOCKED even if the browser cached the text. A CSV cell starting with =HYPERLINK is neutralized and no Sent event is created.

## Failure and concurrency cases

Snapshot expiry, policy revocation after preparation before download, wrong tenant signed URL, large export, formula injection and stale approval deny/redact with counts; silent partial leakage prohibited.

- Scenario 1: Suppressed/policy-blocked contact cannot escape through CSV, draft copy or download endpoint.
- Scenario 2: Formula/newline/Unicode fields remain inert and valid; demo/live markings are correct.
- Scenario 3: Browser captures actual download and verifies payload/hash/scope; no Sent/outcome is created.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-023-01:** Suppressed/policy-blocked contact cannot escape through CSV, draft copy or download endpoint.
- **TEST-BO-023-02:** Formula/newline/Unicode fields remain inert and valid; demo/live markings are correct.
- **TEST-BO-023-03:** Browser captures actual download and verifies payload/hash/scope; no Sent/outcome is created.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `uv run python -m pytest tests/test_authorized_exports.py` | `services/api` | PROPOSED_AFTER_TASK / NOT RUN | Scope, formula, current approval and retention checks pass |
| `pnpm exec playwright test tests/frontend/export-download.spec.ts` | `repo` | PROPOSED_AFTER_TASK / NOT RUN | Real browser download event and artifact content verified |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Disable export capability, expire affected links and retain audit. Prior downloads cannot be recalled; follow incident/deletion process for any leak.

## Effort assumptions

**16–28 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-023 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-023-authorize-and-audit-csv-draft-copy-and-download-without-bypassing-policy.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; planning pack committed at 1512d4c17d4f792e14598d524fdac3c9c37d27e7; a source import of the audited content baseline is still expected, importing tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: Real data export and addressed draft copy/download require current scope/purpose/approval checks, produce auditable artifacts, and never create Sent or expose blocked contact data. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

