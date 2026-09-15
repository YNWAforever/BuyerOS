---
task_id: "BO-005"
title: "Create tenant-safe domain persistence and one migration owner"
phase: "P1"
status: "BLOCKED"
priority: "P0"
source_requirements: ["REQ-DATA","REQ-TENANT"]
depends_on: ["BO-003","BO-004"]
blocked_by: ["B-HOST","B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "backend"
files_to_read: ["db/schema.ts","db/index.ts","drizzle.config.ts","drizzle/meta/_journal.json","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: []
dependency_output_files_to_modify: ["services/api/buyeros_api/main.py", "services/api/buyeros_api/auth.py"]
proposed_files_to_create: ["services/api/buyeros_api/db.py","services/api/buyeros_api/models/core.py","services/api/alembic.ini","services/api/alembic/env.py","services/api/alembic/versions/0001_core.py","services/api/tests/test_tenant_constraints.py"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["03_DATA_API_AND_STATE_CONTRACTS.md"]
migration_impact: "PROPOSED additive migration; serialize through sole Alembic owner; execution only on approved disposable/staging DB"
external_capabilities: ["Approved managed OIDC and PostgreSQL design; use isolated fixtures until authorized"]
external_spend_authorized: false
acceptance_tests: ["TEST-BO-005-01","TEST-BO-005-02","TEST-BO-005-03"]
verification_commands: [{"command":"uv run python -m pytest tests/test_tenant_constraints.py","working_directory":"services/api","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"Local PostgreSQL constraints and role/pool tests pass; abort if database target is not disposable"}]
rollback_or_rollforward: "Pre-live initial migration can be discarded with disposable DB. After persisted pilot data, use forward repair migrations and tested backup restore; never destructive downgrade by default."
effort_range_hours: [24,40]
---

# BO-005 — Create tenant-safe domain persistence and one migration owner

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

A disposable local PostgreSQL instance stores workspace/project/company/buyer/profile/list records with constraints that prevent cross-tenant relationships under API and worker roles.

## Source requirement and present-state evidence

Source requirements: `REQ-DATA`, `REQ-TENANT`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). db/schema.ts is empty and Drizzle's journal has no BuyerOS migration. The starter SQLite scaffold is not a live database or a reason for dual Drizzle/Alembic ownership.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **backend**; phase **P1**.
- Required predecessor evidence: `BO-003`, `BO-004`.
- Blockers: `B-HOST`, `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **Existing application files to modify: none.** New backend/planning files are explicitly proposed below; this is not a claim that those services already exist.

- **PROPOSED new file:** `services/api/buyeros_api/db.py`
- **PROPOSED new file:** `services/api/buyeros_api/models/core.py`
- **PROPOSED new file:** `services/api/alembic.ini`
- **PROPOSED new file:** `services/api/alembic/env.py`
- **PROPOSED new file:** `services/api/alembic/versions/0001_core.py`
- **PROPOSED new file:** `services/api/tests/test_tenant_constraints.py`

**PROPOSED predecessor outputs to modify after their creating task completes** (not existing at the audited commit):

- `services/api/buyeros_api/main.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/api/buyeros_api/auth.py` — inspect producer-task result first; modify only this task's required wiring.

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Implement SQLAlchemy core models and one initial Alembic domain migration following 03. Use workspace-local companies, composite tenant foreign keys, server timestamps, row version counters and immutable versioned ICPs.

2. Introduce memberships, project buyers separate from canonical companies, reviews/lists and audit foundations; later tasks own their migrations serially. Do not put fit only on Company or equate people with buyers.

3. Use dedicated migration-owner, API and worker roles with least privilege. If RLS is used, FORCE policies where appropriate and test non-bypass roles; server tenant checks remain required.

4. Bind tenant context transaction-locally and test pool reuse/reset. Use configured connection pooling and bounded connection counts for API and workers.

5. Run upgrade/constraint/downgrade checks only on an explicitly disposable local database after Build approval. Never run the scaffold db:generate against domain tables or touch an existing production DB.

**Additional exact integration step:** Include user/workspace preference storage and tenant-scoped filter-preset entity/constraints required by the proposed contract in the initial core schema; BO-008/025 later wire their operations. Bind the auth membership repository to real PostgreSQL by updating BO-004 main.py/auth.py, with denial if storage is unavailable.

**Additional authority/concurrency step:** The initial core model includes proposed project-owned sender_identity_versions with immutable version_key, normalized identity/content hash, approval actor/time, active/revoked state and tenant/project foreign keys. This is reviewed sender configuration only, not a connected mailbox or permission to deliver.

**Additional schema/route integration:** Create offer_documents/source-document metadata needed by BO-012 in the core schema; BO-014 extends the evidence/assessment structures via its serial migration. Every domain table remains under Alembic, including table names first introduced by later slices.

## API, schema and state changes

Schema ownership only; version-precondition/error mapping for unique/FK conflicts. Migration impact: new local-only schema pending approval, no data import.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`project_buyers(workspace_id=ws_a, company_id=company_from_ws_b)` fails its composite foreign key; a new tenant-local company relation is required.

## Failure and concurrency cases

Migration role accidentally used by API, missing tenant context, pool state leakage or composite FK omission blocks release. Do not auto-merge unrelated same-domain companies.

- Scenario 1: Cross-workspace foreign keys and duplicate membership insertions fail at DB level.
- Scenario 2: API/worker roles cannot migrate or bypass authorized tenant isolation.
- Scenario 3: Pool sequence tenant A→B→unset cannot leak rows; initial migration round trip succeeds on disposable DB.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-005-01:** Cross-workspace foreign keys and duplicate membership insertions fail at DB level.
- **TEST-BO-005-02:** API/worker roles cannot migrate or bypass authorized tenant isolation.
- **TEST-BO-005-03:** Pool sequence tenant A→B→unset cannot leak rows; initial migration round trip succeeds on disposable DB.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `uv run python -m pytest tests/test_tenant_constraints.py` | `services/api` | PROPOSED_AFTER_TASK / NOT RUN | Local PostgreSQL constraints and role/pool tests pass; abort if database target is not disposable |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Pre-live initial migration can be discarded with disposable DB. After persisted pilot data, use forward repair migrations and tested backup restore; never destructive downgrade by default.

## Effort assumptions

**24–40 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-005 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-005-create-tenant-safe-domain-persistence-and-one-migration-owner.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; currently empty until the exact audited import lands, expected tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: A disposable local PostgreSQL instance stores workspace/project/company/buyer/profile/list records with constraints that prevent cross-tenant relationships under API and worker roles. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

