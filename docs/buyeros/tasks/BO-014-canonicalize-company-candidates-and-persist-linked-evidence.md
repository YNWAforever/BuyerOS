---
task_id: "BO-014"
title: "Canonicalize company candidates and persist linked evidence"
phase: "P3"
status: "BLOCKED"
priority: "P1"
source_requirements: ["REQ-EVIDENCE","REQ-DATA","REQ-BUYERS"]
depends_on: ["BO-008","BO-012","BO-013"]
blocked_by: ["B-APPROVAL"]
base_commit: "b804ba8d1514a1049b7202c861278dd72c473a75"
plan_revision: "v1"
owner_role: "ai"
files_to_read: ["data/demo/fixtures.ts","services/contracts.ts","features/buyers/detail.tsx","docs/buyeros/00_README_AND_DECISIONS.md","docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md"]
existing_files_to_modify: ["features/buyers/detail.tsx"]
dependency_output_files_to_modify: ["services/api/buyeros_api/models/core.py", "services/worker/buyeros_worker/tasks.py", "services/live/client.ts", "services/api/buyeros_api/routes/buyers.py"]
proposed_files_to_create: ["services/worker/buyeros_worker/research/canonicalize.py","services/worker/buyeros_worker/research/evidence.py","services/api/alembic/versions/0005_research_evidence.py","services/worker/tests/test_identity_evidence.py"]
forbidden_paths_or_actions: ["No implementation without explicit selected-task Build approval","Preserve unrelated changes and applicable repository instructions","No automatic commits/push/deploy/cloud resources/paid provider calls/mailboxes/messages","No active AGENTS.md or OpenCode configuration changes outside separately approved scope","No second domain backend, queue, migration owner or replacement frontend"]
contract_refs: ["03_DATA_API_AND_STATE_CONTRACTS.md"]
migration_impact: "PROPOSED additive migration; serialize through sole Alembic owner; execution only on approved disposable/staging DB"
external_capabilities: []
external_spend_authorized: false
acceptance_tests: ["TEST-BO-014-01","TEST-BO-014-02","TEST-BO-014-03"]
verification_commands: [{"command":"uv run python -m pytest tests/test_identity_evidence.py","working_directory":"services/worker","status":"PROPOSED_AFTER_TASK / NOT RUN","expected_result":"Canonicalization, concurrency, provenance and retention tests pass"}]
rollback_or_rollforward: "Keep merge decisions reversible; detach erroneous alias mapping and rebuild project assessments via versioned repair, preserving raw sources/ledger."
effort_range_hours: [20,34]
---

# BO-014 — Canonicalize company candidates and persist linked evidence

**Planning status:** BLOCKED. No implementation is approved or complete. All implementation checks below are **NOT RUN** in this planning session. Dependencies need recorded completion evidence; task approval is separate from dependency completion.

## Observable objective

Duplicate observations resolve to reviewable tenant-local company identities and every important assessment fact can cite versioned permitted evidence.

## Source requirement and present-state evidence

Source requirements: `REQ-EVIDENCE`, `REQ-DATA`, `REQ-BUYERS`; definitions are in [the phased plan](../04_PHASED_IMPLEMENTATION_PLAN.md). fixtures exports rawCandidates and 24 fictional Company records; evidence type has excerpt/language/date/requirement but lacks full live source URL/hash/retention/versioning. BuyerDetail already surfaces contrary evidence and unknowns.

The source baseline is GitHub `b804ba8d1514a1049b7202c861278dd72c473a75`, corroborated against Sites source-tree commit `76892126c86031bfe8e7ab517adba7f306040313`. SOURCE_VERIFIED statements above describe inspected files; historical developer test claims are not current test results. See [source/UI audit](../01_SOURCE_AND_UI_AUDIT.md) for browser evidence and limits.

## Dependencies, blockers and ownership

- Owner: **ai**; phase **P3**.
- Required predecessor evidence: `BO-008`, `BO-012`, `BO-013`.
- Blockers: `B-APPROVAL`.
- Any new file listed below is **PROPOSED** at the audited commit. If a predecessor or newer user work now created it, inspect and reconcile before editing; do not overwrite it as if new.
- Only disjoint file work may run concurrently. Serialize shared contracts, migrations, `features/workspace.tsx` wiring, budget/provider-operation logic and task integration.

## Exact modification scope

- **EXISTING, inspected:** `features/buyers/detail.tsx`

- **PROPOSED new file:** `services/worker/buyeros_worker/research/canonicalize.py`
- **PROPOSED new file:** `services/worker/buyeros_worker/research/evidence.py`
- **PROPOSED new file:** `services/api/alembic/versions/0005_research_evidence.py`
- **PROPOSED new file:** `services/worker/tests/test_identity_evidence.py`

**PROPOSED predecessor outputs to modify after their creating task completes** (not existing at the audited commit):

- `services/api/buyeros_api/models/core.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/worker/buyeros_worker/tasks.py` — inspect producer-task result first; modify only this task's required wiring.
- `services/live/client.ts` — inspect producer-task result first; modify only this task's required wiring.

- **PROPOSED predecessor output to modify:** `services/api/buyeros_api/routes/buyers.py`

Read the files in YAML `files_to_read` plus actual prerequisite outputs. A proposed document referenced by a later task is a dependency output, not evidence that it already exists. Existing runtime/agent configuration is not implicitly in scope.

## Code-level implementation steps

1. Normalize URLs/domains (case, IDNA, registrable domain rules, tracking removal) and legal-name/market signals; use deterministic exact trusted aliases as candidates, not domain-only automatic legal entity merge.

