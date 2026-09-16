# P10 design — bearer identity and tenant membership (BO-004)

**Status: PROPOSED / PLAN ONLY.** Plan revision v1. Recorded 2026-09-16 (Hong Kong).

No application code, lockfile, install, migration, cloud resource, deployment, Site access change, paid provider call, mailbox connection, message, or send is authorized by this document. Execution happens only under an explicit dependency waiver, on the separately approved task.

Related records: [P1 boundary](2026-09-15-p1-boundary-design.md), [P5 draft/approval/export](2026-09-15-p5-draft-approval-export-design.md), [P8 worker](2026-09-15-p8-worker-dispatcher-design.md), [P9 API surface](2026-09-15-p9-api-surface-design.md), [BO-004 task](../tasks/BO-004-verify-api-bearer-identity-and-enforce-tenant-membership.md), [03 contracts](../03_DATA_API_AND_STATE_CONTRACTS.md), [contracts/openapi.proposed.yaml](../contracts/openapi.proposed.yaml). Branch: `p10-bearer-identity`, from `p9-api-surface` at `b11cf5c`.

## Scope

Replace P9's fail-closed authentication **stub** with real RS256/JWKS verification, and make the authenticated path executable end-to-end (a missing runtime-role grant currently makes every authenticated route fail under the intended role). Real Auth0 activation, frontend wiring, CORS/CSRF, audit hooks and deployment remain out of scope.

**Relationship to P9.** P9 built the HTTP layer — app factory, error envelope, `get_principal`, `load_membership`, the route slice and the contract test — with `principal_from_token` deliberately raising even when configured. P10 fills that stub in. The BO-004 task document predates P9 and lists `main.py`, `auth.py`, `errors.py`, `routes/capabilities.py` and `routes/workspaces.py` as files to create; those now exist as `app.py`, `auth.py`, `errors.py` and `routes/*`. **P10 modifies the P9 surface; it does not rebuild it**, and it must not create an alternative app entry point, error module or parallel route module.

## A. Boundaries and units

```
buyeros_api/api/
  auth.py          get_principal (async adapter)  +  claims_to_principal (pure claim rules)
  jwks.py    NEW   JwksKeyCache — fetch/cache/rotate/invalidate; issuer -> public key for a kid
  verifier.py NEW  TokenVerifier — token -> verified Principal
  deps.py          load_membership (existing, unchanged) — the only source of roles
```

- `jwks.py` has one job: given a `kid`, return a usable public key or raise. It owns TTL caching, the single refetch on unknown `kid`, and outage behavior. It knows nothing about tokens or principals.
- `verifier.py` has one job: token → verified `Principal`. It enforces the algorithm allow-list, signature, `iss`, `aud`, `exp`, `nbf`, and maps every failure to `AuthError`. It knows nothing about tenancy.
- `auth.py::get_principal` keeps its P9 role: an async FastAPI dependency that reads the header and converts `AuthError` into `ApiError(401, "UNAUTHENTICATED", ...)`. It delegates the actual work to `TokenVerifier`.
- `deps.py::load_membership` is unchanged. Roles still come only from Postgres. P10 adds a **migration** so it can read `users` under the runtime role; it does not add authorization logic.

**Boundary rule.** Nothing in the verifier trusts a claim for authorization. `Principal` carries only `(issuer, subject)`; every role and every workspace still comes from the database.

## B. Token verification rules

- **Algorithm allow-list:** RS256 only. `alg: none`, `HS256` and every other algorithm are rejected before any signature work. The allowed list is passed explicitly; the algorithm is never derived from the token header alone.
- **Key selection:** the `kid` header must be present and must resolve to a key in the JWKS. A token with no `kid`, or an unresolvable `kid`, is rejected.
- **Claims** are checked by the existing pure `claims_to_principal` (P9, already tested): `iss` exact match; `aud` string-equals or list-contains; `exp` integer `> now`; `nbf` integer `<= now + 60s`; `sub` non-empty. Each failure raises `AuthError` with a specific internal reason.
- **Unconfigured behavior is preserved verbatim.** With no `auth0_issuer`/`auth0_audience`, `get_principal` still returns `401 UNAUTHENTICATED` before any verification is attempted. P9's existing auth tests must keep passing unchanged.
- **Failure disclosure:** every `AuthError` becomes `ApiError(401, "UNAUTHENTICATED", <generic message>)`. The response never states which check failed and never echoes a claim, the token, or any header value.

## C. JWKS cache and key rotation

`JwksKeyCache` is the only stateful, network-touching unit. Its public operation is: **given a `kid`, return a usable public key or raise.**

- **State:** per-process `{keys: dict[kid, public_key], fetched_at: float}` plus the JWKS URI. Populated lazily on demand; no background refresh, no timers.
- **Resolution:**
  1. Cache holds `kid` and is within `jwks_cache_seconds` → return it (no network).
  2. Cache holds `kid` but is stale → refetch once; return `kid` if present, else raise.
  3. Cache lacks `kid` → refetch once (rotation path); return `kid` if present, else raise. **At most one refetch per verification**, so a token with a bogus `kid` cannot be used to hammer the identity provider.
  4. Fetch failure (network error, non-200, malformed document) → if a cache entry exists and is within TTL, serve it; otherwise raise. **Never** return a key, an empty set, or skip verification. A JWKS outage must not become an API outage, and must never become a signature bypass.
