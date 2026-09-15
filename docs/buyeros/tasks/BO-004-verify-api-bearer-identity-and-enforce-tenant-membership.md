---
task_id: "BO-004"
title: "Verify API bearer identity and enforce tenant membership"
phase: "P1"
status: "BLOCKED"
priority: "P0"
source_requirements: ["REQ-TENANT","REQ-CONTRACT"]
depends_on: ["BO-003"]
blocked_by: ["B-IDENTITY","B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "backend"
files_to_read: ["app/chatgpt-auth.ts","app/layout.tsx","features/workspace.tsx","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: []
dependency_output_files_to_modify: ["services/api/pyproject.toml", "services/api/uv.lock", "services/api/buyeros_api/contracts/__init__.py"]
proposed_files_to_create: ["services/api/buyeros_api/main.py", "services/api/buyeros_api/auth.py", "services/api/buyeros_api/errors.py", "services/api/buyeros_api/routes/capabilities.py", "services/api/tests/test_auth_tenant.py", "services/api/buyeros_api/routes/workspaces.py"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["contracts/openapi.proposed.yaml","03_DATA_API_AND_STATE_CONTRACTS.md"]
migration_impact: "none; if current source requires an unlisted migration stop and revise task"
external_capabilities: ["Approved managed OIDC and PostgreSQL design; use isolated fixtures until authorized"]
external_spend_authorized: false
acceptance_tests: ["TEST-BO-004-01","TEST-BO-004-02","TEST-BO-004-03"]
verification_commands: [{"command":"uv run python -m pytest tests/test_auth_tenant.py","working_directory":"services/api","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"All auth-negative and permission tests pass using synthetic tokens/local fixtures"}]
rollback_or_rollforward: "Disable API live capability and roll back auth module only to a still-denying version; never fall back to no-auth."
effort_range_hours: [18,30]
---

# BO-004 — Verify API bearer identity and enforce tenant membership

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

An API request resolves a verified actor and authorized workspace or is denied before reading domain data; capability status exposes no secrets.

## Source requirement and present-state evidence

Source requirements: `REQ-TENANT`, `REQ-CONTRACT`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). app/chatgpt-auth.ts:getChatGPTUser optionally reads trusted-platform identity headers and returns null when required headers are absent; Workspace does not call it. Its mere existence does not verify an API identity boundary or current authenticated user. Hard-coded Willy Lai activity is synthetic attribution, not verified identity.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **backend**; phase **P1**.
- Required predecessor evidence: `BO-003`.
- Blockers: `B-IDENTITY`, `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **Existing application files to modify: none.** New backend/planning files are explicitly proposed below; this is not a claim that those services already exist.

- **PROPOSED new file:** `services/api/buyeros_api/main.py`
- **PROPOSED new file:** `services/api/buyeros_api/auth.py`
- **PROPOSED new file:** `services/api/buyeros_api/errors.py`
- **PROPOSED new file:** `services/api/buyeros_api/routes/capabilities.py`
- **PROPOSED new file:** `services/api/tests/test_auth_tenant.py`

**PROPOSED predecessor outputs to modify after their creating task completes** (not existing at the audited commit):

- `services/api/pyproject.toml` — inspect producer-task result first; modify only this task's required wiring.
- `services/api/uv.lock` — inspect producer-task result first; modify only this task's required wiring.
- `services/api/buyeros_api/contracts/__init__.py` — inspect producer-task result first; modify only this task's required wiring.

- **PROPOSED new file:** `services/api/buyeros_api/routes/workspaces.py`

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Build FastAPI entry point with request IDs, structured errors and readiness/capability routes; distinguish infrastructure readiness from configured provider capabilities.

2. Verify OIDC JWT issuer/audience/algorithm/expiry/JWKS rotation and revocation/session policy; reject unsigned or wrong-audience tokens and never trust client user/workspace claims as membership proof.

3. Resolve actor membership server-side and enforce operator/reviewer/viewer/admin permissions; use workspace path only as a requested scope. Pending schema task may use explicit test repository fixtures, not fake live authentication.

4. Allow only approved frontend origins and authorization headers; no wildcard credentials CORS. For bearer browser flow document CSRF posture and prohibit tokens in URLs/localStorage.

5. Carry actor/workspace/request IDs into application context and deny missing context by default; install minimal audit hooks without raw tokens/personal content.

**Additional exact integration step:** Register listWorkspaces as well as liveness/readiness/capabilities in main.py; list only verified actor memberships. getReadiness is implemented here and reviewed, not newly implemented, during BO-028.

## API, schema and state changes

Bearer authentication and 401/403/404 resource hiding; GET health/readiness and authenticated capabilities. Viewer cannot mutate; provider capability remains unavailable without verified configuration.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`GET /v1/workspaces/ws_b/projects` with an otherwise valid token whose actor belongs only to `ws_a` is denied. Client workspace selection never adds membership.

## Failure and concurrency cases

Expired token returns 401 and preserves unsaved UI input locally in memory. JWKS outage uses bounded safe cache policy, never signature bypass. Workspace switch invalidates server/client caches.

- Scenario 1: Wrong tenant, forged actor, expired/wrong-issuer/audience token and missing membership are denied.
- Scenario 2: Viewer POST and direct object IDs from another workspace are rejected.
- Scenario 3: Capabilities and logs do not disclose secrets, emails, token contents or database URLs.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-004-01:** Wrong tenant, forged actor, expired/wrong-issuer/audience token and missing membership are denied.
- **TEST-BO-004-02:** Viewer POST and direct object IDs from another workspace are rejected.
- **TEST-BO-004-03:** Capabilities and logs do not disclose secrets, emails, token contents or database URLs.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `uv run python -m pytest tests/test_auth_tenant.py` | `services/api` | PROPOSED_AFTER_TASK / NOT RUN | All auth-negative and permission tests pass using synthetic tokens/local fixtures |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Disable API live capability and roll back auth module only to a still-denying version; never fall back to no-auth.

## Effort assumptions

**18–30 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-004 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-004-verify-api-bearer-identity-and-enforce-tenant-membership.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; currently empty until the exact audited import lands, expected tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: An API request resolves a verified actor and authorized workspace or is denied before reading domain data; capability status exposes no secrets. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

