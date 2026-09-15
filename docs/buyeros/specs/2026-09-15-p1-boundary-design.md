# P1 boundary design — authentication, tenant isolation, and demo/live separation

**Status: PROPOSED / PLAN ONLY.** Plan revision v1. Recorded 2026-09-15 (Hong Kong). Design covers tasks **BO-004, BO-005, BO-006** (phase P1). Approved in the Plan review session; this is a design input, not Build approval.

No application code, lockfile, dependency install, database migration, cloud resource, deployment, Site access change, paid provider call, mailbox connection, message, commit or push is authorized or performed by this document.

Related records: [BO-001 runtime/identity decision](../decisions/BO-001-runtime-identity.md), [02 architecture](../02_ARCHITECTURE_AND_REUSE.md), [03 data/API contracts](../03_DATA_API_AND_STATE_CONTRACTS.md), [contracts/openapi.proposed.yaml](../contracts/openapi.proposed.yaml).

Base content commit: `b804ba8d1514a1049b7202c861278dd72c473a75`, tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`. Canonical repository: `YNWAforever/BuyerOS` (the audited source is imported at commit `b804ba8d1514a1049b7202c861278dd72c473a75`, tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`, merged into `main` via `72fef7da785624a35bb6701f1451ebcf0184a089`).

## Scope

Deliver the P1 boundary so that (a) every API request resolves a verified actor and authorized workspace or is denied, (b) the database cannot cross tenants, and (c) the public demo stays reproducible while the authenticated live workspace never falls back to fixtures.

In scope: BO-004 (bearer identity + tenant membership), BO-005 (tenant-safe persistence + one migration owner), BO-006 (demo/live boundary). Out of scope: contract freeze/generation (BO-003, reviewed), profile/review persistence (BO-007+), budgets (BO-010), queue (BO-011), provider calls, delivery.

## A. Authentication and authorization (BO-004)

### Browser
- Auth0 **Authorization Code + PKCE** public SPA flow. Access token held **in memory only**; never localStorage, cookies, or URLs.
- Bearer token sent to FastAPI. No client secret exists in browser code. (Auth0 app must be reconfigured from the current `regular_web`/`client_secret_post` to a public PKCE client with the Site origin registered — still pending; see BO-001 D3a.)

### API middleware
- Verify JWT through cached JWKS with fixed **RS256** allowlist; reject `alg:none`/HS*.
- Require `iss` == configured issuer, `aud` == configured API audience, valid `exp`/`nbf`, bounded clock skew.
- Issuer/audience are configuration inputs. **No invented values** while Auth0 is unreconfigured; live auth stays disabled until supplied.

### Identity and membership
- Upsert `users` by immutable `(issuer, subject)`; minimal display fields only.
- Resolve `memberships(workspace_id, user_id)` **per request**; roles come from the database, never from token claims.
- Never trust client-submitted `workspace_id`, actor, role, timestamps, version, price, or approval hash.
- Tenant is carried explicitly in the path: `/v1/workspaces/{workspace_id}/projects/{project_id}/…`.

### Role → permission matrix (fail-closed)

| Capability | viewer | operator | reviewer | admin |
|---|---|---|---|---|
| Scoped reads (projects, buyers, evidence, usage) | yes | yes | yes | yes |
| Start/cancel/retry runs, notes/owners, record outcomes | — | yes | yes | yes |
| Request contact quote | — | yes | yes | yes |
| Accept/reject buyers; approve/reject drafts | — | — | yes | yes |
| Confirm contact lookup / spend (subject to budget + policy) | — | — | yes | yes |
| Budgets, policy/suppression, membership, sender config | — | — | — | yes |

Unknown role, inactive membership, or missing workspace context → **deny**.

### Errors and lifecycle
- 401 `UNAUTHENTICATED`; 403 `PERMISSION_DENIED`/`POLICY_*`; 404 `NOT_FOUND` non-enumerating for foreign/absent resources; 412 `STALE_REVISION`; 409 conflict family as in 03 §4.
- Capability/health endpoints expose no secrets or provider credentials.
- Token expiry → 401 → frontend clears sensitive cached state, refreshes, replays durable events. Membership revocation is effective on the next request.
- Tenant switch aborts in-flight requests and clears scoped selections, quotes, and editor caches; a late response from a different workspace/project context is rejected.

## B. Persistence and tenant isolation (BO-005)

### Ownership
- SQLAlchemy models + **Alembic** are the sole domain-schema migration owner. The empty Drizzle/SQLite scaffold remains unused for domain tables. Startup never auto-migrates.

