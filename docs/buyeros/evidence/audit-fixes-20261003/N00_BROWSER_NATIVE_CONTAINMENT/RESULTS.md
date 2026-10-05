# N00 / F20 / NA01 — local browser native transport checkpoint

Reviewed source `362b60dd42d034e229b9fa5f51a47d6ffcd4ec04`; BASE `ebe830e16f15d432ad326e7f298d629c8ca59a6f`; branch `codex/n00-browser-websocket-refusal`; checked `2026-10-05T12:01:07.670479+00:00`. **Full N00 and NA01 remain OPEN.** Application/API/UI source remains `5aaf649`; host proxy remains `9e1ef78`. No deployment, external mutation or auth cutover. Author review only; independent review pending.

## Implemented and reproduced

The HTTP-only Chromium context route allowed native WebSocket upgrades. RED: one positive-control upgrade to an owned sink, then **two gateway and two foreign-sink upgrades** across refresh; zero auth reservations. Expected zero guarded upgrades. Actual browser event completion and server upgrade counters establish the failure; no mocked server fetch.

A shared spec-side HTTP route retains the original allowlist and callback semantics. Context-wide `routeWebSocket` now closes every socket without connecting to a server; this fixture needs no WebSockets. GREEN: four guarded attempts produce **zero physical upgrades**; unrestricted positive control still reaches the owned sink once. A new service-worker case verifies existing `serviceWorkers:block`: registration blocked, zero script requests, zero workers. Original three accounting/origin/unknown-restart cases retain their assertions. Exact discovery selects all five cases and excludes N00 from the destructive workbench configs. Code changes are confined to two test files and the bounded plan; no production runtime hardening claimed. [Source patch](source.patch), [author review](reports/source-review.json).

## Fresh checks

| Check | Pass | Fail | Error | Skip |
| --- | ---: | ---: | ---: | ---: |
| Dedicated browser RED | 4 | 1 | 0 | 0 |
| Dedicated actual Chromium GREEN | 5 | 0 | 0 | 0 |
| All 29 root MJS suites | 305 reported / 304 JUnit leaves | 0 | 0 | 0 |
| Strict owned EdDSA diagnostic | 8 | 0 | 0 | 0 |

Browser GREEN: 3231.391 ms, zero global errors/retries/flakes. Root: 125948.7707 ms; one nested parent explains the count difference. Crypto: 1.62s with one existing asyncio deprecation. Types/scoped ESLint/generated contract/routes exit0; **84 operations =70+14**, ledger unchanged. Playwright producer emits the existing NO_COLOR/FORCE_COLOR warning; not hidden. Two report-observer attempts read a still-running XML then omitted UTF-8 on Windows; neither reran/changed tests or counted an incomplete result as pass. Final complete UTF-8/JUnit parsing supplies the counts.

All five fixture cleanup receipts assert owned journal removal and servers closed; native positive-control context explicitly closed, normal page context owned by Playwright. Counting flow has four durable browser/browser/SDK/fixed-CLI auth requests. Unknown-write restart flow commits once and preserves one unknown hold. Refused WS attempts and service-worker registration have zero auth hops/reservations; positive-control sink upgrade is local diagnostic traffic, never a provider check. [Producer observations](reports/browser-observations.json), [fixture screenshot](screenshots/accounting-fixture.png). This is the accounting diagnostic, not the BuyerOS staff journey or true Neon login.

No new build. Whole-root SSR uses the unchanged retained main application output from5aaf649; prior Portable/Vercel compiled SDK flow evidence remains historical and was not rerun this slice. No schema/business/role/auth source changes; read-only Alembic head0037_bulk_manifests, migrations0. Protocol/browser changes require no domain DB suite; crypto does not connect to DB, no required DB skip suppressed. Existing whole-root guarded disposable subprocess tests remain unchanged. Windows / Node24.18.0 / Python3.14.6 / Chromium1120x800; fixture-only loopback servers, no paid/provider/production action. Test durations are conditions, not production performance acceptance.

## Native gaps established, not repaired

