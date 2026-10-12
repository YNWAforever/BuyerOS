# Owned API process and connection lifecycle

C61-25/F07/F11/F12/F18 continuation with the C61-19/20 retained-uncertainty boundary. Reuses the original API, RS256 verification, canonical identity, current membership, RLS, idempotency, rate admission, pools and delivery ledgers.

The default API inventory includes ten new native controls, also required as a positively discovered CI suite:

- A real spawned uvicorn process is stopped before project commit or after durable commit while its HTTP response is withheld. Owner SQL determines the state before another process submits the original key/body. One project, audit, complete idempotency response and budget-account snapshot survive; changed payload conflicts.
- Unknown/accepted delivery states are synthetic owned authority fixtures. Different OS process IDs, original message/operation refs, immutable outbox and full active hold are checked. Original-key reads replay; fresh keys are refused. A concrete provider-submit trap permits no provider POST, send, cost settlement or hold release.
- Explicit ASGI task cancellation before/after commit has distinct rollback/replay controls. It is not evidence that a browser disconnect or a production reverse proxy cancels a request. The independently committed rate admission remains durable.
- Original tenant/rate pools return cancelled transaction and waiting slots. The same backend PID has cleared transaction-local tenant/actor context, the original no-context policy refuses with SQLSTATE22P02, foreign writes fail, and owned A/B reads succeed. Lifespan shutdown is checked against actual backend PID disappearance.

Run from `services/api` with an owned disposable loopback `buyeros_test_*` database and `BUYEROS_STRICT_INTEGRATION=1`:

```sh
uv run --frozen pytest tests/test_owned_api_process_restart_db.py tests/test_owned_api_cancellation_db.py tests/test_owned_api_pool_recovery_db.py --collect-only -q
uv run --frozen pytest tests/test_owned_api_process_restart_db.py tests/test_owned_api_cancellation_db.py tests/test_owned_api_pool_recovery_db.py -q --junitxml=artifacts/c61-owned-api-lifecycle.xml
```

Default full API execution, all twelve required CI jobs and the original actual thirty-minute mixed workload remain required on the same candidate. These controls do not certify production DB/API/worker binding, real Neon sessions, compatible live rollback, provider activation, capacity SLO, human UAT or GS delivery acceptance.
