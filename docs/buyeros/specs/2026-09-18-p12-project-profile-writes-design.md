# P12 design — project, offer and profile writes (BO-007)

**Status: PROPOSED / PLAN ONLY.** Plan revision v1. Recorded 2026-09-18 (Hong Kong).

No application code, lockfile, dependency install, migration, cloud resource, deployment, Site access change, paid provider call, mailbox connection, message, or send is authorized by this document. Execution happens only under an explicit dependency waiver, on the separately approved task.

Related records: [P2 persistence](2026-09-15-p2-persistence-foundation-design.md), [P5 draft/approval/export](2026-09-15-p5-draft-approval-export-design.md), [P9 API surface](2026-09-15-p9-api-surface-design.md), [P10 bearer identity](2026-09-16-p10-bearer-identity-design.md), [P11 demo/live adapter](2026-09-17-p11-demo-live-adapter-design.md), [BO-007 task](../tasks/BO-007-persist-projects-editable-offers-and-immutable-approved-buyer-profiles.md), [03 contracts](../03_DATA_API_AND_STATE_CONTRACTS.md), [contracts/openapi.proposed.yaml](../contracts/openapi.proposed.yaml). Base: `main` @ `d159ae9` (P10 merged); branch `p12-project-profile-writes`.

## Scope

Make the product's first write workflow real: a user creates or selects a project, saves the offer and buyer requirements, approves a specific immutable profile revision, and reloads it. This is the contract's project/profile surface minus sender identity.

**What exists today.** The `projects` table carries only `name` and `status`, while the contract's `Project` requires `company_name`, `offer`, `markets`, `language_preferences` and `version`. `createProject` accepts only `name`; `updateProject` and `archiveProject` are in the P9 `501` registry. `approveICPVersion` works (P10) but does not make the approved version the project's active profile. The client (P11) is read-only: `services/live/client.ts` issues GETs only, and in live mode the wizard is not rendered at all — the live branch shows `LiveOverview`.

**Relationship to BO-007.** The task document predates P9-P11 and is materially stale: it says `migration_impact: none` (this phase adds columns), and it proposes `main.py`, `models/core.py`, `routes/projects.py` and a Playwright spec that do not match the repository. Its acceptance criteria also name two halves that depend on work outside this phase (`sender_identity` linkage, and starting discovery from an unapproved profile); those are recorded as deferred rather than silently dropped.

## A. Boundaries and units

```
services/api/buyeros_api/api/routes/projects.py     MOD  full create, PATCH update, DELETE archive
services/api/buyeros_api/api/schemas.py        NEW  ProjectCreate / ProjectUpdate (strict Pydantic)
services/api/buyeros_api/api/routes/icp.py          MOD  approval settles projects.active_icp_version_id
services/api/buyeros_api/api/unimplemented.py       MOD  updateProject/archiveProject leave the registry
services/api/alembic/versions/0009_...py        NEW  project profile columns + superseded_at
services/live/client.ts                             MOD  write support: body, Idempotency-Key, If-Match
services/live/profile.ts                        NEW  Offer -> ProjectCreate / ICPSaveRequest, market+language resolution
services/live/writes.ts                         NEW  saveProfile / approveProfile orchestration
features/live/profile.tsx                       NEW  live profile panel (active version, approve action)
features/live/offer-wizard.tsx                  NEW  thin live wrapper around the existing Wizard
features/workspace.tsx                              MOD  live branch renders the wizard and profile
tests/live-adapter-checks.mjs                       MOD  mapper, resolver and write-header checks
services/api/tests/test_api_projects_db.py      NEW  persistence, immutability, concurrency, roles
```

Each unit has one job. `schemas.py` validates requests and nothing else. `profile.ts` maps an `Offer` to API payloads and nothing else. `writes.ts` sequences calls and owns idempotency keys. The `.tsx` files render. The routes authorise, persist and shape responses.

## B. Data model, versioning and immutability

**Migration `0009_project_profile_columns`** adds to `projects`: `company_name`, `offer`, `website`, `markets`, `language_preferences`, `version` (integer, not null, default 1, server default for backfill then dropped), and `active_icp_version_id` (UUID, nullable). It adds `superseded_at` (timestamptz, nullable) to `icp_versions`. Existing rows are backfilled with defaults so the migration applies to a populated database, and those defaults are then removed so new inserts must supply the values. Reversible.

