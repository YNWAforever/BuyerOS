---
task_id: "BO-021"
title: "Generate grounded draft revisions from approved facts and evidence"
phase: "P5"
status: "BLOCKED"
priority: "P1"
source_requirements: ["REQ-DRAFT","REQ-EVIDENCE","REQ-BUDGET"]
depends_on: ["BO-009","BO-011","BO-015","BO-020"]
blocked_by: ["B-PROVIDERS","B-POLICY","B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "ai"
files_to_read: ["features/workspace.tsx","services/contracts.ts","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: ["features/workspace.tsx"]
dependency_output_files_to_read: ["services/api/buyeros_api/services/sender_identity.py"]
dependency_output_files_to_modify: ["services/api/buyeros_api/main.py", "services/api/buyeros_api/models/core.py", "services/live/client.ts", "services/worker/buyeros_worker/tasks.py"]
proposed_files_to_create: ["services/api/buyeros_api/routes/drafts.py","services/api/alembic/versions/0007_drafts.py","services/worker/buyeros_worker/drafting/generate.py","services/worker/buyeros_worker/drafting/prompts/draft_v1.md","services/worker/tests/test_grounded_draft.py"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["contracts/openapi.proposed.yaml","03_DATA_API_AND_STATE_CONTRACTS.md"]
migration_impact: "PROPOSED additive migration; serialize through sole Alembic owner; execution only on approved disposable/staging DB"
external_capabilities: []
external_spend_authorized: false
acceptance_tests: ["TEST-BO-021-01","TEST-BO-021-02","TEST-BO-021-03"]
verification_commands: [{"command":"uv run python -m pytest tests/test_grounded_draft.py","working_directory":"services/worker","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"Grounding, race, policy and zero-delivery cases pass with fixtures"}]
rollback_or_rollforward: "Disable generation while keeping existing human revisions readable/editable. Roll forward with prompt/schema version; never rewrite approved content."
effort_range_hours: [22,36]
---

# BO-021 — Generate grounded draft revisions from approved facts and evidence

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

An accepted eligible buyer yields a persisted email draft and optional follow-up whose factual claims cite approved offer/evidence snapshots, with no delivery side effect.

## Source requirement and present-state evidence

Source requirements: `REQ-DRAFT`, `REQ-EVIDENCE`, `REQ-BUDGET`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). Workspace:action('draft') creates synthetic .example recipients, and Outreach generation is an inline template callback. The existing three-pane editor, recipient queue and evidence/review panel are real frontend assets to preserve.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **ai**; phase **P5**.
- Required predecessor evidence: `BO-009`, `BO-011`, `BO-015`, `BO-020`.
- Blockers: `B-PROVIDERS`, `B-POLICY`, `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **EXISTING, inspected:** `features/workspace.tsx`

- **PROPOSED new file:** `services/api/buyeros_api/routes/drafts.py`
- **PROPOSED new file:** `services/api/alembic/versions/0007_drafts.py`
- **PROPOSED new file:** `services/worker/buyeros_worker/drafting/generate.py`
- **PROPOSED new file:** `services/worker/buyeros_worker/drafting/prompts/draft_v1.md`
- **PROPOSED new file:** `services/worker/tests/test_grounded_draft.py`

**PROPOSED predecessor outputs to modify after their creating task completes** (not existing at the audited commit):

- `services/api/buyeros_api/main.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/api/buyeros_api/models/core.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/live/client.ts` — inspect producer-task result first; modify only this task's required wiring.
- `services/worker/buyeros_worker/tasks.py` — inspect producer-task result first; modify only this task's required wiring.

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Create persisted draft and revision structures bound to workspace/project/buyer, recipient/contact, approved offer/ICP versions, cited evidence/policy context, objective/tone/language and versioned prompt/model route.

2. Require applicable buyer acceptance/suppression/research/draft-purpose decisions before provider invocation; permit preparation without a known person only with explicit no-recipient draft state that cannot be approved/exported as addressed outreach.

3. Reserve model spend and enqueue generation durably. Prompt receives only permitted facts/evidence, not arbitrary web instructions; no model tool can enrich contact or send.

4. Validate schema and claim-to-evidence IDs; forbid invented certifications, relationships, buying intent, personal data or savings. Flag unsupported content for human revision rather than silently claiming success.

5. Persist generated revision with content hash and attribution; asynchronous generation cannot overwrite a newer human edit. Store generation result as alternate revision or conflict requiring explicit adoption.

6. Wire existing editor/queue/evidence pane and follow-up controls; preserve demo template as demo only and delivery disabled. Generation starts Draft, never Approved.

**Additional authority/concurrency step:** Resolve sender_identity_version against the active approved project-owned sender_identity_versions record before generation. Never accept arbitrary strings or foreign/revoked versions as identity authority; generation snapshots the server version. A sender change during generation produces a stale/alternate revision requiring fresh review, and no mailbox integration is implied.

## API, schema and state changes

POST project drafts queues generation; GET/PATCH drafts use immutable revisions and expected_version. Generation returns 202, not draft approval.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`generateDraft` returns 202 AsyncJob; completion writes revision 4 only if its expected parent remains current, otherwise a reviewable alternate. Its evidence citations cannot reference e99 when only e1/e2 were supplied.

## Failure and concurrency cases

Provider timeout, unsupported claim, missing evidence, language mismatch and edit-during-generation produce honest failed/review/conflict states. No hard-coded sample recipient in live mode.

- Scenario 1: Invented certification/buying-intent statement is rejected or flagged; each used fact traces to permitted evidence.
- Scenario 2: Generation finishing after user edit cannot overwrite that edit or preserve stale approval.
- Scenario 3: Draft/follow-up generation produces zero send/contact provider calls and reserves/settles model cost once.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-021-01:** Invented certification/buying-intent statement is rejected or flagged; each used fact traces to permitted evidence.
- **TEST-BO-021-02:** Generation finishing after user edit cannot overwrite that edit or preserve stale approval.
- **TEST-BO-021-03:** Draft/follow-up generation produces zero send/contact provider calls and reserves/settles model cost once.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `uv run python -m pytest tests/test_grounded_draft.py` | `services/worker` | PROPOSED_AFTER_TASK / NOT RUN | Grounding, race, policy and zero-delivery cases pass with fixtures |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Disable generation while keeping existing human revisions readable/editable. Roll forward with prompt/schema version; never rewrite approved content.

## Effort assumptions

**22–36 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-021 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-021-generate-grounded-draft-revisions-from-approved-facts-and-evidence.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; planning pack committed at 1512d4c17d4f792e14598d524fdac3c9c37d27e7; a source import of the audited content baseline is still expected, importing tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: An accepted eligible buyer yields a persisted email draft and optional follow-up whose factual claims cite approved offer/evidence snapshots, with no delivery side effect. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

