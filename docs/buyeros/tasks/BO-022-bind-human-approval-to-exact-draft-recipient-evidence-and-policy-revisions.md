---
task_id: "BO-022"
title: "Bind human approval to exact draft, recipient, evidence and policy revisions"
phase: "P5"
status: "BLOCKED"
priority: "P1"
source_requirements: ["REQ-APPROVAL","REQ-POLICY","REQ-RECOVERY"]
depends_on: ["BO-021"]
blocked_by: ["B-POLICY","B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "backend"
files_to_read: ["features/workspace.tsx","services/contracts.ts","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: ["features/workspace.tsx"]
dependency_output_files_to_modify: ["services/api/buyeros_api/routes/drafts.py", "services/api/buyeros_api/services/policy.py", "services/api/buyeros_api/services/profiles.py", "services/live/client.ts", "services/api/buyeros_api/main.py", "services/api/buyeros_api/routes/projects.py", "services/api/buyeros_api/services/sender_identity.py"]
proposed_files_to_create: ["services/api/buyeros_api/services/approvals.py", "services/api/tests/test_draft_approval.py", "tests/frontend/draft-approval.spec.ts", "services/api/buyeros_api/routes/delivery_boundary.py"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["03_DATA_API_AND_STATE_CONTRACTS.md","contracts/openapi.proposed.yaml"]
migration_impact: "none; if current source requires an unlisted migration stop and revise task"
external_capabilities: []
external_spend_authorized: false
acceptance_tests: ["TEST-BO-022-01", "TEST-BO-022-02", "TEST-BO-022-03", "TEST-BO-022-04"]
verification_commands: [{"command":"uv run python -m pytest tests/test_draft_approval.py","working_directory":"services/api","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"DB race and complete material-context invalidation suite passes"},{"command":"pnpm exec playwright test tests/frontend/draft-approval.spec.ts","working_directory":"repo","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"Three-pane editor shows correct revision, reviewer and stale reasons"}]
rollback_or_rollforward: "Disable approval consumption; mark affected approvals stale via audited versioned events. Preserve immutable revisions and evidence of who approved what."
effort_range_hours: [22,36]
---

# BO-022 — Bind human approval to exact draft, recipient, evidence and policy revisions

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

Only an authorized reviewer can approve an exact content/recipient/evidence/policy snapshot, and every material change makes that approval unusable.

## Source requirement and present-state evidence

Source requirements: `REQ-APPROVAL`, `REQ-POLICY`, `REQ-RECOVERY`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). Workspace:editDraft increments local revision and clears approval; approval is an inline handler checking sample sender/policy and .example recipient. This is useful UI behavior, not server authorization or immutable approval binding.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **backend**; phase **P5**.
- Required predecessor evidence: `BO-021`.
- Blockers: `B-POLICY`, `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **EXISTING, inspected:** `features/workspace.tsx`

- **PROPOSED new file:** `services/api/buyeros_api/services/approvals.py`
- **PROPOSED new file:** `services/api/tests/test_draft_approval.py`
- **PROPOSED new file:** `tests/frontend/draft-approval.spec.ts`

**PROPOSED predecessor outputs to modify after their creating task completes** (not existing at the audited commit):

- `services/api/buyeros_api/routes/drafts.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/api/buyeros_api/services/policy.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/api/buyeros_api/services/profiles.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/live/client.ts` — inspect producer-task result first; modify only this task's required wiring.

- **PROPOSED new file:** `services/api/buyeros_api/routes/delivery_boundary.py`

- **PROPOSED predecessor output to modify:** `services/api/buyeros_api/main.py`

- **PROPOSED predecessor output to modify:** `services/api/buyeros_api/routes/projects.py`
- **PROPOSED predecessor output to modify:** `services/api/buyeros_api/services/sender_identity.py`

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Implement PATCH append-only revision with optimistic expected_version; compute canonical content hash over subject/body/followup/recipient/sender/material draft inputs server-side.

2. Review request snapshots immutable content/recipient/contact validation/ICP/evidence/policy versions and buyer acceptance; reviewer identity comes from verified token, never editable approver name.

3. Approval transaction locks current draft/context and requires exact expected revision/hash/recipient/evidence/policy validity, permitted outreach-preparation/export context, contact eligibility, no suppression and reviewer role.

4. Material change in content, recipient, sender, cited evidence, ICP affecting fit, policy, suppression or acceptance invalidates approval synchronously where authoritative writes occur, plus outbox propagation; consuming approval always rechecks current dependency versions.

5. Render independent human review state and precise stale reason; do not display approval as delivery authorization or compliance guarantee. Sending/scheduling endpoints remain absent or explicitly unavailable server-side.

6. Two reviewers can share current revision read but uniqueness/idempotency prevents divergent duplicate approval; viewer/operator restrictions follow approved role model.

**Additional exact integration step:** Register disabledDeliveryBoundary from the proposed contract as an explicit always-disabled MVP-A response with no mailbox/provider code. This implementation belongs here, not in the documentation-only BO-030 delivery-design task.

**Additional authority/concurrency step:** Approval resolves sender_identity_version to the same project's active, reviewer/admin-confirmed immutable sender configuration. Reject forged, foreign, stale or revoked versions. Project PATCH sender changes require sender_confirmation=true plus authorized role; config supersession/revocation invalidates draft approval at consume-time even if async propagation is delayed.

## API, schema and state changes

POST /drafts/{id}/review; POST /drafts/{id}/approvals; PATCH draft with expected_version. Draft→review_requested→approved; material changes→stale/new draft. Approval records exact context fingerprint.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`approveDraft(revision=4, content_hash=h4, recipient/contact/evidence/policy hashes=current)` succeeds only for that context. A subject edit creates revision 5 and makes h4 approval stale.

## Failure and concurrency cases

Simultaneous edit/approve, suppression during transaction, evidence deletion/expiry, policy revocation, recipient swap and lost approval response cannot preserve stale approval.

- Scenario 1: Race subject edit against approve: exactly current immutable revision may be approved, never stale content.
- Scenario 2: Change recipient/evidence/ICP/policy/acceptance/suppression invalidates consume-time approval check.
- Scenario 3: Unauthorized approver is rejected; approving/copying/exporting creates no delivery or Sent state.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-022-01:** Race subject edit against approve: exactly current immutable revision may be approved, never stale content.
- **TEST-BO-022-02:** Change recipient/evidence/ICP/policy/acceptance/suppression invalidates consume-time approval check.
- **TEST-BO-022-03:** Unauthorized approver is rejected; approving/copying/exporting creates no delivery or Sent state.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `uv run python -m pytest tests/test_draft_approval.py` | `services/api` | PROPOSED_AFTER_TASK / NOT RUN | DB race and complete material-context invalidation suite passes |
| `pnpm exec playwright test tests/frontend/draft-approval.spec.ts` | `repo` | PROPOSED_AFTER_TASK / NOT RUN | Three-pane editor shows correct revision, reviewer and stale reasons |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

Additional required negative tests:

- **TEST-BO-022-04:** Forged, foreign-project, unapproved or revoked sender_identity_version is rejected; a reviewer-approved sender config change invalidates prior draft approval and cannot be treated as mailbox/delivery authorization.

## Rollback or roll-forward

Disable approval consumption; mark affected approvals stale via audited versioned events. Preserve immutable revisions and evidence of who approved what.

## Effort assumptions

**22–36 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-022 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-022-bind-human-approval-to-exact-draft-recipient-evidence-and-policy-revisions.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; the audited source is imported at commit b804ba8d1514a1049b7202c861278dd72c473a75 (tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), merged into main via 72fef7da785624a35bb6701f1451ebcf0184a089), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: Only an authorized reviewer can approve an exact content/recipient/evidence/policy snapshot, and every material change makes that approval unusable. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

