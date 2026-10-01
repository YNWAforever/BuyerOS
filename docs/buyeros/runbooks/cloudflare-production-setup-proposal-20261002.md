# Guarded Cloudflare production setup proposal

2026-10-02 Hong Kong. **PROPOSED; production changes are not approved or applied.**
Reviewed implementation source: `6ef38d184023163b8b671350ad151e25f72e3e84`.
Author review is recorded; independent review remains pending. Review draft
[PR10](https://github.com/YNWAforever/BuyerOS/pull/10) before this decision.

## Decision requested

Authorize an attended setup window of at most two hours: take a fresh recovery
branch, apply existing API-owned migrations0034–0036 to the exact production
database below, configure a restricted runtime login and server-only machine
secrets, deploy this compatible app/API with execution off, and create the three
private Cloudflare resources. Then briefly enable the matching selector/API/Worker
for **one ID-only Queue → Workflow → API operational probe**, verify its receipt,
and fence execution again. Cron stays empty throughout. This authorizes no
customer job, provider request, object-store activation, staff seeding or sending.
No billing-plan upgrade is included. Stop the affected platform step if its
existing plan cannot support it; complete independent approved preparation.

This is production setup and a bounded health check. Continuous dispatch and
business capability activation need their own cost, locality, alert and policy
disposition. A positive probe alone does not make the product live.

## Exact targets and current evidence

| Target | Inspected identity and state |
| --- | --- |
| Vercel | Existing `buyer-os`, `prj_qLOzTdqNiKvoS5rBjy5zZ2GeZgMw`, team `team_qvzlsFmfCsLkgItSypqHjw3z`; Pro/active, Fluid, `iad1`, Node24. Production remains `dpl_wdPCQmzg7EkFusgFknHAA2tXdKth`, source `12327c7ac98849b90b0bd08f63872be7dd302ac6`, READY. |
| Public origin | `https://buyer-os-nu.vercel.app`; keep `app` catch-all public and `api` service internal. Existing app → api binding injects `BUYEROS_INTERNAL_API_URL` at function runtime. |
| Neon | `nameless-bar-15324691` / production `br-autumn-block-b3exsqii` / `neondb`; endpoint `ep-dark-dawn-b3au2rn1`, exact host `ep-dark-dawn-b3au2rn1.c-4.ap-southeast-1.aws.neon.tech`; PG18/Singapore/Free,0.25..2CU. Two branches observed; no branch deletion proposed. |
| Cloudflare | Account `e387dfbeded3deb5b8f0023a78a660b5`; production names absent. Create private Worker/Queue `buyeros-jobs`, DLQ `buyeros-jobs-dlq`, Workflow `buyeros-job`, class `BuyerOSJobWorkflow`. No HTTP route, workers.dev or preview URL. |
| Current drain | Read-only production snapshot: users/workspaces/memberships1 each, projects0, outbox/provider operations/holds0, no runtime connection. `buyeros_worker` is NOLOGIN. Repeat immediately before any migration/enablement; this snapshot is not a continuing drain guarantee. |
| Current schema | Actual production0033; no selector/step/nonce/probe tables. Existing `buyeros_graph` checkpoint versions0..9 and tenant FORCE RLS verified. Worker currently has unnecessary schema-version DML;0036 corrects it. |
| Protection | Existing project protection remains unchanged. Verify anonymous internal requests fail closed. If the public production alias requires a bypass, stop and prepare a separately reviewed dedicated protection arrangement; do not reuse the expired preview token. |

GET-only control-plane evidence and bounded READ ONLY/REPEATABLE READ SQL reports
are in `artifacts/cloudflare/CF08-production-*-20261002.json`. SQL used3s statement/
15s transaction limits and returned catalogs/aggregates only. Both transactions
rolled back; no fixture ran against production. A subsequent GET confirmed
production computeidle at2026-10-02 01:36:45HK.

## Configuration and secret sources

| Location | Proposed value/source |
| --- | --- |
| Existing API login | Preserve `BUYEROS_DATABASE_URL` and existing Auth0 issuer/audience/public SPA client/CORS; do not grant worker privileges to `buyeros_api`. |
| Native execution/checkpoints | `BUYEROS_EXECUTION_DATABASE_URL` and `BUYEROS_CHECKPOINT_DATABASE_URL`: TLS direct DSN for new `buyeros_cf_runtime`, INHERIT member of `buyeros_worker`, NOSUPERUSER/NOBYPASSRLS/NOCREATEDB/NOCREATEROLE/nonowner. Create it NOLOGIN first; generate its password privately after approval. |
| API machine identity | `BUYEROS_WORKER_CURRENT_KEY_ID=cf-prod-20261002`; newly generated `BUYEROS_WORKER_CURRENT_SECRET` in Vercel server-only sensitive production storage. No previous key pair or preview key reuse. |
| Worker identity | Matching `WORKER_CURRENT_KEY_ID` / `WORKER_CURRENT_SECRET`; only the secret store receives the value. Worker receives no database, Auth0, provider or object-store credential. |
| Worker routing | Exact HTTPS origin above and one-element `WORKER_API_ALLOWED_ORIGINS`; no path/query/userinfo. `RUNTIME_EPOCH` must equal fresh DB readback, never be reset or guessed. |
| Default off | Worker `EXECUTION_ENABLED=false`; API `BUYEROS_CLOUDFLARE_EXECUTION_ENABLED=false`; Celery/Render runtime flags, paid admission/dispatch, reconciliation egress and R2 false for this setup. No automatic retention policy is invented. |
| Probe phase | API Cloudflare gate and the DB selector/Worker may briefly be true only for the single opaque operational envelope. Other gates stay off; call no claim endpoint and publish no business envelope. |
| Bindings | Worker `JOBS` → private Queue; `QUARANTINE` → DLQ; `JOB_WORKFLOW` → Workflow. App → internal API remains Vercel's service binding, never a manually configured URL. |
| Operator only | Existing owner/direct TLS DSN only in short-lived local operator memory. It is never configured on API/Worker or passed to a test fixture. |

Review the prepared controller JSON, role SQL and generated migration SQL in
`artifacts/cloudflare/CF08-production-*-proposal.*`. These are review artifacts;
Alembic remains the sole schema owner. No numbered revision is overwritten.
Queue retention86400s; batch1/concurrency1/retries5. Global DB permit remains the
native concurrency authority. Source budgets: PDF8s/network45s/native60s/HTTP75s/
Workflow90s; both Vercel functions configure90s. Inspect actual resolved deployment
budgets before enabling the probe. Existing protected preview proved61s, not90s
maximum capacity or a production latency percentile.

## Ordered execution after the exact approval

1. Require green current-source CI and a real source-review disposition. Re-read
   origin, source/diff, production identities/plan, drain, schema and role catalog.
   Halt on unexpected source, branch, role, nonempty work/holds or quota limits.
2. Create `pre-cf-0036-20261002` from exact production branch, with no compute and
   no secret output. Retain its ID/LSN. This replaces reliance on the older
   pre-initialization branch; no restore is executed.
3. From `services/api`, owner-only `uv run --frozen alembic upgrade
   0036_checkpoint_schema_grants`; prove0036 and disabled selector/epoch readback.
   Create the new runtime login initially NOLOGIN, with inherited worker rights
   and no schema ownership/CREATE/version-table DML. The reviewed role SQL has
   no embedded password. Prove these catalogs before enabling LOGIN.
4. Configure the server-only values and explicitly disabled gates; deploy the
   exact source to the existing production project, keeping its aliases and
   protection. Inspect deployed SHA, app/API binding, API/native bundle and both
   function budgets. No diagnostic overlay/reproduction fixture is deployed.
5. Create the private production queues on the existing account plan, deploy the
   matching Worker/Workflow off with Cron `[]`, and inspect bindings/absence of
   public routes. Stop before any plan upgrade or unapproved protection change.
6. Recheck drain and actual epoch. Preview the operator CAS first; briefly enable
   the restricted login and API flag through a compatible deployment, then apply
   the approved backend/epoch change. Synchronize Worker epoch, enable it without
   Cron, and publish one fresh `{v:1,kind:'probe',probe_id:UUID,runtime_epoch:N}`.
   Inspect Workflow binding-origin completion and matching PG timestamp/epoch.
   Record nonce/probe rows separately from business rows. No direct maintenance
   call substitutes for the Queue-created Workflow.
7. Immediately fence again: selector disabled with a newer epoch, Worker off/
   Cron empty/origin invalid, dedicated runtime NOLOGIN, API production flag false
   and compatible off deployment. Keep API staff login available. Verify old
   epochs fail closed, held work unchanged, and receipt preserved. Retain queues;
   do not purge/downgrade/suspend shared production compute. Finish or perform
   required fencing at the two-hour boundary; no scheduled automation is created.
8. Verify current Auth0 login and FIMMICK/workspace_admin visibility through the
   UI with read-only scope. Existing live human confirmation is historical;
   this does not authorize the full customer/provider journey. Report actual
   source/deployment/receipt/role checks individually.

## Costs, locality, alerts and rollback

No Neon/Vercel/Cloudflare plan change, autoscale change or recurring Cron is
included. A continuously active two-hour window at the existing0.25..2CU settings
would use roughly0.5..4CU-hours plus startup/auto-suspend tail and other activity;
this is a scenario, not a bill cap or measured consumption. Remaining account
allowance is unverified. Cloudflare subscription GET403 prevents billing-plan
confirmation; `standard` does not prove Paid. Existing Vercel Pro usage is metered.

All-day minute polling would keep Neon awake: minimum180CU-hours per30-day month
exceeds the published Free100CU-hours. An ongoing schedule/Neon plan needs an
explicit decision; working-hour readiness is not silently changed. Current
[Neon quotas](https://github.com/neondatabase/website/blob/main/content/faqs/free-plan-limits-and-quotas.md),
[Cloudflare pricing](https://developers.cloudflare.com/workers/platform/pricing/),
[Workflow pricing](https://developers.cloudflare.com/workflows/reference/pricing/)
and [Vercel limits/billing](https://vercel.com/docs/functions/limitations) were
checked2026-10-02HK. No total saving or account bill is proven.

Controller metadata is global; Python remainsiad1 and Neon Singapore. The
ID-only probe carries no customer content. Customer-use locality/privacy
disposition remains a real policy gate. Production alert delivery remains
unconfigured: the attended operator observes probe age and errors in this window.
Continuous service needs approved notification routing for PROBE_STALE>180s and
WORK_BACKLOG>300s; no Slack/email message or new monitor is authorized here.

Safe rollback is paused execution on a compatible guarded API. Keep additive
schema and operational evidence;0035/0034 populated downgrades refuse,0036
compatibility downgrade intentionally retains read-only schema-version rights.
Never regrant version writes, decrement epochs, release unknown holds or reuse
Workflow IDs. No Render/Valkey fallback is provisioned. Restore/deletion-journal,
R2, provider/policy/pilot, manual assistive accessibility and the full production
staff journey remain external gates after this setup.
