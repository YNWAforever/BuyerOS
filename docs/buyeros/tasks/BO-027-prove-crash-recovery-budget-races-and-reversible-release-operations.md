---
task_id: "BO-027"
title: "Prove crash recovery, budget races and reversible release operations"
phase: "P6"
status: "BLOCKED"
priority: "P1"
source_requirements: ["REQ-RECOVERY","REQ-BUDGET","REQ-QUEUE","REQ-SECURITY"]
depends_on: ["BO-010","BO-011","BO-016","BO-018","BO-019","BO-020","BO-022","BO-026"]
blocked_by: ["B-HOST","B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "qa"
files_to_read: ["scripts/build-verified.sh","scripts/run-framework.mjs","package.json","tests/domain-checks.mjs","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: []
dependency_output_files_to_modify: ["services/api/pyproject.toml", "services/api/uv.lock", "services/worker/pyproject.toml", "services/worker/uv.lock"]
proposed_files_to_create: ["tests/integration/test_buyeros_failure_matrix.py","tests/integration/test_backup_restore.py","docs/buyeros/operations/recovery-runbook.md","docs/buyeros/evidence/BO-027-recovery-results.md"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["05_TEST_SECURITY_AND_RELEASE.md","03_DATA_API_AND_STATE_CONTRACTS.md"]
migration_impact: "none; if current source requires an unlisted migration stop and revise task"
external_capabilities: []
external_spend_authorized: false
acceptance_tests: ["TEST-BO-027-01","TEST-BO-027-02","TEST-BO-027-03"]
verification_commands: [{"command":"uv run --project services/api python -m pytest tests/integration/test_buyeros_failure_matrix.py tests/integration/test_backup_restore.py","working_directory":"repo","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"All fault-injection, conservation and restore gates pass against verified disposable services; test harness must add worker import paths explicitly"}]
rollback_or_rollforward: "Tear down only explicitly disposable test services. For failures keep live activation blocked and issue narrow repair tasks with preserved evidence."
effort_range_hours: [24,40]
---

# BO-027 — Prove crash recovery, budget races and reversible release operations

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

A disposable full stack survives defined crash windows, reconciles money exactly and can restore data/schema without enabling sending or leaking tenants.

## Source requirement and present-state evidence

Source requirements: `REQ-RECOVERY`, `REQ-BUDGET`, `REQ-QUEUE`, `REQ-SECURITY`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). Existing domain-checks tests deterministic local quote/run behavior; those tests cannot demonstrate PostgreSQL races, durable queue delivery, external uncertainty or backup restore.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **qa**; phase **P6**.
- Required predecessor evidence: `BO-010`, `BO-011`, `BO-016`, `BO-018`, `BO-019`, `BO-020`, `BO-022`, `BO-026`.
- Blockers: `B-HOST`, `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **Existing application files to modify: none.** New backend/planning files are explicitly proposed below; this is not a claim that those services already exist.

- **PROPOSED new file:** `tests/integration/test_buyeros_failure_matrix.py`
- **PROPOSED new file:** `tests/integration/test_backup_restore.py`
- **PROPOSED new file:** `docs/buyeros/operations/recovery-runbook.md`
- **PROPOSED new file:** `docs/buyeros/evidence/BO-027-recovery-results.md`

**PROPOSED predecessor outputs to modify after their creating task completes** (not existing at the audited commit):

- `services/api/pyproject.toml` — inspect producer-task result first; modify only this task's required wiring.
- `services/api/uv.lock` — inspect producer-task result first; modify only this task's required wiring.
- `services/worker/pyproject.toml` — inspect producer-task result first; modify only this task's required wiring.
- `services/worker/uv.lock` — inspect producer-task result first; modify only this task's required wiring.

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Create isolated test environment with local PostgreSQL/Valkey/private storage substitute and deterministic provider fixtures; assert no production URL/paid credential before test start.

2. Inject crashes before/after DB commit, outbox publish, provider acceptance, checkpoint write, contact result settlement and approval commit; assert eventual inspectable state, no lost jobs and no duplicate billable effect.

3. Run real multi-connection reserve/confirm/edit/approve/cancel races, webhook duplicates/out-of-order, tenant-pool reuse and expired quote tests. SQLite/unit mocks are insufficient for these gates.

4. Test backward-compatible migration upgrades and roll-forward repairs on seeded disposable data; backup/restore into separate local target, then replay deletion tombstones and confirm role isolation.

5. Measure proposed queue age/unknown reservation/SSE gap metrics and pause/kill-switch behavior; alert examples contain no personal data.

6. Document exact commands/env target/output/reproduction seed and ownership; failures create task revisions rather than weakened assertions. No cloud deployment occurs from this test task.

## API, schema and state changes

No new product API; exercises approved state contracts end to end. Any discovered schema/API incompatibility requires ADR/task revision before implementation repair.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`crash after provider acceptance before local acknowledgment` is an explicit fault-injection point. The recovered ledger has one financial operation, retained unknown reservation and no second blind dispatch.

## Failure and concurrency cases

Provider accepted-then-crash remains reserved/unknown until reconcile; queue loss is recoverable from outbox; restored deleted data cannot be exposed. Rollback never re-enables obsolete approval semantics.

- Scenario 1: Failure matrix completes with conserved ledger and one external effect per verified provider operation key.
- Scenario 2: Backup restore plus tombstone replay recovers authorized data and excludes deleted/contact-prohibited data.
- Scenario 3: All paid dispatch stops on kill switch; existing pending reconciliation remains visible and safe.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-027-01:** Failure matrix completes with conserved ledger and one external effect per verified provider operation key.
- **TEST-BO-027-02:** Backup restore plus tombstone replay recovers authorized data and excludes deleted/contact-prohibited data.
- **TEST-BO-027-03:** All paid dispatch stops on kill switch; existing pending reconciliation remains visible and safe.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `uv run --project services/api python -m pytest tests/integration/test_buyeros_failure_matrix.py tests/integration/test_backup_restore.py` | `repo` | PROPOSED_AFTER_TASK / NOT RUN | All fault-injection, conservation and restore gates pass against verified disposable services; test harness must add worker import paths explicitly |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Tear down only explicitly disposable test services. For failures keep live activation blocked and issue narrow repair tasks with preserved evidence.

## Effort assumptions

**24–40 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-027 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-027-prove-crash-recovery-budget-races-and-reversible-release-operations.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; currently empty until the exact audited import lands, expected tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: A disposable full stack survives defined crash windows, reconciles money exactly and can restore data/schema without enabling sending or leaking tenants. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