2. Create explicit canonicalization decisions with evidence and reversible aliases; fuzzy/brand-shared-domain matches go to review. Use uniqueness/concurrency constraints to prevent duplicate company inserts without wrongly merging legal entities.

3. Persist raw-candidate→company→project-buyer relation; lists and counts reference project buyers/unique companies, never person rows.

4. Create source/evidence records with retrieval timestamp, URL/provider ID, hash, original language, optional labelled translation, support/contradiction requirement, observation/inference and retention/expiry.

5. Validate evidence belongs to same tenant/run/profile context and excerpts are anchored to source. Deleted/expired/inaccessible sources mark dependent assessments stale/unknown and later approvals invalid.

6. Map live source actions into existing drawer/full page safely while preserving synthetic in-app sources in demo; do not invent third-party logos.

## API, schema and state changes

Buyer evidence GET returns immutable provenance/versioned citations; canonical decisions and source lifecycle internal. Additive research/evidence tables.

Use [the proposed OpenAPI](../contracts/openapi.proposed.yaml) and [state/data contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) as the coordinated boundary. Client/server disagreement requires a reviewed contract revision; do not invent a parallel endpoint. Public request/response examples are in that contract; task-specific state/failure examples are below.

## Concrete request/state example

`raw_candidates=26 → canonical companies=24` in the named demo regression; a separate fixture with two legal entities sharing one brand domain stays at two companies.

## Failure and concurrency cases

Same domain can contain independent subsidiaries; two concurrent discoveries must not create duplicate or over-merge. Cross-tenant evidence ID tampering fails; expired source cannot support a fresh confident claim.

- Scenario 1: 26 raw fixture candidates resolve to 24 canonical companies while shared-domain distinct-entity counterexample stays separate.
- Scenario 2: Concurrent identical candidate creates one canonical relation; alias decision remains auditable/reversible.
- Scenario 3: Tampered/missing/expired source IDs fail evidence linkage and UI shows unknown/stale instead of factual claim.

No timeout may be treated as proof of provider non-acceptance. No live API error may return demo fixtures. These shared invariants apply wherever this task touches external operations or live state.

## Acceptance tests and verification

- **TEST-BO-014-01:** 26 raw fixture candidates resolve to 24 canonical companies while shared-domain distinct-entity counterexample stays separate.
- **TEST-BO-014-02:** Concurrent identical candidate creates one canonical relation; alias decision remains auditable/reversible.
- **TEST-BO-014-03:** Tampered/missing/expired source IDs fail evidence linkage and UI shows unknown/stale instead of factual claim.

| Command | Working directory | Status | Expected result |
|---|---|---|---|
| `uv run python -m pytest tests/test_identity_evidence.py` | `services/worker` | PROPOSED_AFTER_TASK / NOT RUN | Canonicalization, concurrency, provenance and retention tests pass |

`repo` means the confirmed BuyerOS implementation checkout, never this standalone planning-output directory. `PROPOSED_AFTER_TASK` commands require the declared files/tooling to exist and their side effects to be reviewed first. Abort tests if the target is production, credentials enable paid APIs, or a command would migrate unapproved data. No invented `pnpm test` script is assumed. Python projects use proposed pinned uv environments. Current `pnpm build` / `pnpm lint` definitions can be rechecked and used only after safe scope review; their existence is not a passing result.

## Rollback or roll-forward

Keep merge decisions reversible; detach erroneous alias mapping and rebuild project assessments via versioned repair, preserving raw sources/ledger.

## Effort assumptions

**20–34 engineering hours**, excluding owner review waits, account provisioning, live-provider charges, procurement/legal review and unexpected source changes. Assumes the pinned frontend structure, approved contract, one API, one worker/queue, one managed identity approach, PostgreSQL and a small pilot. If a material assumption fails, stop and re-estimate the task rather than silently expanding scope.

## Task-specific OpenCode prompt

```text
Use OpenCode Plan for BO-014 only. Read applicable repository instructions, docs/buyeros/00_README_AND_DECISIONS.md, docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md, docs/buyeros/tasks/BO-014-canonicalize-company-candidates-and-persist-linked-evidence.md, its contract_refs, and the latest progress record. Verify YNWAforever/BuyerOS (canonical; the audited source is imported at commit b804ba8d1514a1049b7202c861278dd72c473a75 (tree b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1), merged into main via 72fef7da785624a35bb6701f1451ebcf0184a089), current HEAD/diff against the audited content baseline b804ba8d1514a1049b7202c861278dd72c473a75, and preserve unrelated changes. Confirm prerequisites and resolve listed blockers with evidence. Objective: Duplicate observations resolve to reviewable tenant-local company identities and every important assessment fact can cite versioned permitted evidence. Propose only the listed file scope and acceptance tests; do not implement in Plan. Do not assume dependencies are complete or this manifest is a native execution engine. After explicit approval of this task, use Build only for the approved scope, run the relevant verified-safe commands, and record exact results, changed files, migrations and remaining risks. Stop and replan if source, contracts, licensing, provider capabilities or cost bounds materially differ. No paid calls, infrastructure, deployment, sending, mailbox connection, push or active agent configuration changes without separate explicit authorization.
```

## Required completion evidence

Record reviewed base/current commit and starting diff; explicit task approval reference; predecessor evidence; exact changed/proposed files; applicable instruction compliance; contract/migration revision; commands with output/exit code and environment target; acceptance test results including NOT RUN; cost/provider proof only if separately authorized; rollback verification; remaining blockers and next eligible task. Update progress without claiming unimplemented dependencies DONE. Do not commit, push, deploy or activate delivery as a completion shortcut.

