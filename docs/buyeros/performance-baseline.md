# T29 performance baseline — local candidate

Source checkout: `f43a9d88b334c2c4029fa06fa71624ed52efe4a2` plus the uncommitted BuyerOS implementation diff. This file records laboratory checks only. There is no reviewed release SHA or production p75 measurement.

## Acceptance conditions from SPEC

| Path | Proposed local target | Current evidence |
| --- | --- | --- |
| Warmed list/read API | P95 <= 500 ms, SQL pages <= 100, no N+1 at 10,000 buyers | Local warmed 1k/10k page P95 measured below 500 ms; in-process fixture only |
| Local mutation and job admission | P95 <= 1,000 ms without external calls; long work returns 202 | Post-rate-pool disposable in-process fixture: buyer PATCH 60.865 ms P95; queued run admission 168.524 ms P95 |
| Dispatcher | Fair progress across 100 workspaces; ready-to-publish P95 <= 5 seconds with healthy broker | Post-rate-pool disposable Valkey publish benchmark: 100/100 unique, P95 2.280 seconds; no worker consume or deployed proof |

## Reproducible read benchmark

Run from the repository root:

```powershell
python scripts/benchmark-buyeros.py --fixture-size 1000 --workspaces 1 --output artifacts/t29-benchmark-1k-1ws.json
python scripts/benchmark-buyeros.py --fixture-size 10000 --workspaces 100 --output artifacts/t29-benchmark-10k-100ws.json
```

For 100 workspaces, the wrapper also starts a disposable Valkey 8 broker stage after the API case. It publishes 100 safe `source.delete` fixture intents through the production dispatcher code; it does not start a Celery worker or call a paid provider. The wrapper refuses an inherited `BUYEROS_TEST_DATABASE_URL` and starts a disposable PostgreSQL 16 Docker container through the strict API fixture. It migrates that container to the sole Alembic head, creates fictional buyers/workspaces/projects/ICP revisions, and removes the container afterward. The case requests a 1,000-item frozen buyer snapshot, warms the last 100-item page three times, then measures 30 sequential and 10 concurrent in-process authenticated reads from one fixture staff actor on a persistent ASGI event loop. A later corrected run also measured ten concurrent distinct fixture staff actors. It records P50/P95, SQL statement count, response bytes, observed DB connections, snapshot-create time, machine/runtime and an `EXPLAIN (ANALYZE, BUFFERS)` plan. Fixture OIDC, no network, no provider, and no real staff identity are involved. Numbers must not be called production latency or live concurrency proof.

A safety check with an inherited external `BUYEROS_TEST_DATABASE_URL` exited 2 before any DB or Docker call. The first concurrent 1k attempt was interrupted before measurement when Docker Desktop stalled alongside the strict full API test. A subsequent isolated 1k run using Starlette TestClient passed its bounded-query check but produced a 3,191.676 ms sequential P95 and 89 DB connections: each TestClient request created a new event loop and cached engine. The SQL page EXPLAIN was 1.238 ms, so that P95 is a harness connection-churn result, not a valid persistent-server baseline. The benchmark now uses one ASGI event loop; the isolated reruns below are the valid local baseline for this harness. The command collected cleanly (1 opt-in case), and the wrapper and case passed Python syntax checks. The corrected persistent-loop read and disposable broker runs below supersede that harness result. Mutation and ten distinct fixture staff identities were measured subsequently; worker-consume age and production-network measurements remain separate work.

## Browser baseline

The built local Vinext/Wrangler server passed the fictional responsive suite 6/6 in 20.7 seconds: en and zh-HK at 390/768/1280/1440 CSS pixels, plus 720 and 320 CSS pixel reflow, reduced motion, buyer drawer keyboard focus return and a Chromium accessibility-tree scan for unnamed interactive controls. A 720 CSS pixel layout approximates a 1440 pixel viewport at 200% zoom; actual browser zoom, contrast auditing, screen reader labels and live Auth0 journey remain unverified. The API-backed production-build workbench suite later passed 5/5 with fixture OIDC and disposable PostgreSQL, covering en/zh-HK across six live routes at 320/390/720/768/1280/1440 CSS pixels, AX names, manual outcome persistence, locale race and partial-failure recovery. Four settled Operations screenshots were visually inspected and retained in `artifacts/t29-screenshots/`. The direct Vinext dev server stalled before binding, while the local production build served normally.

