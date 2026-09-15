---
task_id: "BO-030"
title: "Design a separately approved controlled delivery phase without activating it"
phase: "P7"
status: "BLOCKED"
priority: "P2"
source_requirements: ["REQ-DELIVERY","REQ-POLICY","REQ-APPROVAL"]
depends_on: ["BO-028"]
blocked_by: ["B-DELIVERY","B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "platform"
files_to_read: ["features/workspace.tsx","services/contracts.ts","docs/buyeros/pilot/release-candidate.md","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: []
dependency_output_files_to_modify: []
proposed_files_to_create: ["docs/buyeros/delivery/ADR-delivery-proposed.md","docs/buyeros/delivery/implementation-tasks.proposed.md","docs/buyeros/delivery/activation-gates.proposed.md"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["03_DATA_API_AND_STATE_CONTRACTS.md","05_TEST_SECURITY_AND_RELEASE.md"]
migration_impact: "none; if current source requires an unlisted migration stop and revise task"
external_capabilities: []
external_spend_authorized: false
acceptance_tests: ["TEST-BO-030-01","TEST-BO-030-02","TEST-BO-030-03"]
verification_commands: []
rollback_or_rollforward: "Reject/supersede P7 design; MVP-A remains research/contact/draft-only with delivery disabled."
effort_range_hours: [12,20]
---

# BO-030 — Design a separately approved controlled delivery phase without activating it

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

Only after a separate delivery-design approval, produce a bounded P7 task pack for one sender of record and explicit legal/provider/activation gates; no sending code is enabled by this task.

## Source requirement and present-state evidence

Source requirements: `REQ-DELIVERY`, `REQ-POLICY`, `REQ-APPROVAL`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). Frontend explicitly keeps delivery Not connected and has no send/schedule action. Research report's sending ideas do not authorize real delivery. MVP-A approval/export never creates a Sent state.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **platform**; phase **P7**.
- Required predecessor evidence: `BO-028`.
- Blockers: `B-DELIVERY`, `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **Existing application files to modify: none.** New backend/planning files are explicitly proposed below; this is not a claim that those services already exist.

- **PROPOSED new file:** `docs/buyeros/delivery/ADR-delivery-proposed.md`
- **PROPOSED new file:** `docs/buyeros/delivery/implementation-tasks.proposed.md`
- **PROPOSED new file:** `docs/buyeros/delivery/activation-gates.proposed.md`

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Confirm separate owner approval to begin delivery design, not infer it from MVP-A pilot success; P7 remains outside automatic dependency progression.

2. Select one sender of record only after verifying current provider/mailbox terms and supported outreach use, sender identity/domain authentication, token scopes, rate limits, webhooks/replies/bounces/complaints and suppression APIs.

3. Obtain purpose/jurisdiction review including opt-out, sender identity and recipient eligibility; managed transactional delivery service availability is not proof cold outreach is permitted.

4. Specify scheduling/dispatch consumes exact still-valid revision/recipient/evidence/policy approval under atomic send intent, idempotency, suppression recheck, stop/kill switch and one provider record of delivery truth.

5. Define reply/bounce/suppression loops and accurate event semantics: accepted by provider differs from delivered, reply and conversion. No mailbox synchronization promise without verified interface.

6. Produce new narrow approved-scope implementation tasks/contracts/test plan and explicit activation/spend gate. Do not add send endpoints, connect a mailbox, modify active config or execute delivery during this task.

## API, schema and state changes

Proposed P7 contract revision only; delivery statuses remain independent of draft approval and manual outcomes. No active endpoint change.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`draft Approved` remains independent of future delivery `disabled`; a new P7 design approval is not mailbox connection or permission to send even one message.

## Failure and concurrency cases

Provider terms incompatible with intended use, jurisdiction approval missing, impossible reconciliation or multiple competing senders block P7. MVP-A continues with delivery disabled.

- Scenario 1: Design identifies one sender, actual capability/term references and jurisdiction/policy blockers.
- Scenario 2: No proposal allows stale approvals, suppressed recipients or approval/export to imply delivery.
- Scenario 3: Task pack has independent activation approval, replay/bounce/opt-out tests and kill/rollback plan; no application change occurred.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-030-01:** Design identifies one sender, actual capability/term references and jurisdiction/policy blockers.
- **TEST-BO-030-02:** No proposal allows stale approvals, suppressed recipients or approval/export to imply delivery.
- **TEST-BO-030-03:** Task pack has independent activation approval, replay/bounce/opt-out tests and kill/rollback plan; no application change occurred.

This is a documentation/approval or environment-dependent operations task: no executable product verification command is asserted. Perform the named document/evidence acceptance checks; any future operational command must be recorded against the approved environment before execution. **Product checks: NOT RUN.**

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Reject/supersede P7 design; MVP-A remains research/contact/draft-only with delivery disabled.

## Effort assumptions

**12–20 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-030 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-030-design-a-separately-approved-controlled-delivery-phase-without-activating-it.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; currently empty until the exact audited import lands, expected tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: Only after a separate delivery-design approval, produce a bounded P7 task pack for one sender of record and explicit legal/provider/activation gates; no sending code is enabled by this task. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

