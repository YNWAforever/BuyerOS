# N00 counted APIRequestContext — local checkpoint

Date:2026-10-06 HKT. Base `ad1a54510f6a0fb2485392c878e7e867e9def6be`; author-reviewed/tested source `4ba0a5d7757d5c9e4991593a13c0a2df217be511`; branch `codex/n00-api-request-context`. Six source files,155 insertions/4 deletions. Independent review pending. **Full N00 / NA01 / F20 is OPEN; release NOT READY.**

## Facts by verification boundary

| Fact | Evidence |
| --- | --- |
| Code implemented | Fixed standalone fixture APIRequestContext, strict declaration,10 new Node regressions, one new actual Chromium case, exact six-case discovery and local plan |
| Fixture verified | Whole31-file root318reported/317 JUnit leaves;focused18(adapter10+discovery8),Chromium6,strict EdDSA8 pass;0fail/error/skip |
| Integration verified | Actual local Playwright HTTP through original gateway/journal;two manual hops reserve before backend HTTP;cookie isolation;accepted/lost-response and unknown holds survive restart;foreign redirect sink0;actual ownership races refused |
| Externally blocked/unverified | No true Neon/Google/session/token/Admincleanup or original302 acceptance;trusted parent/broker/browser/raw APIRequestContext/arbitrary provider CLI/control-plane OS isolation incomplete;fresh exact real target/account/cleanup authorization absent;independent review pending |
| Deployed | None;deployedSHA null/unproven. Auth0/application unchanged |

This is an explicit counted consumer; raw native contexts and the trusted parent can still open other sockets. Anonymous fixture page/diagnostic requests and Docker management are outside fictional auth-hop accounting. Real-run admission stays disabled until the complete boundary is demonstrated.

## Interfaces and smallest slice

- `scripts/neon-api-request-context.mjs` reuses `assertFixtureExecutionBoundary`, `ownedFixtureSdkUrl`, existing `holds` validation and gateway `/dispatch`. The server is the only reservation/intent owner;no second domain API,journal,money serializer or migration owner.
- Capture branded gateway/execution/journal/nonce pair and target fingerprint before context creation. Caller exposes only method/path/body/explicit headers;no context/URL/proxy/storage/retry settings. Channel browser;GET/HEAD/POST. In-memory empty cookies/origins;no disk export or browser cookie sharing.
- Actual outer POST goes only to owned loopback `/dispatch`: `maxRedirects:0`, `maxRetries:0`,20..3000ms timeout. Auth302 remains a receipt;each explicitly followed hop reserves separately. Fixed `N00_APIREQUEST_TRANSPORT_UNKNOWN` omits Playwright call logs/body/headers.
- Original validation/holds reused before wire. Serialized envelope limit32768 UTF8 bytes;escaped near-limit bodies refused before gateway HTTP. Original gateway/domain caps preserved. Receipt JSON shape/fixture flags validated;8MiB body guard runs **after** Playwright buffers body, not streaming memory/OS confinement.
- Actual APIResponse disposed in finally;context disposal idempotent. Disposed/owner/target checks before request and after fetch,body,final disposal awaits;closed/rebound gateway cannot supply a stale receipt. Raw context not exposed.
- Backend committed/socket-lost records unknown503/hold. Gateway receipt lost after backend202 yields transport-unknown to parent but durable accepted outcome;neither permits resend. New context/journal and renewed bearer preserve intent/hold.
- `.d.mts` uses existing ExecutionReceipt and fixture cleanup proof;no production auth/frame/identity/provider contract changes. Application/API/UI5aaf649,proxy9e1ef78,browser362b60d,native779138a unchanged.

