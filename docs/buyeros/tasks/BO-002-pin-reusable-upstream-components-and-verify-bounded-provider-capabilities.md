---
task_id: "BO-002"
title: "Pin reusable upstream components and verify bounded provider capabilities"
phase: "P0"
status: "BLOCKED"
priority: "P0"
source_requirements: ["REQ-REUSE","REQ-PROVIDER","REQ-BUDGET"]
depends_on: ["BO-000"]
blocked_by: ["B-PROVIDERS","B-LICENSE","B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "ai"
files_to_read: ["services/contracts.ts","services/http-client.ts","services/mock-client.ts","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/02_ARCHITECTURE_AND_REUSE.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md","docs/buyeros/research/UPSTREAM_AUDIT.md","docs/buyeros/decisions/BO-001-runtime-identity.md"]
existing_files_to_modify: []
dependency_output_files_to_modify: []
proposed_files_to_create: ["docs/buyeros/decisions/BO-002-provider-capabilities.md","docs/buyeros/evidence/provider-contract-fixtures.proposed.json"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["02_ARCHITECTURE_AND_REUSE.md","03_DATA_API_AND_STATE_CONTRACTS.md","research/UPSTREAM_AUDIT.md"]
migration_impact: "none; if current source requires an unlisted migration stop and revise task"
external_capabilities: ["Verified provider contracts and deterministic fixtures; no live calls authorized"]
external_spend_authorized: false
acceptance_tests: ["TEST-BO-002-01","TEST-BO-002-02","TEST-BO-002-03"]
verification_commands: []
rollback_or_rollforward: "Revise capability decision and keep provider disabled; no external mutation."
effort_range_hours: [12,20]
---

# BO-002 — Pin reusable upstream components and verify bounded provider capabilities

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

Each proposed live search, LLM and optional business-email operation has a verified interface, bounded price policy, fixture shape and go/no-go decision.

## Source requirement and present-state evidence

Source requirements: `REQ-REUSE`, `REQ-PROVIDER`, `REQ-BUDGET`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). services/http-client.ts only re-exports the mock-client NOT_CONFIGURED stub. No provider adapter exists. The **normative** upstream commit/path/license inventory is [../research/UPSTREAM_AUDIT.md](../research/UPSTREAM_AUDIT.md) (referenced as normative by 02); use its actual pinned commits, not guessed package imports or report citation tokens. This task performs **documentation/rights evidence only — no paid or live provider call is authorized** (`external_spend_authorized: false`), and it must never invent model identifiers, endpoints or prices; record verified-or-unknown only. Canonical repository is `YNWAforever/BuyerOS` (exact import expected; content baseline `b804ba8d1514a1049b7202c861278dd72c473a75`).

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **ai**; phase **P0**.
- Required predecessor evidence: `BO-000`.
- Blockers: `B-PROVIDERS`, `B-LICENSE`, `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **Existing application files to modify: none.** New backend/planning files are explicitly proposed below; this is not a claim that those services already exist.

- **PROPOSED new file:** `docs/buyeros/decisions/BO-002-provider-capabilities.md`
- **PROPOSED new file:** `docs/buyeros/evidence/provider-contract-fixtures.proposed.json`

The `decisions/` directory now exists (`decisions/BO-001-runtime-identity.md`); create the BO-002 record alongside it. Neither file is a live provider call or credential; fixtures must remain synthetic.

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Revalidate the pinned AI_Find_Customer files and per-component/dependency licenses from the reuse matrix. Select only approved MIT components to adapt; record retained notices and substitutions for single-user storage/auth/schedulers.

2. Resolve the actual linked OpenOutreach/OpenOutFind repositories and licenses. Keep GPL integration optional and deferred until counsel/owner disposition; a separate process does not remove obligations. No invented inbound lead API or CLI flags.

3. Choose one search provider, one approved LLM route per workflow task, and one optional business-email provider from the architecture record; verify official request/response/error/rate/pricing documentation without billable calls.

4. For the email provider record support or lack of idempotency, external correlation ID, status query, signed webhooks, replay identifiers, batch partials, cancellation, invoice/credit reconciliation and maximum charge. If safe bounded submission/reconciliation is unavailable, contact activation is blocked.

5. Create sanitized synthetic fixtures based on verified schemas, including timeout-after-acceptance, pending, partial, duplicate callback and catch-all. No real contact datasets or credentials.

6. Approve price-version validity and ceiling policy; preserve quote snapshots so report/demo USD 0.30 is never used as current pricing.

## API, schema and state changes

Defines provider-operation adapter contracts for lookup submission/status/reconciliation and search/LLM usage; BuyerOS public API remains provider neutral.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`contact_capability = {idempotency: verified | unsupported | unknown, status_lookup: verified | unsupported | unknown, max_charge: bounded | unbounded}`. Unknown/unbounded required capability means disabled, not an invented provider call.

## Failure and concurrency cases

Optional GPL uncertainty does not block independent public-web discovery. Unbounded charges, unsupported required response fields or unknowable submission state block that provider path instead of guessing.

- Scenario 1: Every selected operation cites pinned code or an official schema and exact price/cap validity assumptions.
- Scenario 2: No upstream UI is imported; no unverifiable flag/import/inbound interface appears.
- Scenario 3: Fixtures cover unknown submissions and explicit unsupported capabilities; optional contact path can remain disabled.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-002-01:** Every selected operation cites pinned code or an official schema and exact price/cap validity assumptions.
- **TEST-BO-002-02:** No upstream UI is imported; no unverifiable flag/import/inbound interface appears.
- **TEST-BO-002-03:** Fixtures cover unknown submissions and explicit unsupported capabilities; optional contact path can remain disabled.

This is a documentation/approval or environment-dependent operations task: no executable product verification command is asserted. Perform the named document/evidence acceptance checks; any future operational command must be recorded against the approved environment before execution. **Product checks: NOT RUN.**

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Revise capability decision and keep provider disabled; no external mutation.

## Effort assumptions

**12–20 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-002 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-002-pin-reusable-upstream-components-and-verify-bounded-provider-capabilities.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; planning pack committed at 1512d4c17d4f792e14598d524fdac3c9c37d27e7; a source import of the audited content baseline is still expected, importing tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: Each proposed live search, LLM and optional business-email operation has a verified interface, bounded price policy, fixture shape and go/no-go decision. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

