# P14 design — buyer lists and filter presets (BO-008, Slice 2)

**Status: PROPOSED / PLAN ONLY.** Plan revision v1. Recorded 2026-09-19 (Hong Kong).

No application code, lockfile, dependency install, migration, cloud resource, deployment, Site access change, paid provider call, mailbox connection, message, or send is authorized by this document. Execution happens only under an explicit dependency waiver, on the separately approved task.

Related records: [P9 API surface](2026-09-15-p9-api-surface-design.md), [P11 demo/live adapter](2026-09-17-p11-demo-live-adapter-design.md), [P12 project/profile writes](2026-09-18-p12-project-profile-writes-design.md), [P13 durable buyer review](2026-09-19-p13-buyer-review-design.md), [BO-008 task](../tasks/BO-008-persist-buyer-evidence-views-reviews-stable-selections-and-lists.md), [03 contracts](../03_DATA_API_AND_STATE_CONTRACTS.md), [contracts/openapi.proposed.yaml](../contracts/openapi.proposed.yaml).

**Base: P13.** This phase completes BO-008. It branches from `p13-buyer-review` (which contains `p12-project-profile-writes` @ `91ba848`, `p11-demo-live-adapter` @ `cf20b1a` and `main` @ `d159ae9`), so its pull request targets `p13-buyer-review` until P13 merges, then the chain. Branching from `main` would not compile.

## Scope

Let a user keep the right companies together: create and rename per-project buyer lists, add or remove buyers (including a whole frozen snapshot selection), and read a list's members; and save and reapply reusable buyer-filter presets.

**What exists today.** `0003_p2_tables.py` already creates `buyer_lists` and `list_memberships`, and P13 added `project_buyers.version`. But the five list operations and the two filter-preset operations are still in the P9 `501` registry: `buyer_lists` has no `version`, and there is no `filter_presets` table at all. P13's snapshot materialization deliberately deferred the `list_id` filter because no lists existed yet.

**Relationship to BO-008.** P13 was Slice 1 (durable review). P14 is Slice 2: lists and presets, completing the task and its acceptance test **TEST-BO-008-02** (duplicate add yields one membership; removal retains evidence and company), which Slice 1 recorded as deferred.

## A. Boundaries and units

```
services/api/alembic/versions/0012_filter_presets_and_list_version.py  NEW  filter_presets table + buyer_lists.version
services/api/buyeros_api/db/presets.py            NEW  FilterPreset model
services/api/buyeros_api/db/buyers.py             MOD  BuyerList.version
services/api/buyeros_api/api/schemas.py           MOD  ListWrite, ListMembershipRequest, PresetWrite
services/api/buyeros_api/api/routes/lists.py      NEW  createBuyerList/listBuyerLists/getBuyerList/renameBuyerList/changeListMemberships
services/api/buyeros_api/api/routes/presets.py    NEW  listFilterPresets/saveFilterPreset
services/api/buyeros_api/services/list_service.py NEW  list reads/writes and membership application
services/api/buyeros_api/services/preset_service.py NEW  preset list/upsert
services/api/buyeros_api/services/buyer_selection.py MOD  enable the list_id filter
services/api/buyeros_api/api/app.py               MOD  register the two routers
services/api/buyeros_api/api/deps.py              MOD  seven OPERATION_ROLES entries
services/api/buyeros_api/api/unimplemented.py     MOD  the seven operations leave the registry
services/api/tests/test_buyer_lists_db.py         NEW  lists, memberships, presets and the list_id filter
services/live/mapping.ts                          MOD  list and preset mappers
features/live/lists.tsx                           NEW  live list manager
features/live/buyers.tsx                          MOD  preset save/apply and add-to-list
features/workspace.tsx                            MOD  live lists route
tests/live-adapter-checks.mjs                     MOD  mapper checks
```

Each unit has one job. `list_service.py` owns list reads, renames and membership application; `preset_service.py` owns preset list/upsert; `buyer_selection.py` owns filtering. The routes authorise, persist and shape. The components render.

## B. Data model, migration and versioning

**Migration `0012_filter_presets_and_list_version`** (reversible) mirrors `0003`'s `_common` + RLS pattern:

