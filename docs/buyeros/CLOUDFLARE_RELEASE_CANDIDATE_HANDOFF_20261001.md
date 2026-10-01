# Cloudflare release candidate handoff — 2026-10-01 HK

## Current facts

| Fact | Evidence and practical limit |
| --- | --- |
| Code implemented | CF00 local and CF01–CF08 local implementation complete. One API-owned Python execution engine, strict signed bridge and TypeScript Cron/Queue/Workflow controller; compatible thin Celery adapters remain. Default selector is Celery/off/epoch1. |
| Fixture verified | English/zh-HK at1280×800 and390×844: UI login/scope → create/edit offer → current ICP approval → bounded research → review/list/assign → grounded addressed draft → exact approval/export → manual outcome/refresh. OIDC, search and contact inputs are fictional. Optional unknown contact holds and101-row bulk/restart/page2 are additional cases. |
| Local integration verified | Actual Miniflare Cron/Queue/Workflow → machine HMAC → native FastAPI/SQLAlchemy → owned PostgreSQL. Full API650, worker186, seven current Cloudflare UI cases, six preserved legacy suites, and PG18 compatibility29 have zero required failures/errors/skips. |
| Hosted integration | CF00 hosted package/PDF/checkpoint/protection and both-hop enforcement remain NOT RUN. No fixture/mock is counted as live provider proof. |
| Externally blocked | Exact preview setup authorization; later production plan/quota/privacy and selector scope; independent review; external deletion journal/R2, policy/provider economics/pilot, full authenticated staff trace and assistive accessibility. |
| Deployed | Cloudflare controller/schema/selector remain undeployed. Existing Git integration automatically published app/API **preview** dpl_EPr4wsjaMNcgo3XA2itL1NxDGsc7 at source d8ca315 (READY, targetnull, iad1, branch alias only). This is not protected native-job feasibility or production cutover; historical production12327c7 is not a refreshed live readback. |

**Reviewed code/configuration source:** `d6c2849d50b5851cd24bcab24ce0db4b73ecc3e8`.
CF07 comprehensive source commit `14fcb37d36bf00e65c8d7ab319002cd71fbeee99`.
Migration baseline `aed7a7eb2b7370c10cd7a41306eecf09d378ad42`; no reset.
Audit baseline `5e61f401bf1bcdf80ea1ce254dd9c62e8eedbab0` is not an ancestor;
findings were reconciled against current code. Immutable pack43/43 and ZIP12/12
checks, safe inspection and fictional reproduction limits remain recorded.

