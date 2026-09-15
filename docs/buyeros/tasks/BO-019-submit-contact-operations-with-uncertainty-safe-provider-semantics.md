---
task_id: "BO-019"
title: "Submit contact operations with uncertainty-safe provider semantics"
phase: "P4"
status: "BLOCKED"
priority: "P1"
source_requirements: ["REQ-PROVIDER","REQ-RECOVERY","REQ-BUDGET"]
depends_on: ["BO-018"]
blocked_by: ["B-PROVIDERS","B-POLICY","B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "backend"
files_to_read: ["services/mock-client.ts","features/workspace.tsx","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: []
dependency_output_files_to_modify: ["services/worker/buyeros_worker/tasks.py"]
proposed_files_to_create: ["services/worker/buyeros_worker/providers/contact.py","services/worker/buyeros_worker/enrichment/dispatch.py","services/worker/tests/test_contact_dispatch.py"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["03_DATA_API_AND_STATE_CONTRACTS.md","02_ARCHITECTURE_AND_REUSE.md"]
migration_impact: "none; if current source requires an unlisted migration stop and revise task"
external_capabilities: ["Verified provider contracts and deterministic fixtures; no live calls authorized"]
external_spend_authorized: false
acceptance_tests: ["TEST-BO-019-01","TEST-BO-019-02","TEST-BO-019-03"]
verification_commands: [{"command":"uv run python -m pytest tests/test_contact_dispatch.py","working_directory":"services/worker","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"Deterministic provider stub proves submission, lease, cancellation and uncertainty behavior"}]
rollback_or_rollforward: "Stop contact dispatcher and revoke dispatch capability if needed; continue read-only reconciliation. Never bulk-release unknown funds or blindly replay paid operations."
effort_range_hours: [24,40]
---

# BO-019 — Submit contact operations with uncertainty-safe provider semantics

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

An approved reserved operation is submitted at most once in effect when supported, or becomes explicitly unknown without blind retry when acceptance cannot be determined.

## Source requirement and present-state evidence

Source requirements: `REQ-PROVIDER`, `REQ-RECOVERY`, `REQ-BUDGET`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). The current contact result is based on numeric demo buyer ID modulo values in mock-client:confirm. No production provider contract, idempotency or status capability is implemented.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **backend**; phase **P4**.
- Required predecessor evidence: `BO-018`.
- Blockers: `B-PROVIDERS`, `B-POLICY`, `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **Existing application files to modify: none.** New backend/planning files are explicitly proposed below; this is not a claim that those services already exist.

- **PROPOSED new file:** `services/worker/buyeros_worker/providers/contact.py`
- **PROPOSED new file:** `services/worker/buyeros_worker/enrichment/dispatch.py`
- **PROPOSED new file:** `services/worker/tests/test_contact_dispatch.py`

**PROPOSED predecessor outputs to modify after their creating task completes** (not existing at the audited commit):

- `services/worker/buyeros_worker/tasks.py` — inspect producer-task result first; modify only this task's required wiring.

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Implement exactly one provider adapter from BO-002's verified endpoint/schema/capabilities; use server-only credentials and retained license notices. No guessed inbound upstream interface.

2. Claim operation with DB lease and attempt ID; persist submitting intent/correlation before the external call. Recheck acceptance/current fit/research policy/suppression and cancellation immediately before dispatch.

3. Attach provider-supported idempotency/correlation key where verified. Store minimal request hash/provider request ID/status/price snapshot; do not log returned personal data.

4. Bound timeout/concurrency/retry; confirmed rejection-before-acceptance can follow documented safe retry policy. Timeout, connection loss after send or worker death after acceptance enters unknown with reservation retained.

5. If provider supports authoritative status, reconcile before any resubmission. If it lacks both idempotency/status, prohibit automatic retry; contact capability stays blocked unless a safe bounded manual reconciliation procedure is approved.

6. Cancellation before dispatch prevents call and safely releases unsubmitted amount. In-flight cancellation only stops future work, retaining pending/unknown charge and late-result gates.

## API, schema and state changes

Internal provider submit request/response; enrichment reserved→submitting→pending/found/not_found/failed/unknown. Job state records unknown and the next reconciliation action; the public getEnrichmentJob read route is wired by BO-020.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`provider_operation reserved→submitting→unknown` after request timeout preserves the upper bound. Worker restart consults verified status/idempotency before any further submission.

## Failure and concurrency cases

Crash precisely after provider acceptance before DB acknowledgement must not cause second purchase. Late lease holder cannot overwrite newer result; idempotency mismatch is incident, not retry.

- Scenario 1: Inject crash after provider accepted: reservation persists and restarted worker reconciles instead of resubmitting.
- Scenario 2: Cancellation before dispatch yields no call; cancellation after dispatch retains charge uncertainty.
- Scenario 3: Suppression/policy changed before submit prevents call; unsupported provider capability prevents adapter activation.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-019-01:** Inject crash after provider accepted: reservation persists and restarted worker reconciles instead of resubmitting.
- **TEST-BO-019-02:** Cancellation before dispatch yields no call; cancellation after dispatch retains charge uncertainty.
- **TEST-BO-019-03:** Suppression/policy changed before submit prevents call; unsupported provider capability prevents adapter activation.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `uv run python -m pytest tests/test_contact_dispatch.py` | `services/worker` | PROPOSED_AFTER_TASK / NOT RUN | Deterministic provider stub proves submission, lease, cancellation and uncertainty behavior |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Stop contact dispatcher and revoke dispatch capability if needed; continue read-only reconciliation. Never bulk-release unknown funds or blindly replay paid operations.

## Effort assumptions

**24–40 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-019 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-019-submit-contact-operations-with-uncertainty-safe-provider-semantics.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; planning pack committed at 1512d4c17d4f792e14598d524fdac3c9c37d27e7; a source import of the audited content baseline is still expected, importing tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: An approved reserved operation is submitted at most once in effect when supported, or becomes explicitly unknown without blind retry when acceptance cannot be determined. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

