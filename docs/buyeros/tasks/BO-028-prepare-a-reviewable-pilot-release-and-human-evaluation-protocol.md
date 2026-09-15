---
task_id: "BO-028"
title: "Prepare a reviewable pilot release and human evaluation protocol"
phase: "P6"
status: "BLOCKED"
priority: "P1"
source_requirements: ["REQ-PILOT","REQ-USAGE","REQ-SECURITY"]
depends_on: ["BO-024","BO-025","BO-026","BO-027"]
blocked_by: ["B-PILOT","B-POLICY","B-HOST","B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "qa"
files_to_read: ["DEVELOPER_HANDOFF.md","package.json","scripts/build-verified.sh","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: []
dependency_output_files_to_modify: []
proposed_files_to_create: ["docs/buyeros/pilot/evaluation-protocol.md","docs/buyeros/pilot/release-candidate.md","docs/buyeros/pilot/approval-request.md"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["05_TEST_SECURITY_AND_RELEASE.md","04_PHASED_IMPLEMENTATION_PLAN.md"]
migration_impact: "none; if current source requires an unlisted migration stop and revise task"
external_capabilities: []
external_spend_authorized: false
acceptance_tests: ["TEST-BO-028-01","TEST-BO-028-02","TEST-BO-028-03"]
verification_commands: []
rollback_or_rollforward: "Revise/reject release candidate; no external effects. Keep current Site and production access unchanged."
effort_range_hours: [16,28]
---

# BO-028 — Prepare a reviewable pilot release and human evaluation protocol

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

The owner can approve a specific bounded research/contact/draft pilot with named users, countries, budgets, provider operations, readiness evidence and stop criteria.

## Source requirement and present-state evidence

Source requirements: `REQ-PILOT`, `REQ-USAGE`, `REQ-SECURITY`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). Source fixtures demonstrate interface semantics only; they cannot establish real-company precision, current provider pricing, tenant security or delivery readiness.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **qa**; phase **P6**.
- Required predecessor evidence: `BO-024`, `BO-025`, `BO-026`, `BO-027`.
- Blockers: `B-PILOT`, `B-POLICY`, `B-HOST`, `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **Existing application files to modify: none.** New backend/planning files are explicitly proposed below; this is not a claim that those services already exist.

- **PROPOSED new file:** `docs/buyeros/pilot/evaluation-protocol.md`
- **PROPOSED new file:** `docs/buyeros/pilot/release-candidate.md`
- **PROPOSED new file:** `docs/buyeros/pilot/approval-request.md`

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Assemble requirement/action/test traceability with exact commit/artifact hashes and executed results; list unavailable checks NOT RUN. No implementation task is done merely because a document exists.

2. Define human-labelled authorized company sample and independent labels for fit/evidence/acceptance/contact validity/policy. Prevent dataset leakage into prompt tuning/evaluation splits.

3. Propose initial sample size, labelled quality targets and calibration procedure for acceptance precision/evidence support/reviewer agreement/contact yield/review time/spend per accepted distinct company. Targets remain proposed until owner approval.

4. Set pilot workspace/users/regions/provider credentials owner, total/category/run caps, per-operation limits, permitted dates/purposes/retention and data-sharing constraints; record actual verified price versions separately from estimates.

5. Prepare explicit release/rollback checklist and no-send/no-mailbox invariant. Include infrastructure target and deployment plan as proposal; no creation/publication in this task.

6. Request BO-029 approval against this concrete release candidate, stating exact external writes and maximum paid operations. Missing gate keeps readiness blocked; optional contact capability can remain off without silently claiming it was tested.

## API, schema and state changes

No code/API change. Release decision distinguishes discovery-only readiness from contact/draft readiness and delivery disabled.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`pilot approval request = {release_commit, workspace, users, regions, dates, provider_caps, total_budget, retention, stop_conditions}` must be concrete; a NOT RUN critical gate keeps the corresponding capability disabled.

## Failure and concurrency cases

Insufficient evidence/quality, unknown cost/reconciliation, missing identity/region policy or NOT RUN critical checks block corresponding capability; no lowering target after seeing results without revision.

- Scenario 1: Each release gate names owner/evidence/failure action/rollback and links passing relevant task tests.
- Scenario 2: Proposed pilot spend and data scopes are explicit, finite and approved or blocked.
- Scenario 3: Evaluation distinguishes fixture UI regression from human-labelled real-company outcomes and never treats fit as purchase probability.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-028-01:** Each release gate names owner/evidence/failure action/rollback and links passing relevant task tests.
- **TEST-BO-028-02:** Proposed pilot spend and data scopes are explicit, finite and approved or blocked.
- **TEST-BO-028-03:** Evaluation distinguishes fixture UI regression from human-labelled real-company outcomes and never treats fit as purchase probability.

This is a documentation/approval or environment-dependent operations task: no executable product verification command is asserted. Perform the named document/evidence acceptance checks; any future operational command must be recorded against the approved environment before execution. **Product checks: NOT RUN.**

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Revise/reject release candidate; no external effects. Keep current Site and production access unchanged.

## Effort assumptions

**16–28 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-028 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-028-prepare-a-reviewable-pilot-release-and-human-evaluation-protocol.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; planning pack committed at 1512d4c17d4f792e14598d524fdac3c9c37d27e7; a source import of the audited content baseline is still expected, importing tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: The owner can approve a specific bounded research/contact/draft pilot with named users, countries, budgets, provider operations, readiness evidence and stop criteria. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