- **New `filter_presets`**: the tenant columns (`id`, `workspace_id`, `created_at`, `updated_at`, the `workspaces` FK and `UniqueConstraint(workspace_id, id)`), plus `project_id`, `actor_id`, `name` `String(100)`, `filters` `JSONB`, `sort` `String(16)` and `version` `Integer NOT NULL server_default "1"`; a composite `(workspace_id, project_id) -> projects` FK and `UniqueConstraint(workspace_id, project_id, actor_id, name)`. The table gets `ENABLE`+`FORCE ROW LEVEL SECURITY`, the `tenant_isolation` policy keyed on `app.workspace_id`, and `GRANT SELECT, INSERT, UPDATE, DELETE` to `buyeros_api, buyeros_worker`.
- **`buyer_lists.version`**: `Integer NOT NULL server_default "1"` (kept as a server default, like `project_buyers.version`).

**Versioning.** `buyer_lists.version` starts at 1 and increments on every successful **list mutation** — a rename and any membership add/remove — under a row lock. It is the strong ETag for `renameBuyerList` and `changeListMemberships`; a stale `If-Match` is `412`. `filter_presets.version` starts at 1 and increments when a save replaces an existing `(project, actor, name)` preset.

**Immutability and retention.** Removing a membership deletes only the `list_memberships` row: the project buyer, its company, its evidence, its fit and its review all remain (TEST-BO-008-02). Nothing is hard-deleted beyond a membership row, and no history is rewritten.

## C. API contract details

| Operation | Method and path | Permitted roles | Idempotency | Version |
|---|---|---|---|---|
| `createBuyerList` | POST `/v1/workspaces/{ws}/projects/{p}/lists` | operator/reviewer/workspace_admin | Required | none |
| `listBuyerLists` | GET `/v1/workspaces/{ws}/projects/{p}/lists` | viewer+ | Read-only | none |
| `getBuyerList` | GET `/v1/workspaces/{ws}/lists/{list_id}` | viewer+ | Read-only | none |
| `renameBuyerList` | PATCH `/v1/workspaces/{ws}/lists/{list_id}` | operator/reviewer/workspace_admin | Required | `If-Match` |
| `changeListMemberships` | POST `/v1/workspaces/{ws}/lists/{list_id}/memberships` | operator/reviewer/workspace_admin | Required | `If-Match` |
| `listFilterPresets` | GET `/v1/workspaces/{ws}/projects/{p}/filter-presets` | viewer+ | Read-only | none |
| `saveFilterPreset` | POST `/v1/workspaces/{ws}/projects/{p}/filter-presets` | viewer+ | Required | none |

**Request bodies are strict Pydantic v2 models** (`extra="forbid"`, explicit nulls rejected): `ListWrite{name 1..160}`, `ListMembershipRequest{selection, operation in {add, remove}}`, `PresetWrite{name 1..100, filters, sort in {best_fit, name_asc}}`. `ListWrite` is used by both create and rename; an empty rename body is `422`.

**Response shapes are documented contract subsets** (every emitted key contract-declared):

- `BuyerList` = `id`, `workspace_id`, `version`, `created_at`, `updated_at`, `data_mode`, `project_id`, `name`, `member_count` (COUNT of memberships).
- `FilterPreset` = `id`, `workspace_id`, `version`, `created_at`, `updated_at`, `data_mode`, `name`, `filters`, `sort`, `project_id`, `actor_id`.
- Pages: `BuyerListPage` / `FilterPresetPage` = `{items, offset, limit, total}`.
- `changeListMemberships` returns the Slice 1 `BulkResult` (per-item `id`/`status`/`reason_code`; `BulkItemResult` requires only `id`+`status`).

**Error mapping:** missing/malformed `Idempotency-Key`/`If-Match` -> `400 INVALID_REQUEST`; body validation, an unsupported preset filter, or an invalid selection -> `422 INVALID_REQUEST`; insufficient role -> `403 PERMISSION_DENIED`; absent or foreign project/list -> non-enumerating `404 NOT_FOUND`; same key with a different body -> `409 IDEMPOTENCY_CONFLICT`; a stale list `If-Match` -> `412 STALE_REVISION`.

**Contract-first bookkeeping.** The seven operations leave `UNIMPLEMENTED_OPERATIONS`; the registry test is updated in lockstep and must not be loosened; the operationId/app-exposes and response-subset contract tests gain the new entities.

## D. Lists and membership semantics

**Create, list, get, rename.** `createBuyerList` creates a `version 1` list for a project (member_count 0). `listBuyerLists` pages a project's lists; `getBuyerList` loads one by `(workspace, id)`. `renameBuyerList` requires `If-Match` equal to the list `version`, persists the new name, and increments `version`; it is idempotent (same key + same body replays the current list without a second bump).