Official documentation describes standalone cookie isolation and fetch redirect/retry/disposal options. [Playwright APIRequestContext](https://playwright.dev/docs/api/class-apirequestcontext). Installed1.63.0 is exercised directly;no dependency or lockfile change.

## RED, GREEN and retained attempts

| Report | Pass | Fail | Error | Skip | Meaning |
| --- | ---: | ---: | ---: | ---: | --- |
| `red-node.xml` | 0 | 8 | 0 | 0 | Missing adapter export; actual8 tests, not import-only0 cases |
| `red-browser.xml` | 5 | 1 | 0 | 0 | Existing5 actual Chromium pass; appended consumer fails missing adapter;0 globalerrors |
| `envelope-red.xml` | 7 | 1 | 0 | 0 | Remove serialized-envelope guard only: actual gateway wire1 vs expected0; restored immediately |
| `root-first.xml` | 314 | 1 | 0 | 0 | Old discovery expected5 vs intended6;315 leaves/316 reported; exact six-case inventory and named-case check updated |
| `race-red.xml` | 8 | 1 | 0 | 0 | Ownership change during awaited body exposes stale receipt |
| `race-red-both.xml` | 8 | 2 | 0 | 0 | Independent body and disposal cases each fail missing rejection before fix |
| `green-final.xml` | 18 | 0 | 0 | 0 | Adapter10+discovery8;17454.2441ms |
| `root-final.xml` | 317 | 0 | 0 | 0 | Whole31files;318 Node reported includes one nested parent;519306.7825ms |
| `browser-final.xml` | 6 | 0 | 0 | 0 | Actual Chromium;0 globalerrors;47.728449s |
| `crypto.xml` | 8 | 0 | 0 | 0 | Strict EdDSA fixture;1.96s;one existing asyncio deprecation warning |

Race witness takes a public APIResponse from an actual owned anonymous HTTP probe, delegates the original public body/dispose method, pauses only owned `/dispatch`, closes the actual gateway, then observes rejection. No synthetic response/private SDK/vendor patch. Each case restores the method and releases waiters in finally. Smallest fix rechecks ownership after both awaits. Original five Chromium cases,other config selectors,assertions,deadlines and DB guards unchanged.

`reports/all-attempt-counts.json` lists all XML attempts,earlier eight-case greens,and first failed root alias `root-green.xml`. Final verification uses `*-final`;historical names retain actual failed outcomes. No0tests/skip counted as pass or assertion weakening. Root/focused/crypto overlap is not summed.

## Exact commands and environment

PowerShell,isolated worktree,strict1 and both DB DSNs unset:

```powershell
$env:PYTHONUTF8='1'
$env:BUYEROS_STRICT_INTEGRATION='1'
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:BUYEROS_TEST_DATABASE_URL -ErrorAction SilentlyContinue
$taskTests=@(Get-ChildItem tests -Filter '*.test.mjs' -File | Sort-Object Name | ForEach-Object { 'tests/'+$_.Name })
node --test --test-concurrency=1 --test-reporter=spec --test-reporter-destination=test-results/n00-api-request-context/root-final.log --test-reporter=junit --test-reporter-destination=test-results/n00-api-request-context/root-final.xml @taskTests
node node_modules/@playwright/test/cli.js test --config playwright.neon-execution.config.ts
node node_modules/typescript/bin/tsc --noEmit
node node_modules/eslint/bin/eslint.js scripts/neon-api-request-context.mjs tests/neon-api-request-context.test.mjs tests/neon-compatibility-discovery.test.mjs tests/e2e/audit-neon-execution.spec.ts --max-warnings=0
services/api/.venv/Scripts/python.exe -m pytest -q tests/fixtures/neon-runtime-flow/test_verify.py --junitxml=test-results/n00-api-request-context/crypto.xml
node scripts/generate-api-types.mjs --check
uv run --frozen --project services/api python scripts/generate-operation-routes.py --check
```

Every final command exit0;expanded31-file argv/return codes in `reports/commands.json`. Empty type/lint logs have separate recorded exits. Read-only Alembic from services/api: `uv run --frozen --project . alembic heads` ->0037_bulk_manifests. Zero migrations/allocation/DB rollback. New protocol cases do not need canonical DB;no applicable required DB suite skipped,no remote DSN substituted;root disposable Docker/loopback tests retain guards.

Host Node24.18.0/Python3.14.6/Playwright1.63.0/Docker29.8.1,cached Linux image NODE_VERSION22.23.1;immutable ID in `reports/environment.json`. Existing native root cases run actual local Docker with no pull. Final owned label inventory containers/networks0 (`reports/owned-absence-final.json`). Duration includes Docker/guarded fixtures and is not product/provider performance or production SLA evidence.

No fresh build:source is host-only fixture harness/tests. Root SSR uses retained application5aaf649 output;prior portable/Vercel SDK builds retain historical scope,not new-build/live-Neon evidence.

## Cases, contracts, preservation and UI

| ID/scope | Result |
| --- | --- |
| F20/NA01 | Still open;counted context verified locally,full Neon runtime/session/account/OS gate incomplete |
| Original strict302 | Unchanged,not rerun;earlier synthetic500/200 outcome remains historical OPEN |
| Domain API | Generated types/84route mappings exit0;70original+14extensions;ledger bytes unchanged,no new operation |
| Schema |0037 head;0migrations;peer0038 unmerged |
| Other findings/cases | Statuses preserved;no additional closure/live claim |

`reports/preservation-final.json` checks3659 prior input/evidence files,24 other audit tasks,31 legacy T objects,98 original fifteen case columns,97 other case rows,operation bytes,threeforeign trees and193 unrelated dirty paths. `reports/source-proof.json` binds tested raw files,LF-normalized index and committed blobs. Preservation is not independent review.

Fresh `screenshots/api-context-fixture.png` visually inspected: “N00 accounting fixture” and “Counted API context hops:2;private cookie isolation:true;fixture only:true”. Diagnostic page,not staff/login/provider acceptance. Fresh six-case Chromium supplies12 actual observation/cleanup attachments (`reports/browser-final-observations.json`);context disposed,journal removed,servers closed. Failed/green/final artifact files retained byte-for-byte. Windows long destination paths required five artifact destinations to be flattened into `reports/short-path-artifacts/`;`reports/artifact-copy-map.json` maps all70 original artifact files to evidence copies. Initial copy failed at four screenshot destinations;the fifth path was shortened proactively. A provisional4-vs-5 copy-count assertion was corrected against the actual mapping;Git then rejected a redundant long partial-copy path during index readback,so its identical unmapped duplicate was removed after path/hash verification. Original and mapped copies retained;no tests/source were changed or results fabricated. No fresh full staff/en/zh acceptance claimed.

## Rollback and next

Revert following metadata commit then source `4ba0a5d7757d5c9e4991593a13c0a2df217be511`. `source.patch` reverse apply check0;applicability only,not executed. No DB/schema/identity/membership undo. Preserve admitted/unknown journal entries and reconcile accepted outcomes before retry;code rollback never authorizes erasing holds.

Next eligible local N00:trusted parent/broker/browser/control-plane OS egress feasibility/composition,including raw APIRequestContext/arbitrary provider CLI. Real Neon/Google/session/token/Admincleanup needs fresh exact target/account/cleanup/budget authorization after full harness review;expired preview authority is not renewed by continue. N01/N02/Q13/Q16/Q17/live staff/provider/independent-review gates OPEN;auth and Cloudflare cutovers separate. No push,remotePR,account/mail/link/grant,paidprovider,production migration/auth/Cloudflare action or deploy.
