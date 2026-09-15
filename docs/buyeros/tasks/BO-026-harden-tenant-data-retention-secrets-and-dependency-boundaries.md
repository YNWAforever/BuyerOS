---
task_id: "BO-026"
title: "Harden tenant data, retention, secrets and dependency boundaries"
phase: "P6"
status: "BLOCKED"
priority: "P1"
source_requirements: ["REQ-SECURITY","REQ-TENANT","REQ-EVIDENCE"]
depends_on: ["BO-012","BO-020","BO-022","BO-023","BO-024","BO-025"]
blocked_by: ["B-POLICY","B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "platform"
files_to_read: ["package.json","pnpm-lock.yaml","app/chatgpt-auth.ts","services/http-client.ts","features/workspace.tsx","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: []
dependency_output_files_to_modify: ["services/api/buyeros_api/main.py", "services/api/buyeros_api/auth.py", "services/api/buyeros_api/services/storage.py", "services/api/buyeros_api/services/approvals.py", "services/worker/buyeros_worker/tasks.py", "services/api/buyeros_api/routes/documents.py"]
proposed_files_to_create: ["services/api/buyeros_api/services/retention.py", "services/worker/buyeros_worker/maintenance/delete_data.py", "services/api/tests/test_security_lifecycle.py", "docs/buyeros/operations/data-lifecycle-runbook.md", "docs/buyeros/operations/dependency-license-inventory.md", "services/api/buyeros_api/routes/audit.py"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["05_TEST_SECURITY_AND_RELEASE.md","03_DATA_API_AND_STATE_CONTRACTS.md"]
migration_impact: "none; if current source requires an unlisted migration stop and revise task"
external_capabilities: ["Approved managed OIDC and PostgreSQL design; use isolated fixtures until authorized"]
external_spend_authorized: false
acceptance_tests: ["TEST-BO-026-01","TEST-BO-026-02","TEST-BO-026-03"]
verification_commands: [{"command":"uv run python -m pytest tests/test_security_lifecycle.py","working_directory":"services/api","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"Tenant matrix, lifecycle and secret-boundary negative tests pass"}]
rollback_or_rollforward: "Fail closed by disabling affected capabilities; quarantine records, rotate affected credentials after separate authorization and replay deletion tombstones after restore. Never disable authorization to restore availability."
effort_range_hours: [24,40]
---

# BO-026 — Harden tenant data, retention, secrets and dependency boundaries

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

Cross-tenant data paths and personal-data lifecycle withstand negative tests, secrets remain server-only, and dependencies/licenses are documented before live data activation.

## Source requirement and present-state evidence

Source requirements: `REQ-SECURITY`, `REQ-TENANT`, `REQ-EVIDENCE`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). Frontend has no live security boundary; current .example/local-only restrictions cannot substitute for server roles/storage lifecycle. No backend security, retention or provider credential handling exists yet.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **platform**; phase **P6**.
- Required predecessor evidence: `BO-012`, `BO-020`, `BO-022`, `BO-023`, `BO-024`, `BO-025`.
- Blockers: `B-POLICY`, `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **Existing application files to modify: none.** New backend/planning files are explicitly proposed below; this is not a claim that those services already exist.

- **PROPOSED new file:** `services/api/buyeros_api/services/retention.py`
- **PROPOSED new file:** `services/worker/buyeros_worker/maintenance/delete_data.py`
- **PROPOSED new file:** `services/api/tests/test_security_lifecycle.py`
- **PROPOSED new file:** `docs/buyeros/operations/data-lifecycle-runbook.md`
- **PROPOSED new file:** `docs/buyeros/operations/dependency-license-inventory.md`

**PROPOSED predecessor outputs to modify after their creating task completes** (not existing at the audited commit):

- `services/api/buyeros_api/main.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/api/buyeros_api/auth.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/api/buyeros_api/services/storage.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/api/buyeros_api/services/approvals.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/worker/buyeros_worker/tasks.py` — inspect producer-task result first; modify only this task's required wiring.

- **PROPOSED new file:** `services/api/buyeros_api/routes/audit.py`

- **PROPOSED predecessor output to modify:** `services/api/buyeros_api/routes/documents.py`

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Run systematic tenant/RBAC tests across reads/writes/events/files/exports/jobs with API/worker non-owner DB roles and connection reuse; block any bypassing role or unscoped relation.

2. Implement configurable source/document/contact/draft retention and deletion propagation including object store, checkpoints/caches, traces and derived assessments/approvals; retain only policy-approved minimal financial/audit facts.

3. On deletion/expiry invalidate assessment support and dependent approvals immediately at consume-time; background sweep completes physical deletion with retries and report. Do not promise permanent source retention.

4. Review secret paths/build bundles/log redaction, signed URL scoping, CORS/JWT rotation, safe fetch/parse and rendered-source sanitization. No personal content in default logs/checkpoints beyond approved minimization.

5. Record SBOM/dependency and per-component license notices for copied/adapted code; optional GPL path stays absent unless approved. Pin/update critical versions only in separately scoped approved changes.

6. Add audited admin retention/kill-switch controls and clear operator runbooks; dependency scanners use local/approved read-only inputs, never upload proprietary source to an unapproved service.

**Additional schema/route integration:** Implement listAuditEvents with admin/reviewer scope and redacted fields, and wire deleteOfferDocument to the lifecycle service in the predecessor document router; audit log access must itself be auditable.

## API, schema and state changes

Admin retention/deletion request and status if in approved contract; otherwise propose contract revision before coding endpoint. Lifecycle tombstones and invalidation use existing services.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`delete evidence e1 while approval a1 depends on it` makes a1 unusable immediately; physical object/checkpoint deletion follows audited retryable lifecycle, including restore tombstone replay.

## Failure and concurrency cases

Delete while generation/lookup is in flight rechecks result gates and retains needed cost reconciliation. Deletion retry cannot re-expose stale personal data. Backups have documented expiry/restore deletion replay.

- Scenario 1: Cross-tenant events/export/files/jobs tests deny every unauthorized path with non-owner roles.
- Scenario 2: Delete evidence/contact during approved draft and in-flight lookup invalidates approval and prevents late data reappearance.
- Scenario 3: Client bundles/logs contain no provider/DB secrets; dependency notices and approved retention config are complete.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-026-01:** Cross-tenant events/export/files/jobs tests deny every unauthorized path with non-owner roles.
- **TEST-BO-026-02:** Delete evidence/contact during approved draft and in-flight lookup invalidates approval and prevents late data reappearance.
- **TEST-BO-026-03:** Client bundles/logs contain no provider/DB secrets; dependency notices and approved retention config are complete.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `uv run python -m pytest tests/test_security_lifecycle.py` | `services/api` | PROPOSED_AFTER_TASK / NOT RUN | Tenant matrix, lifecycle and secret-boundary negative tests pass |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Fail closed by disabling affected capabilities; quarantine records, rotate affected credentials after separate authorization and replay deletion tombstones after restore. Never disable authorization to restore availability.

## Effort assumptions

**24–40 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-026 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-026-harden-tenant-data-retention-secrets-and-dependency-boundaries.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; the audited source is imported at commit b804ba8d1514a1049b7202c861278dd72c473a75 (tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), merged into main via 72fef7da785624a35bb6701f1451ebcf0184a089), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: Cross-tenant data paths and personal-data lifecycle withstand negative tests, secrets remain server-only, and dependencies/licenses are documented before live data activation. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

