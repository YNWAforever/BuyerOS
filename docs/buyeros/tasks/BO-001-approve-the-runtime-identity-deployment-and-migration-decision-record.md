---
task_id: "BO-001"
title: "Approve the runtime, identity, deployment and migration decision record"
phase: "P0"
status: "BLOCKED"
priority: "P0"
source_requirements: ["REQ-STACK","REQ-TENANT"]
depends_on: ["BO-000"]
blocked_by: ["B-IDENTITY","B-HOST","B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "platform"
files_to_read: ["package.json","vite.config.ts","next.config.ts","scripts/run-framework.mjs","app/chatgpt-auth.ts","db/schema.ts","db/index.ts","drizzle.config.ts","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: []
dependency_output_files_to_modify: []
proposed_files_to_create: ["docs/buyeros/decisions/BO-001-runtime-identity.md"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["03_DATA_API_AND_STATE_CONTRACTS.md"]
migration_impact: "none; if current source requires an unlisted migration stop and revise task"
external_capabilities: ["Approved managed OIDC and PostgreSQL design; use isolated fixtures until authorized"]
external_spend_authorized: false
acceptance_tests: ["TEST-BO-001-01","TEST-BO-001-02","TEST-BO-001-03"]
verification_commands: []
rollback_or_rollforward: "Supersede the ADR; no runtime or cloud rollback needed."
effort_range_hours: [6,12]
---

# BO-001 — Approve the runtime, identity, deployment and migration decision record

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

One approved deployment/authentication diagram fixes issuer/audience, tenant mapping, frontend runtime and Alembic ownership before implementation depends on them.

## Source requirement and present-state evidence

Source requirements: `REQ-STACK`, `REQ-TENANT`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). The inspected runtime is Vinext 1.0.0-beta.5 with React 19.2.6, Vite and next/navigation imports. app/chatgpt-auth.ts is an unauthenticated scaffold; db/schema.ts is empty and drizzle.config.ts targets local SQLite. No live BuyerOS domain backend was found.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **platform**; phase **P0**.
- Required predecessor evidence: `BO-000`.
- Blockers: `B-IDENTITY`, `B-HOST`, `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **Existing application files to modify: none.** New backend/planning files are explicitly proposed below; this is not a claim that those services already exist.

- **PROPOSED new file:** `docs/buyeros/decisions/BO-001-runtime-identity.md`

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Preserve Vinext/React/TypeScript and pnpm@11.25.0; verify the current supported frontend hosting path, keeping Sites unchanged. Vercel compatibility is a validation question, not permission for a Next.js migration.

2. Select managed Auth0 OIDC provisionally, browser authorization-code/PKCE with in-memory access token and API bearer verification; confirm issuer, audience, redirect origins, session expiry/revocation, operator/reviewer/viewer/admin mapping and tenant-membership authority without secrets.

3. Confirm separate FastAPI API and Celery/LangGraph worker hosting supports long-running processes, restart semantics, outbound restrictions and one Valkey queue. Document actual current hosting limits from official sources; no provisioning.

4. Choose PostgreSQL/Neon proposed region and private S3-compatible store; reserve SQLAlchemy/Alembic as the only domain-table migration owner. Existing SQLite scaffold remains unused for BuyerOS domain records; any removal is a separately reviewed change.

5. Record owner sign-off or precise blockers on identity provider, region/retention/controller, infrastructure ceiling and staging URL. No new domain Node BFF, Kubernetes, vector service or secondary queue.

## API, schema and state changes

Proposed bearer security scheme and workspace membership contract; no resources created.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`identity_decision = {issuer: <owner-verified>, audience: <owner-verified>, membership_source: postgres, browser_flow: authorization_code_pkce}`. Missing issuer/audience leaves live authentication disabled.

## Failure and concurrency cases

If Vinext target hosting cannot be supported, stop and propose a scoped hosting ADR before changing framework. Missing OIDC issuer/audience or unclear membership source blocks API authentication work.

- Scenario 1: Decision has one architecture and one migration owner, with each choice labelled verified/proposed.
- Scenario 2: A sequence for login, expiry, revocation and workspace switching names server checks.
- Scenario 3: Documented resource/region choices are approved or explicitly blocked; no credentials appear.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-001-01:** Decision has one architecture and one migration owner, with each choice labelled verified/proposed.
- **TEST-BO-001-02:** A sequence for login, expiry, revocation and workspace switching names server checks.
- **TEST-BO-001-03:** Documented resource/region choices are approved or explicitly blocked; no credentials appear.

This is a documentation/approval or environment-dependent operations task: no executable product verification command is asserted. Perform the named document/evidence acceptance checks; any future operational command must be recorded against the approved environment before execution. **Product checks: NOT RUN.**

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Supersede the ADR; no runtime or cloud rollback needed.

## Effort assumptions

**6–12 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-001 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-001-approve-the-runtime-identity-deployment-and-migration-decision-record.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; planning pack committed at 1512d4c17d4f792e14598d524fdac3c9c37d27e7; a source import of the audited content baseline is still expected, importing tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: One approved deployment/authentication diagram fixes issuer/audience, tenant mapping, frontend runtime and Alembic ownership before implementation depends on them. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

