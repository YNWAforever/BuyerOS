# P9 design — auth-agnostic API surface (contract-first)

**Status: PROPOSED / PLAN ONLY.** Plan revision v1. Recorded 2026-09-15 (Hong Kong). Approved in the Plan review session; this is a design input, not Build approval.

No application code, lockfile, install, migration, cloud resource, deployment, Site access change, paid provider call, mailbox connection, message, or send is authorized by this document. Execution happens only under an explicit dependency waiver.

Related records: [P1 boundary](2026-09-15-p1-boundary-design.md), [P2](2026-09-15-p2-persistence-foundation-design.md), [P8 worker](2026-09-15-p8-worker-dispatcher-design.md), [BO-001 decision](../decisions/BO-001-runtime-identity.md), [03 contracts](../03_DATA_API_AND_STATE_CONTRACTS.md), [contracts/openapi.proposed.yaml](../contracts/openapi.proposed.yaml). Base commit: `4cd159a` (`main`, PR #1 merged).

## Scope

Deliver the first HTTP surface over the existing domain services: a FastAPI app with a **fail-closed** auth/tenant dependency, one working vertical slice of routes, a contract-conformance test, and generated TypeScript types. Real Auth0 activation, provider-backed endpoints, frontend wiring and deployment are out of scope.

## A. Architecture and boundaries

- New `services/api/buyeros_api/api/`: `app.py` (app factory), `deps.py` (auth + tenant dependencies), `errors.py` (envelope + handlers), `unimplemented.py` (declared-path 501 registry), `routes/{health,workspaces,projects,icp,buyers}.py`.
- Routers are thin: they call existing domain services inside `tenant_session`; no business rules live in the router layer.
- Liveness is a **non-contract** probe at `GET /health/live` only. Authenticated readiness and capabilities are contract routes under `/v1/workspaces/{workspace_id}/...`; there is no `/health/ready` contract path.
- No frontend changes and no worker coupling in this phase.

## B. Auth and tenant dependencies (fail-closed, pluggable)

- `get_principal(request)` reads `Authorization: Bearer`. With **no verifier configured** (no `auth0_issuer`/`auth0_audience`) it fails closed with `401 UNAUTHENTICATED` — nothing is reachable unauthenticated and live auth cannot be half-enabled.
- With a verifier configured: RS256 only, cached JWKS, `iss`/`aud`/`exp`/`nbf` validation, then resolve the actor by immutable `(issuer, subject)`.
- `require_membership(workspace_id)` loads the **active membership from Postgres**; roles come from the database, never from token claims. Foreign/absent workspace → non-enumerating `404`; insufficient role → `403`.
- Tenant context is derived **only** from the membership-checked `workspace_id` in the path. A client-supplied workspace id is never trusted on its own.

## C. Contract-first workflow

- `contracts/openapi.proposed.yaml` stays authoritative. Implemented routes must match its `operationId`, method, path, and schema names exactly.
- A **contract test** loads the spec and asserts: every implemented route exists in the spec with matching `operationId` and method; success bodies validate against the schema's required fields; `data_mode == "live"`.
- `services/generated/buyeros-api.ts` is generated from the spec with an **exactly pinned** `openapi-typescript` devDependency in `services/api/package.json`, installed and run through the repository's pnpm toolchain (no unpinned `npx` fetch). The generation command and resolved version are recorded.
- Known-but-unimplemented operations are not silently absent: they are enumerated in a registry and answered with an explicit `501 NOT_IMPLEMENTED` on their **declared** contract path+method only. No parallel or invented endpoint is introduced.

## D. Route slice and error envelope

Implemented operations: the non-contract `GET /health/live` liveness probe, the authenticated contract routes `GET /v1/workspaces/{workspace_id}/readiness` and `/capabilities`, `listWorkspaces`, `listProjects`/`createProject`/`getProject`, `listICPVersions`/`saveICPVersion`/`approveICPVersion` (hash-bound approval addressed by `icp_version_id`), `listBuyers`/`getBuyer`.

- Success envelope: `{data, request_id, data_mode:"live"}`.
- Error envelope: `{code, message, request_id, retryable}` using the 03 §4 status map, including `401 UNAUTHENTICATED`, `403 PERMISSION_DENIED`, `404 NOT_FOUND`, `409 IDEMPOTENCY_CONFLICT`, `412 STALE_REVISION`, `501 NOT_IMPLEMENTED`, `503 PROVIDER_UNAVAILABLE`.
- Mutations require an `Idempotency-Key`; versioned edits require `If-Match`. No demo fixture ever appears in a live response.
- Readiness reflects real state (database reachable, queue state, providers disabled) and exposes no secrets.

## E. Testing

- FastAPI `TestClient` plus pytest-asyncio against a **disposable PostgreSQL** (reusing `pg_dsn`/`migrated` fixtures).
- Cases: unconfigured auth → 401 on every route; forged/expired/wrong-audience token; foreign-workspace id → 404 with no leakage; viewer write → 403; `Idempotency-Key` replay and conflict; `If-Match` stale → 412; ICP approval hash binding; contract conformance; readiness leaks no secrets.
- Auth-configured paths use a **local test keypair/JWKS**; no live Auth0 call.

## F. Scope, limits and non-goals

- **In:** app factory, auth + membership dependencies, the narrow route slice, error envelope, contract test, typed client generation, tests.
- **Out:** activating Auth0 (blocked by B-IDENTITY), provider-backed discovery/contact/draft endpoints, frontend wiring, deployment, real-data migration. Runs under a **dependency waiver** (BO-004 not complete).
- Anything outside the slice returns explicit `501 NOT_IMPLEMENTED`.

## Completion criteria

The phase is complete only when its acceptance evidence is recorded and reviewed; this document completes no task. A `401`/`501` from an unconfigured environment is an expected state, not a passing integration.

## Rollback / roll-forward

Supersede this design with a dated successor for design changes. On failure, disable the affected route/capability and keep read-only/health paths available; never weaken the auth or tenant checks to obtain a green result.
