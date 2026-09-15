---
task_id: "BO-007"
title: "Persist projects, editable offers and immutable approved buyer profiles"
phase: "P2"
status: "BLOCKED"
priority: "P0"
source_requirements: ["REQ-PROFILE","REQ-DATA","REQ-UI"]
depends_on: ["BO-005","BO-006"]
blocked_by: ["B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "backend"
files_to_read: ["features/discovery/wizard.tsx","features/workspace.tsx","services/contracts.ts","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: ["features/discovery/wizard.tsx","features/workspace.tsx"]
dependency_output_files_to_modify: ["services/api/buyeros_api/main.py", "services/api/buyeros_api/models/core.py", "services/live/client.ts"]
proposed_files_to_create: ["services/api/buyeros_api/routes/projects.py", "services/api/buyeros_api/services/profiles.py", "services/api/tests/test_projects_profiles.py", "tests/frontend/profile-wizard.spec.ts", "services/api/buyeros_api/services/sender_identity.py"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["contracts/openapi.proposed.yaml","03_DATA_API_AND_STATE_CONTRACTS.md"]
migration_impact: "none; if current source requires an unlisted migration stop and revise task"
external_capabilities: []
external_spend_authorized: false
acceptance_tests: ["TEST-BO-007-01", "TEST-BO-007-02", "TEST-BO-007-03", "TEST-BO-007-04"]
verification_commands: [{"command":"uv run python -m pytest tests/test_projects_profiles.py","working_directory":"services/api","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"Persistence, immutability and cross-tenant/version tests pass"},{"command":"pnpm exec playwright test tests/frontend/profile-wizard.spec.ts","working_directory":"repo","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"Existing four-step form persists correctly in live fixtures"}]
rollback_or_rollforward: "Disable project writes if contracts mismatch; retain previous immutable versions. Correct records through audited new versions, not in-place history rewrite."
effort_range_hours: [24,40]
---

# BO-007 — Persist projects, editable offers and immutable approved buyer profiles

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

A user creates/selects a real project, saves offer/market requirements, approves a specific immutable profile revision and reloads it without losing the preserved four-step workflow.

## Source requirement and present-state evidence

Source requirements: `REQ-PROFILE`, `REQ-DATA`, `REQ-UI`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). Wizard:Offer/sample/next validates local fields and confirmed checkbox. Workspace:startRun assigns profileVersion from run count; project selector is a single fictional project. Profile APIs are declarations only.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **backend**; phase **P2**.
- Required predecessor evidence: `BO-005`, `BO-006`.
- Blockers: `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **EXISTING, inspected:** `features/discovery/wizard.tsx`
- **EXISTING, inspected:** `features/workspace.tsx`

- **PROPOSED new file:** `services/api/buyeros_api/routes/projects.py`
- **PROPOSED new file:** `services/api/buyeros_api/services/profiles.py`
- **PROPOSED new file:** `services/api/tests/test_projects_profiles.py`
- **PROPOSED new file:** `tests/frontend/profile-wizard.spec.ts`

**PROPOSED predecessor outputs to modify after their creating task completes** (not existing at the audited commit):

- `services/api/buyeros_api/main.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/api/buyeros_api/models/core.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/live/client.ts` — inspect producer-task result first; modify only this task's required wiring.

- **PROPOSED new file:** `services/api/buyeros_api/services/sender_identity.py`

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Implement project create/list/get/update and draft ICP save with expected_version; scope all repository queries to membership workspace and project.

2. Validate required offer facts, markets/types/languages and must/nice/exclusion fields using server schemas. Manual facts retain actor/provenance; unknown certifications stay unknown.

3. Approval creates immutable profile version/content hash with actor/time; edits fork a new draft, clear confirmation and do not mutate prior run assessments.

4. Wire project selection and Wizard save/approve to persisted API responses. Keep current table-first navigation, sample-project entry and four-step summary.

5. Require approved current ICP on future start-run requests; stale expected version returns a conflict with reload/review action. Offer-document ingestion stays separately owned by BO-012.

**Additional authority/concurrency step:** Implement the contract's project PATCH sender_identity plus sender_confirmation=true flow: only reviewer/workspace_admin may approve that field; generate an immutable server-controlled version_key scoped to the project. Operators can prepare identity text for review but cannot forge approval. Config editing/revocation supersedes the prior version and invalidates dependent draft approvals; no mailbox is connected.

## API, schema and state changes

/projects CRUD; /projects/{project_id}/icp-versions POST and approval operation in proposed contract. Draft→approved immutable profile; project state uses optimistic concurrency.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`saveICPVersion` creates version 2 as draft; `approveICPVersion` approves that immutable version. Editing `must_have` creates version 3 draft while an older run continues referencing version 2.

## Failure and concurrency cases

Two editors cannot approve contradictory versions unnoticed. Deleting/archiving a project does not silently orphan runs; denied edits retain in-memory form for correction.

- Scenario 1: Refresh and deep link preserve project/offer/profile; workspace B cannot read it.
- Scenario 2: Changing approved must-have or markets creates new unapproved version while old run reference stays fixed.
- Scenario 3: Concurrent expected_version edits yield one success/one conflict; unapproved ICP cannot start discovery.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-007-01:** Refresh and deep link preserve project/offer/profile; workspace B cannot read it.
- **TEST-BO-007-02:** Changing approved must-have or markets creates new unapproved version while old run reference stays fixed.
- **TEST-BO-007-03:** Concurrent expected_version edits yield one success/one conflict; unapproved ICP cannot start discovery.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `uv run python -m pytest tests/test_projects_profiles.py` | `services/api` | PROPOSED_AFTER_TASK / NOT RUN | Persistence, immutability and cross-tenant/version tests pass |
| `pnpm exec playwright test tests/frontend/profile-wizard.spec.ts` | `repo` | PROPOSED_AFTER_TASK / NOT RUN | Existing four-step form persists correctly in live fixtures |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

Additional required negative tests:

- **TEST-BO-007-04:** An operator/foreign-project/forged sender_identity version cannot be approved or attached to a draft; reviewer-confirmed project config produces one immutable active version and retains prior history.

## Rollback or roll-forward

Disable project writes if contracts mismatch; retain previous immutable versions. Correct records through audited new versions, not in-place history rewrite.

## Effort assumptions

**24–40 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-007 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-007-persist-projects-editable-offers-and-immutable-approved-buyer-profiles.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; planning pack committed at 1512d4c17d4f792e14598d524fdac3c9c37d27e7; a source import of the audited content baseline is still expected, importing tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: A user creates/selects a real project, saves offer/market requirements, approves a specific immutable profile revision and reloads it without losing the preserved four-step workflow. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