**Versioning.** `projects.version` starts at 1 and increments on every successful update. It is the strong ETag: responses carry `ETag: "<version>"`, and `If-Match` must equal it (the contract's pattern `^"[1-9][0-9]*"$`). A stale writer receives `412 STALE_REVISION` rather than overwriting a newer edit.

**Immutability.** `icp_versions` are never updated in place: an edit saves a new `number`. The new `superseded_at` makes the contract's `status` derivable: `superseded` when set, else `approved` when `approved_at` is set, else `saved`. `projects.active_icp_version_id` is the pointer to the profile in force; it is set only by a successful approval of a version belonging to that project, and cleared when a material change makes it stale.

**What counts as material.** An update that changes `offer` or `markets` marks the active version `superseded_at` and clears `active_icp_version_id` in the same transaction, per the contract's updateProject description. `name`, `website` and `language_preferences` changes are not material.

**Retention.** `archiveProject` sets `status = "archived"`; it never deletes, and every version and approval remains.

**Idempotency.** Every project mutation requires `Idempotency-Key`, and the existing `IdempotencyRecord` (P4, `db/contact.py`) already provides the store: `(workspace_id, actor_id, operation_id, key)` is unique, alongside `request_hash`, `status` and `resource_id`. `services/confirm_service.py` already provides the two pure primitives this needs: `request_fingerprint(body)` for the canonical body hash and the rule that the same key with a **different** body is a conflict. So the behaviour is: same key and same body re-reads and returns the recorded `resource_id` (a replay, not a new version); same key with a different body returns `409 IDEMPOTENCY_CONFLICT`; a new key proceeds normally. The `operation_id` is the route's contract operation (`createProject`, `updateProject`, `archiveProject`), so keys cannot collide across operations. ICP save/approve keep their current presence-only enforcement, and that difference is recorded.

## C. API contract details

**Request bodies are strict Pydantic v2 models** (`extra="forbid"`), replacing `createProject`'s ad-hoc field checks: `markets` matches `^[A-Z]{2}$` with 1-20 items, `language_preferences` 1-10, `name` 2-160, `company_name` 2-200, `offer` up to 20000 characters, `website` a URI. `ProjectUpdate` has all fields optional with `minProperties: 1`. Invalid bodies return `422` through the envelope P9 registered. A body containing `sender_identity` is a `422`, not a silent ignore.

**Response shape** is the contract's `Project` minus the deferred field: `id`, `workspace_id`, `version`, `created_at`, `updated_at`, `data_mode`, `name`, `company_name`, `offer`, `website`, `markets`, `language_preferences`, `status`, `active_icp_version_id`. `createProject` returns `201`, `updateProject` and `archiveProject` return `200`, all with `data: Project` and an `ETag` header.

**Error mapping:** missing or malformed `Idempotency-Key`/`If-Match` to `400 INVALID_REQUEST`; body validation to `422 INVALID_REQUEST`; insufficient role to `403 PERMISSION_DENIED`; absent or foreign project to a non-enumerating `404 NOT_FOUND`; the same `Idempotency-Key` with a different body to `409 IDEMPOTENCY_CONFLICT`; a stale `If-Match` to `412 STALE_REVISION`.

**Contract-first bookkeeping.** `updateProject` and `archiveProject` leave `UNIMPLEMENTED_OPERATIONS`. The P9 test that asserts the registry equals every non-implemented contract operation is updated in lockstep and must not be loosened; the response-subset test gains the new fields so every emitted key stays contract-declared.

## D. Client write path and the Offer mapper

`services/live/client.ts` gains `request({path, method, token, scope, signal, body?, idempotencyKey?, ifMatch?})`: it sets `Content-Type` and JSON-encodes `body` when present, sends `Idempotency-Key` and `If-Match` only when supplied, and maps failures to the same `LiveError` codes. It remains body-agnostic.

`services/live/profile.ts` holds pure, testable mappers:

- `resolveMarkets(text)` and `resolveLanguages(text)` split on commas and slashes, trim, and look up case-insensitively in a small explicit table (English and local names). They return `{codes, unknown}` and never drop an unrecognised entry.
- `toProjectCreate(offer)` maps `company_name`, `offer`, `website`, `markets` and `language_preferences`. The contract needs a project `name` the wizard does not collect, so the initial name is the company name, documented as a label the user can rename later through `updateProject`.
- `toIcpSaveRequest(offer)` maps `requirements` (from must/nice/exclude, with `category`), `buyer_types`, `languages`, `markets`, `desired_roles` and `offer_facts`.

Both mappers raise a typed `ProfileError` naming the offending value instead of coercing or guessing, so the UI can say which value it did not recognise.

`services/live/writes.ts` sequences the calls: `saveProfile` creates the project when none is selected and then saves an ICP version; `approveProfile` approves a version with `If-Match: "<number>"` and its `content_hash`. One `Idempotency-Key` is generated per user action, so a retried action replays rather than creating a second version.

In the UI, the existing `Wizard` renders in live mode with `save` bound to `saveProfile`, and a small live profile panel shows the saved offer, the active ICP version and an **Approve profile** action that surfaces `403` and `412` honestly. The demo branch is unchanged.

## E. Testing and acceptance mapping

**Backend** uses pytest against a disposable PostgreSQL as the runtime role, so RLS is genuinely in force. It covers: the migration applying and reversing; full create; partial update with a version bump; archive leaving history intact; stale `If-Match` to `412`; missing headers to `400`; wrong role to `403`; foreign or absent project to `404`; idempotent replay; a material change superseding the active version while that version and its approval remain retrievable; and approval setting `active_icp_version_id` only for a version of that project.

**Frontend** extends the P11 node-script harness with **no new dependency**: the resolvers (known names resolve, unknown values are returned and then rejected loudly), the two mappers (exact field mapping, no fabricated values), and the write path's headers (`Content-Type`, `Idempotency-Key`, `If-Match` set only when supplied; `412`/`403`/`422` mapped correctly). The wizard UI is verified by `tsc`, lint and `pnpm build`, since a `.tsx` cannot be loaded by the harness.

| Criterion | In this phase | Deferred (recorded, NOT RUN) |
|---|---|---|
| **TEST-BO-007-01** refresh and deep link preserve project/offer/profile; workspace B cannot read it | backend cross-tenant `404`; the profile is fetched from the API so a refresh restores it | live project URL routing; the shell's routes are unchanged |
| **TEST-BO-007-02** changing an approved must-have or markets creates a new unapproved version while the old reference stays fixed | supersede plus a new version; the superseded version and its approval remain retrievable | the "old run reference stays fixed" half; runs are `501` this phase |
| **TEST-BO-007-03** concurrent edits yield one success and one conflict | two updates with the same `If-Match` give `200` then `412` | "an unapproved ICP cannot start discovery"; no run endpoint exists yet |
| **TEST-BO-007-04** one immutable active version with prior history; operator or foreign project cannot approve | `403` for operator, `404` for a foreign or mismatched version, exactly one active version, history retained | the `sender_identity` and draft-attachment half (sender identity is out of scope) |

## F. Out of scope and rollback

- **`sender_identity` linkage** is deferred; strict request models reject the field rather than ignore it.
- **Discovery runs** remain `501`; the enforceable half of TEST-BO-007-03 is that approval is the only thing that sets the active profile.
- **Live URL routing for projects** is unchanged.
- **`ICPSaveRequest` validation** keeps its current key-extraction; tightening it is a follow-up, recorded so this phase does not half-refactor it.
- **Idempotency replay for ICP save/approve** stays presence-only, unlike the project mutations, and the difference is documented.
- **Real Auth0 activation, CORS/CSRF, audit hooks, browser tests, and any UI redesign** are unchanged from P10/P11.

**Rollback.** The migration is reversible (drop the added columns, including `superseded_at`). Every route added here was previously in the `501` registry, so disabling the phase means restoring those entries; no data migration is required on rollback, and no history is rewritten. Corrections happen through new versions; archiving only sets a status.

## Completion criteria

The phase is complete only when its acceptance evidence is recorded and reviewed: backend tests run against a real database under the runtime role, and the frontend checks are green. Live mode stays gated off, so a `401` from an unconfigured environment remains an expected state rather than a passing integration.
