# BuyerOS Render worker setup for review

Prepared on 2026-10-01 after the user asked the agent to create the worker. **Not provisioned or activated.** The repository root [render.yaml](../../../render.yaml) defines the following exact proposal. Render account/workspace access and the priced-resource decision remain pending.

## Resources and cost

| Name | Role | Region | Plan / instances | Base monthly cost |
| --- | --- | --- | --- | --- |
| buyer-os-worker | Celery consumer and its existing recovery beat schedule | Singapore | 0.5c-512mb / 1 | US$7 |
| buyer-os-dispatcher | Continuous PostgreSQL outbox dispatcher | Singapore | 0.5c-512mb / 1 | US$7 |
| buyer-os-broker | The single Valkey broker | Singapore | 256mb | US$10 |

**Total base resource price: US$24/month.** This excludes tax, the account's existing workspace plan, bandwidth/build overages and other usage extras; it is not a hard invoice cap. No workspace plan upgrade or additional disk/database is proposed. Prices and new plan IDs were checked against [Render pricing](https://render.com/pricing) and [compute plans](https://render.com/docs/compute-plans) on 2026-10-01. The 512 MB worker is an initial configuration; representative memory/throughput has not been measured on Render. Any size increase requires a revised cost decision.

Both processes initially have `BUYEROS_WORKER_RUNTIME_ENABLED=false`. The launcher imports no BuyerOS application module in standby, opens no database/broker connection and waits for shutdown. Paying for these resources would not establish worker integration or authorize consuming production jobs. Paid dispatch and R2 remain false; delivery stays permanently disabled.

## Build and routing

- Repository: YNWAforever/BuyerOS; candidate branch `codex/fix-vercel-tslib-ssr`. Verify its exact reviewed/CI-passing head before first creation and the actual deployed source after build. Automatic service deploys and paid preview environments are off. Do not create from an unreviewed later branch head.
- Build from the repository root so the existing `services/worker` editable dependency on `../api` resolves: `python -m pip install uv==0.11.27 && uv sync --project services/worker --frozen --no-dev --python 3.12`. This retains the existing frozen dependency lock and CI's Python 3.12 series.
- Start the consumer with `services/worker/.venv/bin/python scripts/run-render-worker.py worker`; start the dispatcher with the same interpreter and `dispatcher` argument.
- Upon separate runtime activation, the consumer execs the canonical `buyeros_worker.app:celery_app`, prefork concurrency1, prefetch1 and worker recycle after100 tasks. Its embedded beat uses the existing lease-recovery task; one instance prevents an extra scheduler. Beat's local schedule file is ephemeral; durable business/outbox/lease state remains in PostgreSQL.
- The dispatcher execs the existing `dispatch --loop --max-total 10 --time-budget-seconds 10 --idle-seconds 2` CLI. Worker+beat alone cannot publish newly committed ready intents. Both Render processes allow up to300 seconds for graceful platform shutdown.
- These are background processes with no HTTP route. The existing Vercel app and single bound internal FastAPI domain API remain the public application architecture. The API commits its PostgreSQL outbox; only the Render dispatcher publishes to Valkey. No external Valkey access or Vercel broker credential is needed.

## Runtime variables and their sources

| Variable | Initial source/value | Activation boundary |
| --- | --- | --- |
| PYTHONUNBUFFERED | 1 | Unbuffered status/error output |
| BUYEROS_ENVIRONMENT | production | Explicit environment required by activated launcher |
| BUYEROS_WORKER_RUNTIME_ENABLED | false | Keep false until the exact runtime/queue scope is authorized and connection/catalog checks pass |
| BUYEROS_EAGER | false | Real broker execution; fixture eager mode is not a production adapter |
| BUYEROS_PAID_DISPATCH_ENABLED | false | Named provider/policy/budget/pilot decision required before paid dispatch |
| BUYEROS_RECONCILIATION_ENABLED | true | Existing recovery semantics; standby still runs no tasks |
| BUYEROS_R2_ENABLED | false | Separate private-bucket/credential/retention approval |
| BUYEROS_BROKER_URL | Render fromService connectionString from buyer-os-broker, on both callers | One broker, database0, private network; do not paste or publish its URL |
| BUYEROS_DATABASE_URL | Not included in initial standby setup | Server-only Neon pooled TLS DSN for a dedicated buyeros_worker_runtime login inheriting the existing non-bypass buyeros_worker role; production role creation/grant and secret placement need an exact later decision |
| BUYEROS_CHECKPOINT_DATABASE_URL | Not included | Separate server-only worker graph connection if/when a reviewed graph/source-deletion capability requires it |
| BUYEROS_RETENTION_POLICY_VERSION | Not included | A genuinely reviewed policy version; do not invent an owner record |

