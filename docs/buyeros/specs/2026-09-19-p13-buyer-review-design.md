# P13 design — durable buyer review (BO-008, Slice 1)

**Status: PROPOSED / PLAN ONLY.** Plan revision v1. Recorded 2026-09-19 (Hong Kong).

No application code, lockfile, dependency install, migration, cloud resource, deployment, Site access change, paid provider call, mailbox connection, message, or send is authorized by this document. Execution happens only under an explicit dependency waiver, on the separately approved task.

Related records: [P9 API surface](2026-09-15-p9-api-surface-design.md), [P10 bearer identity](2026-09-16-p10-bearer-identity-design.md), [P11 demo/live adapter](2026-09-17-p11-demo-live-adapter-design.md), [P12 project/profile writes](2026-09-18-p12-project-profile-writes-design.md), [BO-008 task](../tasks/BO-008-persist-buyer-evidence-views-reviews-stable-selections-and-lists.md), [03 contracts](../03_DATA_API_AND_STATE_CONTRACTS.md), [contracts/openapi.proposed.yaml](../contracts/openapi.proposed.yaml).

**Base: P12.** This phase extends the P12 write surface. It branches from `p12-project-profile-writes` (which contains `p11-demo-live-adapter` @ `cf20b1a` and `main` @ `d159ae9`), so its pull request targets `p12-project-profile-writes` until P12 merges, then `main`. Branching from `main` would not compile.

## Scope

Make buyer review durable: freeze a bounded, filtered selection into a server-owned snapshot, read it back paged, and persist human review (accept / reject / needs-information) and notes/owner against the exact frozen versions, while company evidence stays intact.

**What exists today.** `0003_p2_tables.py` already creates `companies`, `project_buyers`, `source_documents`, `evidence`, `fit_assessments`, `human_reviews`, `buyer_lists`, `list_memberships`, `buyer_snapshots`, `buyer_snapshot_items`. `listBuyers`/`getBuyer` (P9) already read from a snapshot but return identity + note only, and `createBuyerSnapshot`, `updateBuyer`, `reviewBuyers`, `listBuyerEvidence` and `getEvidence` are all in the P9 `501` registry. `ProjectBuyer` has no `version`, so the contract's optimistic-concurrency token cannot be supplied yet. The frontend buyer table/drawer is demo-only local state.

**Relationship to BO-008.** The task document is materially stale: it lists `services/api/buyeros_api/main.py`, `models/core.py` and a Playwright spec that do not match the repository, and records `migration_impact: none` although `ProjectBuyer.version` (and the idempotency response store below) need a migration. This phase is **Slice 1** of BO-008. **Slice 2** (buyer lists: `createBuyerList`/`listBuyerLists`/`getBuyerList`/`renameBuyerList`/`changeListMemberships`, and filter presets: `listFilterPresets`/`saveFilterPreset`) is explicitly deferred, as is acceptance test TEST-BO-008-02 which depends on lists.

## A. Boundaries and units

```
services/api/buyeros_api/api/routes/buyers.py     MOD  createBuyerSnapshot, fuller listBuyers/getBuyer, updateBuyer, evidence reads
services/api/buyeros_api/api/routes/reviews.py    NEW  reviewBuyers
services/api/buyeros_api/api/schemas.py           MOD  SnapshotCreate/BuyerFilters, ReviewRequest/Selection, BuyerUpdate
services/api/buyeros_api/api/idempotency.py       MOD  optional stored response for bulk replay
services/api/buyeros_api/services/buyer_selection.py NEW  filter -> ordered snapshot materialization
services/api/buyeros_api/services/buyer_view.py   NEW  Buyer / Evidence response shapers
services/api/buyeros_api/db/buyers.py             MOD  ProjectBuyer.version
services/api/buyeros_api/db/contact.py            MOD  IdempotencyRecord.response
services/api/buyeros_api/api/unimplemented.py     MOD  the seven operations leave the registry
services/api/alembic/versions/0011_...py          NEW  project_buyers.version + idempotency_records.response
services/api/tests/test_buyer_review_db.py        NEW  persistence, selection, review, evidence
services/live/mapping.ts                          MOD  buyer/evidence mappers
features/live/buyers.tsx                          NEW  live table (snapshot -> pages -> selection -> review)
features/live/buyer-detail.tsx                    NEW  live drawer (evidence, note editor; owner deferred)
features/workspace.tsx                            MOD  live discover route renders the live buyers table
tests/live-adapter-checks.mjs                     MOD  mapper and selection checks
```

