# Q02 local repair evidence — 2026-10-03

Base `338ee8e623b0f9b117c5cd6d3f84dc63a0a05b9d`; reviewed source `fb184819d038dc2ad56b7f1746362fe9b7a6089a`. No push, GitHub PR, merge, deployment, production mutation, email, identity linking, or provider activation. Cases U06/U07/U08/S06; local F03/F04.

## Environment

Windows PowerShell; host Node24.18.0/pnpm11.25.0; frozen uv Python3.14.6. Docker Postgres16 disposable loopback `buyeros_test_*`; non-owner runtime role with RLS; existing fixture guards unchanged. Chromium Playwright1.63.0. UI uses the existing owned Linux Node22.23.2 Vinext/Nitro Vercel-target fixture, localhost5173 and loopback API8000. Fake public OIDC client/issuer; no real identity/provider acceptance. Real database inserts/queries/HTTP responses/mutations, separated from mocked identity.

Commands below run from the isolated worktree unless `services/api` is specified. `BUYEROS_TEST_DATABASE_URL` and `BUYEROS_DATABASE_URL` are unset before pytest; all necessary DB suites have `BUYEROS_STRICT_INTEGRATION=1`.

## RED evidence

| Run | Result | What failed |
|---|---|---|
| `uv run --frozen --project services/api pytest -q services/api/tests/test_membership_directory_db.py --junitxml=test-results/q02-api-red-final.xml` | 3fail/2pass/0skip | Search returns250 rather than1; duplicate names missing; eligible lookup absent |
| `node node_modules/@playwright/test/cli.js test --config playwright.audit-fixes.config.ts tests/e2e/audit-memberships.spec.ts --grep 'all 250'` | 1fail | Expected20 rows, received100; original UI no subsequent pages |
| Waiting-admin regression with only the added post-lock `_admin` removed, always restored in finally | 1fail/5deselected/0skip | Baseline authorization-before-lock behavior writes200 after administrator revocation, expected403 |
| `uv run --frozen --project services/api pytest -q services/api/tests/test_membership_directory_db.py -k pre_q02` | 1fail/6deselected/0skip | Legacy durable response misses required display_name |
| `node node_modules/@playwright/test/cli.js test --config playwright.audit-fixes.config.ts tests/e2e/audit-memberships.spec.ts --grep 'lost committed'` | 1fail | Unknown membership result lacks explicit reconciliation guidance |

Early wrong working-directory/file-not-found, fictional fixture cleanup FK/column errors, type-error interruption, occupied-port runs and cleanup loader errors are execution/fixture errors, not product RED. The first complete UI six-case run5pass/1fail found a real late Settings locale overwrite, fixed by leaving locale to its existing global owner. A later 29-case run was interrupted after a fake callback readiness timeout (`Completing sign-in…`); the helper now waits for the authenticated workspace access request, keeping all result/role/count assertions and test timeouts. Prior full28-case run passed; final gate recorded below is on current source.

## Final GREEN gates

- `services/api`: `uv run --frozen pytest -q tests/test_membership_directory_db.py tests/test_admin_operations_db.py tests/test_bulk_jobs_db.py tests/test_tenant_isolation_db.py tests/test_buyer_review_db.py tests/test_api_routes_contract.py --junitxml=../../test-results/q02-api-cwd-final.xml` → **72pass/0fail/0skip/0error**, 14 deprecation warnings, 275.01s. A prior invocation from repo root gave70pass/2fail due to these existing contract tests' relative paths; preserved separately. Covers7 new directory cases, admin/revocation/idempotency, bulk/individual owner behavior, actual RLS, route contracts and owned-DB migration rollback tests.
- `node --test tests/audit-auth-render.test.mjs tests/audit-research-intent.test.mjs tests/audit-draft-guard.test.mjs tests/audit-member-contract.test.mjs` → **13pass/0fail/0skip**.
- Final UI: `node node_modules/@playwright/test/cli.js test --config playwright.audit-fixes.config.ts` → **29pass/0fail/0skip/0error**, JUnit aggregate 348.635498s (console5.8min). All required audit specs actually matched; zero-tests/skip is not accepted. Named Q02 suite has7 cases; four preceding repairs have22.
- `node scripts/generate-api-types.mjs --check` → exit0; `uv run --frozen --project services/api python scripts/generate-operation-routes.py --check` → exit0,79operations.
- `node node_modules/typescript/bin/tsc --noEmit` and ESLint on changed settings/directory/locale/test/helper/client-contract files → exit0. Readiness helper lint additionally checked.

## Case details

| Case | Concrete evidence | Limit |
|---|---|---|
| U06 | All250 IDs exactly once through13 pages; searchable101st row; literal%/_ search; filtered total; empty range; late page/A-B-A; 503read/retry; en/zh-HK390px | Fixture scale250, no10k/product p95 claim |
| U07 | Authorized names + full IDs for duplicate Alex names/same tail8; missing name fallback; no email/issuer/subject/token projection; exact If-Match/reason/key; durable changed version2 with other member version1; legacy replay; one lost-response PATCH then read | No live admin grant or identity migration |
| U08 | Two simultaneous self-demotions: one200, one409LAST_ADMIN, one active admin and one audit. Sole-admin UI rejection understandable. Authority revoked during advisory wait returns403, target version1/audit0 | Actual owned Postgres concurrency; no production account rehearsal |
| S06 | Current-role admin directory/operator-admin eligible lookup; viewer/reviewer negatives; cross-workspace404; forced RLS suites; inactive assignee omitted and rejected on submission | Current Auth0 fixture authority; N05/Neon matrix remains unexecuted |

## Schema, rollback, performance, release

No new Alembic revision, schema migration, backfill or identity link. `uv run --frozen alembic heads` inservices/api → `0036_checkpoint_schema_grants (head)`. Existing integration tests exercise owned empty downgrade/upgrades0011/0016/0017 and restore currenthead. Three destructive/owner guards byte-equal tobase.

Rollback is one Q02 source/contract revert. `git apply --check --reverse Q02.patch` passed against the staged complete20-file boundary; no actual revert or database mutation performed.. Audited role changes need separate compensating approval and current version; no automatic data reversal.

Test wall times include local startup, fixture crypto, container/DB work, and host contention. No database cold-start/root-cause or production latency inference. Q16 lacks SQLSTATE/driver/pool evidence; Q17 remains blocked. Actual staff/live identity rehearsal, paid providers, production auth/config/grants/deployment, Neon N00 built compatibility and full programme release remain separate gates. Next eligible local task Q05; original source evidence package and98original case fields remain immutable.
