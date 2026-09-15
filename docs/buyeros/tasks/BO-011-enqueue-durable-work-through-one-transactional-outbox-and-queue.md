---
task_id: "BO-011"
title: "Enqueue durable work through one transactional outbox and queue"
phase: "P2"
status: "BLOCKED"
priority: "P0"
source_requirements: ["REQ-QUEUE","REQ-RECOVERY","REQ-TENANT"]
depends_on: ["BO-005","BO-010"]
blocked_by: ["B-HOST","B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "platform"
files_to_read: ["services/run-engine.ts","features/workspace.tsx","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: []
dependency_output_files_to_modify: ["services/api/pyproject.toml", "services/api/uv.lock", "services/api/buyeros_api/main.py", "services/api/buyeros_api/services/policy.py"]
proposed_files_to_create: ["services/api/buyeros_api/services/outbox.py", "services/api/alembic/versions/0004_outbox.py", "services/worker/pyproject.toml", "services/worker/buyeros_worker/celery_app.py", "services/worker/buyeros_worker/tasks.py", "services/worker/tests/test_outbox_recovery.py", "services/worker/uv.lock", "services/api/buyeros_api/routes/async_jobs.py"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["03_DATA_API_AND_STATE_CONTRACTS.md"]
migration_impact: "PROPOSED additive migration; serialize through sole Alembic owner; execution only on approved disposable/staging DB"
external_capabilities: ["Approved managed OIDC and PostgreSQL design; use isolated fixtures until authorized"]
external_spend_authorized: false
acceptance_tests: ["TEST-BO-011-01","TEST-BO-011-02","TEST-BO-011-03"]
verification_commands: [{"command":"uv run python -m pytest tests/test_outbox_recovery.py","working_directory":"services/worker","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"Local PostgreSQL/Valkey failure-injection tests pass with no external providers"}]
rollback_or_rollforward: "Pause dispatcher/workers, retain outbox and leases, deploy compatible consumer or replay only idempotent jobs. Never purge pending financial operations."
effort_range_hours: [22,36]
---

# BO-011 — Enqueue durable work through one transactional outbox and queue

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

A committed 202 job survives process/queue restart and executes at least once without duplicate business effects or losing tenant context.

## Source requirement and present-state evidence

Source requirements: `REQ-QUEUE`, `REQ-RECOVERY`, `REQ-TENANT`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). Workspace's 700ms timer calls advanceRun locally. There is no durable queue or server worker; simulated event IDs only deduplicate in-memory demo charges.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **platform**; phase **P2**.
- Required predecessor evidence: `BO-005`, `BO-010`.
- Blockers: `B-HOST`, `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **Existing application files to modify: none.** New backend/planning files are explicitly proposed below; this is not a claim that those services already exist.

- **PROPOSED new file:** `services/api/buyeros_api/services/outbox.py`
- **PROPOSED new file:** `services/api/alembic/versions/0004_outbox.py`
- **PROPOSED new file:** `services/worker/pyproject.toml`
- **PROPOSED new file:** `services/worker/buyeros_worker/celery_app.py`
- **PROPOSED new file:** `services/worker/buyeros_worker/tasks.py`
- **PROPOSED new file:** `services/worker/tests/test_outbox_recovery.py`
- **PROPOSED new file:** `services/worker/uv.lock`

**PROPOSED predecessor outputs to modify after their creating task completes** (not existing at the audited commit):

- `services/api/pyproject.toml` — inspect producer-task result first; modify only this task's required wiring.
- `services/api/uv.lock` — inspect producer-task result first; modify only this task's required wiring.

- **PROPOSED new file:** `services/api/buyeros_api/routes/async_jobs.py`

- **PROPOSED predecessor output to modify:** `services/api/buyeros_api/main.py`
- **PROPOSED predecessor output to modify:** `services/api/buyeros_api/services/policy.py`

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Add outbox rows atomically in same PostgreSQL transaction as job creation/reservation; API returns 202 only after durable commit.

2. Use one Celery+Valkey queue for API-originated jobs, with explicit routing/leases/retry policy but no competing secondary scheduler. Outbox dispatcher leases rows with lock/skip-locked semantics and retries publish safely.

3. Workers load tenant/job from authoritative DB, verify allowed transition and lease generation, and use idempotent business operation keys. Reject missing or mismatched workspace context.

4. Acknowledge work only after durable business/checkpoint progress; late/duplicate Celery deliveries are expected. Keep LangGraph checkpoints separate from job/ledger truth.

5. Add job-heartbeat/orphan recovery and bounded backoff with jitter; classify permanent validation/policy errors versus retryable transport errors. Provider side effects require BO-019 uncertainty handling, not generic auto retry.

6. Propose worker/api deployment process and graceful shutdown probes only; no cloud resource creation in this task unless separately authorized.

**Additional exact integration step:** Register getAsyncJob and wire policy invalidation events to the transactional outbox through the predecessor policy service. The proposed worker uv package depends on ../api's buyeros-api domain package; workers reuse its authoritative models/services rather than creating another schema owner.

## API, schema and state changes

202 durable job identity; run/enrichment/draft jobs use shared outbox. Additive outbox/lease schema, no domain duplicate backend.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`job queued + outbox inserted` commit together. Crash before publish leaves a recoverable outbox row; duplicate publish yields the same operation ID and no duplicate business effect.

## Failure and concurrency cases

Crash before commit yields no job; after commit before publish is recovered; after publish before mark-published may deliver twice. Queue outage does not fabricate progress or erase accepted jobs.

- Scenario 1: Kill API after commit before publish; job is later delivered once in effect.
- Scenario 2: Duplicate publish and worker crash preserve a single business transition and cost reservation.
- Scenario 3: Cross-tenant job payload tampering is rejected; exhausted retry becomes inspectable failed/unknown state.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-011-01:** Kill API after commit before publish; job is later delivered once in effect.
- **TEST-BO-011-02:** Duplicate publish and worker crash preserve a single business transition and cost reservation.
- **TEST-BO-011-03:** Cross-tenant job payload tampering is rejected; exhausted retry becomes inspectable failed/unknown state.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `uv run python -m pytest tests/test_outbox_recovery.py` | `services/worker` | PROPOSED_AFTER_TASK / NOT RUN | Local PostgreSQL/Valkey failure-injection tests pass with no external providers |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Pause dispatcher/workers, retain outbox and leases, deploy compatible consumer or replay only idempotent jobs. Never purge pending financial operations.

## Effort assumptions

**22–36 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-011 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-011-enqueue-durable-work-through-one-transactional-outbox-and-queue.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; the audited source is imported at commit b804ba8d1514a1049b7202c861278dd72c473a75 (tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), merged into main via 72fef7da785624a35bb6701f1451ebcf0184a089), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: A committed 202 job survives process/queue restart and executes at least once without duplicate business effects or losing tenant context. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

