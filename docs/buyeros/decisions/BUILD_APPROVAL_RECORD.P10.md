# Build approval record — P10 bearer identity (dependency waiver)

**Status: APPROVED (owner-authorized this session).** Plan revision v1. Recorded 2026-09-16 (Hong Kong).

| Field | Value |
|---|---|
| Task | **BO-004** — verify API bearer identity and enforce tenant membership |
| Phase | **P10 bearer identity** (first HTTP surface made executable) |
| Scope | Replace the fail-closed auth stub with real RS256/JWKS verification; add `JwksKeyCache` and `TokenVerifier`; wire `get_principal`; add Alembic `0008_grant_users_select`; authenticate DB-backed route acceptance tests |
| Spec | `docs/buyeros/specs/2026-09-16-p10-bearer-identity-design.md` |
| Plan | `docs/buyeros/plans/2026-09-16-p10-bearer-identity-implementation.md` |
| Base | branch `p10-bearer-identity` from `p9-api-surface` @ `b11cf5c` |
| Allowed files | create `services/api/buyeros_api/api/{jwks,verifier}.py`, `services/api/alembic/versions/0008_grant_users_select.py`, `services/api/tests/{auth_fixtures,test_jwks_cache,test_auth_tenant,test_auth_routes_db}.py`; modify `services/api/buyeros_api/api/auth.py`, `services/api/tests/{test_api_auth,test_api_tenant_isolation,test_api_routes_contract,test_api_buyers}.py`, `services/api/pyproject.toml`, `services/api/uv.lock`; docs under `docs/buyeros/**` |
| Scope extension (owner-approved, execution session) | `tests/test_api_routes_contract.py` and `tests/test_api_buyers.py` were added to the modify set so the **test-only** auth-seam migration could ride with Task 4. `get_principal` stops calling `principal_from_token`, so tests that made auth succeed by patching that symbol must patch `_verifier_from_settings` instead. No production behaviour change; keeping the suite green at every commit. |
| New dependency | `pyjwt[crypto]` (pinned) — P9 explicitly omitted it; `uv.lock` changes are in scope |
| Migration | `0008_grant_users_select` — `GRANT SELECT ON users` to the runtime roles. Privilege grant only; no table/column/index/row change; reversible |
| Dependencies with evidence | BO-003/BO-004 prerequisites waived (see below) |
| Approver | Owner (execution mode = subagent-driven) |
| Environment/spend | none; local disposable PostgreSQL and a local RSA keypair only |
| Excluded | real Auth0 activation, provider calls, deployments, cloud resources, real-data migrations, mailboxes, sends, frontend wiring, CORS/CSRF, audit hooks |

## Dependency waiver (explicit)

B-IDENTITY (a real Auth0 tenant) is unresolved, so live bearer verification cannot be exercised against a
hosted provider. The owner waived that prerequisite for this phase: P10 proves the **production verification
code path** (algorithm allow-list, signature, key selection, `iss`/`aud`/`exp`/`nbf`, JWKS caching and
rotation) using a local RSA keypair and an injected JWKS fetcher, with no network and no credentials.
Consequences accepted: no live login is exercised; activating a real tenant remains a separate, later act.
This waiver does not mark BO-003 or BO-004 complete in the task index and authorizes no other phase.

## Sign-off (owner)

Recorded from the owner's in-session direction on 2026-09-16: the owner approved the P10 spec, approved the
P10 implementation plan, and selected subagent-driven execution of that plan (option "1"). This record
captures that authorization; it is not a verbatim quotation and no remote push, deploy or activation is
authorized by it.
