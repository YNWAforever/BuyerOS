# Q06 / PR-13 local repair evidence — 2026-10-03

Base `b083ea43988ed73e9d8e9ab112ba3d6305f2c941`; reviewed source `b3477e341c35807bcdcbb400edfed7cceaa46de4`; branch `codex/audit-fixes-20261003`. F07, B12/B13/P04 and additional B16 scope regression. Complete **17-file** product/test diff: [Q06.patch](Q06.patch); [tested working/staged hashes](q06-tested-source.json), [author review](../../../review/2026-10-03-audit-fixes/Q06-review.md), [local PR description](../../../review/2026-10-03-audit-fixes/Q06-pr.md). No remote PR, push, deployment or production mutation occurred.

## Finding and implementation

F07 was still open at this task's base: BulkJobPanel used setInterval after its initial full read, walked every 100-row result page again on each interval, and could overlap. Q06 fixes this local source behavior with fresh fixture/HTTP/DB evidence. The old audit's requests/minute was an estimate; the controlled comparison below is measured. Production performance and the complete staff journey remain unverified.

`getAsyncJobSummary` returns strict generated AsyncJobSummary with durable status, seven counters, timestamps, kind and optional result ID; no result_page or command/actor claims. One shared `_read_actor_job` guard protects detail and summary: current membership/RLS, original canonical actor or current workspace administrator, tenant and missing-job denial. Existing detail endpoint/20-row UI paging remains compatible. There is one domain API, one Alembic owner and no SQL schema change.

The shared `startJobPoller` allows one request per view lifetime, waits2s after settlement, times out/aborts at10s, applies2/4/8/16/30s transient backoff and honors429 Retry-After seconds/date. Hidden pages pause/abort quietly; visibility coalesces one resumption, including rapid hidden-visible while abort settles. Scope/unmount aborts obsolete results; terminal states stop. Known401/403/404 stop automatic retries. Tokens are acquired from the current in-memory session each time. Summary success clears only its poll error in Operations, retaining unrelated errors.

Bulk results are fetched only after Show job results, offset/limit20; selected pages use real generated BulkItemResult.id. Terminal arrival refreshes the visible page once and the committed buyer snapshot once. Operations polls the selected running job through summary and refreshes its current detail page once at terminal. No new worker/provider intent, mailbox, CRM or delivery activation was introduced. Current Auth0, canonical users/memberships/audit/job actors and independent Cloudflare HMAC remain unchanged.

## Environment and safety

Windows PowerShell; Node24.18.0/pnpm11.25.0/uv0.11.27; locked Python3.14.6; Docker29.7.2/PostgreSQL16; Chromium/Playwright1.63.0. Browser fixture uses Linux Node22.23.2-bookworm-slim Vinext/Nitro dev,4CPU/6GiB, localhost5173→actual FastAPI8000 with least-privilege runtime/RLS DB role. Fictional OIDC identities and deliberately seeded job states/results are fixture evidence, not true Auth0/Neon/provider/continuous-worker proof. Domain envelopes can report data_mode=live because actual handlers execute; measurement artifacts explicitly say fixture_only=true.

Required DB runs set `BUYEROS_STRICT_INTEGRATION=1` and remove both BUYEROS_TEST_DATABASE_URL and BUYEROS_DATABASE_URL first. Existing destructive guards are unchanged ([proof](q06-db-guards.json)); no production/shared DB or Neon branch DSN used. Bounded audit_jobs seeds only0/21/101/1000 rows and changes only an owner-verified known fictional workspace/project/actor job. Guard implementation and owner proof were read before running. No paid provider or real identity mutation.

## RED, intermediate failures and corrections

