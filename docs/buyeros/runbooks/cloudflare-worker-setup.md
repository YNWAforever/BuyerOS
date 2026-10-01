# Cloudflare execution setup and recovery

Status: local implementation/fixtures only. No Cloudflare resources, production
migration, paid providers or delivery have been activated by this migration.
Architecture exception and local implementation approval are in TASKS.json;
they do not authorize production activation. Auth0, Neon, R2 and the one native
FastAPI domain owner remain. Celery is a compatible optional adapter.

## Required configuration

| Location | Variable/binding | Source and rule |
|---|---|---|
| Worker | `JOBS` / `JOB_WORKFLOW` / `QUARANTINE` | One private active queue `buyeros-jobs`, Workflow `buyeros-job`, DLQ `buyeros-jobs-dlq`; no HTTP route. |
| Worker | `EXECUTION_ENABLED` | `false` until exact hosted activation approval. |
| Worker | `RUNTIME_EPOCH` | Current DB selector epoch, never guessed or reset. |
| Worker | `WORKER_API_ORIGIN`, `WORKER_API_ALLOWED_ORIGINS` | Exact approved HTTPS origin and JSON allowlist, no path/query/userinfo. Production URL/protection still to be verified. |
| Worker + API | current key ID/secret; optional previous pair | Newly generated machine key in server-only secret stores. Do not put in Git/browser/public env. API uses `BUYEROS_WORKER_*`; Worker uses `WORKER_*`. |
| Worker only | `WORKER_API_PROTECTION_BYPASS` (optional) | Dedicated preview project automation bypass secret. Header only after HTTPS origin approval; never URL/query/cookie/browser. Proxy strips it before the internal API. No value committed/configured. |
| API | `BUYEROS_EXECUTION_DATABASE_URL` | Dedicated nonowner NOBYPASSRLS member of `buyeros_worker`; inspect current role catalog. No production migration connection. |
| API | `BUYEROS_CLOUDFLARE_EXECUTION_ENABLED` | `false` by default; selector and environment must both agree. |
| API | `BUYEROS_RETENTION_POLICY_VERSION` | Explicit reviewed current retention policy, maximum64 characters; absent means no invented automatic retention policy. |
| API | existing provider/price/paid dispatch/reads/policy gates | Independently approved, unchanged. Never give these credentials to the Worker. |
| Operator only | `BUYEROS_RUNTIME_ADMIN_DATABASE_URL` | Explicit approved migration/operator connection, never an application runtime secret. |

Inspect wrangler.jsonc for exact queue/Workflow names. Config is default off,
Cron once per minute, Queue batch1/concurrency1/retries5. DB global permit is
the authority for one native execution step. Queue concurrency alone cannot
limit Workflow concurrency. Generated contract is public78 + separate internal5.

## Admission and execution budgets

Claims: at most10 opaque IDs in10 seconds, persistent tenant cursor. Maintenance:
at most10 recovered parents/tombstones in10 seconds; at most one new status-only
child per parent, with parent held dispatched until all uncertain operations
have durable children. Flush tenant writes before each scope change. Never run
provider or object-store I/O while holding recovery locks.

Native step:60 seconds, network45, PDF child8; HTTP75, Workflow step90,
response receipt2048 bytes and request8192 bytes. At most512 durable step receipts
per outbox and2048 controller actions. Transport retries5, backoff≤30 seconds;
permit contention does not consume the transient retry budget. Stored money,
query/page/time counters and approvals are not reset on restart.

Both local budget mechanisms are validated: API service functions use the resolved
`buyeros_api/api/vercel.py` with maxDuration90; Nitro emits the app gateway
`.vc-config.json` with maxDuration90. These are schema/build proofs. Actual hosted
plan enforcement, native bundle, parser, checkpoint and protected signed hop remain
unverified activation gates; local timing does not establish account capability.

## Readiness and alerts

An actual Queue→Workflow→signed API operational probe records only UUID, epoch
and API timestamp. Readiness is ready only for the selected/enabled Cloudflare
epoch with receipt age0..180 seconds. Environment flags, old Celery heartbeats,
direct claim calls and duplicate probe IDs cannot refresh this proof.

`PROBE_STALE`: receipt missing/old, epoch mismatch or execution paused.
`WORK_BACKLOG`: persisted oldest ready/dispatched work older than300 seconds.
The cursor accumulates oldest age across a bounded full tenant sweep; it may
lag by the sweep duration. Hosted alert routing/notification is not configured.

## Pause, drain, fence and resume

