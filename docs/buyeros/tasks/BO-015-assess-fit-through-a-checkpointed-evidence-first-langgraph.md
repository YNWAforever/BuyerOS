---
task_id: "BO-015"
title: "Assess fit through a checkpointed evidence-first LangGraph"
phase: "P3"
status: "BLOCKED"
priority: "P1"
source_requirements: ["REQ-FIT","REQ-EVIDENCE","REQ-QUEUE"]
depends_on: ["BO-014"]
blocked_by: ["B-PROVIDERS","B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "ai"
files_to_read: ["services/contracts.ts","services/run-engine.ts","features/buyers/detail.tsx","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: []
dependency_output_files_to_modify: ["services/worker/buyeros_worker/tasks.py", "services/worker/pyproject.toml", "services/worker/uv.lock"]
proposed_files_to_create: ["services/worker/buyeros_worker/research/graph.py","services/worker/buyeros_worker/research/fit.py","services/worker/buyeros_worker/research/schemas.py","services/worker/buyeros_worker/research/prompts/fit_v1.md","services/worker/tests/test_fit_graph.py"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["03_DATA_API_AND_STATE_CONTRACTS.md"]
migration_impact: "none; if current source requires an unlisted migration stop and revise task"
external_capabilities: []
external_spend_authorized: false
acceptance_tests: ["TEST-BO-015-01","TEST-BO-015-02","TEST-BO-015-03"]
verification_commands: [{"command":"uv run python -m pytest tests/test_fit_graph.py","working_directory":"services/worker","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"Graph transition, citation, injection and restart tests pass with deterministic providers"}]
rollback_or_rollforward: "Disable fit node version and route pending runs to pause/review; retain immutable prior assessments and checkpoint version compatibility or explicitly fork a new run."
effort_range_hours: [26,44]
---

# BO-015 — Assess fit through a checkpointed evidence-first LangGraph

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

A restartable graph returns profile-specific Match/Needs review/Not a match assessments whose rationale and contradictions trace to evidence, then stops for human acceptance.

## Source requirement and present-state evidence

Source requirements: `REQ-FIT`, `REQ-EVIDENCE`, `REQ-QUEUE`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). Company.fit/why are fixture values and run-engine stages are local; no persisted assessment or graph exists. BuyerDetail's current fit/unknown/contrary visual hierarchy should consume real structured evidence.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **ai**; phase **P3**.
- Required predecessor evidence: `BO-014`.
- Blockers: `B-PROVIDERS`, `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **Existing application files to modify: none.** New backend/planning files are explicitly proposed below; this is not a claim that those services already exist.

- **PROPOSED new file:** `services/worker/buyeros_worker/research/graph.py`
- **PROPOSED new file:** `services/worker/buyeros_worker/research/fit.py`
- **PROPOSED new file:** `services/worker/buyeros_worker/research/schemas.py`
- **PROPOSED new file:** `services/worker/buyeros_worker/research/prompts/fit_v1.md`
- **PROPOSED new file:** `services/worker/tests/test_fit_graph.py`

**PROPOSED predecessor outputs to modify after their creating task completes** (not existing at the audited commit):

- `services/worker/buyeros_worker/tasks.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/worker/pyproject.toml` — inspect producer-task result first; modify only this task's required wiring.
- `services/worker/uv.lock` — inspect producer-task result first; modify only this task's required wiring.

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Build bounded graph nodes validate/load approved ICP→queries→discover→canonicalize→fetch evidence→hard exclusions→structured fit→verify citations→persist assessment→await human review.

2. Key checkpoints by tenant/project/run/profile version; Postgres checkpoint store is resumability only, domain rows/ledger/outbox remain authoritative. Allocate checkpoint schema under documented sole ownership strategy.

3. Apply deterministic hard exclusions before LLM calls; fit output schema includes supported requirements, contrary evidence, unknowns, cited IDs, short rationale and next action without private chain-of-thought.

4. Validate all referenced evidence against allowed input set and stale/retention/version constraints; unsupported assertions downgrade/reject rather than fabricate. Separate translated text from original evidence.

5. Use approved model route/prompt versions and budget reservation per call; bounded retries/escalation. Research graph has no edge to contact lookup, sending or acceptance.

6. Checkpoint after durable accepted node output; cancellation/pause is checked between bounded nodes and before provider dispatch. Resume cannot duplicate assessment version or cost.

## API, schema and state changes

FitAssessment immutable per project-buyer/ICP/evidence set; independent ai_fit and human_review dimensions. Graph terminal state awaiting review produces committed run/buyer events.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`fit = {verdict: Needs review, supported_evidence_ids:[e1], contradictory_evidence_ids:[e2], unknowns:[purchasing_authority]}` is distinct from `human_review=awaiting_review`; the graph stops without contact lookup.

## Failure and concurrency cases

LLM schema failure, contradictory must-have, missing evidence, injected content and worker restarts yield inspectable needs_review/partial/failure. No inference of buying intent from fit.

- Scenario 1: Every important fit claim uses an allowed source ID; contradictory evidence cannot be hidden by positive rationale.
- Scenario 2: Crash between checkpoint and business persistence recovers without duplicate assessment/cost.
- Scenario 3: Graph never emits contact/send/auto-accept action and stops on hard exclusions or budget limits.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-015-01:** Every important fit claim uses an allowed source ID; contradictory evidence cannot be hidden by positive rationale.
- **TEST-BO-015-02:** Crash between checkpoint and business persistence recovers without duplicate assessment/cost.
- **TEST-BO-015-03:** Graph never emits contact/send/auto-accept action and stops on hard exclusions or budget limits.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `uv run python -m pytest tests/test_fit_graph.py` | `services/worker` | PROPOSED_AFTER_TASK / NOT RUN | Graph transition, citation, injection and restart tests pass with deterministic providers |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Disable fit node version and route pending runs to pause/review; retain immutable prior assessments and checkpoint version compatibility or explicitly fork a new run.

## Effort assumptions

**26–44 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-015 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-015-assess-fit-through-a-checkpointed-evidence-first-langgraph.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; currently empty until the exact audited import lands, expected tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: A restartable graph returns profile-specific Match/Needs review/Not a match assessments whose rationale and contradictions trace to evidence, then stops for human acceptance. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