| Evidence | Actual result | Classification |
|---|---|---|
| [API RED](q06-api-red.xml), [UI RED](q06-ui-red.log) |3 API failures and1 UI failure, zero skip| Missing summary404/contract; old UI issued detailed page instead of summary. Meaningful product RED |
| [Construction RED](q06-unit-construction-red.log) | Missing module import | Construction evidence only |
| [First poller](q06-unit-first.log) |9pass/1fail| Visibility was scheduled0ms instead of immediate coalesced refresh; corrected,10pass next |
| [Rapid visibility RED](q06-visibility-race-red.log) |10pass/1fail| Aborted request settlement imposed2s on rapid resume; corrected without assertion changes,11pass |
| [Operations recovery RED](q06-operations-recovery-red.xml) |1fail| Valid summary left prior503 alert; separate/clear pollError only |
| [First UI](q06-ui-first.xml) |8pass/2fail| Terminal5s assertion shorter than2.5s+2s+2.5s; synchronize actual terminal response within12s. B has no project so require absent panel |
| [Second UI](q06-ui-second.xml), [third scope](q06-scope-third.xml) |9pass/1fail; then1fail| Hand-injected bulk_job was dropped by actual navigation. Reopen via supported Operations Job ID/Load job after A-B-A; no navigation or scope guard weakened |
| [Named UI](q06-ui-third.xml) |10pass/0fail/0skip| Before the additional Operations recovery regression |
| [First combined UI](q06-ui-combined-first.xml) |43pass/1fail/0skip| D02 Save401 failed in enter(), before dirty fields/Save, with actual Vinext read ECONNRESET Build Error. Same44-case suite/source/assertions/timeouts rerun unchanged |
| [First completion gate](q06-final-gate-first-error.log) | TypeScript child failure | Scratch rollback copy had a relative import and was included by root tsconfig. Preserve bytes as .ts.txt after testing; no compiler config/source/test weakening |
| Generator/rollback/edit tooling | Missing--write, CRLF authored patch and wrong JSX edit needle | Original error logs retained; --write corrected, authored patch LF, actual JSX matched. No product results fabricated |

## Final GREEN commands

All commands at worktree root except API/Alembic cwd services/api. [Exact command/environment inventory](q06-commands.json).

| Check | Command | Exact result |
|---|---|---|
| Strict API/DB/contracts | `uv run --frozen pytest -q tests/test_job_summary_db.py tests/test_bulk_jobs_db.py tests/test_api_routes_contract.py tests/test_contract_required_fields.py --junitxml=../../test-results/q06-api-final.xml` | **24pass/0fail/0error/0skip**,9 dependency warnings,56.53s;4 new +13 bulk +7 contracts; [log](q06-api-final.log), [JUnit](q06-api-final.xml) |
| Full audit UI | `node node_modules/@playwright/test/cli.js test --config playwright.audit-fixes.config.ts` | **44pass/0fail/0skip**,5.9m wall including fixture lifecycle; [log](q06-ui-final.log), [JUnit](q06-ui-final.xml). testMatch actually includes new audit-*.spec.ts |
| Poller + related units | `node --test tests/job-poller-checks.mjs tests/audit-bulk-confirmation.test.mjs tests/audit-member-contract.test.mjs tests/audit-research-intent.test.mjs tests/audit-draft-guard.test.mjs tests/audit-auth-render.test.mjs` | **29pass/0fail/0skip** =11 poller +18 related; fresh completion gate |
| Adapter/auth | `node --test tests/live-adapter-checks.mjs tests/live-auth-checks.mjs` |2 file tests pass/zero skip, **74 adapter +8 auth internal checks**; do not miscount as82 node:test cases |
| Generated contracts | `node scripts/generate-api-types.mjs --check`; `uv run --frozen --project services/api python scripts/generate-operation-routes.py --check` | exit0; **80 operations = original70 +10 extensions** |
| Type/lint | `node node_modules/typescript/bin/tsc --noEmit`; changed-file ESLint in command inventory | exit0, no diagnostics or added rule suppression; fresh completion gate |
| Required report checker | `python scripts/check-required-tests.py --junit test-results/q06-api-final.xml` and UI equivalent |24/0/0/0 and44/0/0/0 |
| Completion | `task-done .superpowers/sdd/q06-job-summary/q06-job-summary.md 1 b083ea43988ed73e9d8e9ab112ba3d6305f2c941 -- node test-results/q06-final-gate.mjs` | exit0; [tool log](q06-task-done.log), [gate script](q06-final-gate.mjs), [fresh output](q06-final-gate.log), [ledger](q06-task-ledger.md). Reads actual JUnit and reruns light gates, not another heavy DB/UI run |

## Cases and measured P04 conditions

