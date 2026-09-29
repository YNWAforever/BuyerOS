# BuyerOS worker runtime (T15)

This is a local runbook for one Celery/Valkey broker and the existing PostgreSQL outbox. It does not authorize a provider, deployment or paid request.

## Process roles

- The API commits job, budget hold and outbox intent together. A broker message is only a wakeup containing workspace, intent key and fencing generation.
- `buyeros-worker dispatch --loop --max-total 10 --time-budget-seconds 10` runs as a supervised process. One cycle rotates a workspace cursor, claims at most the global count and stops at the time budget; an empty workspace does not hold the cursor. The process probes the same Celery/Valkey broker before each cycle and records a global dispatcher heartbeat. A failure writes `unavailable` when PostgreSQL is reachable and uses bounded backoff. Ctrl+C disposes the engine.
- `buyeros-worker dispatch` and `buyeros-worker sweep` remain one-shot commands. Celery beat invokes the sweep task for expired dispatched leases. Running only worker+beat does not claim new ready rows: run the dispatcher process too.
- Celery tasks create an async engine on their own event loop, execute and dispose it before the loop closes. A ready row is rejected until claimed; generation fencing and terminal-state checks reject stale/duplicate delivery. Database-only handlers commit business effect and terminal outbox state together. The dispatcher DB credential must use the least-privilege `buyeros_worker` role; `buyeros_api` can read heartbeats but cannot write them. Local disposable tests grant a test-only login to this role.

## External operation boundary

`provider.external` and `provider.reconcile` are routed by the Celery task using server-owned outbox payloads. `external_runner.execute_external` commits a fenced `submitting` operation before the adapter await, then finalizes in a fresh transaction. A timeout or crash retains the reservation; accepted or unknown submission completes the original wakeup and creates one durable reconciliation intent. A duplicate wakeup cannot resubmit. Reconciliation with a verified reference may query status even after a later tariff change or cancellation request. It does not release a hold from a mere rejected/pending/unknown response. The external await holds no DB transaction.

The live provider registry is empty. T18–T22 must bind server-owned producer requests, verified cost evidence and actual vendor callbacks/status before activation. No fixture adapter is selected by a Celery process in production. The disposable fixture test proves routing and retention, not vendor acceptance or charge settlement.

On Windows, every worker and dispatcher entrypoint creates a Selector event loop for psycopg; engines are created and disposed on that same loop. The separate-process Celery/Valkey test exposed and then verified this requirement.

## Local checks and response

The exact T15 task check uses disposable PostgreSQL and Valkey: `BUYEROS_STRICT_INTEGRATION=1 uv run --frozen pytest -q tests/test_dispatcher_runtime.py tests/test_external_runner_db.py tests/test_valkey_integration.py tests/test_worker_integrity_db.py` from `services/worker`. Check its JUnit with `python scripts/check-required-tests.py --junit services/worker/artifacts/t15-task-green.xml` from the root. These tests do not prove a deployed broker or paid vendor.

On broker outage, leave committed ready/dispatched intents in PostgreSQL. Restore the single broker and dispatcher; the sweeper reclaims expired leases. On shutdown, stop new dispatch first, let workers finish or expire, and keep provider unknown holds for reconciliation. Do not flush Valkey, delete outbox rows or release unknown reservations to make dashboards look clear.
