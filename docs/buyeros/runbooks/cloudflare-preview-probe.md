# Protected native execution probe (CF00)

The local probe is harmless fictional PDF/ID-only graph work. It is not a worker,
does not create schema/roles, and rejects every non-loopback/shared/production DSN.
Local CPython and Docker results are not hosted Vercel proof.

## Local Linux reproduction

Read `services/api/tools/probe_worker_runtime.py` and the probe Dockerfile first.
Start an owned loopback `postgres:16` test container. Apply existing Alembic
head to a `buyeros_test_*` database and enable the test-only `buyeros_worker`
login. Inspect role catalogs: non-owner, non-superuser, NOBYPASSRLS, worker member.
Run the probe container with `--network container:<owned-postgres-name>` so
its DSN remains localhost. Do not use host networking or production credentials.
Supply an exact `BUYEROS_PROBE_SOURCE_SHA`; mount only the owned evidence output
directory. Run the Dockerfile's frozen no-dev entrypoint with `--output`.
Retain the native Linux report separately from the Windows report.

## Exact hosted proof to prepare before activation

1. Select dedicated protected Vercel project `buyeros-cf-preview` and a fresh
   empty Neon project `BuyerOS-CF-preview-20261001` (not a production clone);
   obtain specific authorization for preview deployment/role/schema/secrets.
2. Inspect actual app and API service runtime schemas and configured >=90-second
   budgets, region, memory/CPU, plan billing and deployment protection. Preserve
   `app -> api` binding and public routing. No production branch or user seeding.
3. Package the extracted API under its reviewed frozen no-dev lock. Measure
   actual deployed Python bundle, native imports, sanitized subprocess PDF
   extraction/8-second kill and Linux caps, cold/warm duration/CPU/peak memory.
4. Execute the same ID-only interrupted/resumed checkpoint graph and cross-tenant
   negative using the dedicated non-owner worker login. Runtime must not call
   checkpoint setup; Alembic alone owns schema. Never redirect existing destructive
   fixtures to this preview or any remote DSN.
5. Add a temporary protected diagnostic that runs a harmless >=60-second sleep,
   invoked through both the Nitro gateway and FastAPI hop, under machine HMAC.
   Confirm both budgets and uncertainty/status behavior; remove the diagnostic
   before RC. Do not raise customer run ceilings to obtain a pass.
6. Save deployment/source identities and measured output. Hosted fields remain
   `not_run` until that evidence exists. A native incompatibility requires revising
   the design before activation; it cannot be waived by a local/mock result.

There is intentionally no remote-execution switch in the local probe. A hosted
runner must use the separately reviewed machine-authenticated bridge and exact
approved new project/branch/origin. Actual generated IDs must be read back
before secrets or migrations. Budget config and optional header are locally
verified in CF08; no hosted diagnostic/remote fixture has been executed.
The temporary diagnostic is prepared at source
`07a7537befbf1e2290ee7079e18a258083615ed6`, in
`scripts/cloudflare-preview/runtime_probe.py` and
`scripts/prepare-cloudflare-preview.py`. The release API does not import it.
Deployment still requires exact new-target readback and specific hosted setup
authorization. Default-off, HMAC, role and expiry guards are locally verified.
Create/run that bounded diagnostic only within the specifically approved preview
session, then remove it; preserve the five internal operation contract.
Require protection denial without the bypass and application401 without valid
HMAC even with the bypass, no redirect forwarding, exact source readback and
private API binding. Collect actual60-plus-second two-hop output before claiming
90-second account support. Do not run local destructive fixtures remotely. No deployment or paid resource was created for CF00.

## Prepared overlay

The preparer renders four files into a new owned `.sites-runtime/cf-preview-*`
directory: temporary API entrypoint/target manifest, temporary gateway HMAC
allowlist and service configuration using that entrypoint with90-second budget.
App/API names, public catch-all and app→privateAPI binding remain the same.
Apply it to a Git archive of its exact recorded source, never the release
checkout or the overlay directory alone. There is one domain/migration owner.
No remote override was added to the original probe or destructive fixtures.

