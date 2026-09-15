---
task_id: "BO-000"
title: "Reconcile the exact source, missing inputs, and OpenCode baseline"
phase: "P0"
status: "READY_FOR_REVIEW"
priority: "P0"
source_requirements: ["REQ-IDENTITY","REQ-INPUTS","REQ-OPENCODE"]
depends_on: []
blocked_by: []
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "platform"
files_to_read: ["package.json", "pnpm-lock.yaml", "DEVELOPER_HANDOFF.md", "scripts/run-framework.mjs", "scripts/build-verified.sh", "docs/buyeros/00_README_AND_DECISIONS.md", "docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md", "docs/buyeros/inputs/PLANNING_MASTER.supplied.md", "docs/buyeros/inputs/FRONTEND_SPEC.earlier-upload.md"]
existing_files_to_modify: []
dependency_output_files_to_modify: []
proposed_files_to_create: ["docs/buyeros/evidence/BO-000-baseline.md"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: []
migration_impact: "none; if current source requires an unlisted migration stop and revise task"
external_capabilities: []
external_spend_authorized: false
acceptance_tests: ["TEST-BO-000-01","TEST-BO-000-02","TEST-BO-000-03"]
verification_commands: [{"command":"git rev-parse HEAD","working_directory":"repo","status":"CURRENT_VERIFIED / NOT RUN in task","expected_result":"Record current SHA and compare against audited baseline"},{"command":"git status --short","working_directory":"repo","status":"CURRENT_VERIFIED / NOT RUN in task","expected_result":"Record every pre-existing change"},{"command":"opencode --version","working_directory":"repo","status":"NOT RUN; unavailable in planning environment","expected_result":"Only run if command -v opencode succeeds; capture exact installed version"}]
rollback_or_rollforward: "Retain the previous plan revision and append a dated baseline correction. No code, configuration, database, or infrastructure changes."
effort_range_hours: [4,8]
---

# BO-000 — Reconcile the exact source, missing inputs, and OpenCode baseline

**Planning status:** READY_FOR_REVIEW means ready for OpenCode Plan inspection, not Build approval. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

A reviewer can identify exactly which checkout, instructions, input set and OpenCode runtime the next task will use, with a written disposition for each missing reference.

## Source requirement and present-state evidence

Source requirements: `REQ-IDENTITY`, `REQ-INPUTS`, `REQ-OPENCODE`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). **Canonical repository is now owner-confirmed as `YNWAforever/BuyerOS`; the planning pack is committed there at `1512d4c17d4f792e14598d524fdac3c9c37d27e7` (documentation only). A source import of the audited content baseline is still expected, and that import commit must produce tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`.** The audited content baseline was GitHub `YNWAforever/buyerosgpt` main `b804ba8d1514a1049b7202c861278dd72c473a75`; its source tree matches Sites commit `76892126c86031bfe8e7ab517adba7f306040313`. package.json names site-creator-vinext-starter, not a different repository. The requested references directory and three reference contents are unavailable; an earlier frontend master was separately read. `command -v opencode` found no executable in the planning environment; a later review located the OpenCode **desktop** app v1.18.30 (`%LOCALAPPDATA%\Programs\@opencode-aidesktop\OpenCode.exe`) but no CLI on PATH. See [BO-001 disposition](../decisions/BO-001-runtime-identity.md).

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **platform**; phase **P0**.
- Required predecessor evidence: none; this is the first review task.
- Blockers: Input/runtime gaps are the object of this planning review, not permission to build..
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **Existing application files to modify: none.** New backend/planning files are explicitly proposed below; this is not a claim that those services already exist.

- **PROPOSED new file:** `docs/buyeros/evidence/BO-000-baseline.md`

- **planning input to read (provided provenance snapshot):** `docs/buyeros/inputs/PLANNING_MASTER.supplied.md`
- **planning input to read (provided provenance snapshot):** `docs/buyeros/inputs/FRONTEND_SPEC.earlier-upload.md`

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Check git remote/HEAD/diff and compare the current tree with the pinned audit. Stop on a different repository; preserve all pre-existing changes. Read applicable ancestor and nested instructions; absence of root AGENTS.md at the audited commit is not absence everywhere.

2. Recover 01_CODEX_PLANNING_MASTER_INSTRUCTION.md/references from the original pack if available, or obtain an explicit owner decision to proceed with the two provided master copies plus the separately identified frontend specification. Do not reconstruct unavailable reports or invent their hashes.

3. Record the actual OpenCode executable/version in the implementation environment and current official Plan/Build/permission instructions; if missing, propose installation separately without executing it. Do not invent a model ID or activate configuration.

4. Review package scripts for side effects before proposing any baseline execution. Record inspected definitions separately from results. Refresh browser/source correlation without changing Site access.

5. Write only the baseline document and update blocker dispositions; do not mark any implementation task approved or complete.

## API, schema and state changes

No application API/schema change. Output is an input/source/version decision record.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`source_check = {repository: YNWAforever/BuyerOS, content_baseline_repository: YNWAforever/buyerosgpt, expected_tree: b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1, actual_commit: <observed>, diff: <observed>}`. An observed mismatch transitions baseline review to BLOCKED until reconciled; it never authorizes git reset.

## Failure and concurrency cases

Different source commit is a review stop until differences are assessed, not a request to reset the user's tree. Missing references are not fabricated; missing OpenCode remains an installation blocker.

- Scenario 1: Verify exact repository/project identifiers and clean-versus-dirty state are recorded with command evidence.
- Scenario 2: Every missing reference has recovered provenance or explicit owner waiver; unavailable content remains labelled unavailable.
- Scenario 3: OpenCode version is actual output or NOT INSTALLED; no actionable configuration is invented.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-000-01:** Verify exact repository/project identifiers and clean-versus-dirty state are recorded with command evidence.
- **TEST-BO-000-02:** Every missing reference has recovered provenance or explicit owner waiver; unavailable content remains labelled unavailable.
- **TEST-BO-000-03:** OpenCode version is actual output or NOT INSTALLED; no actionable configuration is invented.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `git rev-parse HEAD` | `repo` | CURRENT_VERIFIED / NOT RUN in task | Record current SHA and compare against audited baseline |
| `git status --short` | `repo` | CURRENT_VERIFIED / NOT RUN in task | Record every pre-existing change |
| `opencode --version` | `repo` | NOT RUN; unavailable in planning environment | Only run if command -v opencode succeeds; capture exact installed version |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Retain the previous plan revision and append a dated baseline correction. No code, configuration, database, or infrastructure changes.

## Effort assumptions

**4–8 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-000 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-000-reconcile-the-exact-source-missing-inputs-and-opencode-baseline.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; planning pack committed at 1512d4c17d4f792e14598d524fdac3c9c37d27e7; a source import of the audited content baseline is still expected, importing tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: A reviewer can identify exactly which checkout, instructions, input set and OpenCode runtime the next task will use, with a written disposition for each missing reference. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

