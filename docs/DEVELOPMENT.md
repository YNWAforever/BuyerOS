# Development and executable checks

Run commands from the repository root unless stated otherwise. Keep `pnpm-lock.yaml`
and both Python `uv.lock` files frozen; do not replace pnpm with npm installation.

## Setup and local demo

CI uses Node 24, pnpm 11.25.0, Python 3.12 and uv 0.11.27. The package's Node floor
is 22.13.0. Docker and Chromium are needed only for the relevant integration layers.

```sh
corepack pnpm --version                         # 11.25.0
corepack pnpm install --frozen-lockfile
uv sync --project services/api --frozen
uv sync --project services/worker --frozen
corepack pnpm dev                               # http://localhost:5173/app
```

Python setup is optional for the demo and `test:core`. If Corepack's default cache
is unwritable in a sandbox, set `COREPACK_HOME` to a writable task/workspace cache
for those commands. Preserve configured proxies and CA trust.

## Execution profiles

`scripts/execution-profile.mjs` reads ignored `.sites-runtime/execution-profile.json`.
A clean clone defaults to `portable`: `dev` runs Vinext on port 5173; `build` runs
Vinext directly. The `managed-linux` profile uses Vite and the bounded build helper.
In a Sites-managed checkout, use the Sites plugin to configure the profile and own
the preview lifecycle. The managed `terminal.local:4173` address is internal only.
Profile state, caches, `.wrangler/`, `dist/` and `.vercel/` are not source artifacts.

## Local API and identity

For a manually configured development API, first identify an owned disposable
PostgreSQL target and use separate migration/runtime credentials. Alembic selects
`BUYEROS_DATABASE_MIGRATION_URL`, falling back to `BUYEROS_DATABASE_URL`; it is never
an automatic app-start migration. With those values already configured for the
verified local target:

```sh
(cd services/api && uv run --frozen alembic upgrade head)
(cd services/api && uv run --frozen uvicorn buyeros_api.api.vercel:app --host 127.0.0.1 --port 8000)
```

`GET /health/live` proves process liveness only. Point the frontend at the API with
public build-time `BUYEROS_API_BASE_URL=http://127.0.0.1:8000` and configure the exact
browser origin in API `BUYEROS_CORS_ORIGINS` (a JSON list). App root `.env` files are
not a universal Python service configuration loader; supply API environment explicitly.

Auth0 uses `BUYEROS_AUTH0_ISSUER`, `BUYEROS_AUTH0_CLIENT_ID` and
`BUYEROS_AUTH0_AUDIENCE` in the browser, plus API issuer/audience. Register the
`/auth/callback` URL on the public SPA client. Never provide a client secret to Vite.
Neon uses server-selected `BUYEROS_AUTH_PROVIDER=neon`, the cookie route, and separate
API JWT settings; see [deployment configuration](DEPLOYMENT.md#configuration-boundaries).
Signing in does not create membership. Use the owned synthetic test harness for local
acceptance without real credentials. Do not start the fixture server as a live API.

## Verification ladder

| Check | Command | What it proves |
| --- | --- | --- |
| Core client recovery | `corepack pnpm test:core` | Named Node cases: normalized research intent/retry, streamed progress, scope cancellation, draft recovery validation/isolation/capacity. No network or persistent writes. |
| Demo domain | `node tests/domain-checks.mjs` | Synthetic research, quotes/budgets, suppression and CSV behavior. |
| Live client boundary | `node tests/live-adapter-checks.mjs` | Request mapping, errors, auth/scope and intent behavior with deterministic transports. |
| TypeScript | `corepack pnpm exec tsc --noEmit` | Compile-time types, including generated API boundary. |
| Lint | `corepack pnpm lint` | Repository ESLint policy. |
| Cloudflare controller | `corepack pnpm cloudflare:types`, `corepack pnpm cloudflare:lint`, `corepack pnpm cloudflare:bindings`, `corepack pnpm cloudflare:test` | Local controller types, bindings and Queue/Workflow tests; not hosted execution. |
| API integration | `(cd services/api && BUYEROS_STRICT_INTEGRATION=1 uv run --frozen pytest tests -q)` | API/domain PostgreSQL integration; owns disposable containers when no DSN is inherited. Some specialized targets need the CI setup below. |
| Worker integration | `(cd services/worker && BUYEROS_STRICT_INTEGRATION=1 uv run --frozen pytest tests -q)` | Worker/broker recovery and domain integration in disposable fixtures. |
| Core browser journey | `services/api/.venv/bin/python services/api/tools/run_core_isolated.py` | Owned PostgreSQL, synthetic OIDC/research, saved draft readback and retry. Requires both venvs, Docker, pnpm and Chromium. |

For the core browser runner install Chromium with `corepack pnpm exec playwright install chromium`
and OS browser dependencies as needed. It owns ports 8000/5173, refuses existing
fixture markers/servers, creates evidence under ignored `outputs/core-isolated-*`,
and verifies container identity again before exact cleanup. The runner currently
uses `/workspace/.cache` for child Corepack/uv caches; outside managed Linux review
that path before choosing this runner. It is not a portable one-command live setup.

**Database fixtures are destructive.** Start with no inherited `BUYEROS_*` database
selectors. The full CI jobs additionally create owned policy and marketing targets;
copy their setup/cleanup steps from
[`buyeros-ci.yml`](../.github/workflows/buyeros-ci.yml) when reproducing the entire
suite. Loopback and a test-looking database name alone do not establish ownership.
Use existing identity receipts, not a production/preview DSN. Strict mode turns
unavailable integration dependencies into failures; skipped integration tests are
not acceptance evidence.

### Named CI evidence

```sh
corepack pnpm test:core --test-reporter=junit --test-reporter-destination=test-results/core-client.xml
python scripts/check-required-tests.py --junit test-results/core-client.xml
```

The wrapper puts Node flags before test files and uses `--experimental-test-isolation=none` to
preserve named cases on the supported runtime. Tests restore per-test fetch mocks.
CI also requires 21 unique named cases, rejecting file-only reports; update that
inventory deliberately when adding cases. Use `--test-name-pattern` only for local
iteration, never as the required whole-suite evidence.

## Contracts and migrations

The browser contract is `docs/buyeros/contracts/openapi.proposed.yaml`; generated
files are not hand-maintained copies of business rules. After changing the contract:

```sh
node scripts/generate-api-types.mjs --write
node scripts/generate-api-types.mjs --check
(cd services/api && uv run --frozen python ../../scripts/generate-operation-routes.py --check)
node --test tests/api-types-generation.test.mjs
corepack pnpm exec tsc --noEmit
```

If route generation is stale, run the same Python generator without `--check`,
review the diff and rerun the check. Worker API generation has a separate
`scripts/generate-worker-api-types.mjs` entrypoint. Review migration SQL, grants/RLS,
upgrade and retained-history rollback behavior on owned fixtures. `db:generate`
is for the optional D1 starter example, not BuyerOS domain schema changes.

## Builds

```sh
corepack pnpm build                  # default Cloudflare frontend artifact
corepack pnpm start                  # local built Worker, loopback, not deployment
node scripts/run-vercel.mjs build    # Vercel/Nitro app artifact
```

The Vercel target forces same-origin live mode; an auth-unavailable state without
server configuration is expected. Production deployment and full service readiness
are separate checks described in [DEPLOYMENT.md](DEPLOYMENT.md).
