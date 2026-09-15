---
task_id: "BO-008"
title: "Persist buyer evidence views, reviews, stable selections and lists"
phase: "P2"
status: "BLOCKED"
priority: "P0"
source_requirements: ["REQ-BUYERS","REQ-EVIDENCE","REQ-UI"]
depends_on: ["BO-007"]
blocked_by: ["B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "backend"
files_to_read: ["features/workspace.tsx","features/buyers/detail.tsx","services/contracts.ts","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: ["features/workspace.tsx","features/buyers/detail.tsx"]
dependency_output_files_to_modify: ["services/api/buyeros_api/main.py", "services/api/buyeros_api/models/core.py", "services/live/client.ts"]
proposed_files_to_create: ["services/api/buyeros_api/routes/buyers.py", "services/api/buyeros_api/routes/lists.py", "services/api/buyeros_api/services/selections.py", "services/api/tests/test_buyer_review_lists.py", "tests/frontend/buyer-review.spec.ts", "services/api/buyeros_api/routes/filter_presets.py"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["contracts/openapi.proposed.yaml","03_DATA_API_AND_STATE_CONTRACTS.md"]
migration_impact: "none; if current source requires an unlisted migration stop and revise task"
external_capabilities: []
external_spend_authorized: false
acceptance_tests: ["TEST-BO-008-01","TEST-BO-008-02","TEST-BO-008-03"]
verification_commands: [{"command":"uv run python -m pytest tests/test_buyer_review_lists.py","working_directory":"services/api","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"Selection, idempotent membership, audit and version tests pass"},{"command":"pnpm exec playwright test tests/frontend/buyer-review.spec.ts","working_directory":"repo","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"Table filters, page size, drawer/full-page, review and lists preserve layout and behavior"}]
rollback_or_rollforward: "Disable bulk writes if snapshot or version bugs arise; read views remain available. Restore incorrect reviews through new audit events, not evidence deletion."
effort_range_hours: [28,44]
---

# BO-008 — Persist buyer evidence views, reviews, stable selections and lists

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

The current buyer table/drawer and list views support durable per-project review, notes/owners and bounded all-filtered selection while company evidence remains intact.

## Source requirement and present-state evidence

Source requirements: `REQ-BUYERS`, `REQ-EVIDENCE`, `REQ-UI`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). Workspace:rows/pageRows/selected use local arrays and offset slicing; reviewed/update mutate in-memory Company. BuyerDetail has Overview/Evidence/Contacts/Activity tabs and owner/note inputs. List actions are local modal branches.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **backend**; phase **P2**.
- Required predecessor evidence: `BO-007`.
- Blockers: `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **EXISTING, inspected:** `features/workspace.tsx`
- **EXISTING, inspected:** `features/buyers/detail.tsx`

- **PROPOSED new file:** `services/api/buyeros_api/routes/buyers.py`
- **PROPOSED new file:** `services/api/buyeros_api/routes/lists.py`
- **PROPOSED new file:** `services/api/buyeros_api/services/selections.py`
- **PROPOSED new file:** `services/api/tests/test_buyer_review_lists.py`
- **PROPOSED new file:** `tests/frontend/buyer-review.spec.ts`

**PROPOSED predecessor outputs to modify after their creating task completes** (not existing at the audited commit):

- `services/api/buyeros_api/main.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/api/buyeros_api/models/core.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/live/client.ts` — inspect producer-task result first; modify only this task's required wiring.

- **PROPOSED new file:** `services/api/buyeros_api/routes/filter_presets.py`

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Implement buyer snapshot creation with fixed filter/sort/candidate IDs, tenant/project scope, expiry and offset page reads; deterministic tie-breaker prevents shifting pages. Explicit page vs all-filtered selection remains visible.

2. Implement detail/evidence reads and project-buyer review writes with actor/reason/version; distinguish fit from human review and add needs-information state where mapped UI requires it.

3. For bulk review resolve selected IDs against server snapshot, recheck each membership/version and return item-level applied/blocked/conflict status; do not act on a changed filter silently.

4. Implement duplicate-safe list memberships and create/rename/removal; remove membership without deleting company, source or assessment. Store notes/owner references with length limits and server timestamps.

5. Wire existing controls and deep links to API; preserve four evidence tabs and contrary/unknown information. Restore focus on drawer close and no full redesign.

**Additional exact integration step:** Implement listFilterPresets/saveFilterPreset from the contract with actor/project/workspace scope, validated filter vocabulary and server timestamps; preserve the current saved-preset control and clear its selected-row state when a preset changes.

## API, schema and state changes

POST buyer-snapshots; GET project buyers with snapshot_id/offset/limit; POST buyer-reviews; lists/memberships and buyer patch. Unreviewed→accepted/rejected/needs_information independent of fit.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`createBuyerSnapshot` fixes filtered IDs [buyer_a,buyer_b]; `reviewBuyers` applies only those versioned IDs. A new buyer matching the filter after snapshot creation is not silently accepted.

## Failure and concurrency cases

Expired snapshot requires refresh and new explicit selection; mixed eligibility yields scoped partial results. Stale note saves cannot overwrite another editor. Missing buyer deep link shows real 404.

- Scenario 1: All-filtered selection remains fixed when other users add/review buyers; cross-tenant IDs never mutate.
- Scenario 2: Duplicate add yields one membership; removal retains evidence and company.
- Scenario 3: Acceptance updates derived counts and invalidation hooks; concurrent review conflict preserves previous record/version.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-008-01:** All-filtered selection remains fixed when other users add/review buyers; cross-tenant IDs never mutate.
- **TEST-BO-008-02:** Duplicate add yields one membership; removal retains evidence and company.
- **TEST-BO-008-03:** Acceptance updates derived counts and invalidation hooks; concurrent review conflict preserves previous record/version.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `uv run python -m pytest tests/test_buyer_review_lists.py` | `services/api` | PROPOSED_AFTER_TASK / NOT RUN | Selection, idempotent membership, audit and version tests pass |
| `pnpm exec playwright test tests/frontend/buyer-review.spec.ts` | `repo` | PROPOSED_AFTER_TASK / NOT RUN | Table filters, page size, drawer/full-page, review and lists preserve layout and behavior |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Disable bulk writes if snapshot or version bugs arise; read views remain available. Restore incorrect reviews through new audit events, not evidence deletion.

## Effort assumptions

**28–44 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-008 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-008-persist-buyer-evidence-views-reviews-stable-selections-and-lists.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; planning pack committed at 1512d4c17d4f792e14598d524fdac3c9c37d27e7; a source import of the audited content baseline is still expected, importing tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: The current buyer table/drawer and list views support durable per-project review, notes/owners and bounded all-filtered selection while company evidence remains intact. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

