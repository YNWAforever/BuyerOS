---
task_id: "BO-029"
title: "Execute only the separately approved bounded live MVP-A pilot"
phase: "P6"
status: "BLOCKED"
priority: "P1"
source_requirements: ["REQ-PILOT","REQ-BUDGET","REQ-USAGE"]
depends_on: ["BO-028"]
blocked_by: ["B-PILOT","B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "platform"
files_to_read: ["docs/buyeros/pilot/release-candidate.md","docs/buyeros/pilot/approval-request.md","docs/buyeros/pilot/evaluation-protocol.md","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: []
dependency_output_files_to_modify: []
proposed_files_to_create: ["docs/buyeros/pilot/authorized-run-log.md","docs/buyeros/pilot/evaluation-results.md","docs/buyeros/pilot/go-no-go.md"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["docs/buyeros/pilot/release-candidate.md","05_TEST_SECURITY_AND_RELEASE.md"]
migration_impact: "none; if current source requires an unlisted migration stop and revise task"
external_capabilities: ["Approved hosting and selected real providers; explicit activation/spend approval required"]
external_spend_authorized: false
acceptance_tests: ["TEST-BO-029-01","TEST-BO-029-02","TEST-BO-029-03"]
verification_commands: []
rollback_or_rollforward: "Pause live dispatch, retain safe reads/reconciliation, disable staging capability or roll back approved release per runbook; preserve immutable ledger and apply retention policy to pilot data."
effort_range_hours: [20,36]
---

# BO-029 — Execute only the separately approved bounded live MVP-A pilot

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

After specific owner approval, a small authorized workspace completes live discovery→evidence→acceptance→optional quote/contact→grounded draft→approval→manual outcome with measured costs and no sending.

## Source requirement and present-state evidence

Source requirements: `REQ-PILOT`, `REQ-BUDGET`, `REQ-USAGE`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). No live paid provider, cloud resource, deployment, mailbox or application implementation has been authorized or performed in this planning session. This task is an explicit later activation gate, not automatic follow-on execution.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **platform**; phase **P6**.
- Required predecessor evidence: `BO-028`.
- Blockers: `B-PILOT`, `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **Existing application files to modify: none.** New backend/planning files are explicitly proposed below; this is not a claim that those services already exist.

- **PROPOSED new file:** `docs/buyeros/pilot/authorized-run-log.md`
- **PROPOSED new file:** `docs/buyeros/pilot/evaluation-results.md`
- **PROPOSED new file:** `docs/buyeros/pilot/go-no-go.md`

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Before any action verify explicit BO-029 Build approval separately includes named staging/deployment/resources and exact provider spend/data scope. If approval omits either, keep those actions blocked; task external_spend_authorized remains false until recorded owner authorization.

2. Use only approved target and release commit with least-privilege secrets; follow documented deploy/runbook without changing current Sites URL/access unless separately named. Do not create a replacement repository or database.

3. Run bounded health/auth checks then approved discovery sample; human reviewers assess evidence/fit and accept accounts. Optional contact requires its own permitted purpose and quote confirmation within approved total cap.

4. Exercise real draft generation/revision approval with no send/mailbox connection. Record outcomes only as manual when actually observed and retain provenance.

5. Reconcile provider operation/credit/invoice evidence and ledger, including unknowns; report actual empirical quality/cost/review times against proposed approved thresholds.

6. Pause on cap/uncertainty/security/quality triggers; produce go/no-go with remaining gaps and exact next task proposal. No automatic P7 activation.

## API, schema and state changes

Uses existing approved APIs only; no new delivery endpoint. Capabilities enabled only within recorded pilot approval; data_mode=live is backed by real integration evidence.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`approved_run_cap=25.000000 USD` is illustrative only and must be replaced by owner-approved amount before execution. No approval in this planning session means live request count=0 and deployment count=0.

## Failure and concurrency cases

Provider uncertainty pauses new spend and retains reservation. Security/policy incident disables impacted capability and follows rollback; reaching target buyer count is not guaranteed.

- Scenario 1: Authorized live request IDs/provider receipts prove research/contact/draft operations and ledger bounds; unavailable operations remain NOT RUN.
- Scenario 2: Human evaluation and displayed claim-evidence links meet approved structural/empirical gates or produce no-go.
- Scenario 3: No mailbox connected, message sent, Site access changed or unapproved resource created; optional contact stays off unless separately allowed.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-029-01:** Authorized live request IDs/provider receipts prove research/contact/draft operations and ledger bounds; unavailable operations remain NOT RUN.
- **TEST-BO-029-02:** Human evaluation and displayed claim-evidence links meet approved structural/empirical gates or produce no-go.
- **TEST-BO-029-03:** No mailbox connected, message sent, Site access changed or unapproved resource created; optional contact stays off unless separately allowed.

This is a documentation/approval or environment-dependent operations task: no executable product verification command is asserted. Perform the named document/evidence acceptance checks; any future operational command must be recorded against the approved environment before execution. **Product checks: NOT RUN.**

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Pause live dispatch, retain safe reads/reconciliation, disable staging capability or roll back approved release per runbook; preserve immutable ledger and apply retention policy to pilot data.

## Effort assumptions

**20–36 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-029 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-029-execute-only-the-separately-approved-bounded-live-mvp-a-pilot.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; the audited source is imported at commit b804ba8d1514a1049b7202c861278dd72c473a75 (tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), merged into main via 72fef7da785624a35bb6701f1451ebcf0184a089), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: After specific owner approval, a small authorized workspace completes live discovery→evidence→acceptance→optional quote/contact→grounded draft→approval→manual outcome with measured costs and no sending. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