**Membership application.** `changeListMemberships` resolves its `Selection` exactly as Slice 1 does: `explicit{buyers:[{id,version}]}` verbatim, or `snapshot{snapshot_id, excluded_ids}` expanded by `ordinal` with the frozen `BuyerSnapshotItem.buyer_version`. A missing or expired snapshot is `404`. Under a single `FOR UPDATE` lock on the list:

- the list `If-Match` is checked first (stale -> `412`);
- each item's buyer must be a `ProjectBuyer` of the list's project, else the item is `blocked`;
- an expected version that differs from the buyer's current version is a `conflict` (nothing changes for that item);
- `operation=add`: an existing `(list, buyer)` membership is `unchanged`; otherwise a membership row is inserted (`updated`);
- `operation=remove`: an absent membership is `unchanged`; otherwise the membership row is deleted (`updated`);
- the list `version` increments once for the request.

The unique `(workspace, list, buyer)` constraint makes a duplicate add a no-op rather than a duplicate row (TEST-BO-008-02). Removal never touches the buyer, its company or its evidence.

**Reading a list's members.** `getBuyerList` returns the list with `member_count`; the members themselves are read through `listBuyers` with `filters.list_id`, which this phase enables.

## E. Filter presets and the `list_id` filter

**Presets** are scoped to `(project, actor)`. `listFilterPresets` returns the caller's presets for a project, paged. `saveFilterPreset` validates the strict `BuyerFilters` (a non-empty **deferred** filter is `422` naming the field, so a stored preset can never be one that fails when applied) and upserts by `(project, actor, name)`: a new name creates a `version 1` row; an existing name replaces `filters` and `sort` and increments `version`. The upsert is race-safe: a concurrent insert for the same scope is caught as a unique-constraint violation and retried as an update rather than surfacing a `500`.

**The `list_id` filter** moves from deferred to supported in `buyer_selection.materialize`, joining `list_memberships` on `(workspace, list_id, buyer)`. A snapshot created with `filters.list_id` therefore freezes exactly the list's members at that moment; a member removed afterwards is absent from any new snapshot. `list_id` is also allowed inside a saved preset.

## F. Testing and acceptance mapping

**Backend** (pytest against the disposable PostgreSQL as the runtime role) covers: list create/list/get; rename version, `If-Match`, `412`, `400`, `409`, replay; foreign list `404`; membership add (duplicate -> one membership, correct `member_count`), remove retaining evidence and company (**TEST-BO-008-02**), snapshot-selection membership with `excluded_ids`, per-item `updated`/`unchanged`/`blocked`/`conflict`, the one-per-request version bump, and the `403` role gate; presets (create `v1`, upsert-by-name bumps `version`, deferred filter `422`, per-actor isolation, page, replay); and the `list_id` filter freezing and re-freezing membership.

**Frontend** extends the zero-dependency node harness with the list and preset mappers. The live UI (list manager, preset controls, add-to-list) is verified by `tsc -p tsconfig.json`, `eslint` and `pnpm build`, since a `.tsx` cannot be loaded by the harness and live mode is gated off.

| Criterion | In this phase | Deferred (recorded, NOT RUN) |
|---|---|---|
| **TEST-BO-008-01** frozen selection; cross-tenant IDs never mutate | kept green from Slice 1; `list_id` snapshots freeze membership | live discovery producing new buyers |
| **TEST-BO-008-02** duplicate add yields one membership; removal retains evidence and company | the membership add/remove tests | none |
| **TEST-BO-008-03** review updates derived state; concurrent conflict preserves the prior version | kept green from Slice 1 | draft-approval invalidation (P5) |

## G. Out of scope and rollback

- **`contacts`, `policies`, `market`, `buyer_type`** and their filters (and the deferred `markets`, `buyer_types`, `contact`, `suppressed`, `source_types`, `run_id` filters) still wait on P3/P4/P5; suppression is BO-009.
- **Discovery, runs and fit generation** remain `501`; **draft-approval invalidation** is P5.
- **Live activation and workspace selection** are unchanged; live mode stays gated off.
- **P13's recorded Minors** are carried, not fixed here unless a task touches the same code.

**Rollback.** Migration `0012` is reversible (drop `filter_presets`; drop `buyer_lists.version`). Every route added here was previously in the `501` registry, so disabling the phase means restoring those entries; `list_id` returns to the deferred set. No history is rewritten.

## Completion criteria

The phase is complete only when its acceptance evidence is recorded and reviewed: backend tests run against a real database under the runtime role, and the frontend checks are green. Live mode stays gated off, so a `401` from an unconfigured environment remains an expected state rather than a passing integration.
