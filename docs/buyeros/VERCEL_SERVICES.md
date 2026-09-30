# Vercel Services configuration and activation status

`vercel.json` defines two HTTP services. `app` is the Vinext/React frontend built with Vite + Nitro's Vercel preset; it receives the public catch-all route. `api` is FastAPI at `services/api` and has no public service rewrite. The app's `/v1/*` route forwards each browser bearer request to `api` with the runtime service binding `BUYEROS_INTERNAL_API_URL`. Vercel generates this variable for the `app` function; do not set it in the dashboard or a build environment. Browser code uses a same-origin `/v1/*` URL and never receives the binding. The proxy handles FastAPI redirects manually and rewrites internal `/v1/*` locations back to the public path.

The Celery dispatcher/worker is a continuous Valkey consumer, not an HTTP request handler. It remains on the existing external worker host with the single approved Valkey broker. It does not call a Vercel service over HTTP, so there is no worker service or binding in this candidate. Database migrations remain Alembic's responsibility outside a Vercel build.

Local source checks:

```powershell
node --test tests/vercel-services.test.mjs
pnpm.cmd exec tsc --noEmit
pnpm.cmd lint
node scripts/run-vercel.mjs build
node --test tests/vercel-render.test.mjs
```

The build command emits Nitro's `.vercel/output` Build Output API bundle. With Vercel Services access and an approved, isolated runtime configuration, `vercel dev -L` is the service-level local check; a direct Nitro function smoke test does not prove Vercel's service router, Python builder, or deployed networking. Vercel reports approved production deployment `dpl_GEgeCkt2iBUhvvLDEXD7yn74y1Q3` READY at source `62d40bc7687477f42e971ae5143485806630f1a6`. Live initial HTML, anonymous proxy routing and Auth0 login entry have passed; authenticated staff access and the complete staff journey remain unverified.

The public Auth0 issuer/client ID and same-origin API configuration are saved in Vercel production. User-approved Neon initialization reached `0033_api_rate_windows`; the restricted, pooled `buyeros_api` connection is saved as sensitive `BUYEROS_DATABASE_URL`. The migration owner is not stored in Vercel. The user-approved deployment dpl_GEgeCkt2iBUhvvLDEXD7yn74y1Q3 applied the nine saved production values; the public API proxy returns expected unauthenticated 401, and three frontend routes return 200. Paid admission and R2 remain false.

The user-approved Auth0 configuration is now applied and verified. BuyerOS is a public SPA with token endpoint authentication None and authorization-code/PKCE; both production aliases have callback `/auth/callback`, logout `/app` and exact origins, with existing localhost entries retained. The custom BuyerOS API `https://buyer-os-nu.vercel.app/v1` uses RS256 and one-hour access tokens, with offline access disabled. `BUYEROS_AUTH0_AUDIENCE` is saved in Vercel production. Both production callback probes now return expected unauthenticated `login_required`; an invalid callback and unknown audience are rejected.

The approved production deployment serves `/`, `/app` and `/auth/callback` with initial HTML HTTP 200. A browser reaches Auth0 Universal Login from Sign in with no application console/page errors. The real authorization request uses the exact saved public client ID, audience and primary callback, response type `code` and PKCE S256. No real staff token or authenticated application session has been verified. See [the exact configuration and results](AUTH0_CONFIGURATION_PROPOSAL.json).

See [the current execution checkpoint](REMAINING_DEVELOPMENT_STATUS.md) for exact source, migration, restore-branch, permission and environment evidence. The separately approved first FIMMICK workspace and verified account's active workspace_admin membership are committed and read back in Neon; [the setup execution record](INITIAL_WORKSPACE_PROPOSAL.json) distinguishes the denied owner role-switch check from successful exact-row/catalog verification. Fresh anonymous deployment checks passed 4/4; the user confirmed FIMMICK and the admin role visible on 2026-10-01 HK. Full staff continuity and an agent-observed authenticated API trace remain unverified. Provider, R2 and continuous worker/Valkey remain open gates. No service binding authorizes a paid provider, enables sending or changes the disabled delivery endpoint.

## Linux SSR regression and source fix

The production frontend initially returned 500 while RSC/API routing worked and the browser recovered to Sign in. This was reproduced from committed source on Linux Node 24.18.0: the workspace chunk imported tslib's CommonJS default through its Node export wrapper and crashed before rendering. For the Vercel build only, `vite.config.ts` resolves bare tslib to the package's public `tslib.es6.mjs` entry. Exact tslib 2.8.1 is now an explicit dependency, preserving the already-locked version. The emitted-function regression runs in Linux CI after the build; the baseline failed 3/3 and the fixed candidate passed 3/3.

The changed source is deployed in production after the user's specific approval. The separate anonymous deployed check is explicit: set `BUYEROS_VERCEL_VERIFY_URL` to the exact origin and run `node --test tests/deployment/vercel-runtime.mjs`. Its latest production result on source 62d40bc is **4 passed, 0 failed/cancelled/skipped in 5271.2125ms**; the earlier source 0852552 result was 1 pass/3 failures. It does not acquire a token, mutate data or call a provider.
