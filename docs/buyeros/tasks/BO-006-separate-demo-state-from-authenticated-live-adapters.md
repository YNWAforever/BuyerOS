---
task_id: "BO-006"
title: "Separate demo state from authenticated live adapters"
phase: "P1"
status: "BLOCKED"
priority: "P0"
source_requirements: ["REQ-DEMO","REQ-UI","REQ-TENANT"]
depends_on: ["BO-004","BO-005"]
blocked_by: ["B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "frontend"
files_to_read: ["features/workspace.tsx","services/contracts.ts","services/http-client.ts","services/mock-client.ts","data/demo/fixtures.ts","app/layout.tsx","locales/index.ts","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: ["features/workspace.tsx","services/http-client.ts","services/contracts.ts","locales/index.ts","package.json","pnpm-lock.yaml"]
dependency_output_files_to_modify: ["services/generated/buyeros-api.ts", "services/live/mapping.ts"]
proposed_files_to_create: ["services/live/client.ts","features/providers/data-mode.tsx","features/providers/workspace-session.tsx","tests/frontend/data-mode.spec.ts"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["contracts/openapi.proposed.yaml","03_DATA_API_AND_STATE_CONTRACTS.md"]
migration_impact: "none; if current source requires an unlisted migration stop and revise task"
external_capabilities: ["Approved managed OIDC and PostgreSQL design; use isolated fixtures until authorized"]
external_spend_authorized: false
acceptance_tests: ["TEST-BO-006-01","TEST-BO-006-02","TEST-BO-006-03"]
verification_commands: [{"command":"pnpm exec playwright test tests/frontend/data-mode.spec.ts","working_directory":"repo","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"Demo/live isolation, capability and tenant-switch assertions pass against isolated fixtures"}]
rollback_or_rollforward: "Disable live mode through server capability; retain working demo mode. Revert adapter wiring without importing live records into demo."
effort_range_hours: [20,32]
---

# BO-006 — Separate demo state from authenticated live adapters

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

Explicit demo and live sessions share the preserved screen shell while live requests authenticate, fail honestly and never load fictional companies on failure.

## Source requirement and present-state evidence

Source requirements: `REQ-DEMO`, `REQ-UI`, `REQ-TENANT`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). Workspace imports seed/quote/confirm/advanceRun directly and creates useState<Store>(seed); http-client only re-exports NOT_CONFIGURED. Browser keys are buyer os demo/draft/prefs keys spelled exactly buyeros-demo-v1, buyeros-drafts-v1, buyeros-prefs-v1 in source.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **frontend**; phase **P1**.
- Required predecessor evidence: `BO-004`, `BO-005`.
- Blockers: `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **EXISTING, inspected:** `features/workspace.tsx`
- **EXISTING, inspected:** `services/http-client.ts`
- **EXISTING, inspected:** `services/contracts.ts`
- **EXISTING, inspected:** `locales/index.ts`
- **EXISTING, inspected:** `package.json`
- **EXISTING, inspected:** `pnpm-lock.yaml`

- **PROPOSED new file:** `services/live/client.ts`
- **PROPOSED new file:** `features/providers/data-mode.tsx`
- **PROPOSED new file:** `features/providers/workspace-session.tsx`
- **PROPOSED new file:** `tests/frontend/data-mode.spec.ts`

**PROPOSED predecessor outputs to modify after their creating task completes** (not existing at the audited commit):

- `services/generated/buyeros-api.ts` — inspect producer-task result first; modify only this task's required wiring.
- `services/live/mapping.ts` — inspect producer-task result first; modify only this task's required wiring.

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Add explicit demo/live data-source provider without replacing Vinext routes, table/drawer or styling. Preserve existing demo fixture and domain tests.

2. Move live server state behind typed client and request cache keyed by actor/workspace/project/data mode; keep drawer/tab/filter/modal state transient. Extract only the state wiring needed for this task, not broad UI redesign.

3. Replace http-client stub with an explicit live adapter that sends verified bearer tokens in headers and maps structured errors. Keep unavailable capabilities disabled and display actionable NOT_CONFIGURED/401/503 errors.

4. Gate seed imports/local fixture loaders/timer engines behind demo mode. Preserve synthetic .example draft restore restrictions; never migrate local demo state into live tenant data.

5. On tenant/project change, abort in-flight requests and discard late responses whose scope token differs. Store only locale/non-sensitive preferences in browser storage; access tokens remain in memory.

6. Render connection state from server capabilities and label partially available workflows. Removing the demo banner cannot change mode or make a connection appear live.

7. Add the minimal Playwright development test dependency/version only after checking compatibility and install-script side effects; preserve pnpm@11.25.0 and existing lockfile entries. Record local browser test commands; CI and tests must have no live provider credentials.

## API, schema and state changes

Authenticated client calls agreed /v1 API; mode is a trusted adapter choice, not client permission. 401 refresh/login flow must not replay non-idempotent writes automatically.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`mode=live; GET buyers → 503 PROVIDER_UNAVAILABLE` produces an unavailable view with zero fallback fixtures. Switching to demo requires an explicit mode action, never an error handler.

## Failure and concurrency cases

503, parse failure, offline state and timeout expose errors, never seed(). Race of old workspace response after switch is ignored. No live data passes through WebMCP list_demo_buyers.

- Scenario 1: Break live API and assert zero fictional companies/usage; demo still renders 24 fixture companies.
- Scenario 2: Switch tenant during pending fetch and assert old data/events never render.
- Scenario 3: Browser storage contains no live contacts, uploaded documents, tokens or proprietary drafts; WebMCP remains synthetic only.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-006-01:** Break live API and assert zero fictional companies/usage; demo still renders 24 fixture companies.
- **TEST-BO-006-02:** Switch tenant during pending fetch and assert old data/events never render.
- **TEST-BO-006-03:** Browser storage contains no live contacts, uploaded documents, tokens or proprietary drafts; WebMCP remains synthetic only.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `pnpm exec playwright test tests/frontend/data-mode.spec.ts` | `repo` | PROPOSED_AFTER_TASK / NOT RUN | Demo/live isolation, capability and tenant-switch assertions pass against isolated fixtures |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Disable live mode through server capability; retain working demo mode. Revert adapter wiring without importing live records into demo.

## Effort assumptions

**20–32 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-006 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-006-separate-demo-state-from-authenticated-live-adapters.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; the audited source is imported at commit b804ba8d1514a1049b7202c861278dd72c473a75 (tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), merged into main via 72fef7da785624a35bb6701f1451ebcf0184a089), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: Explicit demo and live sessions share the preserved screen shell while live requests authenticate, fail honestly and never load fictional companies on failure. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