### Constraints
- Every tenant-owned table: `workspace_id NOT NULL`, `UNIQUE(workspace_id,id)`, and `(workspace_id,parent_id)` composite foreign keys.
- Project-bound cross-links (buyer↔list, buyer↔assessment, ICP↔run, evidence↔assessment, draft↔buyer) additionally prove a common project via `(workspace_id,project_id,id)`.
- IDs are opaque and server-generated; clients cannot set actor, state, settled cost, or approval hashes by patching arbitrary fields.

### Row-level security and roles
- Distinct Postgres roles: **migration owner**, **api**, **worker**. Runtime roles are non-owner and have no `BYPASSRLS`; they cannot mutate schema.
- Each transaction sets `SET LOCAL app.workspace_id` (and actor) before queries; `FORCE ROW LEVEL SECURITY` policies apply; **missing context fails closed**.
- Application predicates remain as defense-in-depth; RLS is not the only control.

### Pooling and environment
- All queries are transaction-scope and compatible with pooled connections; **no session-level tenant variable may survive connection reuse** (Neon pooled DSN for runtime, direct DSN for migrations).
- Tests run against a disposable local PostgreSQL (container). Deployed staging uses Neon `ap-southeast-1` (Singapore) when provisioned.
- Never hold a DB transaction open across an external HTTP call.

### Migrations
- Expand/backfill/read-switch/contract discipline; serialized authorship under the backend owner.
- Destructive column/table removal requires a later approved task plus backup evidence. Roll-forward with an additive repair is preferred to rollback that discards committed financial records.

## C. Demo/live boundary (BO-006)

- **Mode:** `BUYEROS_MODE = demo|live` resolved from the execution profile/env; **default demo** so the public Site stays reproducible. Live additionally requires the API base URL and Auth0 configuration.
- **Isolation:** the demo path keeps existing fixtures, localStorage keys (`buyeros-demo-v1`, `buyeros-prefs-v1`, `buyeros-drafts-v1`), and the mock adapter unchanged and synthetically labelled. The live path uses the generated client + `services/live/mapping.ts` and asserts `data_mode:"live"`; `data_mode:"demo"` must not deserialize into a live adapter.
- **Banner:** read-only mode indicator; **never** the integration switch. Authentication/provenance determine access.
- **Failure policy:** live error/offline/session-expiry shows a typed error or empty state; **never** fixtures. Demo restore validation is not a server authorization mechanism.
- **Parity:** identical shell, routes, table/drawer/editor components in both modes. `data_mode` is not a globally mutable switch.
- **Cache hygiene:** switching workspace or mode discards scoped live caches and selections; demo state never imports into a live tenant.

## Data flow

Live: browser (in-memory PKCE token) → `Authorization: Bearer` → middleware (JWKS verify → membership lookup → role check → set transaction-local tenant context) → SQLAlchemy transaction (RLS + composite FKs) → response envelope `{data, request_id, data_mode:"live"}`.
Demo: browser → existing isolated fixture/mock adapter; no API call, no bearer, no tenant context.

## Interfaces

Public API is provider-neutral and matches the proposed OpenAPI (`/v1/workspaces/{workspace_id}/…`); BO-004 adds only the bearer security scheme and the membership/permission guard, not new endpoints. Error codes and envelopes follow 03 §4. No parallel endpoint may be invented; any client/server disagreement becomes a reviewed contract revision.

## Testing (all PROPOSED_AFTER_TASK / NOT RUN)

| Test | Expectation |
|---|---|
| TEST-BO-004-01 | invalid/expired/wrong-audience/unsigned token, revoked member, viewer write → 401/403 or non-enumerating 404; zero domain writes; denial audit excludes personal payload |
| TEST-BO-005-01 | composite-FK violation rejected; RLS under non-owner roles; pooled A→B reuse leaks no context; missing tenant context fails closed; migration on fresh/previous schema |
| TEST-BO-006-01 | live 500/offline/session-expiry shows real error and no fixtures; mode/tenant switch discards caches; demo restore stays synthetic |

Supporting checks: OpenAPI parse (70 ops / 139 schemas / 0 unresolved refs — verified during planning), `node tests/domain-checks.mjs` (11 demo checks), `pnpm exec tsc --noEmit` — all NOT RUN in this planning session.

## Assumptions, blockers and non-goals

- **Pending external decisions:** Auth0 app reconfigure (public PKCE + Site origin), membership owner, actual issuer/audience values, Neon/Render/R2 provisioning and sizes. The design assumes configurable values and invents none.
- **Non-goals:** provider integrations, contact purchase, budgets, queue/outbox, drafting, delivery, cloud provisioning, migrations executed, and any Build action.

## Completion criteria

BO-004/005/006 may be marked DONE only when their own acceptance tests and approval obligations have recorded evidence; this document does not complete any task.

## Rollback / roll-forward

Supersede this design with a dated successor for design changes; for implementation, roll back application versions only when schema-compatible, otherwise roll forward with an additive repair. Never discard committed financial records.
