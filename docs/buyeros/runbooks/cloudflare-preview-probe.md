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

1. Select a protected disposable Vercel preview and disposable Neon branch;
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
approved branch/origin. No deployment or paid resource was created for CF00.