Current branch `codex/fix-vercel-tslib-ssr`; origin `YNWAforever/BuyerOS`.
[Existing draft PR10](https://github.com/YNWAforever/BuyerOS/pull/10) is the review
vehicle under the earlier explicit push/PR authorization; no merge is authorized.
Historical BO/plan approval records are preserved. Cloudflare architecture/local
implementation approval does not authorize paid resources or production rollout.

## Changed files and ownership

[Complete migration file list](../../artifacts/cloudflare/CF08-changed-files.json)
records the baseline/reviewed SHA and176 source/config/test paths, plus retained
evidence and documentation. The PR also retains earlier deployment and Render
standby proposals; no Render resources were created, and Cloudflare is now the
selected proposed job host.

| Group | Main paths and purpose |
| --- | --- |
| Domain owner | `services/api/buyeros_api/execution/`: extracted checkpoints/research/fit/document/PDF/provider/bulk/draft/retention/reconcile engine. `services/worker/buyeros_worker/`: import-compatible adapters and selector guards, no second domain API. |
| Security/protocol | `api/worker_auth.py`, `worker_schemas.py`, `routes/worker_internal.py`, `services/worker_execution.py`, `services/worker_recovery.py`; current actor/policy, bounded ID-only payloads, replay/epoch/lease fences and one global DB permit. |
| Schema | API Alembic0034/0035, `db/worker_execution.py`, outbox backend/epoch. No overwritten revisions, D1 or Worker-owned business database. |
| Controller | `services/cloudflare-jobs/src/`: scheduled claims/publication, verified Queue handoff, deterministic Workflow/status-first recovery and HMAC client. Optional protected-preview bypass stays at the approved origin and is stripped at the app proxy. |
| Deployment | Root `vercel.json`, Nitro budget in `vite.config.ts`, isolated disabled `wrangler.jsonc --env preview`, generated contracts/binding types, mature pinned toolchain and strict CI gates. |
| Verification | New actual-PG/Workers/platform/recovery tests, shared staff journey, guarded emitted-Vercel frontend fixture, source/evidence manifest, PG18 owned-cluster reproducer and operating benchmarks. Legacy assertion/required-skip gates remain. |
| Handoff | TASKS, status/operation CSV, this handoff, setup/probe/cost runbooks and exact CF00–CF08 checkpoint artifacts. |

## Exact checks and outputs

Counts are **passed/failed/errors/skipped**. Commands below are actual local
invocations, not proposed hosted commands. Clear inherited database credentials;
strict DB fixtures create fresh owned loopback containers and clean only their
own resources. Windows Node24.18.0/pnpm11.25.0/Python3.14.6; production metadata
PG18 prompted the additional fresh-container18.6 compatibility gate.

CF07 full suites are retained at their source/input manifests. CF08 changes
configuration and an optional platform header; backend/business/UI route source
is unchanged from CF07. UI suites were not rerun locally after those CF08 deltas; fresh Linux CI
subsequently reran the full seven-case journey successfully at d8ca315.
The current optional header and gateway path are covered by27 controller and19
Node checks; application HMAC still matches the fixed vector.

| cwd | Exact command | Result | Output |
| --- | --- | --- | --- |
| services/api | `uv run --frozen pytest tests -q --junitxml=../../artifacts/cloudflare/CF07-api-final.xml` | 650/0/0/0 | [CF07-api-final.xml](../../artifacts/cloudflare/CF07-api-final.xml) |
| services/worker | `uv run --frozen pytest tests -q --junitxml=../../artifacts/cloudflare/CF07-worker-final.xml` | 186/0/0/0 | [CF07-worker-final.xml](../../artifacts/cloudflare/CF07-worker-final.xml) |
| services/api | `uv run --frozen pytest tests/test_runtime_readiness_db.py tests/test_admin_operations_db.py tests/test_cloudflare_recovery_db.py tests/test_cloudflare_platform_db.py -q --junitxml=../../artifacts/cloudflare/CF07-readiness-final.xml` | 20/0/0/0 | [CF07-readiness-final.xml](../../artifacts/cloudflare/CF07-readiness-final.xml) |
| . | `pnpm.cmd exec vitest run --config services/cloudflare-jobs/vitest.config.ts --reporter=default --reporter=junit --outputFile.junit=artifacts/cloudflare/CF07-controller-final.xml` | 25/0/0/0 | [CF07-controller-final.xml](../../artifacts/cloudflare/CF07-controller-final.xml) |
| services/api | `uv run --frozen pytest tests/test_cloudflare_platform_db.py -q --junitxml=../../artifacts/cloudflare/CF07-platform-last.xml` | 1/0/0/0 | [CF07-platform-last.xml](../../artifacts/cloudflare/CF07-platform-last.xml) |
| services/api | `uv run --frozen pytest tests/benchmark_cloudflare_case.py -q --junitxml=../../artifacts/cloudflare/CF07-operating-final.xml` | 2/0/0/0 | [CF07-operating-final.xml](../../artifacts/cloudflare/CF07-operating-final.xml) |
| services/api | `uv run --frozen pytest tests/benchmark_buyeros_case.py -q --junitxml=../../artifacts/cloudflare/CF07-read-benchmark.xml` | 1/0/0/0 | [CF07-read-benchmark.xml](../../artifacts/cloudflare/CF07-read-benchmark.xml) |
| . | `pnpm.cmd exec playwright test --config playwright.mvp-research.config.ts tests/e2e/mvp-a-research.spec.ts --workers=1 --reporter=line,junit` | 4/0/0/0 | [CF07-legacy-research.xml](../../artifacts/cloudflare/CF07-legacy-research.xml) |
| . | `pnpm.cmd exec playwright test --config playwright.workbench.config.ts tests/e2e/daily-workbench.spec.ts --workers=1 --reporter=line,junit` | 8/0/0/0 | [CF07-legacy-workbench.xml](../../artifacts/cloudflare/CF07-legacy-workbench.xml) |
| . | `pnpm.cmd exec playwright test --config playwright.buyer.config.ts tests/e2e/buyer-results.spec.ts --workers=1 --reporter=line,junit` | 1/0/0/0 | [CF07-legacy-buyers.xml](../../artifacts/cloudflare/CF07-legacy-buyers.xml) |
| . | `pnpm.cmd exec playwright test --config playwright.buyer-management.config.ts tests/e2e/buyer-management.spec.ts --workers=1 --reporter=line,junit` | 3/0/0/0 | [CF07-legacy-management.xml](../../artifacts/cloudflare/CF07-legacy-management.xml) |
| . | `pnpm.cmd exec playwright test --config playwright.mvp.config.ts tests/e2e/mvp-a-journey.spec.ts --workers=1 --reporter=line,junit` | 1/0/0/0 | [CF07-legacy-mvp.xml](../../artifacts/cloudflare/CF07-legacy-mvp.xml) |
| . | `pnpm.cmd exec playwright test --config playwright.live-zoom.config.ts tests/e2e/api-browser-zoom.spec.ts --workers=1 --reporter=line,junit` | 2/0/0/0 | [CF07-legacy-zoom.xml](../../artifacts/cloudflare/CF07-legacy-zoom.xml) |
| . | `node --experimental-strip-types --test tests/api-types-generation.test.mjs tests/vercel-services.test.mjs tests/worker-gateway.test.mjs tests/vercel-render.test.mjs tests/deployment/cloudflare-release-config.test.mjs tests/deployment/built-ui-fixture.test.mjs tests/deployment/cloudflare-acceptance.test.mjs tests/deployment/cloudflare-python-runtime.test.mjs` | 19/0/0/0 | [CF08-node-final.txt](../../artifacts/cloudflare/CF08-node-final.txt) |
| . | `pnpm.cmd exec vitest run --config services/cloudflare-jobs/vitest.config.ts --reporter=default --reporter=junit --outputFile=artifacts/cloudflare/CF08-controller.xml` | 27/0/0/0 | [CF08-controller-green.txt](../../artifacts/cloudflare/CF08-controller-green.txt) |
| . | `services/api/.venv/Scripts/python.exe .sites-runtime/cf08-pg18-proof.py` | 29/0/0/0 | [CF08-pg18.txt](../../artifacts/cloudflare/CF08-pg18.txt) |
| . | `pnpm.cmd exec tsc --noEmit` | exit0 | [CF08-types-final.txt](../../artifacts/cloudflare/CF08-types-final.txt) |
| . | `pnpm.cmd lint` | exit0 | [CF08-lint-final.txt](../../artifacts/cloudflare/CF08-lint-final.txt) |
| . | `pnpm.cmd run cloudflare:types` | exit0 | [CF08-controller-types-final.txt](../../artifacts/cloudflare/CF08-controller-types-final.txt) |
| . | `pnpm.cmd run cloudflare:lint` | exit0 | [CF08-controller-lint.txt](../../artifacts/cloudflare/CF08-controller-lint.txt) |
| . | `pnpm.cmd run cloudflare:bindings` | exit0 | [CF08-bindings-final.txt](../../artifacts/cloudflare/CF08-bindings-final.txt) |
| . | `pnpm.cmd exec wrangler deploy --dry-run --env preview --config services/cloudflare-jobs/wrangler.jsonc --outdir .sites-runtime/cloudflare-preview-dry-run` | exit0 | [CF08-preview-dry-run-final.txt](../../artifacts/cloudflare/CF08-preview-dry-run-final.txt) |
| . | `node scripts/run-vercel.mjs build` | exit0 | [CF08-vercel-build.txt](../../artifacts/cloudflare/CF08-vercel-build.txt) |
| services/api | `uv run --frozen alembic heads` | exit0 | [CF08-alembic-heads.txt](../../artifacts/cloudflare/CF08-alembic-heads.txt) |

The PG18 run used the reviewed ignored script; `scripts/run-cloudflare-pg18-proof.py`
is byte-identical and is the committed/CI reproducer. It rejects inherited DSNs
and overrides only the owned fixture's image for the current process. It is not
a remote test switch. PG18 includes the actual native transport wrapper; its
nested2 cases are not counted as two additional unique API tests.

Required JUnit command (root): `uv run --frozen --project services/api python scripts/check-required-tests.py --junit PATH`.
Every final required XML has zero failures/errors/skips. Static/public78/internal5
generation, strict TS/lint/bindings, frozen pnpm, normal Vinext build and Vercel
build pass in retained CF07/CF08 evidence. CI YAML parses eight jobs; new remote CI is reported separately below from these local passes.

CF08 red before fix: configuration0 passed/3 failed; stale binding generation
exit1; protection transport3 passed/3 failed. Green19 Node,27 Workers, PG18
29; disabled dry-run137.54KiB/gzip24.49KiB. Earlier failed setup, dev startup,
fixtures, scope interception and outside-test errors remain in CF07 artifacts.
Seven passing tests with an outside-test error were retained as an overall
failure; the later final run is exit0. No required DB skip was suppressed.
Whitespace-only log normalization and original hashes are recorded separately.

[CF07 checkpoint](../../artifacts/cloudflare/CF07-checkpoint.json),
[CF08 checkpoint](../../artifacts/cloudflare/CF08-checkpoint.json),
[original CF08 log hashes](../../artifacts/cloudflare/CF08-log-normalization.json),
[author review rulings](../../artifacts/cloudflare/CF08-review-rulings.md).
Author review is not independent approval; no agents were authorized.

## Fresh pushed-source CI and automatic app/API preview

[CI36859284850](https://github.com/YNWAforever/BuyerOS/actions/runs/36859284850)
is completed SUCCESS, eight/eight jobs at branch source d8ca315. GitHub checked
out its synthetic test-merge8634fba, not a merged PR. The acceptance manifest
matches all recorded source files to the branch Git blobs. Exact current archive
digests and safe namespaces were verified; retained older reports/failures in
the uploaded directory were not relabelled as fresh results.

| Fresh Linux gate | Actual result |
| --- | --- |
| API |650 passed,96 warnings,195.27s; required checker650/0/0/0 |
| Worker |186 passed,1 warning,24.81s; required checker186/0/0/0 |
| Controller |27/0/0/0, actual Workers runtime; dry-run137.54KiB/gzip24.49KiB |
| PG18 compatibility |29 passed,9 warnings,41.06s; required checker29/0/0/0 |
| Operating repetitions |2 passed,1 warning,41.71s; required checker2/0/0/0 |
| Staff journey after CF08 |7/0/0/0,1.2m; exact build/test exits0 |
| Legacy continuity |4/8/1/3/1; each required checker zero failure/error/skip |
| Remaining jobs |Frontend/contract/types/lint/both builds, smoke and actual zoom all SUCCESS |

[Remote summaries and preview metadata](../../artifacts/cloudflare/CF08-remote-ci.json),
[verified current CI manifest/XML/report](../../artifacts/cloudflare/ci-d8ca315/).
A following documentation/evidence-only head can retain this reviewed code proof;
its own new Git-triggered CI status must not be fabricated as complete.

Vercel metadata confirms existing Git automation created a READY branch app/API
preview at d8ca315, deployment dpl_EPr4wsjaMNcgo3XA2itL1NxDGsc7, regioniad1,
targetnull. No explicit platform deploy command or production alias change was
performed. No runtime job, protected diagnostic, CF resource or production schema
activation was verified by that preview. The isolated preview proposal remains
required because this existing project is not a dedicated empty test target.

## Audit A01–A18 closure table

| Finding | Classification | Current evidence / remaining limit |
| --- | --- | --- |
| A01 login/workspace | already fixed with evidence | Historical approved FIMMICK/admin setup readback and human sign-in confirmation. Local fictional OIDC journeys pass; agent-authenticated full hosted API trace remains open. |
| A02 API domain | source changed | One same-origin app proxy with runtime app→API binding; actual emitted frontend and native integration verified. Historical deployed anonymous401/bootstrap only, not this migration rollout. |
| A03 ICP replay/numbering | already fixed with evidence | Existing actual-PG immutable/idempotent numbering races retained; four complete UI-created current-version approvals. |
| A04 typed validation | already fixed with evidence | Strict public and private contracts; malformed/extra/oversize payload denial, sanitized errors, generated78+5 current. |
| A05 offer persistence | already fixed with evidence | Four UI-created offers edited/reloaded and then used through research, draft, export and outcome. |
| A06 exact approval | already fixed with evidence | Edited offer/ICPv2 and recipient-bound exact-context approval; member/policy/expiry changes deny. Approved delivery remains403. |
| A07 scope races | already fixed with evidence | Held actual proxy reply A→B→A; old A absent in B and durable A rows restored; local negative roles and partial failures retained. |
| A08 idempotency | already fixed with evidence | Same-key target/body/precondition fingerprint races;20 concurrent requests and actor checks retained. |
| A09 locking/stale profile | already fixed with evidence | Project→ICP ordering/races, one active pointer, stale/version rejection; no lock during provider I/O. |
| A10 snapshots/pagination | already fixed with evidence | Actor/current-scope/expiry guards; actual page2 for101 bulk, bounded late SQL page at10k buyers, persisted filters/list and finite limits. |
| A11 demo controls | source changed | Actual API/PG/Queue/Workflow staff journey, durable assignments/lists/notes/drafts/exports/outcomes. OIDC/providers remain explicit fixture seams. |
| A12 maintenance/bulk | already fixed with evidence |101 rows in50-row units, restart/receipt conservation, real second page, retry/cancel/export/current actor and viewer negatives retained. |
| A13 operations/recovery | still open | Local process kill, restart, platform expiry, epoch fencing, older-backup replay and unknown0.300000 hold conservation pass. External journal custody/completeness, physical object deletion and hosted recovery remain open. |
| A14 worker completion | source changed | Actual Cron/Queue/Workflow/HMAC/nativePG; retained actual Celery/Valkey continuity. No deployed controller/provider completion is inferred. |
| A15 performance/cost | still open | Two local10-job repetitions meet first-step P95 target;100-workspace fairness and10k late SQL page measured. Hosted latency, actual billing and all-day Neon quota decision remain open. |
| A16 locale/a11y | still open | English/zh-HK at390/1280, negative roles, current screenshots and actual200% Chromium zoom over six routes verified. Manual screen reader/non-text elements remain unverified. |
| A17 evidence truth | still open | All required local suites zero skip; full journey/state/hold/restart proof and red artifacts retained. Live identity/provider/pilot and new remote CI/hosted acceptance remain separate. |
| A18 activation | still open | Current actor/RLS/approval, intent/holds, private transport, paused readiness, CAS/drain/refusal verified. No new cloud resources/production migration/provider activation; preview and later production approval still required. |

Totals:10 already fixed with evidence,3 source changed,5 still open;0 classified
not reproducible. This classification does not close a hosted/owner/provider gate.

## Public70 plus extensions and internal coverage

Original pack70 operation IDs and current public78 match the status CSV exactly.
Extensions: `assignBuyerOwners`, `cancelAsyncJob`, `exportBulkFailures`,
`listAsyncJobs`, `listMemberships`, `listOfferDocuments`, `retryFailedAsyncJob`,
`updateMembership`. Private operations remain separate: `workerClaim`,
`workerExecuteStep`, `workerStepStatus`, `workerRecordPublication`,
`workerMaintenance`. No sixth hosted diagnostic is shipped.

[Coverage and contract hashes](../../artifacts/cloudflare/CF08-operation-coverage.json)
and [per-operation status](remaining/API_OPERATION_STATUS.csv). Handler/schema
coverage is78/78; each operation's recorded integration proof is preserved.
Neither all78 individual UI/live checks nor deployed verification is claimed.
Unknown acceptance holds and status-only reconciliation are persistent; fixture
provider submissions/status reads are not live provider acceptance.

## UI screenshots

Four final fixture journeys share the real emitted Vercel function/static assets
and runtime service proxy. [Fourteen current screenshots](../../artifacts/cloudflare/screenshots/)
include exports/outcomes/readback plus bulk/restart/unknown hold; legacy/zoom
screenshots remain [separate](../../artifacts/cloudflare/legacy-screenshots/).
Current en/zh-HK desktop/mobile captures were visually inspected, including:

- [English desktop outcome](../../artifacts/cloudflare/screenshots/cloudflare-continuity-en-desktop-outcome-fixture.png)
- [English mobile outcome](../../artifacts/cloudflare/screenshots/cloudflare-continuity-en-mobile-outcome-fixture.png)
- [zh-HK desktop outcome](../../artifacts/cloudflare/screenshots/cloudflare-continuity-zh-HK-desktop-outcome-fixture.png)
- [zh-HK mobile approved export](../../artifacts/cloudflare/screenshots/cloudflare-continuity-zh-HK-mobile-approved-export-fixture.png)
- [101-row restart/pagination](../../artifacts/cloudflare/screenshots/CF07-bulk-restart-zh-HK-mobile.png)
- [unknown acceptance/retained hold](../../artifacts/cloudflare/screenshots/CF07-unknown-contact-hold-en.png)

No screen-reader or real Auth0/provider screenshot is implied by these fixtures.

## Migrations, rollback and operating conditions

One current local Alembic head: `0035_worker_recovery_probe`.0034 was allocated
after inspecting0033;0035 after0034.0034 adds the selector/step receipts/nonces and
outbox fence;0035 adds minimal global probe/recovery cursor and restricted API
selector reads. Defaults are off. No production schema query/migration was run
for this migration; historical production0033 is not a new live readback.

CF02/CF06 owned-PG empty downgrade/re-upgrade succeeds; populated replay/probe/
recovery evidence refuses downgrade atomically without deleting receipts,
operations or unknown0.300000 hold. Real process-kill after receipt yields one
business write/audit; older backup replay keeps reads closed and preserves
RLS/ledger conservation. PG18 compatibility29 applies current chain and covers
security/control/recovery/native transport; detailed0035 round-trip/process
boundaries are retained PG16 evidence.

[Setup/pause/drain/rollback runbook](runbooks/cloudflare-worker-setup.md) uses
privileged operator dry-run/CAS only. Pause increments epoch; enabling refuses
live permits/dispatched leases. Do not purge queues, release unknown holds,
decrement epoch or run unsupported old claimers. Roll forward after real use;
Celery fallback requires compatible resources and is not provisioned here.

[Measured operating/cost worksheet](runbooks/cloudflare-operating-conditions.md):
ten simultaneous non-provider jobs, body≤1s, maximum native concurrency1.
Two repetitions first-step P50/P95 seconds7.20/9.85 and8.61/14.07;100 workspaces
and ten cold claim ticks each P95115.17/173.65ms. Probe age6.00/6.58s. Whole
Python fixture CPU2.66/3.58s and peak RSS165421056/172158976bytes, excluding
Node/workerd/Docker. Immediate benchmark claims and accelerated UI fixture Cron
are not the production60-second Cron. Hosted cold starts/provider latency remain
untested.10k-buyer ASGI offset900/limit100 P50/P9542.42/58.60ms; ten concurrent
P95262.44ms same actor/258.65ms distinct,11queries/page,50,721bytes,10connections.

Thirty-day idle enabled minute polling:43,200 probes,86,400 signed calls,
172,800 two-hop Vercel invocations before customer work. At0.25CU all-day
Neon compute implies180CU-hours/month, above published Free100CU-hours.
Read-only production metadata confirms PG18/Singapore/Free/min0.25/max2 and a
suspended endpoint. It does not measure remaining quota or approve an upgrade.
The US$5 Workers Paid base excludes shared account overages, Neon, Vercel, tax
and providers. No promised all-in saving or automatic production scheduling change.

## Single next activation decision: protected feasibility preview only

**Requested, not received:** authorize the following bounded setup and fictional
machine-only tests. Local architecture/code approval is already received.
This decision does not activate production customer jobs, providers or delivery.

| Target | Exact proposal / verified fact |
| --- | --- |
| Source | Reviewed code `d6c2849d50b5851cd24bcab24ce0db4b73ecc3e8`, plus separately reviewed default-off temporary diagnostic patch before hosted deployment. Current RC has no diagnostic endpoint. |
| Cloudflare account | Read-only identity: `Laichiwillyjp@gmail.com's Account`, ID `e387dfbeded3deb5b8f0023a78a660b5`. Current billing plan not inspected. Workers Paid US$5/month base if needed; metered shared-account overages additional. Stop before any other paid plan/resource. |
| Cloudflare resources | Private Worker/Queue `buyeros-jobs-preview`; DLQ `buyeros-jobs-preview-dlq`; Workflow `buyeros-job-preview`. Root production names distinct/off. No fetch route, workers.dev or public preview URL. Queue batch1/concurrency1/retries5, DB permit1 is the true execution limit. |
| Vercel | New dedicated protected project `buyeros-cf-preview` in existing team `team_qvzlsFmfCsLkgItSypqHjw3z`. Retain app/API service names, app public catch-all and runtime app→internalAPI binding. No new paid Vercel plan included; stop if required. Read generated project ID/domain/actual budgets back before secrets. Existing `buyer-os` project unchanged. |
| Neon | New **empty** project `BuyerOS-CF-preview-20261001`, existing organization `org-soft-sunset-25251479`, Singapore `aws-ap-southeast-1`, PG18, Free, fixed0.25CU if account permits. No production branch/data/roles/DSN clone. Read project/branch/host IDs and quota back before migration. No paid Neon upgrade included. |
| Schema/roles | Initialize only that verified empty target through sole API Alembic0035; dedicated nonowner/NOBYPASSRLS API and worker logins inherit only existing canonical roles. Current catalog/RLS/checkpoint ownership must be verified. No destructive test fixture, production migration, owner-credential runtime or invented approval row. |
| Scope/window | Native imports, harmless PDF/8-second child isolation, fictional ID-only interrupted checkpoint/cross-tenant negative, signed private hop/protection and60-plus-second diagnostic to verify both90-second budgets; actual operational probe/receipt if packaging succeeds. No staff/user records or providers. Maximum2h, then pause/fence preview selector and disable Cron/execution; retain evidence, do not purge uncertain work. Fixed0.25CU implies0.5CU-hours plus startup/tail, not a hard bill cap. |
| Locality/privacy | CF stores UUID/epoch orchestration only; no customer payload, identity token, provider/database secret or document. PG stays in Singapore; record actual Vercel placement before deploying. Preview contains fictional data only. Production locality/privacy review remains separate. |

### Variable-to-source map (no values or secret creation yet)

| Location | Variable/binding | Exact source/rule |
| --- | --- | --- |
| App function | `BUYEROS_INTERNAL_API_URL` | Vercel-injected api service URL; binding on calling app. Never set manually, no build/middleware usage. |
| Worker | `WORKER_API_ORIGIN` / `WORKER_API_ALLOWED_ORIGINS` | Read-back protected preview HTTPS origin, exact JSON allowlist. No credentials/path/query/redirect. Invalid defaults remain in Git. |
| Worker | `WORKER_CURRENT_KEY_ID` / `WORKER_CURRENT_SECRET` | New dedicated machine identity, key ID1..64 and secret32..4096bytes; server-only Wrangler secret. No value in vars/Git/browser/logs. |
| API | `BUYEROS_WORKER_CURRENT_KEY_ID` / `BUYEROS_WORKER_CURRENT_SECRET` | Same newly generated dedicated pair in API runtime secret store; optional prior pair only for separately reviewed rotation. HMAC/replay/application authorization remain required with bypass. |
| Worker only | `WORKER_API_PROTECTION_BYPASS` | New preview-project Vercel automation secret; optional server-only header1..4096 printable bytes, never query/cookie/redirect. App proxy strips it. Dedicated project prevents production-project reuse. |
| API only | `BUYEROS_DATABASE_URL` | Restricted pooled TLS preview API login DSN; no owner/production DSN. |
| API only | `BUYEROS_EXECUTION_DATABASE_URL` / `BUYEROS_CHECKPOINT_DATABASE_URL` | Dedicated verified preview worker login; session-safe TLS connection for forcedRLS tenant/checkpoint/permit transactions. Never put DB credentials in Cloudflare/browser. |
| Operator only | `BUYEROS_DATABASE_MIGRATION_URL` / `BUYEROS_RUNTIME_ADMIN_DATABASE_URL` | Explicit approved empty preview target only, ephemeral owner/operator connection, not runtime secrets. No production fixture override. |
| Runtime | `EXECUTION_ENABLED`, `RUNTIME_EPOCH`, `BUYEROS_CLOUDFLARE_EXECUTION_ENABLED` | Initially false/current DB epoch from readback. Only bounded fictional preview probe may temporarily enable after packaging/security proof; pause at end. No production selector cutover. |
| API | `BUYEROS_PAID_ADMISSION_ENABLED`, `BUYEROS_PAID_DISPATCH_ENABLED`, `BUYEROS_R2_ENABLED` | false throughout. Production adapters unconfigured. No provider/R2/Auth0 tenant change; mailbox/CRM/sending disabled and delivery403 always. |

[Exact hosted proof recipe](runbooks/cloudflare-preview-probe.md) is preparation,
not an already implemented remote runner. Existing local probe/harness rejects
remote DSNs/preview mode. Before publishing the approved temporary diagnostic,
review its exact diff and exact new target; keep production/other projects out.
Run the protected probe through the actual gateway and internal API. Verify
missing bypass denied, missing/invalid HMAC401, replay409, and private API denial.
Collect deployed SHA, actual Linux/native import/PDF/checkpoint/limits/timing,
then remove the diagnostic and leave execution off. Failure requires a design
revision, not a waived hosted gate.

Production activation is a later exact decision after hosted CF00 proof,
independent review, production drain/role/schema/epoch inspection, account
quotas/alerts/locality, and the applicable policy/provider/R2/pilot approvals.
No deployed SHA or product-live claim follows from passing local tests.
