# Build approval record — P12 project/profile writes (BO-007)

**Status: APPROVED (owner-authorized this session).** Plan revision v1. Recorded 2026-09-18 (Hong Kong).

| Field | Value |
|---|---|
| Task | **BO-007** — persist projects, editable offers and immutable approved buyer profiles |
| Phase | **P12 project/profile writes** (the first write workflow over the P11 client seam) |
| Scope | Project write surface (`createProject` full validation, `updateProject` with `If-Match`, `archiveProject`), idempotency on every project mutation, approval settling the project's active ICP version, migration `0009`, the P11 client write support, a pure Offer mapper, write orchestration, and the live wizard/profile UI |
| Spec | `docs/buyeros/specs/2026-09-18-p12-project-profile-writes-design.md` |
| Plan | `docs/buyeros/plans/2026-09-18-p12-project-profile-writes-implementation.md` |
| Base | branch `p12-project-profile-writes` from `p11-demo-live-adapter` @ `cf20b1a` (which contains `main` @ `d159ae9`, P10 merged) |
| Allowed files | create `services/api/buyeros_api/api/schemas.py`, `services/api/buyeros_api/api/idempotency.py`, `services/api/alembic/versions/0009_project_profile_columns.py`, `services/api/tests/test_api_projects_db.py`, `services/live/profile.ts`, `services/live/writes.ts`, `features/live/{offer-wizard,profile}.tsx`; modify `services/api/buyeros_api/db/icp.py`, `services/api/buyeros_api/api/routes/{projects,icp}.py`, `services/api/buyeros_api/api/unimplemented.py`, `services/api/tests/{conftest,test_api_buyers,test_api_routes_contract}.py`, `services/live/client.ts`, `tests/live-adapter-checks.mjs`, `features/workspace.tsx`; docs under `docs/buyeros/**` |
| Dependencies with evidence | BO-003/BO-005/BO-006 are complete as far as P9-P11 carried them. The B-IDENTITY blocker (no live Auth0) is accepted below |
| Approver | Owner (execution mode = subagent-driven) |
| Environment/spend | none; no network, no identity provider, no credentials. Backend tests use the disposable `postgres:16` fixture; frontend checks use a stubbed fetch |
| Excluded | `sender_identity` linkage, discovery runs (`501`), live project URL routing, real Auth0 activation, CORS/CSRF, audit hooks, browser tests, UI redesign |

## Dependency waiver (explicit)

B-IDENTITY is unresolved, so no configured identity provider can issue a token the API would verify. The owner
waived that prerequisite: P12 proves the **write surface and its seam** — strict contract request schemas, project
versioning through `If-Match`, idempotent replay, approval settling the active profile, the mapper's explicit
rejection of unresolvable input, and the write orchestration — against the disposable database and a stubbed fetch,
with no network and no live mode. Consequences accepted: `sender_identity` requests are rejected (`422`) rather than
implemented; live mode stays gated and off, so the authenticated round trip is not exercised here. This waiver does
not mark BO-007 complete in the task index and authorizes no other phase.

## Pre-execution plan corrections (recorded)

The plan was validated before dispatch (30 code blocks; 0 non-ASCII; only the intended indented fragments fail
standalone parsing). Four contract/spec violations were found and corrected in the committed plan before execution:

1. **`createProject` was not idempotent** though the contract marks it `x-idempotency: Required`, and the helper
   never recorded `resource_id`, so replay was dead code. `begin_idempotency`/`complete_idempotency` now return and
   complete the record, and create replays the same key+body.
2. **`Idempotency-Key` was unvalidated**; it is now length-checked `8..200` per the contract parameter.
3. **`archiveProject` ignored the contract's required `ArchiveRequest.reason`**; the route now takes and validates it
   (the reason is part of the idempotency fingerprint).
4. **`website` was not validated as a URI** and `offer` carried an invented minimum length; the schema now matches
   the contract.

## Recorded deviations from the BO-007 task text

1. **No Playwright.** The task specifies a browser spec; the existing zero-dependency node check convention is
   extended instead, so **no new dependency** is added. The wizard/profile UI is verified by `tsc`, `eslint` and
   `pnpm build`.
2. **`sender_identity` deferred.** Strict request models reject the field rather than ignore it; the deferred half of
   the acceptance criteria is recorded in the spec, not silently dropped.
3. **`archiveProject` reason not persisted.** It is validated per the contract but no column stores it this phase;
   `ICPSaveRequest` validation also keeps its current key-extraction.

## Sign-off (owner)

Recorded from the owner's in-session direction on 2026-09-18: the owner approved the P12 spec, approved the P12
implementation plan, and authorized subagent-driven execution of that plan under the dependency waiver above. This
record captures that authorization; it is not a verbatim quotation and no remote push, deploy or activation is
authorized by it.
