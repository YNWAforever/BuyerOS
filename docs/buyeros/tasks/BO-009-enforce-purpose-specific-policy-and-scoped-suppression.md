---
task_id: "BO-009"
title: "Enforce purpose-specific policy and scoped suppression"
phase: "P2"
status: "BLOCKED"
priority: "P0"
source_requirements: ["REQ-POLICY","REQ-TENANT","REQ-APPROVAL"]
depends_on: ["BO-008"]
blocked_by: ["B-POLICY","B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "backend"
files_to_read: ["services/mock-client.ts","features/workspace.tsx","features/buyers/detail.tsx","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: ["features/workspace.tsx","features/buyers/detail.tsx"]
dependency_output_files_to_modify: ["services/api/buyeros_api/main.py", "services/api/buyeros_api/models/core.py", "services/live/client.ts"]
proposed_files_to_create: ["services/api/buyeros_api/services/policy.py","services/api/buyeros_api/routes/policy.py","services/api/alembic/versions/0002_policy.py","services/api/tests/test_policy_suppression.py"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["03_DATA_API_AND_STATE_CONTRACTS.md","contracts/openapi.proposed.yaml"]
migration_impact: "PROPOSED additive migration; serialize through sole Alembic owner; execution only on approved disposable/staging DB"
external_capabilities: ["Approved managed OIDC and PostgreSQL design; use isolated fixtures until authorized"]
external_spend_authorized: false
acceptance_tests: ["TEST-BO-009-01","TEST-BO-009-02","TEST-BO-009-03"]
verification_commands: [{"command":"uv run python -m pytest tests/test_policy_suppression.py","working_directory":"services/api","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"Independent-purpose, late-result and scoped authorization cases pass"}]
rollback_or_rollforward: "Fail closed on policy service failure; revert rules through versioned decision supersession with approval, retaining minimal audit."
effort_range_hours: [18,30]
---

# BO-009 — Enforce purpose-specific policy and scoped suppression

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

Contact research, draft/export and future outreach receive separate server decisions with policy provenance; unknown or suppressed cases are blocked consistently.

## Source requirement and present-state evidence

Source requirements: `REQ-POLICY`, `REQ-TENANT`, `REQ-APPROVAL`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). mock-client:block tests Company.policy==='Allowed' and suppressed boolean; settings mutates suppression locally. A draft's policyReviewed checkbox is not a verified purpose/legal decision.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **backend**; phase **P2**.
- Required predecessor evidence: `BO-008`.
- Blockers: `B-POLICY`, `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **EXISTING, inspected:** `features/workspace.tsx`
- **EXISTING, inspected:** `features/buyers/detail.tsx`

- **PROPOSED new file:** `services/api/buyeros_api/services/policy.py`
- **PROPOSED new file:** `services/api/buyeros_api/routes/policy.py`
- **PROPOSED new file:** `services/api/alembic/versions/0002_policy.py`
- **PROPOSED new file:** `services/api/tests/test_policy_suppression.py`

**PROPOSED predecessor outputs to modify after their creating task completes** (not existing at the audited commit):

- `services/api/buyeros_api/main.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/api/buyeros_api/models/core.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/live/client.ts` — inspect producer-task result first; modify only this task's required wiring.

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Persist scoped suppressions for workspace/client/controller with normalized address/domain/company targets, reason, actor/source/version, activation and review/retention dates; no cross-tenant shared contact corpus.

2. Persist policy decisions keyed by purpose, jurisdiction/entity context, subject, policy version and evidence; only authorized reviewer/admin can record permitted/blocked decisions with provenance.

3. Implement one deterministic eligibility service used by quote/confirm/dispatch/result/draft/approval/export. Fit, acceptance, contact validity, suppression and policy remain distinct inputs and output reason codes.

4. Revoke/invalidate dependent draft approvals and prevent exposure of late prohibited contact results on suppression/policy changes; send durable invalidation work through outbox once BO-011 exists.

5. Wire settings editor and detail explanations to permitted server operations. Client checkboxes request review or display decisions; they cannot grant policy permission.

## API, schema and state changes

Policy/suppression endpoints; unknown/requires_review/permitted/blocked by purpose. Policy changes raise version and downstream stale state. Migration impact: additive policy/suppression tables.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`policy(contact_research)=permitted` and `policy(outreach)=unknown` permit neither addressed outreach approval nor delivery merely because lookup is allowed. Adding an active matching suppression blocks the applicable purpose regardless of validity.

## Failure and concurrency cases

Late lookup result after suppression is quarantined/discarded by policy while cost reconciliation continues. Controller scope must be explicit; unclear cross-client scope blocks policy approval.

- Scenario 1: Research permission never implies outreach permission; valid address never overrides unknown policy.
- Scenario 2: Suppression flips between quote, confirm, dispatch and result blocks appropriate action each time.
- Scenario 3: Only authorized policy roles can permit; tenant-scoped suppression cannot disclose other tenant contact data.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-009-01:** Research permission never implies outreach permission; valid address never overrides unknown policy.
- **TEST-BO-009-02:** Suppression flips between quote, confirm, dispatch and result blocks appropriate action each time.
- **TEST-BO-009-03:** Only authorized policy roles can permit; tenant-scoped suppression cannot disclose other tenant contact data.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `uv run python -m pytest tests/test_policy_suppression.py` | `services/api` | PROPOSED_AFTER_TASK / NOT RUN | Independent-purpose, late-result and scoped authorization cases pass |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Fail closed on policy service failure; revert rules through versioned decision supersession with approval, retaining minimal audit.

## Effort assumptions

**18–30 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-009 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-009-enforce-purpose-specific-policy-and-scoped-suppression.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; the audited source is imported at commit b804ba8d1514a1049b7202c861278dd72c473a75 (tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), merged into main via 72fef7da785624a35bb6701f1451ebcf0184a089), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: Contact research, draft/export and future outreach receive separate server decisions with policy provenance; unknown or suppressed cases are blocked consistently. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