The non-secret target JSON has exactly these read-back fields:
`vercel_project_id`, `vercel_project_name`, `neon_project_id`,
`neon_project_name`, `neon_branch_id`, `neon_host`, `database`, `worker_role`,
`api_role`, `source_sha`, `session_started_at`, `expires_at`.
Pinned names: `buyeros-cf-preview`, `BuyerOS-CF-preview-20261001`, database
`buyeros_cf_preview`, logins `buyeros_cf_preview_api` and
`buyeros_cf_preview_worker`. The direct Singapore Neon host, TLS
`sslmode=require` and optional `channel_binding=require` must match exactly;
other DSN options/owner logins/production IDs fail closed. UTC timestamps must
be aware, active and no more than7200seconds apart. No field is an owner approval
record. Do not populate it with fictional test IDs for a real deployment.

```powershell
python scripts/prepare-cloudflare-preview.py --target-json .sites-runtime/cf-preview-target.json --output .sites-runtime/cf-preview-overlay-20261001
```

The preparer requires current committed UTF-8 source (CRLF normalized, every
substantive character retained), writes per-file hashes and rejects existing or
outside output. It creates no cloud resource, credentials, role or schema.

| API runtime input | Exact rule |
| --- | --- |
| `BUYEROS_PREVIEW_PROBE_ENABLED` | Missing/default false; exactly true only during approved test; disable/remove afterward. |
| `VERCEL_ENV`, `VERCEL_PROJECT_ID` | Actual injected preview environment and compiled new-project ID; expose system metadata, never fabricate it. |
| `BUYEROS_PREVIEW_PROBE_SOURCE_SHA` | Exact archived source, with separate overlay/deployment hashes retained. |
| `BUYEROS_PREVIEW_PROBE_KEY_ID` / `BUYEROS_PREVIEW_PROBE_SECRET` | New distinct cf-preview-* identity and32..4096byte secret, API/operator only, no Git/browser/log values. |
| API/worker/checkpoint DSNs | Compiled host/database/dedicated roles; runtime migration/admin DSNs forbidden. |
| Paid admission, R2, Cloudflare/Celery execution | false during native feasibility; remove this overlay before a later operational-controller phase. |
| Protection bypass | Dedicated new Vercel project; header to exact approved HTTPS origin only, no redirects/cookies/query; gateway strips it. |

POST `/v1/internal/runtime-probe` accepts exactly `{"operation":"native"}` or
`{"operation":"duration"}`,256bytes maximum, no duplicate/unknown fields or
query. Use existing worker header names with the distinct preview key:
`HMAC-SHA256(secret, POST + "\n" + exact_path + "\n" + unix_seconds + "\n" + canonical_UUID_nonce + "\n" + SHA256(raw_body))`.
The guard runs before I/O. Canonical PostgreSQL role/nonce checks commit before
work; replay409 survives app recreation and a failed diagnostic.

Duration really sleeps61seconds. Native checks use a separate45-second child,
DSN on bounded stdin, matching compiled target, sanitized environment and
8192byte output bound. Actual pinned imports, production PDF/8-second kill,
interrupted/resumed saver and cross-tenant negative run without setup/schema
creation. Linux checks observe installed AS/CPU/file caps. Error responses retain
only an error class. `development_dependencies_present=true` is not frozen
no-dev bundle proof. Reports deliberately leave hosted_feasible=false until
deployed bundle/protection/private binding/two-hop evidence is collected.

Local evidence:48/0/0/0 in93.90s (`CF00-preview-preparation-final.xml`), actual
61-second ASGI wait (`CF00-preview-duration-local.json`) and owned-PG native work
(`CF00-preview-native-local.json`). Only the isolated test fixture overrides
host validation for its strict owned loopback container; no product override.
Windows Linux caps remain NOT RUN. Initial red checks and two Git status-cache
fixture setup failures are retained; the corrected fixture verifies committed
content with git diff, not timing-sensitive stat-cache output.

Read-only preflight: Vercel team Pro/active and target lookup404; Neon
Free/PG18/Singapore and fresh name absent from22-project inventory; no BuyerOS
names in13Workers/4Queues/2Workflows. Workers account setting standard does not
prove Paid: subscriptions GET returned403. Billing and hosted setup are pending.