Each unit has one job. `buyer_selection.py` turns filters into an ordered snapshot and nothing else. `buyer_view.py` shapes `Buyer`/`Evidence` responses and nothing else. The routes authorise, persist and shape. The `.tsx` files render. The mappers map.

## B. Data model, versioning and immutability

**Migration `0011_project_buyer_version`** (reversible) adds:

- `project_buyers.version` — `Integer`, NOT NULL, `server_default "1"`. Unlike P12's profile columns, the server default is **kept** so a raw insert still defaults to 1; the model declares `default=1, server_default="1"`. It is the buyer's optimistic-concurrency token: `updateBuyer`'s `If-Match` and each `Selection` item's `version`.
- `idempotency_records.response` — `JSONB`, nullable. The P4 idempotency row stores a `resource_id`; a bulk operation has no single resource, so it stores its committed result here and a same-key/same-body replay returns it verbatim.

The same migration also widens `human_reviews.reason` to `varchar(2000)` so the contract's review `reason` (3..2000) is storable; its downgrade truncates with `USING left(reason, 400)` so it stays reversible on a database that already holds a long reason. No other schema change is required: every other table exists.

**Human review is append-only.** `reviewBuyers` never edits or deletes a `human_reviews` row; the current review is the newest row for the buyer. `fit_assessments` remain immutable and separate from human review. Removing or changing a review is a new review event, not a deletion.

**Snapshot immutability.** `buyer_snapshots` + `buyer_snapshot_items` freeze ordered `(buyer_id, buyer_version)` pairs. The snapshot's order and membership never expand when new buyers appear; a reader pages the frozen items by `ordinal`.

**Owner mapping.** The contract carries `owner_membership_id`, but `project_buyers` stores `owner_user_id`. The write path validates the incoming `owner_membership_id` is an active membership of the workspace and stores that membership's `user_id`; the read path resolves and emits the membership id for `(workspace_id, user_id)`, emitting `null` when the owner has no active membership in that workspace. No new column.

## C. API contract details

| Operation | Method and path | Permitted roles | Idempotency | Version |
|---|---|---|---|---|
| `createBuyerSnapshot` | POST `/v1/workspaces/{ws}/projects/{p}/buyer-snapshots` | viewer/operator/reviewer/workspace_admin | Required | none |
| `listBuyers` | GET `/v1/workspaces/{ws}/projects/{p}/buyers` | viewer+ | Read-only | none |
| `getBuyer` | GET `/v1/workspaces/{ws}/buyers/{buyer_id}` | viewer+ | Read-only | none |
| `updateBuyer` | PATCH `/v1/workspaces/{ws}/buyers/{buyer_id}` | operator/reviewer/workspace_admin | Required | `If-Match` |
| `reviewBuyers` | POST `/v1/workspaces/{ws}/projects/{p}/buyer-reviews` | reviewer/workspace_admin | Required | per item |
| `listBuyerEvidence` | GET `/v1/workspaces/{ws}/buyers/{buyer_id}/evidence` | viewer+ | Read-only | none |
| `getEvidence` | GET `/v1/workspaces/{ws}/evidence/{evidence_id}` | viewer+ | Read-only | none |

**Request bodies are strict Pydantic v2 models** (`extra="forbid"`, explicit nulls rejected): `SnapshotCreate{filters, sort∈{best_fit,name_asc}, requested_limit 1..1000}`, `BuyerFilters` (all optional), `ReviewRequest{selection, status∈{accepted,rejected,needs_information}, reason 3..2000}`, `Selection` = `explicit{buyers:[{id,version}] 1..1000}` | `snapshot{snapshot_id, excluded_ids[]}`, and `BuyerUpdate{note?, owner_membership_id?}` with `minProperties: 1`.

**Response shape is the contract's `Buyer` subset** — every emitted key is contract-declared; omitted keys are recorded deferrals (P9 precedent):

- emitted: `id`, `workspace_id`, `version`, `created_at`, `updated_at`, `data_mode`, `project_id`, `company_id`, `name` (company `display_name`), `normalized_domain` (company `domain`), `contact_research_status` (`"not_researched"` literal), `suppressed` (`false` literal), `owner_membership_id`, `note`, `evidence_count`, `fit` when a row exists, and `review` only when the review's assessment is known (`fit` present and `review.fit_assessment_id` set) — so an emitted `review` always carries its contract-required `assessment_id` and `icp_version_id`. A review recorded on a buyer with no fit assessment is stored but omitted from the response until an assessment exists.
- omitted: `market`, `buyer_type` (P3 normalization), `contacts` (P4), `policies` (P5).