1. Stop new admission and set Worker `EXECUTION_ENABLED=false` using the approved
   platform change. Disable paid dispatch independently. Keep status-only
   reconciliation permitted where already approved. Do not purge either queue.
2. Inspect current DB selector and all dispatched leases, step receipts,
   unknown/submitting operations and holds. Take approved backup/operational
   evidence. Never release unknown holds just to empty a queue.
3. Preview the exact DB change using the operator tool (API cwd):
   `uv run --frozen python tools/set_execution_runtime.py --expected-epoch N --backend cloudflare --enabled false --reason "Reviewed incident pause"`.
   Default is dry run. Only explicitly approved execution adds `--apply`.
   The DB role must be privileged; staff/API/Worker roles cannot activate.
4. Pause increments epoch atomically, immediately fencing late claims/finalizers.
   Preserve existing permit until it expires/drains. Enabling either runtime
   refuses any live permit or dispatched lease. CAS rejects stale epoch.
5. Deploy a compatible reviewed API/legacy adapter with execution off; inspect
   actual deployed SHA/schema0035 and stop every unsupported old claimer.
   Old binaries that ignore the selector must never remain connected.
6. After real drain, recover expired local receipts to a newer generation.
   Unknown/submitting/accepted/pending provider operations receive only permanent
   status-only reconciliation keys; no repeated submit, settlement or hold
   release in maintenance. Invalid intent is retained failed for inspection,
   without inventing an operation identity. Reconciliation children can poll in
   newer generations. Terminal business rows stay terminal even after platform
   instance deletion or retention expiry. Never restart the same Workflow ID.
7. Preview/approve the selected backend + enabled change with the new epoch.
   Only then synchronize Worker epoch/env and verify a real fresh probe.
   CF→Celery is tested on disposable DB only; no fallback worker/broker is
   provisioned by this migration. Compatibility and available resources are
   prerequisites, not inferred from a green test.

## Schema rollback and restore

Migration owner: API Alembic, next allocated0035 after0034; no revision overwritten.
0035 adds a minimal global probe row, persistent recovery cursor and limited API
selector reads. Empty upgrade→downgrade0034→re-upgrade is locally verified.
Populated probe/recovery evidence refuses downgrade atomically, preserving
holds, operations and receipts. After activation use pause + compatible roll
forward; do not drop operational evidence or decrement epoch.

For an older-backup restore keep `BUYEROS_LIVE_READ_ENABLED=false`, admission and
dispatch off. Replay the external authoritative tombstone journal before any
read enablement. Reapply source/contact redaction, approval/export invalidation
and physical deletion intents idempotently; then prove tenant RLS, ledger/spend
conservation and private-object deletion. Local two-container rehearsal uses
a separately held fictional journal/private-store seam. Real journal custody,
authenticity/completeness and real R2 deletion remain external gates.

## Local verification versus hosted verification

Run with strict integration and no shared DSN. Tests create fresh owned loopback
`buyeros_test_*` Docker clusters; no production credentials are inherited by
Workers. Actual local Queue/Workflow/HMAC/PG evidence is recorded separately
from HTTP mocks and fictional identity/provider/R2 seams in CF06 checkpoint.
The killed-process test really kills a native process after committed receipt,
then advances owned fixture lease clocks; it proves one resumed buyer update
and audit, not live provider acceptance.

Mailbox/CRM/sending remain off. Approved draft delivery still returns403
`DELIVERY_DISABLED`. Hosted resources, production schema/selector, provider scope,
R2 policy and pilot activation require the exact later reviewed proposal.

## Isolated preview target (prepared, not created)

`wrangler.jsonc` defines `--env preview`: private Worker/Queue
`buyeros-jobs-preview`, DLQ `buyeros-jobs-preview-dlq`, Workflow
`buyeros-job-preview`. Default and preview execution are off, origins
invalid/allowlist empty and no fetch/public route exists. Do not set the Vercel
service binding manually. Preview variable/secret placement and the exact
resource/migration/scope decision are in
[the current release handoff](../CLOUDFLARE_RELEASE_CANDIDATE_HANDOFF_20261001.md).
Root production names stay distinct. `WORKER_API_PROTECTION_BYPASS` is optional
and absent from committed Wrangler vars and required-secret types.
The typed API-client settings accept it at runtime; application HMAC is independent.
[Vercel automation protection bypass](https://vercel.com/docs/deployment-protection/methods-to-bypass-deployment-protection/protection-bypass-automation)
uses a project-scoped secret; use a dedicated preview project because a token can
access other deployments in its project. No production token is reused.
