---
task_id: "BO-012"
title: "Safely ingest offer files and fetch permitted web evidence"
phase: "P2"
status: "BLOCKED"
priority: "P0"
source_requirements: ["REQ-FETCH","REQ-EVIDENCE","REQ-SECURITY"]
depends_on: ["BO-007","BO-009","BO-011"]
blocked_by: ["B-HOST","B-POLICY","B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "platform"
files_to_read: ["features/discovery/wizard.tsx","features/buyers/detail.tsx","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: ["features/discovery/wizard.tsx"]
dependency_output_files_to_modify: ["services/api/buyeros_api/main.py", "services/api/buyeros_api/models/core.py", "services/live/client.ts", "services/worker/pyproject.toml", "services/worker/uv.lock"]
proposed_files_to_create: ["services/api/buyeros_api/routes/documents.py","services/api/buyeros_api/services/storage.py","services/worker/buyeros_worker/fetch.py","services/worker/buyeros_worker/parse_document.py","services/worker/tests/test_safe_fetch_upload.py"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["contracts/openapi.proposed.yaml","03_DATA_API_AND_STATE_CONTRACTS.md"]
migration_impact: "none; if current source requires an unlisted migration stop and revise task"
external_capabilities: []
external_spend_authorized: false
acceptance_tests: ["TEST-BO-012-01","TEST-BO-012-02","TEST-BO-012-03"]
verification_commands: [{"command":"uv run python -m pytest tests/test_safe_fetch_upload.py","working_directory":"services/worker","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"Network/parser fixture cases pass with network denied except local test harness"}]
rollback_or_rollforward: "Disable ingestion/fetch capability, quarantine suspect objects and rotate affected signed-url policy. Retain metadata needed for deletion/audit; no broad bucket-public fallback."
effort_range_hours: [24,40]
---

# BO-012 — Safely ingest offer files and fetch permitted web evidence

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

A validated private offer upload or permitted source fetch produces a provenance-bearing sanitized document under strict size/network/parser limits.

## Source requirement and present-state evidence

Source requirements: `REQ-FETCH`, `REQ-EVIDENCE`, `REQ-SECURITY`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). Wizard file picker accepts PDF/TXT/Markdown <=5MB, reads text locally, and explicitly says PDF extraction is unconnected. BuyerDetail opens synthetic source panels, not real retrieved URLs.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **platform**; phase **P2**.
- Required predecessor evidence: `BO-007`, `BO-009`, `BO-011`.
- Blockers: `B-HOST`, `B-POLICY`, `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **EXISTING, inspected:** `features/discovery/wizard.tsx`

- **PROPOSED new file:** `services/api/buyeros_api/routes/documents.py`
- **PROPOSED new file:** `services/api/buyeros_api/services/storage.py`
- **PROPOSED new file:** `services/worker/buyeros_worker/fetch.py`
- **PROPOSED new file:** `services/worker/buyeros_worker/parse_document.py`
- **PROPOSED new file:** `services/worker/tests/test_safe_fetch_upload.py`

**PROPOSED predecessor outputs to modify after their creating task completes** (not existing at the audited commit):

- `services/api/buyeros_api/main.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/api/buyeros_api/models/core.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/live/client.ts` — inspect producer-task result first; modify only this task's required wiring.
- `services/worker/pyproject.toml` — inspect producer-task result first; modify only this task's required wiring.
- `services/worker/uv.lock` — inspect producer-task result first; modify only this task's required wiring.

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Implement the contract's uploadOfferDocument multipart endpoint with quarantine/private object storage; server validates file size, content signature/type and workspace association. Do not invent separate upload-session/finalization endpoints. No public bucket, browser credentials or accepting extension alone.

2. Parse allowed formats in an isolated worker with time/memory/bytes/page limits; prohibit unsafe archives/executable content. Preserve manual offer facts and expose extraction errors instead of fabricating results.

3. Build shared safe fetch with HTTPS/scheme policy, resolved public-IP validation for IPv4/IPv6, DNS rebinding protection, same checks on every redirect, disallowed metadata/private/link-local endpoints and bounded redirects/body/decompression/time/concurrency.

4. Minimize outgoing provider data and forbid webpage text from choosing new tools/destinations. Respect authorized source access/retention constraints; authenticated/paywalled content is not bypassed.

5. Persist original URL/provider ID, retrieval time, content hash, original language, permitted retention and parse status. Signed downloads bind workspace/object/expiry and reauthorize before issue.

6. Wire wizard actual upload/extraction status and editable extracted facts with source references; retain explicit local-only behavior in demo. Render excerpts as text/sanitized content.

## API, schema and state changes

The contract's uploadOfferDocument multipart upload, ingestOfferUrl and document status/deletion operations; async parsing queued durably. Signed retrieval follows the approved storage boundary; any new public operation requires contract revision first. Documents uploaded→validating→parsed/rejected/failed/deleted.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`uploadOfferDocument` receives one multipart PDF <=5 MiB plus filename/content validation; response is a durable parsing job/document identity. A URL redirect to 169.254.169.254 is rejected before network fetch.

## Failure and concurrency cases

SSRF redirect/rebind, content-type mismatch, zip bomb, huge PDF, signed-URL misuse, malicious HTML and parser crash fail boundedly. Upload retries cannot create duplicate billed extraction.

- Scenario 1: Blocked IPv4/IPv6/private/metadata/rebind/redirect destinations never receive fetch traffic.
- Scenario 2: Oversized/mismatched/malicious docs reject; timeout terminates parser and retains honest status.
- Scenario 3: Workspace B cannot sign/download A object; rendered evidence cannot execute scripts.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-012-01:** Blocked IPv4/IPv6/private/metadata/rebind/redirect destinations never receive fetch traffic.
- **TEST-BO-012-02:** Oversized/mismatched/malicious docs reject; timeout terminates parser and retains honest status.
- **TEST-BO-012-03:** Workspace B cannot sign/download A object; rendered evidence cannot execute scripts.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `uv run python -m pytest tests/test_safe_fetch_upload.py` | `services/worker` | PROPOSED_AFTER_TASK / NOT RUN | Network/parser fixture cases pass with network denied except local test harness |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Disable ingestion/fetch capability, quarantine suspect objects and rotate affected signed-url policy. Retain metadata needed for deletion/audit; no broad bucket-public fallback.

## Effort assumptions

**24–40 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-012 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-012-safely-ingest-offer-files-and-fetch-permitted-web-evidence.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; the audited source is imported at commit b804ba8d1514a1049b7202c861278dd72c473a75 (tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), merged into main via 72fef7da785624a35bb6701f1451ebcf0184a089), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: A validated private offer upload or permitted source fetch produces a provenance-bearing sanitized document under strict size/network/parser limits. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