`BuyerSnapshot` returns `id`, `workspace_id`, `project_id`, `actor_id`, `filters_hash`, `sort`, `total` (the number of materialized items, i.e. the frozen selection size), `created_at`, `expires_at`, `snapshot_version` (literal `1`), `result_limit_reached` (the matched set was larger than `requested_limit`). `BulkResult` returns `requested`, `updated`, `blocked`, `conflicts`, `results:[{id,status∈{updated,unchanged,blocked,conflict},reason_code?,version?}]`. `Evidence` returns `id`, `workspace_id`, `project_id`, `company_id`, `source_document_id`, `version` (literal `1`), `source_url`, `excerpt`, `original_language`, `retrieved_at`, `kind`, `requirement_id`, `relationship`, `status` (`"available"` literal), `data_mode`, plus translation fields when present.

**Error mapping:** missing/malformed `Idempotency-Key`/`If-Match` → `400 INVALID_REQUEST`; body validation, unsupported filter, invalid owner → `422 INVALID_REQUEST`; insufficient role → `403 PERMISSION_DENIED`; absent or foreign project/buyer/snapshot/evidence → non-enumerating `404 NOT_FOUND`; same key with a different body → `409 IDEMPOTENCY_CONFLICT`; stale buyer version → `412 STALE_REVISION`.

**Contract-first bookkeeping.** The seven operations leave `UNIMPLEMENTED_OPERATIONS`; the P9 registry test is updated in lockstep and must not be loosened; the response-subset test gains the new `Buyer` fields.

## D. Snapshot materialization and review semantics

**Materialization.** The base set is the active `ProjectBuyer` rows for `(workspace_id, project_id)`. Supported filters: `q` (company `display_name` ILIKE), `fit` (newest `FitAssessment.verdict`), `review` (newest `HumanReview.state`), `owner_membership_id`, and `evidence_retrieved_after` (via `evidence` joined to `source_documents.retrieved_at`). A non-empty deferred filter (`markets`, `buyer_types`, `contact`, `suppressed`, `source_types`, `run_id`, `list_id`) is rejected with `422` naming the field — a filter is never silently dropped. `source_types` is deferred because neither `evidence` nor `source_documents` carries a source-type column until P3/BO-014 ingestion. Order is deterministic: `best_fit` ranks verdict (`match` > `needs_review` > `not_a_match` > none) then `display_name` then `buyer_id`; `name_asc` orders `display_name` then `buyer_id`. Materialize `min(matched, requested_limit)` rows; `result_limit_reached = matched > requested_limit`. `filters_hash` is a canonical hash of the normalized filters and sort. `expires_at = now + 15 minutes`. Creation is idempotent under a project-scoped operation id (`createBuyerSnapshot:<project_id>`), so the same key on a different project cannot replay another project's snapshot; a replay re-reads the recorded snapshot. `reviewBuyers` is scoped the same way (`reviewBuyers:<project_id>`).

**listBuyers.** Loads the snapshot scoped to `(workspace, project, id)`; a missing or expired snapshot is `404` (the client refreshes with a new explicit selection). It pages `buyer_snapshot_items` by `ordinal` and joins the current `ProjectBuyer`/`Company`; `total` is the item count. A buyer created after the snapshot is not in it (TEST-BO-008-01).

**updateBuyer.** Under the P12 idempotency rule and an `If-Match` equal to the buyer `version`: a replay returns the current buyer without a second bump; a stale `If-Match` is `412`; success persists the note/owner and increments `version`. `note` is bounded to the column length (`4000`); `owner_membership_id` must be an active workspace membership.

**reviewBuyers.** Resolve the selection: `explicit` items carry `(id, version)`; `snapshot` items are expanded by `ordinal` with `excluded_ids` removed and `buyer_snapshot_items.buyer_version` as the expected version. For each item, under `FOR UPDATE`: a buyer not in this project → `blocked`; a version mismatch → `conflict` (the previous record and version are preserved); the buyer already in the requested state → `unchanged`; otherwise append a `human_reviews` row and increment `version` → `updated`. The response rechecks and reports every item; no success may conceal a blocked or conflicting row. The whole request is idempotent; because re-deriving would re-apply, the committed `BulkResult` is stored in `idempotency_records.response` and returned verbatim on a same-key/same-body replay.