The existing Neon project/branch/database remains nameless-bar-15324691 / br-autumn-block-b3exsqii / neondb. API/migration-owner credentials must not be reused for the worker. The dedicated login must have no superuser/createdb/createrole/replication/bypassrls or table/schema ownership. The launcher checks the intended login name and required TLS; this does **not** verify database role attributes, membership or RLS. Read the current catalog and verify the least-privilege role/session contract before activation. No SQL mutation or migration is part of this standby-resource proposal; sole Alembic head remains0033_api_rate_windows.

Valkey uses `noeviction`, `journal-snapshot` and an empty external IP allowlist. Current [Render Key Value documentation](https://render.com/docs/key-value) confirms new instances run Valkey8 and paid persistence is required. AOF can lose up to the last second of broker writes on interruption; PostgreSQL leases/fencing/recovery remain authoritative. No second broker, result backend, public route or destructive flush is introduced.

## Evidence and creation procedure

1. Verify the Render account/workspace identity and current billing plan through authenticated access. Official CLI2.28.0 is now prepared in ignored checkout-local storage, after checking its release archive SHA256 and all extraction paths; device sign-in is pending. No authenticated workspace/credential is yet verified. Check that the three proposed names do not match unrelated existing resources; a Blueprint can update matching existing names. Do not apply over unrelated services.
2. Obtain the concrete decision to create the two Singapore workers and one paid persistent Valkey instance at the US$24/month base price, initially in standby. A generic continuation supplies no priced provisioning or production role grant.
3. Verify the exact candidate SHA and fresh CI gates, including the frozen production build, canonical CLI imports, standalone nine-test launch regression, Linux standby/SIGTERM check, official Blueprint schema and the required zero-skip API/worker gates. Record evidence at that SHA.
4. Create only the reviewed resources; retain the returned resource IDs, region, plan, binding and deployed source as sanitized evidence. Verify both service logs say standby and both runtime-enabled/paid-dispatch switches are false. This initial state produces no genuine worker heartbeat and must not be shown as Connected/live-ready.
5. Prepare the exact Neon worker login/permissions, secret placement and activation scope for review. Then perform authorized catalog/connection/RLS/broker checks, enable the worker and dispatcher only for that scope, and retain actual heartbeat and end-to-end recovery evidence. Do not run production destructive fixtures, seed fictional rows or infer live provider acceptance from local fixtures.

Local evidence: named launch regressions first **0 passed/9 failed/0 skipped** against the absent launcher; implemented launcher **9 passed/0 failed/skipped**. Official schema validation first rejected YAML's unquoted `off` as boolean; quoting the intended enum corrected the configuration without changing the validator. The corrected schema and two standby `--check` commands pass; both canonical Celery/dispatcher help entrypoints import successfully.

Reviewed worker-setup source: **e061d33a32a46502a084d5a5c26d9262904a7b60**. [CI36807776580](https://github.com/YNWAforever/BuyerOS/actions/runs/36807776580) completed **6/6 jobs SUCCESS**. Retained artifact: artifacts/t30-render-worker-ci-e061d33-20261001.json. Actual required JUnit gates: API577/0/0/0, worker174/0/0/0, five continuity suites4+8+1+3+1 and zoom2, all zero failures/errors/skips; smoke1. New launcher9 passed in0.006s and real Linux standby/SIGTERM2 passed; exact frozen no-dev build, both standby checks and both canonical CLI imports pass with Python3.12.14/uv0.11.27. Official schema/manifest hashes match the local validation. Actual disposable DB/Valkey/dispatcher/Celery with fictional identity/search/contact proves fixture integration; it does not verify a deployed Render service or paid provider.

## Stop and rollback

Before any active rollback, stop new dispatcher publication first. Retain outbox, leases, recipient contexts, unknown-provider holds and ledger history. Allow the compatible worker to finish or safely expire, then change runtime-enabled to false and redeploy the reviewed standby launcher. Do not flush Valkey or replay addressed commands through pre4181062 workers. Current app/worker source12327c7 matches reviewed4181062; the candidate adds this launch/configuration layer. Resource suspension/deletion and billing cessation require explicit checks; this document neither deletes a broker nor claims invoice caps. Production schema stays unchanged.