## Measured disposable read baseline — 2026-09-28

Both commands exited 0 with 1 opt-in benchmark case passed, 0 failed/skipped and 8 warnings each. Source HEAD `f43a9d88b334c2c4029fa06fa71624ed52efe4a2` plus the uncommitted implementation diff; Windows 11 10.0.26200, PostgreSQL 16 Docker, fixture OIDC, in-process FastAPI ASGITransport on one event loop, no network/provider, three warmups, 30 sequential samples and 10 concurrent requests from one fixture actor. Values are milliseconds unless noted.

| Fixture | Snapshot creation | Page sequential P50/P95 | Page concurrent P50/P95 | SQL/query count | Response bytes | DB connections | EXPLAIN page time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,000 buyers; 1 workspace/project/ICP | 483.788 | 33.944 / 51.986 | 343.188 / 354.999 | 11 per request | 50,621 | 8 | 3.348 |
| 10,000 buyers; 100 workspaces/projects/ICP revisions | 546.924 | 64.513 / 105.791 | 295.747 / 321.873 | 11 per request | 50,721 | 8 | 4.070 |

The 10k query reads a 100-row page at offset 900 of a 1,000-item frozen snapshot. Its `EXPLAIN (ANALYZE, BUFFERS)` used `uq_buyer_snapshot_items_ordinal`, `uq_project_buyers_workspace_id` and `pk_companies`; 6,026 shared hits, zero reads. The page remains SQL bounded by the snapshot cap, though the offset scan visits 1,000 rows. No new index was justified by this local plan. The warmed local read P95 target <=500 ms is met under these stated conditions. This does not measure HTTP transport, browser render, Neon pooling, 10 distinct staff identities, worker-consume age, mutation/admission P95 or production p75.

Artifacts: `artifacts/t29-benchmark-1k-1ws-asgi.json` (SHA256 `826A35F30E1105FC10147B135313D233869499ABC6327C13E74BD1FB6F9CFB94`) and `artifacts/t29-benchmark-10k-100ws-asgi.json` (SHA256 `F42A9ED564FCF6811F059636A72BDBA4048E80B31EB338085EE386826ECFD6C0`).

## Combined 10k/100-workspace rerun with disposable broker — 2026-09-28

`python scripts/benchmark-buyeros.py --fixture-size 10000 --workspaces 100 --output artifacts/t29-benchmark-10k-100ws-combined.json` exited 0. API opt-in case: 1 passed, 0 failed/skipped, 8 warnings in 84.49s. Worker dispatcher opt-in case: 1 passed, 0 failed/skipped, 4 warnings in 51.15s. The combined JSON SHA256 is `A422F5B33E55509C5377F2FF0ED139B70C0CD4597E366BFB4AAAB4470920ED42`.

The repeat API run used the same 10,000 buyers, 100 workspaces/projects/ICP revisions, 1,000-item actor-bound snapshot, 100-row offset-900 page, three warmups, 30 sequential reads and 10 concurrent requests from one fixture actor. Snapshot creation was 321.909ms. Sequential P50/P95 was 32.141/41.543ms; same-actor concurrent P50/P95 was 268.317/280.139ms. It made 11 SQL statements/request, returned 50,721 bytes/page, observed 8 DB connections, and its EXPLAIN execution time was 2.528ms with 6,026 shared hits and zero reads. Variation from the prior isolated 10k run reflects local run conditions; both are retained.

The worker stage seeded 100 `source.delete` intents, one per workspace, in disposable PostgreSQL 16; a disposable Valkey 8 broker accepted all 100 unique publishes in one bounded dispatcher cycle. Every workspace progressed. Ready-to-broker-publish P50/P95/max was 0.617/1.436/1.650 seconds. The local proposed P95 <=5 seconds is met for broker publication under these fixture conditions. No Celery worker consumed these messages, so this does not measure ready-to-terminal age or live delivery. No real identity, provider, external network, Neon or Render was used.

## Distinct staff, mutations and broker rerun — 2026-09-28