| Case | Proven local outcome | Limit |
|---|---|---|
| B12 |1000-result unopened job summary only; RTT2.5s one in-flight; selected20-row pages; terminal refresh current offset20 exactly once| RTT injected; counts/states persisted fictional fixtures |
| B13 | Hidden pause, coalesced visibility, rapid abort/resume, timeout,2/4/8/16/30s,429 seconds/date,503 recovery, negative access stops; en/zh-HK390 controls| Browser429/503 overlays and fake visibility explicitly controlled; real envelope/client and DB reads used |
| B16 | Held old running summary cannot replace new completed job after A-B-A; current20 real IDs remain| Operations Job ID/Load job supports reopening; no persistent browser job/intent restoration added |
| P04 | Every scheduled request replayed through actual HTTP/runtime-role PostgreSQL; real Response.content bytes and SQL execute events counted| Fake clock scheduling, not wall-clock latency/SLA or live performance |

P04 freezes1000 persisted results,10 visible views, logical60s and per-request injected RTT2500ms. The before reader is extracted literally from `b083ea43988ed73e9d8e9ab112ba3d6305f2c941` with source/fragment hashes; after uses the actual new poller. All requests **started within**60000ms are replayed to completion, including those pending at the logical deadline. Ten fictional current admins retain the unchanged120/minute actor limit; logical start30s before a UTC minute boundary, fresh fictional windows only between independent experiments. SQL executes include existing auth/RLS/membership/rate-window work; summary makes no async_job_items query. [Schedules/source hashes](q06-traffic-schedule.json), [real schemas](q06-traffic-samples.json), [measured results](q06-traffic-results.json).

| Metric | Before | After |
|---|---:|---:|
| Requests |1250|140|
| Actual response body bytes |9,293,390|69,440|
| Actual DB executes |10,000|840|
| Result-table executes |2500|0|
| Maximum in-flight per view |13|1|
| HTTP200 responses |1250|140|

No production p50/p95/p99, cold/warm, real Auth0/Neon account, provider cost, worker restart or8-module live UAT claim follows.

## Screenshots, integrity and rollback

[English](q06-bulk-en.png):1000 persisted results, current21–40 page and aggregate666 failures. [繁中390px](q06-bulk-zh-mobile.png):21–21 page, full ID wraps and no horizontal overflow; surrounding snapshot may still be loading. Both visually inspected, fictional fixture screenshots.

New migrations **0**; `uv run --frozen alembic heads` returned0036_checkpoint_schema_grants ([log](q06-alembic-heads.log)). Existing strict bulk suite verifies empty disposable downgrade0016→0015 then upgrade to0036; no production migration/rollback executed. Original31 input hashes,98 original case columns,25-task input CSV and approved plan bytes remain unchanged; nested evidence ZIP SHA256 `19369591a175edad7dd2e9f3ddb5bfdebc6cdc5130a2770243b1e9de2a42d35a`, CRC/safe entries reverified ([proof](q06-input-integrity.json)). Working/staged Git bytes differ where CRLF is normalized; both hashes retained and normalized equality asserted.

**Rollback is manual Refresh, never restore the old interval/full-page walk.** Apply [manual-refresh-rollback.patch](manual-refresh-rollback.patch) after `git apply --check ...`; it changes only the shared poller into one summary read per explicit lifetime/Refresh, retains timeout/abort and leaves API/schema/current memberships unchanged. Bulk Refresh remains usable after an initial valid summary; on initial failure use Operations Job ID/Load job for an explicit20-row read. [Exact patch scratch-copy proof](q06-rollback-copy-proof.json), [3pass/0fail/0skip behavior checks](q06-rollback-final.log). Only scratch source was patched, with its import alias relocated for test loading; the tested production working hash is unchanged. No rollback browser/build/deployment run claimed. Full Q06.patch reverse-check is forensic applicability only, **not a recommended revert**, because a full revert restores the unsafe interval.

Owned fixture containers/markers removed by global teardown; dependency volume was positively label-verified and removed ([cleanup](q06-fixture-cleanup.json)). Unrelated resources/worktrees untouched. Raw logs/JUnit/JSON/ledger retain bytes under `* -text`; whitespace checks target source/authored docs, not raw CRLF captures.

## Remaining gates

Author review only; independent review pending. Live performance, true provider/Neon/built-handler evidence, hard-browser unknown assignment recovery and complete staff UAT remain open. Q16 lacks SQLSTATE/driver/pool root-cause evidence; Q17 not guessed. Auth0 retained, delivery activation unchanged/disabled. No external activation decision needed for this local checkpoint; each future production/provider/auth/Cloudflare action requires its concrete existing authorization.

**Code implemented; fictional fixture verified; actual local HTTP/DB integration verified; external gates unverified; deployed SHA null. Next eligible local task: Q07** (fixed-template controls/copy), predecessor Q15 satisfied.