- **Parsing:** strict. Only `kty=RSA` keys; only `use=sig` when `use` is present; `kid`, `n` and `e` required. A malformed key entry is skipped, never coerced. Keys are built with the crypto library's RSA key type.
- **Fetching:** the JWKS URI derives from `auth0_issuer` (`jwks_uri_for`), with an explicit bounded timeout. No invented provider endpoint.
- **Concurrency:** process-local, guarded so concurrent requests do not stampede a cold or rotating cache — one in-flight fetch is shared and the rest await its result. Each process keeps its own cache; the identity provider is the source of truth, so a cold cache costs one fetch, not correctness.

**New dependency.** JWT/crypto support is **not currently installed**: `services/api/pyproject.toml` records that `pyjwt[crypto]` was intentionally omitted during the P9 spike, and `uv.lock` has no JWT or `cryptography` package. P10 adds it — a single pinned `pyjwt[crypto]` dependency (which brings `cryptography` for RSA) — and records the resolved version. `uv.lock` changes are part of the approved scope. No other dependency is added.

## D. The `users` grant migration

**The gap.** `0002_rls_and_roles` grants the runtime role on `memberships`; `0007_outbox_terminal_state` grants `SELECT` on `workspaces`. Nothing grants `users`. Both `load_membership` and `list_workspaces` read `users`, so under `buyeros_api` every authenticated route fails with `permission denied for table users` (500). This was recorded as a blocking prerequisite during P9.

**Migration `0008_grant_users_select`** (new Alembic revision, `down_revision = "0007_outbox_terminal_state"`):

- Upgrade: `GRANT SELECT ON users TO buyeros_api, buyeros_worker;`
- Downgrade: `REVOKE SELECT ON users FROM buyeros_api, buyeros_worker;`

**SELECT only.** The API resolves actors by reading `users` and never writes them (see §E), so no `INSERT`/`UPDATE` grant is added and `users` gains no RLS policy. `users` stays non-RLS, consistent with `workspaces`.

This is a privilege grant, not a schema change: no table, column, index or row is touched, so it is safe to apply and safe to reverse. It is still a migration, and is therefore explicitly in scope for P10 rather than left implicit.

## E. Unknown-actor rule

A valid, verified token whose `(issuer, subject)` has no `users` row is treated exactly like a non-member: **non-enumerating `404 NOT_FOUND`**. No auto-provisioning. Membership creation remains an explicit, reviewed act. Because the API never creates `users` rows, the migration needs no write grant.

This also means a valid token for an unknown subject and a valid token for a subject who belongs to a different workspace are indistinguishable from the client's perspective, which is the required non-enumerating behavior.

## F. Testing

Four layers, each able to fail independently:

| Layer | File | Proves |
|---|---|---|
| Crypto and claims (unit) | `tests/test_auth_tenant.py` (new) | signature, `alg`, `kid`, `iss`, `aud`, `exp`, `nbf`, `sub` |
| JWKS cache (unit) | `tests/test_jwks_cache.py` (new) | TTL hit, stale refetch, rotation refetch, single-refetch bound, outage-serves-valid-cache, outage-with-no-cache-raises, malformed document |
| Authenticated routes (DB-backed) | extend `tests/test_api_tenant_isolation.py`, `tests/test_api_routes_contract.py` | real request → verify → membership → RLS-scoped rows |
| Regression | P9's auth tests and full suite | fail-closed behavior unchanged |

**Fixtures:** one `tests/auth_fixtures.py` module generates a session-scoped RSA keypair, exposes a JWKS document for it, a token-signing helper, and a fake fetcher the cache is constructed against. No network, no Auth0, no credentials. Tokens are minted in-process with real RS256, so production verification runs unmodified. The task document's single `test_auth_tenant.py` is split as above because the cache's state machine (rotation, staleness, outage) is not auth-claim logic and deserves its own isolated tests.

**Acceptance mapping:**

- **TEST-BO-004-01** — forged signature, `alg: none`, unknown `kid`, expired, future `nbf`, wrong issuer, wrong audience, and a valid token for a subject with no membership are each denied. The membership case is a non-enumerating `404`; the rest are `401 UNAUTHENTICATED`. No response discloses token contents.
- **TEST-BO-004-02** — authenticated as a seeded viewer, `POST .../projects` returns `403 PERMISSION_DENIED`; a valid member of workspace A requesting workspace B's `project_id` returns `404`.
- **TEST-BO-004-03** — readiness/capabilities responses contain no DSN, token, email or credential; the 401 body is a fixed generic message.

**Unskipped:** `test_api_tenant_isolation.py::test_route_tenant_scope_comes_from_the_membership_checked_path`, currently skipped with the `users`-grant blocker recorded, becomes a live assertion once `0008` lands.

## G. Out of scope (recorded, not silently dropped)

The BO-004 task document lists these as implementation steps; they are **deferred** and this document must not be read as covering them:

- **CORS origin allow-listing and CSRF posture** (task step 4). There is no browser client in this phase; frontend wiring is a later phase. No wildcard-credentials CORS is introduced.
- **Audit hooks carrying actor/workspace/request IDs** (task step 5). Request IDs already exist (P9 middleware); actor-scoped audit is deferred with the audit store.
- **Revocation and session policy.** Not modelled by RS256 access tokens alone; requires an identity-provider decision that B-IDENTITY owns.
- **Real Auth0 activation.** Blocked by B-IDENTITY; P10 proves the code path with a local keypair, and configuring a real tenant is a later, separately approved act.

## Completion criteria

The phase is complete only when its acceptance evidence is recorded and reviewed. A `401` from an unconfigured environment remains an expected state, not a passing integration; the passing integration is a signed token from the local fixture reaching real data through the membership check under the runtime role.

## Rollback / roll-forward

Roll back the verifier to the still-denying P9 stub — **never** to a no-auth state. `0008`'s downgrade revokes only the grant it added. Supersede this design with a dated successor for design changes.