`python scripts/benchmark-buyeros.py --fixture-size 10000 --workspaces 100 --output artifacts/t29-benchmark-10k-100ws-distinct-corrected.json` exited 0: API 1 passed, 0 failed/skipped, 8 warnings in 31.62s; dispatcher 1 passed, 0 failed/skipped, 4 warnings in 35.52s. SHA256 `09678DA5B0FCEC62C215AF649E8BBBDCBA2391DC2BA7C832B22E475AFB1ECA87`. On one persistent ASGI loop, ten concurrent distinct fixture staff each read their own actor-bound 1,000-item snapshot over 10,000 fictional buyers: P50/P95 268.018/274.030ms, 11 SQL statements/request, 8 observed DB connections. The 30 sequential reads P50/P95 were 30.220/36.074ms; same-actor concurrent P50/P95 were 264.705/269.906ms. The 100-workspace disposable Valkey stage published 100 unique safe intents and progressed every workspace; ready-to-publish P50/P95/max was 3.410/4.039/4.084s. This is broker publication, not Celery consumption.

`python scripts/benchmark-buyer-mutations.py --output artifacts/t29-mutations-20x20-clean.json` exited 0: 1 passed, 0 failed/skipped, 8 warnings in 33.71s. SHA256 `9C1DA799A2D8F7C06E504464CD060516D0B3847056A54D6693C8ABE0F848F29A`. After three warmups each, 20 persisted buyer-note PATCH requests measured P50/P95 41.035/62.865ms and 18 SQL/request; 20 run admissions measured 73.659/88.219ms and 33 SQL/request. The fixture ended with 23 buyer edits, 23 queued runs and 23 outbox intents, so these were persisted writes and HTTP 202 admissions. The wrapper refused an inherited `BUYEROS_TEST_DATABASE_URL` with exit 2 before DB access. There was no paid provider, external network, worker completion, real identity or deployed service.

These artifacts precede the later rate-admission pool fix. A one-slot domain pool then reproduced HTTP 500/SQLAlchemy `TimeoutError` because admission opened a second connection while the membership transaction held the only slot. A dedicated bounded rate pool made the regression and existing durable actor-scoped 429 test pass 2/2 on disposable PostgreSQL (`services/api/artifacts/t29-rate-pool.xml`). The post-fix benchmark refresh follows. The full strict API rerun remains pending; pre-fix latency must not be attributed to the final code. The 500 is a real defect under pool pressure, while the earlier invalid TestClient connection-churn measurement was a harness artifact.

### Post-rate-pool disposable benchmark — 2026-09-28

`python scripts/benchmark-buyeros.py --fixture-size 10000 --workspaces 100 --output artifacts/t29-benchmark-10k-100ws-post-rate-pool.json` exited 0: API 1 passed, 0 failed/skipped, 8 warnings in 105.78s; dispatcher 1 passed, 0 failed/skipped, 4 warnings in 42.36s. SHA256 `B8025F2BB53AF593F9AA9EED30F4227359FB80E9AAD9A8C432CC57A9D60D57A5`. With 10,000 fictional buyers, 100 workspaces/projects/ICP revisions and one persistent ASGI event loop, sequential page P50/P95 was 35.013/39.377ms; ten concurrent same-actor requests 262.338/274.006ms; ten concurrent distinct fixture staff 229.513/244.895ms. Each read made 11 SQL statements; 10 DB connections were observed. The disposable Valkey stage published 100 unique workspace intents, every workspace progressed, and ready-to-broker-publish P50/P95/max was 0.690/2.280/2.393s. No Celery worker consumed these messages.

`python scripts/benchmark-buyer-mutations.py --output artifacts/t29-mutations-20x20-post-rate-pool.json` exited 0: 1 passed, 0 failed/skipped, 8 warnings in 33.40s. SHA256 `37026EF99E9810514992BD44422551B28362E73FFFD109AACC9EFE72C67D8022`. Twenty persisted buyer PATCH samples measured P50/P95 43.108/60.865ms with 18 SQL/request; twenty run admissions measured P50/P95 90.145/168.524ms with 33 SQL/request. The fixture ended with 23 buyer edits, 23 queued runs and 23 outbox intents. Proposed local P95 targets were met under these in-process, fixture OIDC, disposable PostgreSQL 16/Valkey conditions. This is neither production latency nor worker-consumption evidence.
