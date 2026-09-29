# Vercel Services deployment candidate

`vercel.json` defines two HTTP services. `app` is the Vinext/React frontend built with Vite + Nitro's Vercel preset; it receives the public catch-all route. `api` is FastAPI at `services/api` and has no public service rewrite. The app's `/v1/*` route forwards each browser bearer request to `api` with the runtime service binding `BUYEROS_INTERNAL_API_URL`. Vercel generates this variable for the `app` function; do not set it in the dashboard or a build environment. Browser code uses a same-origin `/v1/*` URL and never receives the binding. The proxy handles FastAPI redirects manually and rewrites internal `/v1/*` locations back to the public path.

The Celery dispatcher/worker is a continuous Valkey consumer, not an HTTP request handler. It remains on the existing external worker host with the single approved Valkey broker. It does not call a Vercel service over HTTP, so there is no worker service or binding in this candidate. Database migrations remain Alembic's responsibility outside a Vercel build.

Local source checks:

```powershell
node --test tests/vercel-services.test.mjs
pnpm.cmd exec tsc --noEmit
pnpm.cmd lint
node scripts/run-vercel.mjs build
```

The last command emits Nitro's `.vercel/output` Build Output API bundle. With Vercel Services access and an approved, isolated runtime configuration, `vercel dev -L` is the service-level local check; a direct Nitro function smoke test does not prove Vercel's service router, Python builder, or deployed networking. This configuration has not been deployed.

The live app also needs the public Auth0 SPA issuer, client ID and audience described in the README, and the API needs its corresponding issuer/audience and an explicitly configured `BUYEROS_DATABASE_URL`. Apply Alembic migrations via the established migration process. Provider, R2, Render worker, Valkey and Neon activation still require their separate existing decisions. No service binding authorizes a paid provider, enables sending or changes the disabled delivery endpoint.
