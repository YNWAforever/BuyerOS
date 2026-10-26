# Build and deployment runbook

These instructions describe repository controls. Check the exact source SHA,
project, environment, schema and runtime receipts before treating a deployed URL as
that release. This documentation update does not provision or deploy anything.

## Targets

| Target | Build/configuration | Operational boundary |
| --- | --- | --- |
| Default frontend | `corepack pnpm build`; `dist/server/wrangler.json` | Vinext/Cloudflare frontend artifact. `pnpm start` previews locally. Optional starter D1 is not the domain DB. Sites publishing uses its hosting workflow. |
| Vercel app + API | `node scripts/run-vercel.mjs build`; root `vercel.json` | Nitro app service plus internal FastAPI service at `buyeros_api.api.vercel:app`. App owns routing/auth proxy. |
| Python execution | `render.yaml`, `scripts/run-render-worker.py` | Celery worker and dispatcher with persistent Valkey. Checked-in proposal starts in standby, auto-deploy off, and still references `codex/fix-vercel-tslib-ssr`; reconcile branch/SHA before provisioning. |
| Cloudflare execution alternative | `services/cloudflare-jobs/wrangler.jsonc` | Queue/Workflow controller calls authenticated worker API. Execution defaults off; workers.dev/preview URLs are disabled. Local tests do not deploy it. |

Do not deploy the default frontend artifact as a substitute for the Vercel app/API
build. `vercel.json` disables Git deployment for specific named branches; it does
not disable every new branch preview. Pushing a PR may trigger an existing project
preview integration. Provider/runtime admission remains independently gated.

## Configuration boundaries

| Scope | Required configuration / source of truth |
| --- | --- |
| Browser | `BUYEROS_API_BASE_URL` plus public Auth0 SPA values for that provider. Vite's Vercel target forces `/` as the same-origin API base. Never add secrets to `vite.config.ts` definitions. |
| Neon app auth | `BUYEROS_AUTH_PROVIDER=neon`, `BUYEROS_NEON_AUTH_ROUTE_ENABLED=1`, `BUYEROS_NEON_ENVIRONMENT`, `BUYEROS_NEON_AUTH_URL`, `BUYEROS_NEON_EXPECTED_AUTH_URL`, `BUYEROS_PUBLIC_ORIGIN`, `BUYEROS_NEON_EXPECTED_PUBLIC_ORIGIN`, server-only `BUYEROS_NEON_COOKIE_SECRET` (32+ characters). Exact expected URL/origin bindings and production environment are validated by `lib/auth/neon-config.ts`. |
| API auth/database | `services/api/buyeros_api/settings.py`: runtime `BUYEROS_DATABASE_URL`; separate migration-owner URL; `BUYEROS_AUTH_MODE` and issuer/audience/JWKS configuration for the selected provider. Neon has independent expected issuer/audience/JWKS bindings. Membership is DB-authoritative. |
| Execution | `services/worker/buyeros_worker/config.py`, API execution configuration and controller bindings. Match transport, runtime epoch, internal API identity, DB role and broker. Never enable both paths for the same work. |
| Private files/providers | API object-store configuration and named provider policies/credentials. Paid admission, delivery admission, paid dispatch, R2 and controller execution are distinct switches; none is a readiness shortcut. |

Configure values through the hosting project's scoped secret/configuration system.
Use the appropriate environment; do not copy production credentials into fixture
runs, commit `.env*`, or put credentials in docs, browser bundles or CI artifacts.

## Release procedure

1. **Verify the candidate.** Record full SHA and PR diff. Require BuyerOS CI at that
   SHA, including named discovery/execution evidence and zero required skips. Run
   both frontend build paths when changing shared runtime code. Retain the previous
   known-good deployment identity and migration compatibility assessment.
2. **Verify schema and runtime bindings.** Alembic is the only domain migration
   owner. `services/api/tools/check_schema_readiness.py` is a read-only readiness
   tool; app startup never runs migrations. Any required migration runs separately
   with the reviewed migration-owner target and upgrade/rollback plan. Never use the
   runtime API/worker role to alter schema.
3. **Collect bounded observations.** The manually dispatched
   [`buyeros-runtime-acceptance.yml`](../.github/workflows/buyeros-runtime-acceptance.yml)
   reads reviewed schema/API controls on `main` through the protected
   `buyeros-runtime-readonly` environment. Publication defaults off. Partial reads
   fail and do not constitute a promotion bundle.
4. **Stage and bind a candidate.** Dispatch
   [`buyeros-runtime-bundle.yml`](../.github/workflows/buyeros-runtime-bundle.yml)
   on `main` with the successful same-source `ci_run_id`. `stage_candidate` defaults
   false; enable it only for the explicitly approved staging operation. Protected
   contracts, exact identities, encrypted observations, runtime bundle and signoff
   bind the source, deployment and acceptance evidence. Do not hand-build a substitute
   bundle or treat an ordinary READY preview as this evidence.
5. **Promote through the guarded workflow.** After release approval, dispatch
   [`buyeros-promote.yml`](../.github/workflows/buyeros-promote.yml) on `main`, supplying
   the successful protected bundle's `runtime_run_id`. It uses the protected
   `buyeros-production-promote` environment, downloads the attested bundle, validates
   gates and executes the guarded promotion. Inspect `promotion.json` and hosted
   readback; a submitted workflow is not a completed rollout.
6. **Verify runtime.** Check the exact deployment/source, authenticated owned and
   foreign/revoked controls, saved-state reload, schema contract and worker/controller
   heartbeat. Verify any separately enabled provider operation with its receipt and
   ledger reconciliation. Keep fixture, anonymous HTTP and real staff/provider
   evidence separately identified.

No raw `vercel --prod`, `wrangler deploy`, blueprint application or migration command
is a replacement for these gates. The legacy Render setup and broader historical
release records remain under `docs/buyeros/runbooks/` and `docs/buyeros/RELEASE_READINESS.md`;
their recorded versions and permissions are not current-source acceptance.

## Rollback and incidents

Record the previous deployment ID before promotion; the protected staging workflow
binds `BUYEROS_ROLLBACK_DEPLOYMENT_ID`. Follow the reviewed release recovery decision
and verify source, alias and runtime readback after rollback. Do not assume a code
rollback reverses a domain migration or an external provider operation.

For ambiguous external submission, inspect the durable operation and reconciliation
state before retrying. Preserve reservations for unknown outcomes. For a schema
incompatibility, stop new admissions and restore a compatible application/runtime
combination; do not blindly downgrade retained history. For data restoration,
replay retention/erasure records before reopening reads. The
[architecture risk map](../ARCHITECTURE.md#risk-map) identifies the remaining operational
investments; a rollback is complete only when those relevant controls are verified.
