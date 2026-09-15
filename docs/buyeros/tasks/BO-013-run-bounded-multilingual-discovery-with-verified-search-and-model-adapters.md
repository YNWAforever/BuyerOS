---
task_id: "BO-013"
title: "Run bounded multilingual discovery with verified search and model adapters"
phase: "P3"
status: "BLOCKED"
priority: "P1"
source_requirements: ["REQ-DISCOVERY","REQ-BUDGET","REQ-REUSE"]
depends_on: ["BO-002","BO-010","BO-011","BO-012"]
blocked_by: ["B-PROVIDERS","B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "ai"
files_to_read: ["features/discovery/wizard.tsx","services/run-engine.ts","data/demo/fixtures.ts","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: []
dependency_output_files_to_modify: ["services/worker/buyeros_worker/tasks.py", "services/worker/buyeros_worker/celery_app.py"]
proposed_files_to_create: ["services/worker/buyeros_worker/providers/search.py","services/worker/buyeros_worker/providers/llm.py","services/worker/buyeros_worker/research/queries.py","services/worker/buyeros_worker/research/discover.py","services/worker/tests/test_bounded_discovery.py"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["03_DATA_API_AND_STATE_CONTRACTS.md","02_ARCHITECTURE_AND_REUSE.md"]
migration_impact: "none; if current source requires an unlisted migration stop and revise task"
external_capabilities: ["Verified provider contracts and deterministic fixtures; no live calls authorized"]
external_spend_authorized: false
acceptance_tests: ["TEST-BO-013-01","TEST-BO-013-02","TEST-BO-013-03"]
verification_commands: [{"command":"uv run python -m pytest tests/test_bounded_discovery.py","working_directory":"services/worker","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"Synthetic search/LLM fixtures obey every cap and failure path"}]
rollback_or_rollforward: "Disable discovery capability/provider route, preserve already collected permitted candidates and ledger. Revert adapter code with compatible provider-operation records."
effort_range_hours: [24,40]
---

# BO-013 — Run bounded multilingual discovery with verified search and model adapters

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

An approved ICP produces bounded local-language search queries and raw company candidates with real source references while every billable step is budget-authorized.

## Source requirement and present-state evidence

Source requirements: `REQ-DISCOVERY`, `REQ-BUDGET`, `REQ-REUSE`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). Wizard shows static German/Dutch query previews; advanceRun fabricates deterministic fixture stages. No real query generation/search capability exists. Upstream reuse allowed only for pinned symbols approved in BO-002.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **ai**; phase **P3**.
- Required predecessor evidence: `BO-002`, `BO-010`, `BO-011`, `BO-012`.
- Blockers: `B-PROVIDERS`, `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **Existing application files to modify: none.** New backend/planning files are explicitly proposed below; this is not a claim that those services already exist.

- **PROPOSED new file:** `services/worker/buyeros_worker/providers/search.py`
- **PROPOSED new file:** `services/worker/buyeros_worker/providers/llm.py`
- **PROPOSED new file:** `services/worker/buyeros_worker/research/queries.py`
- **PROPOSED new file:** `services/worker/buyeros_worker/research/discover.py`
- **PROPOSED new file:** `services/worker/tests/test_bounded_discovery.py`

**PROPOSED predecessor outputs to modify after their creating task completes** (not existing at the audited commit):

- `services/worker/buyeros_worker/tasks.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/worker/buyeros_worker/celery_app.py` — inspect producer-task result first; modify only this task's required wiring.

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Load immutable approved profile; normalize market/language/type inputs with deterministic rules. For DE/NL/BE include relevant German/Dutch/French/English queries as configured; other countries derive supported strategies or return an explicit unsupported request.

2. Use a versioned schema-constrained query prompt only where necessary; set maximum query count/rounds/results/time/tokens/provider concurrency and fetch budget from approved run limits.

3. Adapt only licensed verified upstream query/search extraction code behind BuyerOS-owned interfaces; replace upstream auth, global config/local files/schedulers and UI. Retain notices.

4. Before each paid search/model call reserve upper bound through BO-010 and persist provider operation; apply conservative uncertainty semantics. Retry only safe idempotent operations with bounded count.

5. Normalize search outputs into raw candidates retaining provider ID/URL/query/market/retrieval/provenance and error details. Do not discover contacts or automatically enrich.

6. Cache permitted normalized query results with tenant-safe scope/TTL and price semantics; return partial/paused_budget/no_results honestly rather than fixture substitution.

## API, schema and state changes

Internal DiscoverCandidates request binds workspace/project/run/icp_version/limits; returns raw candidate IDs + cost references, not final fit or accepted buyers.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`ICP market=[DE,NL,BE], languages=[de,nl,fr,en]` produces a bounded approved query plan. Query count/token/page limits use the concrete RunLimits defaults and maxima in 03; unsupported filters return validation errors.

## Failure and concurrency cases

Provider unavailable, invalid schema, unsupported filter/market, query overflow, budget cap and timeout terminate/pause clearly. No fixed 24-result assumption.

- Scenario 1: Same approved profile fixture yields bounded valid multilingual queries, no fake sample results for custom offer.
- Scenario 2: Provider call counter never exceeds limits; budget exhaustion prevents next paid call.
- Scenario 3: Prompt injection in search text cannot alter tools/provider settings; invalid output does not become a buyer.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-013-01:** Same approved profile fixture yields bounded valid multilingual queries, no fake sample results for custom offer.
- **TEST-BO-013-02:** Provider call counter never exceeds limits; budget exhaustion prevents next paid call.
- **TEST-BO-013-03:** Prompt injection in search text cannot alter tools/provider settings; invalid output does not become a buyer.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `uv run python -m pytest tests/test_bounded_discovery.py` | `services/worker` | PROPOSED_AFTER_TASK / NOT RUN | Synthetic search/LLM fixtures obey every cap and failure path |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Disable discovery capability/provider route, preserve already collected permitted candidates and ledger. Revert adapter code with compatible provider-operation records.

## Effort assumptions

**24–40 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-013 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-013-run-bounded-multilingual-discovery-with-verified-search-and-model-adapters.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; planning pack committed at 1512d4c17d4f792e14598d524fdac3c9c37d27e7; a source import of the audited content baseline is still expected, importing tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: An approved ICP produces bounded local-language search queries and raw company candidates with real source references while every billable step is budget-authorized. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