**Evidence.** `listBuyerEvidence` loads the buyer scoped (foreign → `404`) and pages `evidence` for the buyer's project and company ordered by `created_at`/`id`; `getEvidence` loads one by `(workspace, id)`, foreign → `404`.

## E. Client and UI

`services/live/mapping.ts` gains strict `toBuyerPage`/`toEvidence`/`toEvidencePage` and a widened `toBuyers` (all raising `MapError` on a missing required field, never coercing). `features/live/buyers.tsx` creates one snapshot for the selected workspace/project, pages `listBuyers`, and renders rows with page-vs-all-filtered selection; its review bar calls `reviewBuyers`. `features/live/buyer-detail.tsx` shows evidence and a **note editor** that calls `updateBuyer` with `If-Match`; an **owner control is deferred** because live mode has no membership picker (recorded in the approval record). Both surface `LiveError`/`MapError` honestly and never fall back to demo data. `features/workspace.tsx` renders `LiveBuyers` on the discover route and extends the P12 route-aware availability gate so overview, wizard and buyers are available while lists/outreach/results/settings remain unavailable; `services/live/mode.ts` and the demo branch are byte-identical.

## F. Testing and acceptance mapping

**Backend** (pytest against the disposable PostgreSQL as the runtime role, so RLS is in force) covers: snapshot materialization, order, limit and `result_limit_reached`; deferred-filter `422`; `expired`/foreign snapshot `404`; a buyer added after the snapshot is excluded; `updateBuyer` version/`If-Match`/`412`/`409`/replay; `reviewBuyers` explicit and snapshot selections, per-item `conflict`/`blocked`/`unchanged`, reviewer-only `403`, and a bulk replay that returns the stored result without a second bump; evidence scoping and `404`; and the cross-tenant `404` for a foreign buyer, snapshot and evidence.

**Frontend** extends the zero-dependency node harness with the buyer/evidence mappers and a pure page-vs-all-filtered selection helper. The live UI is verified by `tsc`, `eslint` and `pnpm build`, since a `.tsx` cannot be loaded by the harness and live mode is gated off.

| Criterion | In this phase | Deferred (recorded, NOT RUN) |
|---|---|---|
| **TEST-BO-008-01** all-filtered selection stays fixed when others add/review; cross-tenant IDs never mutate | snapshot materialization + frozen-order tests; cross-tenant `404` | live discovery producing new buyers |
| **TEST-BO-008-02** duplicate add yields one membership; removal retains evidence and company | — | the whole criterion: lists are Slice 2 |
| **TEST-BO-008-03** acceptance updates derived state; concurrent review conflict preserves the previous record/version | `reviewBuyers` state persistence + per-item version conflict | draft-approval invalidation (P5) |

## G. Out of scope and rollback

- **Lists** (`createBuyerList`/`listBuyerLists`/`getBuyerList`/`renameBuyerList`/`changeListMemberships`) and **filter presets** (`listFilterPresets`/`saveFilterPreset`) are Slice 2; `list_id` filtering is therefore rejected.
- **`contacts`, `policies`, `market`, `buyer_type`** and their filters wait on P3/P4/P5; suppression is a `false` literal until BO-009.
- **Discovery, runs and fit generation** remain `501`; `fit`/`review` appear only when seeded rows exist.
- **Draft-approval invalidation** on a material review change is P5.
- **Evidence reads** are pulled forward from BO-014 deliberately so the live drawer's evidence view is real; they add no table.
- **Real Auth0 activation, CORS/CSRF, audit hooks, browser tests, live workspace selection and any UI redesign** are unchanged from P10-P12; live mode stays gated off.

**Rollback.** Migration `0011` is reversible (drop `project_buyers.version` and `idempotency_records.response`). Every route added here was previously in the `501` registry, so disabling the phase means restoring those entries; no data migration is required on rollback, and no history is rewritten. Reviews are corrected through new review events, and archiving is not part of this phase.

## Completion criteria

The phase is complete only when its acceptance evidence is recorded and reviewed: backend tests run against a real database under the runtime role, and the frontend checks are green. Live mode stays gated off, so a `401` from an unconfigured environment remains an expected state rather than a passing integration.
