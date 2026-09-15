---
task_id: "BO-025"
title: "Preserve bilingual responsive interactions and deep-link behavior"
phase: "P5"
status: "BLOCKED"
priority: "P1"
source_requirements: ["REQ-UI","REQ-DEMO"]
depends_on: ["BO-006","BO-007","BO-008","BO-016","BO-020","BO-022","BO-023","BO-024"]
blocked_by: ["B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "frontend"
files_to_read: ["features/workspace.tsx","features/discovery/wizard.tsx","features/buyers/detail.tsx","app/layout.tsx","app/[...slug]/page.tsx","app/globals.css","locales/index.ts","locales/context.tsx","tests/responsive-harness.html","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: ["features/workspace.tsx","features/discovery/wizard.tsx","features/buyers/detail.tsx","app/globals.css","locales/index.ts"]
dependency_output_files_to_modify: ["services/live/client.ts", "features/providers/data-mode.tsx", "features/providers/workspace-session.tsx", "services/api/buyeros_api/main.py", "services/api/buyeros_api/models/core.py"]
proposed_files_to_create: ["tests/e2e/buyeros-parity.spec.ts", "tests/e2e/buyeros-accessibility.spec.ts", "docs/buyeros/evidence/BO-025-visual-parity.md", "services/api/buyeros_api/routes/preferences.py", "services/api/tests/test_preferences.py"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["01_SOURCE_AND_UI_AUDIT.md","05_TEST_SECURITY_AND_RELEASE.md"]
migration_impact: "none; if current source requires an unlisted migration stop and revise task"
external_capabilities: []
external_spend_authorized: false
acceptance_tests: ["TEST-BO-025-01","TEST-BO-025-02","TEST-BO-025-03"]
verification_commands: [{"command": "pnpm exec playwright test tests/e2e/buyeros-parity.spec.ts tests/e2e/buyeros-accessibility.spec.ts", "working_directory": "repo", "status": "PROPOSED_AFTER_TASK / NOT RUN", "expected_result": "All route, locale, viewport and keyboard regression cases pass"}, {"command": "node tests/domain-checks.mjs", "working_directory": "repo", "status": "CURRENT_VERIFIED script / NOT RUN in planning", "expected_result": "Existing 12 domain checks pass if dependencies are installed and side effects remain reviewed"}, {"command": "uv run python -m pytest tests/test_preferences.py", "working_directory": "services/api", "status": "PROPOSED_AFTER_TASK / NOT RUN", "expected_result": "Scoped locale/default-market persistence and conflict tests pass"}]
rollback_or_rollforward: "Revert scoped CSS/dictionary/interaction regression while preserving API contracts; keep screenshot evidence and do not restore unsafe client authorization."
effort_range_hours: [20,34]
---

# BO-025 — Preserve bilingual responsive interactions and deep-link behavior

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

The live vertical slices retain the known BuyerOS navigation, density, evidence drawer and editor at 1440/1280/768/390px, with complete English/zh-HK system copy and functional deep links.

## Source requirement and present-state evidence

Source requirements: `REQ-UI`, `REQ-DEMO`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). Actual single Workspace owns views under Vinext next/navigation; BuyerDetail four tabs and Wizard four steps are present. zh dictionary fallback leaves some advanced/static copy English. Source includes responsive harness, not proof of a current mobile browser pass. Source has a RootLayout that mounts Workspace and does not render children; do not assume a conventional per-route component tree.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **frontend**; phase **P5**.
- Required predecessor evidence: `BO-006`, `BO-007`, `BO-008`, `BO-016`, `BO-020`, `BO-022`, `BO-023`, `BO-024`.
- Blockers: `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **EXISTING, inspected:** `features/workspace.tsx`
- **EXISTING, inspected:** `features/discovery/wizard.tsx`
- **EXISTING, inspected:** `features/buyers/detail.tsx`
- **EXISTING, inspected:** `app/globals.css`
- **EXISTING, inspected:** `locales/index.ts`

- **PROPOSED new file:** `tests/e2e/buyeros-parity.spec.ts`
- **PROPOSED new file:** `tests/e2e/buyeros-accessibility.spec.ts`
- **PROPOSED new file:** `docs/buyeros/evidence/BO-025-visual-parity.md`

**PROPOSED predecessor outputs to modify after their creating task completes** (not existing at the audited commit):

- `services/live/client.ts` — inspect producer-task result first; modify only this task's required wiring.
- `features/providers/data-mode.tsx` — inspect producer-task result first; modify only this task's required wiring.
- `features/providers/workspace-session.tsx` — inspect producer-task result first; modify only this task's required wiring.

- **PROPOSED new file:** `services/api/buyeros_api/routes/preferences.py`
- **PROPOSED new file:** `services/api/tests/test_preferences.py`

- **PROPOSED predecessor output to modify:** `services/api/buyeros_api/main.py`
- **PROPOSED predecessor output to modify:** `services/api/buyeros_api/models/core.py`

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Use captured baseline/source audit as visual reference; preserve sidebar/topbar/table-first layout, current routes, drawer/full-page tabs, wizard summary and three-pane desktop editor and existing stacked mobile queue/editor/review (mobile tabs only as an explicitly proposed usability improvement). Fix verified defects rather than restyling brand.

2. Complete dictionary coverage for new status/reason/error/empty/policy/progress copy and existing advanced-system gaps. Keep original foreign-language evidence/user text distinct from labelled translation.

3. Verify /app, discover/new/run, buyers/id, lists/id, outreach, results and settings refresh/back/forward with auth/project context; no reliance on previous in-memory record.

4. Add keyboard/focus/escape/status announcement/200% zoom/reduced-motion tests. Preserve filter sheet/mobile cards and no page-level overflow at required widths.

5. Audit every actionable control against source matrix; loading/empty/partial/offline/stale-session states have recovery and no dead success-only button.

6. Document browser/version/viewport/final URL/screenshots and mark any inaccessible environment case NOT RUN; do not activate WebMCP for live data as part of parity.

**Additional exact integration step:** Implement getPreferences/updatePreferences using BO-005's scoped preference storage and server validation for supported locale/default markets; wire the existing Settings fields. Preserve locale-only device preference as an explicit local convenience, not an authorization or live dataset store. Verify concurrent preference edits and workspace switching.

## API, schema and state changes

No new domain endpoints; consume previously approved contract states accurately. May fix local view/state mapping only.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`/app/buyers/buyer_a` opened directly at 390px in zh-HK restores the authorized drawer/full-page context or shows a tenant-safe 404; it does not require earlier in-memory navigation.

## Failure and concurrency cases

Locale switch during request, long translated labels, evidence drawer focus return, unknown deep-link ID and session expiry must remain usable. Do not hide system errors behind demo fallback.

- Scenario 1: Full demo regression retains 26→24 and 14/6/4 plus three detailed dossiers; live fixture mode distinct.
- Scenario 2: 1440/1280/768/390 widths have usable primary actions/no page overflow in en/zh-HK; keyboard core journey completes.
- Scenario 3: Each preserved route refreshes and exposes correct empty/404/expired-session state without phantom fixture record.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-025-01:** Full demo regression retains 26→24 and 14/6/4 plus three detailed dossiers; live fixture mode distinct.
- **TEST-BO-025-02:** 1440/1280/768/390 widths have usable primary actions/no page overflow in en/zh-HK; keyboard core journey completes.
- **TEST-BO-025-03:** Each preserved route refreshes and exposes correct empty/404/expired-session state without phantom fixture record.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `pnpm exec playwright test tests/e2e/buyeros-parity.spec.ts tests/e2e/buyeros-accessibility.spec.ts` | `repo` | PROPOSED_AFTER_TASK / NOT RUN | All route, locale, viewport and keyboard regression cases pass |
| `node tests/domain-checks.mjs` | `repo` | CURRENT_VERIFIED script / NOT RUN in planning | Existing 12 domain checks pass if dependencies are installed and side effects remain reviewed |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

Additional preference check (PROPOSED_AFTER_TASK / NOT RUN): `uv run python -m pytest tests/test_preferences.py` in `services/api` → Scoped locale/default-market persistence and conflict tests pass.

## Rollback or roll-forward

Revert scoped CSS/dictionary/interaction regression while preserving API contracts; keep screenshot evidence and do not restore unsafe client authorization.

## Effort assumptions

**20–34 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-025 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-025-preserve-bilingual-responsive-interactions-and-deep-link-behavior.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; planning pack committed at 1512d4c17d4f792e14598d524fdac3c9c37d27e7; a source import of the audited content baseline is still expected, importing tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: The live vertical slices retain the known BuyerOS navigation, density, evidence drawer and editor at 1440/1280/768/390px, with complete English/zh-HK system copy and functional deep links. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

