---
task_id: "BO-016"
title: "Expose durable run progress, cancellation and retry in the existing UI"
phase: "P3"
status: "BLOCKED"
priority: "P1"
source_requirements: ["REQ-EVENTS","REQ-DISCOVERY","REQ-UI"]
depends_on: ["BO-006","BO-007","BO-011","BO-015"]
blocked_by: ["B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "frontend"
files_to_read: ["features/workspace.tsx","services/run-engine.ts","services/contracts.ts","features/discovery/wizard.tsx","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: ["features/workspace.tsx","services/http-client.ts","features/discovery/wizard.tsx"]
dependency_output_files_to_modify: ["services/api/buyeros_api/main.py", "services/live/client.ts"]
proposed_files_to_create: ["services/api/buyeros_api/routes/runs.py","services/api/buyeros_api/services/run_events.py","services/api/tests/test_run_events.py","tests/frontend/run-progress.spec.ts"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["contracts/openapi.proposed.yaml","03_DATA_API_AND_STATE_CONTRACTS.md"]
migration_impact: "none; if current source requires an unlisted migration stop and revise task"
external_capabilities: ["Verified provider contracts and deterministic fixtures; no live calls authorized"]
external_spend_authorized: false
acceptance_tests: ["TEST-BO-016-01","TEST-BO-016-02","TEST-BO-016-03"]
verification_commands: [{"command":"uv run python -m pytest tests/test_run_events.py","working_directory":"services/api","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"Durable ordering, replay, authorization and cancel state tests pass"},{"command":"pnpm exec playwright test tests/frontend/run-progress.spec.ts","working_directory":"repo","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"Live fixture progress/reconnect/deep-link states render without demo timer"}]
rollback_or_rollforward: "Disable new run creation, keep read/poll status available, pause worker consumers as needed. Do not erase cancelled/partial results."
effort_range_hours: [22,36]
---

# BO-016 — Expose durable run progress, cancellation and retry in the existing UI

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

Start, reconnect, cancel and retry display committed live progress on the preserved run screen, with partial results and no duplicate event application.

## Source requirement and present-state evidence

Source requirements: `REQ-EVENTS`, `REQ-DISCOVERY`, `REQ-UI`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). Workspace:startRun and 700ms timer drive local states; run-engine:cancelRun/retryRun retains demo results. usePathname maps existing /app/discover/:runId deep links.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **frontend**; phase **P3**.
- Required predecessor evidence: `BO-006`, `BO-007`, `BO-011`, `BO-015`.
- Blockers: `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **EXISTING, inspected:** `features/workspace.tsx`
- **EXISTING, inspected:** `services/http-client.ts`
- **EXISTING, inspected:** `features/discovery/wizard.tsx`

- **PROPOSED new file:** `services/api/buyeros_api/routes/runs.py`
- **PROPOSED new file:** `services/api/buyeros_api/services/run_events.py`
- **PROPOSED new file:** `services/api/tests/test_run_events.py`
- **PROPOSED new file:** `tests/frontend/run-progress.spec.ts`

**PROPOSED predecessor outputs to modify after their creating task completes** (not existing at the audited commit):

- `services/api/buyeros_api/main.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/live/client.ts` — inspect producer-task result first; modify only this task's required wiring.

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Implement start/list/get/cancel/retry runs under approved ICP/version/budget/role checks; idempotent start enqueues transactionally via outbox and returns 202 run identity.

2. Persist monotonic per-run event sequence in same transaction as meaningful business state; explicit allowed run transitions distinguish partial, paused_budget, cancel_requested, cancelled, failed and completed.

3. Serve authorized resumable event stream with after/Last-Event-ID semantics or bearer fetch-stream. Native EventSource cannot add bearer headers; use tested fetch streaming or short-lived authorized stream scheme with no long-lived token in URL.

4. Implement polling fallback/resync when event gap/expired cursor occurs; deduplicate by run sequence and ignore old tenant/run responses. No synthetic percent timer in live mode.

5. Cancel sets cancel_requested and stops undispatched work, preserving completed results and unknown cost reservations. Retry targets approved failed work with stable identities and cannot blindly redispatch uncertain provider calls.

6. Preserve route/deep-link/navigation and existing demo scenarios; UI shows genuine stage/results/cost source, unavailable/partial/no-results actions and reconnection status.

## API, schema and state changes

POST project runs; GET runs/{run_id}/events; POST cancel/retry. 202 means queued durable, not completed. Events have monotonic sequence and data mode.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`getRunEvents(after_sequence=17)` returns committed sequences 18 onward; duplicate 18 is ignored. Gap/resume failure reloads getRun snapshot and reconnects, never advances a client timer.

## Failure and concurrency cases

Network disconnect, replay/gaps, token expiry, lease restart, same-key repeated start, cancel during dispatch and stale deep links show recoverable state without fake progress.

- Scenario 1: Reconnect after event N applies N+1 onward once; gap causes snapshot resync.
- Scenario 2: Cancel mid-run keeps committed buyers and active unknown reservation; retry avoids duplicated provider side effects.
- Scenario 3: Direct run URL reload and mobile status announcements work with authorized polling fallback.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-016-01:** Reconnect after event N applies N+1 onward once; gap causes snapshot resync.
- **TEST-BO-016-02:** Cancel mid-run keeps committed buyers and active unknown reservation; retry avoids duplicated provider side effects.
- **TEST-BO-016-03:** Direct run URL reload and mobile status announcements work with authorized polling fallback.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `uv run python -m pytest tests/test_run_events.py` | `services/api` | PROPOSED_AFTER_TASK / NOT RUN | Durable ordering, replay, authorization and cancel state tests pass |
| `pnpm exec playwright test tests/frontend/run-progress.spec.ts` | `repo` | PROPOSED_AFTER_TASK / NOT RUN | Live fixture progress/reconnect/deep-link states render without demo timer |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Disable new run creation, keep read/poll status available, pause worker consumers as needed. Do not erase cancelled/partial results.

## Effort assumptions

**22–36 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-016 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-016-expose-durable-run-progress-cancellation-and-retry-in-the-existing-ui.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; the audited source is imported at commit b804ba8d1514a1049b7202c861278dd72c473a75 (tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), merged into main via 72fef7da785624a35bb6701f1451ebcf0184a089), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: Start, reconnect, cancel and retry display committed live progress on the preserved run screen, with partial results and no duplicate event application. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

