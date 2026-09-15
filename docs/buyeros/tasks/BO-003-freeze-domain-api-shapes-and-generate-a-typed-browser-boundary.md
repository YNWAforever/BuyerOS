---
task_id: "BO-003"
title: "Freeze domain API shapes and generate a typed browser boundary"
phase: "P1"
status: "BLOCKED"
priority: "P0"
source_requirements: ["REQ-CONTRACT","REQ-DEMO"]
depends_on: ["BO-001","BO-002"]
blocked_by: ["B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "backend"
files_to_read: ["services/contracts.ts","services/http-client.ts","features/workspace.tsx","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/02_ARCHITECTURE_AND_REUSE.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md","docs/buyeros/contracts/openapi.proposed.yaml"]
existing_files_to_modify: ["services/contracts.ts"]
dependency_output_files_to_modify: []
proposed_files_to_create: ["services/api/pyproject.toml","services/api/buyeros_api/contracts/__init__.py","services/api/tests/test_openapi_contract.py","services/generated/buyeros-api.ts","services/live/mapping.ts","tests/contracts/live-mapping.test.ts","services/api/uv.lock"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["contracts/openapi.proposed.yaml","03_DATA_API_AND_STATE_CONTRACTS.md"]
migration_impact: "none; if current source requires an unlisted migration stop and revise task"
external_capabilities: []
external_spend_authorized: false
acceptance_tests: ["TEST-BO-003-01","TEST-BO-003-02","TEST-BO-003-03"]
verification_commands: [{"command":"uv run python -m pytest tests/test_openapi_contract.py","working_directory":"services/api","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"All schema/example/operation uniqueness cases pass"}]
rollback_or_rollforward: "Keep generated artifacts versioned; roll forward by compatible contract revision. Do not silently weaken required guards."
effort_range_hours: [14,24]
---

# BO-003 — Freeze domain API shapes and generate a typed browser boundary

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

The agreed OpenAPI validates and generated browser types distinguish live account/person/evidence/policy dimensions without breaking the existing demo contract.

## Source requirement and present-state evidence

Source requirements: `REQ-CONTRACT`, `REQ-DEMO`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). services/contracts.ts contains demo-only RecordBase.dataMode, conflated Company fit/review/contact fields and a BuyerDiscoveryClient proposal; it is not a wire contract. Existing HTTP module does not implement network methods.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **backend**; phase **P1**.
- Required predecessor evidence: `BO-001`, `BO-002`.
- Blockers: `B-APPROVAL`.
- **Ordering:** the provider-operation adapter shapes BO-002 must pin (one search, one approved LLM route per task, optional business-email) constrain this freeze; do not pre-empt or invent them. BO-003 stays BLOCKED until BO-001 and BO-002 have recorded completion evidence.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **EXISTING, inspected:** `services/contracts.ts`

- **PROPOSED new file:** `services/api/pyproject.toml`
- **PROPOSED new file:** `services/api/buyeros_api/contracts/__init__.py`
- **PROPOSED new file:** `services/api/tests/test_openapi_contract.py`
- **PROPOSED new file:** `services/generated/buyeros-api.ts`
- **PROPOSED new file:** `services/live/mapping.ts`
- **PROPOSED new file:** `tests/contracts/live-mapping.test.ts`
- **PROPOSED new file:** `services/api/uv.lock`

`services/live/` and `tests/contracts/` are additional PROPOSED locations under the 02 directory plan; no JS test runner exists in the current repo, so `tests/contracts/live-mapping.test.ts` requires a pinned runner decision (see step 4). `uv` availability is unverified, so the Python commands remain PROPOSED_AFTER_TASK.

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Review contracts/openapi.proposed.yaml and 03 for paths, snake_case wire names, error envelope, money strings, version fields, tenant paths, async responses and idempotency. Resolve mismatches in the contract before implementing endpoints.

2. Introduce a generated live contract file and explicit mapping module; retain compatibility with existing demo Store/types. Do not rewrite the entire UI to match upstream campaign/lead terminology.

3. Define immutable ICP/assessment/revision DTOs, separate contact validity/suppression/research policy/outreach policy and approval/delivery dimensions.

4. Set up a pinned uv Python packaging/test project for Pydantic/FastAPI schemas after reviewing dependency/license effects. Verify `uv` is actually installed before any `uv run`; `services/api/pyproject.toml` and `uv.lock` are PROPOSED task outputs and must not be created against production credentials. Keep pnpm as the existing JS manager. Separately pin a JS test runner (none exists today) for `tests/contracts/live-mapping.test.ts`, or route the check through the existing node test harness; record the chosen tool and version before generating artifacts.

5. Add schema/fixture round-trip and error-code checks; require no paid providers. Record generation command and tool version only after selection.

**Additional exact integration step:** Proposed package name is buyeros-api, with import package buyeros_api. The separate worker uv project must depend on this one domain package by local path ../api; do not duplicate SQLAlchemy models, authorization, budget or policy rules in worker-owned models.

## API, schema and state changes

Freeze /v1/workspaces/{workspace_id} contract; response snake_case maps to existing camelCase view props. Every async POST returns durable identity and request ID.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`Money.amount = "0.300000"` with `currency = "USD"` is a wire decimal string. `data_mode = "demo"` must not deserialize into a live response adapter.

## Failure and concurrency cases

Unknown enum values and missing required provenance must fail visibly. A contract mapping failure cannot substitute demo rows. Concurrent contract edits are serialized under backend owner.

- Scenario 1: Invalid currency floats, missing workspace provenance and overloaded contact/suppression fields fail schema validation.
- Scenario 2: All operationIds are unique and documented request examples validate.
- Scenario 3: Legacy demo regressions remain valid and live mapping rejects data_mode=demo.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-003-01:** Invalid currency floats, missing workspace provenance and overloaded contact/suppression fields fail schema validation.
- **TEST-BO-003-02:** All operationIds are unique and documented request examples validate.
- **TEST-BO-003-03:** Legacy demo regressions remain valid and live mapping rejects data_mode=demo.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `uv run python -m pytest tests/test_openapi_contract.py` | `services/api` | PROPOSED_AFTER_TASK / NOT RUN | All schema/example/operation uniqueness cases pass |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Keep generated artifacts versioned; roll forward by compatible contract revision. Do not silently weaken required guards.

## Effort assumptions

**14–24 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-003 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-003-freeze-domain-api-shapes-and-generate-a-typed-browser-boundary.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; planning pack committed at 1512d4c17d4f792e14598d524fdac3c9c37d27e7; a source import of the audited content baseline is still expected, importing tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: The agreed OpenAPI validates and generated browser types distinguish live account/person/evidence/policy dimensions without breaking the existing demo contract. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