The standalone [read-only probe](reports/native-gap-probe.mjs) installs the actual global fetch guard, then uses native `node:http.get` toward an owned sink: one physical request while fetch forwarded0. A real Chromium `context.request.get` also reaches that sink once with context HTTP routing callbacks0. Total external/auth requests0; [raw observation](reports/native-gap-probe.json) explicitly sets all_native_contained:false. These successful observations are **open findings**, not containment passes. Fixed CLI is only the known Node helper; stripping inherited secrets does not contain arbitrary neonctl/process/net/https/TLS/undici/worker traffic. [Transport matrix and next preparation](TRANSPORT_MATRIX.md).

Original strict302 assertion is unchanged and not rerun here; its prior failure stays open. True Neon/Google, all-native egress/accounting, actual Managed Admin cleanup/schema/absence and independent/human review remain open. N01/N02 prerequisites not bypassed; NA01 historical fields preserved. Q16 still lacks underlying SQLSTATE/root cause and Q17 is not guessed. Auth0, canonical users.id/memberships/owner/approval/audit/job actor/RLS, independent Cloudflare HMAC and delivery403 retained. No full live/pilot acceptance.

## Exact commands and scope

Cwd is this isolated worktree. Browser/root/crypto use PYTHONUTF8=1, BUYEROS_STRICT_INTEGRATION=1 and unset DATABASE_URL/BUYEROS_TEST_DATABASE_URL. The archived native-gap-probe source uses its original relative imports; to replay from a fresh checkout, create test-results/n00-browser-websocket-refusal and copy reports/native-gap-probe.mjs there before running the recorded command. Do not execute the evidence copy in place.

```powershell
# Before implementation: RED; after implementation: GREEN. Reports copied immediately.
node node_modules/@playwright/test/cli.js test --config playwright.neon-execution.config.ts
# All root suites, serial, no tests filtered out
$taskTests=@(Get-ChildItem -LiteralPath tests -Filter '*.test.mjs' -File | Sort-Object Name | ForEach-Object {'tests/'+$_.Name})
node --test --test-concurrency=1 --test-reporter=spec --test-reporter-destination=test-results/n00-browser-websocket-refusal/root-green.log --test-reporter=junit --test-reporter-destination=test-results/n00-browser-websocket-refusal/root-green.xml @taskTests
services/api/.venv/Scripts/python.exe -m pytest -q tests/fixtures/neon-runtime-flow/test_verify.py --junitxml=test-results/n00-browser-websocket-refusal/crypto.xml
node node_modules/typescript/bin/tsc --noEmit
node node_modules/eslint/bin/eslint.js tests/e2e/audit-neon-execution.spec.ts tests/neon-compatibility-discovery.test.mjs --max-warnings=0
node scripts/generate-api-types.mjs --check
uv run --frozen --project services/api python scripts/generate-operation-routes.py --check
node test-results/n00-browser-websocket-refusal/native-gap-probe.mjs
# Read-only, cwd services/api
.venv/Scripts/python.exe -m alembic heads
git diff --cached --check
git apply --reverse --check test-results/n00-browser-websocket-refusal/source.patch
```

RED/green XML/JSON/logs, full-root/crypto outputs, source patch, physical observations, all cleanup receipts and local screenshot are committed byte-exact with SHA256 manifest. Prior3563 tracked input/evidence files, other24 audit task objects,31 legacy tasks, other97 case rows and all98 original15 fields,84-operation ledger and three foreign worktrees including193 dirty paths remain unchanged; final integrity report verifies this. Original evidence pack unchanged.

## Rollback and eligibility

Source reverse applicability exit0, no actual production rollback performed. Revert following metadata commit then `362b60dd42d034e229b9fa5f51a47d6ffcd4ec04`. No DB/data migration or auth undo. Do not delete admitted/unknown journals to permit a replay.

Next local preparation is a single explicit counted transport and owned disposable OS egress boundary for native Node/APIRequestContext/provider CLI, with adversarial loopback probes and exact readback/delete receipts. Current fixtures cannot be repointed at real targets. Only after that implementation/review may the old real-roundtrip proposal be refreshed and exact fresh target/account/cleanup authorization requested. Earlier authorizations expired/consumed; no approval record inferred.

Code implemented: dedicated test-harness WS guard. Fixtures verified: five actual Chromium cases. Local integration verified: owned HTTP/WS, journal/restart, pinned SDK/fixed helper, EdDSA diagnostic. Externally blocked: true Neon/Google and full containment/cleanup/review. Deployed: none / SHA NULL.
