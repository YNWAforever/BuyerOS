# Cloudflare release candidate handoff — 2026-10-01 HK

## Current facts

**2026-10-02 HK update:** reviewed implementation6ef38d1 adds0036 checkpoint
schema-version permissions and a fail-closed catalog proof. Focused23, ownedPG18
37, full worker186 and gateway/release4 pass; current full CI is pending.
The preceding8ffd91f checkpoint CI now passes8/8. Production was freshly
read-only inspected at source12327c7/schema0033, with no work/holds/runtime login.
No production mutation or new hosted verification occurred.
See [the exact guarded setup proposal](runbooks/cloudflare-production-setup-proposal-20261002.md)
and [current preparation checkpoint](../../artifacts/cloudflare/CF08-production-preparation-checkpoint.json).
Earlier source-bound test/hosted tables below remain historical to their named source.

| Fact | Evidence and practical limit |
| --- | --- |
| Code implemented | CF00 local and CF01–CF08 local implementation complete. One API-owned Python execution engine, strict signed bridge and TypeScript Cron/Queue/Workflow controller; compatible thin Celery adapters remain. Default selector is Celery/off/epoch1. |
| Fixture verified | English/zh-HK at1280×800 and390×844: UI login/scope → create/edit offer → current ICP approval → bounded research → review/list/assign → grounded addressed draft → exact approval/export → manual outcome/refresh. OIDC, search and contact inputs are fictional. Optional unknown contact holds and101-row bulk/restart/page2 are additional cases. |
| Local integration verified | Latest full CI79d6caf: actual Miniflare Cron/Queue/Workflow → HMAC → native FastAPI/SQLAlchemy → owned PostgreSQL. API686, worker186, staff7, PG18compat29, operating2, legacy4/8/1/3/1, zoom2 and smoke1; all required suites zero failures/errors/skips. Eight jobs SUCCESS. |
| Hosted integration | Approved isolated CF00 native/PDF/checkpoint/protection and actual61-second two-hop checks pass at595865f. One real Queue-created Workflow completed its signed API operational probe and matching Neon receipt. All payloads fictional/ID-only; no live provider verification. |
| Externally blocked | Production plan/quota/privacy, role/schema/drain/selector scope and alert routing; independent review; external deletion journal/R2, policy/provider economics/pilot, full authenticated staff trace and assistive accessibility. |
| Deployed | Isolated protected Vercel native dpl_HP2YJ8NpPWPhZr6Gz6CQMZDt2xCP and release API dpl_2ZzGXSXkfERBYyYzxufCoVCvH1FD at595865f were READY/preview/iad1. Private Cloudflare preview now executionfalse/noCron/epoch3, version992537e3-7d93-402a-8c98-dafb110958a4. Neon is idle and restricted logins NOLOGIN; bypass revoked. No production Cloudflare cutover; historical production12327c7 is not a refreshed live readback. |

**Current deployed preview code source:** `595865f5e4dce418e2b96d4819f72633378eba2b`.
The shared PDF child now receives only installed code/package metadata paths,
with no inherited credentials or PYTHONPATH. This changes production parser
source from the historical RCd6c2849. The stronger legacy regression successor
is `93de21f8201f9ddb9f481f061a579a59d50efc37`. Current reviewed source including
the screenshot collection fix is `79d6caf8b51aac00560cf6d69b0198c8614df528`;
[CI36893525903](https://github.com/YNWAforever/BuyerOS/actions/runs/36893525903)
is8/8 SUCCESS. Its19 source hashes and synthetic test-merge tree match the source.
API686/0/0/0 in261.25s (97warnings), worker186/0/0/0 in25.60s (1warning),
controller27, PG18compat29 in37.54s, operating2 in38.12s, staff7,
legacy4/8/1/3/1, zoom2 and smoke1 pass; strict skip checkers all succeed.
[Current CI manifest](../../artifacts/cloudflare/ci-79d6caf-hosted-successor/manifest.json)
records every exact command/result, raw log hashes and official9,017,076-byte
artifact digest45b17aa6…3421eaa. Twelve fresh journey PNGs plus two fresh special
cases are preserved; four locale/layout captures visually inspected. Full
assistive accessibility and live staff/provider evidence remain open.
Author review is not independent approval.
**Reviewed temporary-preview preparation source:** `07a7537befbf1e2290ee7079e18a258083615ed6`.
Historical [CI36875943355](https://github.com/YNWAforever/BuyerOS/actions/runs/36875943355)
at91b1f9b/test-merge d78fcadf is8/8 SUCCESS, with matching Git trees.
API679/0/0/0 includes29 preparation checks; actual local Linux native PDF limit
assertions pass. Worker186, controller27, PG18compat29, operating2, staff7,
zoom2, smoke1 and legacy4/8/1/3/1 pass with required skip gates enforced.
[Historical91b1f9b evidence manifest](../../artifacts/cloudflare/ci-91b1f9b/manifest.json)
verifies official artifact digest,19 source hashes and fresh7/29/2 XML counts.
Two fresh special-case screenshots are visually inspected; twelve retained
bilingual local PNGs at that checkpoint were historical because journey PNGs were written
outside the upload selection. Eleven anonymous built-fixture Error messages
remain unattributed and retained; test assertion passes do not erase them.
See `CF00-preview-remote-ci-91b1f9b.json` for exact job commands, times, warnings,
raw decoded-log hashes and the last observed app/API preview metadata.
No hosted/controller/production feasibility is implied by those historical local CI results.
Current isolated hosted evidence is in
[CF00 final checkpoint](../../artifacts/cloudflare/CF00-hosted-preview-checkpoint.json).
The earlier48 zero-skip local preparation checks alone did not verify hosting;
current actual hosted evidence is recorded separately above.
Release routes/schema are unchanged. Prior RC CI36861185237 at229a76c/
test-merge57b8560 is8/8 SUCCESS; it predates this preparation source.
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

[Historical migration file list](../../artifacts/cloudflare/CF08-changed-files.json)
records the baseline/reviewed SHA and176 source/config/test paths, plus retained
evidence and documentation. [Current Git changed-file inventory](../../artifacts/cloudflare/CF00-hosted-changed-files.json)
records692 total tracked delta paths and21 committed session paths at79d6caf;
it includes evidence/documentation, and does not relabel every path a code change.
The PR also retains earlier deployment and Render
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
| A02 API domain | source changed | One same-origin app proxy with runtime app→API binding; actual emitted frontend/native integration and protected hosted61-second two-hop transport verified in isolated preview. Full production staff trace remains open. |
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
| A14 worker completion | source changed | Actual local Cron/Queue/Workflow/HMAC/nativePG and retained Celery/Valkey continuity. Isolated hosted Queue-created Workflow completed one signed operational step with matching Neon receipt; no customer/provider completion claimed. |
| A15 performance/cost | still open | Two local10-job repetitions,100-workspace fairness and10k late SQL page measured. Isolated native request28.74s,61-second two-hop65.91s, one Workflow step12.06s observed; these are single samples, not workload P95. Actual billing and all-day Neon quota decision remain open. |
| A16 locale/a11y | still open | English/zh-HK at390/1280, negative roles, current screenshots and actual200% Chromium zoom over six routes verified. Manual screen reader/non-text elements remain unverified. |
| A17 evidence truth | still open | All required local suites zero skip; full journey/state/hold/restart proof and red artifacts retained. Live identity/provider/pilot and new remote CI/hosted acceptance remain separate. |
| A18 activation | still open | Specifically approved isolated resources and0035 initialization verified; native and operational probes pass. Preview now fenced epoch3/NOLOGIN/controlleroff/Cronoff/bypassrevoked/Neonidle. Production migration/roles/selector/providers/pilot and independent review still require the exact later decision. |

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

Four current fixture journeys use the actual emitted Vercel function/static
assets and runtime service proxy. [Fourteen fresh79d6caf screenshots](../../artifacts/cloudflare/ci-79d6caf-hosted-successor/screenshots/)
include approved exports, manual outcomes/readback, bulk/restart and unknown hold.
Official artifact digest/source/XML counts and every PNG hash are verified.
Four en/zh-HK desktop/mobile captures were visually inspected:

- [English desktop outcome](../../artifacts/cloudflare/ci-79d6caf-hosted-successor/screenshots/cloudflare-continuity-en-desktop-outcome-fixture.png)
- [English mobile approved export](../../artifacts/cloudflare/ci-79d6caf-hosted-successor/screenshots/cloudflare-continuity-en-mobile-approved-export-fixture.png)
- [zh-HK desktop outcome](../../artifacts/cloudflare/ci-79d6caf-hosted-successor/screenshots/cloudflare-continuity-zh-HK-desktop-outcome-fixture.png)
- [zh-HK mobile approved export](../../artifacts/cloudflare/ci-79d6caf-hosted-successor/screenshots/cloudflare-continuity-zh-HK-mobile-approved-export-fixture.png)

[Author visual evidence](../../artifacts/cloudflare/CF00-current-ui-visual-review.json).
Earlier local/legacy/zoom screenshots remain separate historical evidence.
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

## Approved isolated hosted preview and shutdown

Direct human approval covered the exact named preview for at most two hours:
2026-10-01T14:48:41Z to16:48:41Z, conditional Workers Paid US$5/month base if
needed plus shared metered overages. No billing plan was changed. This approval
did not cover production cutover, customer jobs, providers, R2 or delivery.

| Target | Actual identity and result |
| --- | --- |
| Cloudflare | Account e387dfbeded3deb5b8f0023a78a660b5; private Worker/Queue buyeros-jobs-preview, DLQ buyeros-jobs-preview-dlq, Workflow buyeros-job-preview. Queue retention3600s, batch/concurrency1, retries5. No public route or Cron during any hosted phase. Subscription GET403 remains unverified; deployment success does not prove Paid. |
| Vercel | Dedicated protected prj_YfIdLRKWvBjomGG56RhwEmqyxRRR in team_qvzlsFmfCsLkgItSypqHjw3z; actual preview targetnull, Node24/Python3.12.14, iad1, Fluid/default90. App public catch-all, API internal, app→API BUYEROS_INTERNAL_API_URL binding injected at runtime. No custom domains or production secrets copied. Standard function-memory tier observed; physical memory/CPU not independently measured. |
| Neon | Fresh empty rapid-night-21766635 / br-old-shape-b3eel1kb / ep-little-lab-b3rk8fx5, host ep-little-lab-b3rk8fx5.c-4.ap-southeast-1.aws.neon.tech. Singapore PG18.6 Free fixed0.25CU, database buyeros_cf_preview. Zero public tables before sole owner-only Alembic upgrade through0035. Nonowner API/worker logins NOSUPERUSER/NOBYPASSRLS/NOCREATEDB/NOCREATEROLE; worker catalog prooftrue. Runtime schema setup absent. |
| Native source |595865f5e4dce418e2b96d4819f72633378eba2b plus four hashed temporary overlay files, dpl_HP2YJ8NpPWPhZr6Gz6CQMZDt2xCP. Linux imports/PDF/8-second child kill/AS536870912/CPU6/file1048576 caps/ID-only checkpoint interrupt-resume/cross-tenant denial pass. |
| Actual bundle |8664 regular files,186540543 uncompressed bytes,0symlinks, all native package roots in task, pytest absent. Measurement0.322s. Actual ZIP transport size unavailable; build-cache281.83MB and uploaded source521nodes are different measurements. |
| Actual hop/security |No bypass401; bypass without HMAC401; valid native200; nonce replay409; valid duration200 with API61.00048s/client65.91246s. Native client28.73526s/API21.97781s, cold imports0.77252s/warm0.00579s; parent/child reported peak RSS131051520bytes. Single samples, not P95/account maximum proof. |
| Operational source |Same595865f fresh Git archive with diagnostic overlay removed, dpl_2ZzGXSXkfERBYyYzxufCoVCvH1FD. Privileged dry-run then CAS epoch1→2 enabled only this empty preview. One JSON ID-only Queue publish HTTP200 created Workflow bop1-691e21aea5f642dcae8265fb5701537e-e2 through binding. One step12.056s, complete/done/OK; receipt UUID/epoch2 at16:22:45.364297Z. Operator never called maintenance directly. Source verifies acknowledgement after Workflow existence; no separate hosted ack telemetry was collected. |
| Data boundary |users/workspaces/memberships/outbox_events/provider_operations/worker_steps all0 before and after. Only fictional checkpoint/replay/probe operational evidence. No Auth0 staff/provider/R2/paid admission/delivery activation. |
| Shutdown |Completed16:26:11.821617Z before expiry. CAS epoch2→3/cloudflarefalse; both new runtime logins NOLOGIN; six preview gatesfalse; bypass revoked and former bypassHTTP401; private Worker executionfalse/noCron/invalidorigin/epoch3; Neon endpoint idle. Receipt and queues retained, no purge/downgrade. |

Vercel pause API returned400, “Active production deployment does not
exist”. It cannot pause these preview-only deployments. No production deployment
was created to satisfy it; the independently verified DB, credential, controller,
protection and compute fences provide the shutdown. Old deployment env values
are immutable, and the diagnostic also rejects requests after compiled expiry.

### Exact commands and retained failures

Commands actually ran from repository root with PYTHONUTF8=1:
`services/api/.venv/Scripts/python.exe .sites-runtime/cf-preview-session-20261001/hosted_probes.py`
returned exit0, five strong status/source/duration assertions. Preparation,
release deployment, single Queue publication/receipt inspection, shutdown and
sanitization scripts in that same ignored operator directory are recorded with
source/overlay/config hashes and platform identities in the checkpoint. Private
credential files are excluded from Git and all public output.

Focused actual-process regression command (services/api):
`uv run --frozen pytest -q tests/test_cloudflare_local_steps_db.py::test_pdf_child_keeps_sanitized_env_and_eight_second_timeout tests/test_pdf_subprocess_runtime.py --junitxml=../../artifacts/cloudflare/CF00-legacy-isolation-green.xml`
returned2/0/0/0 in4.23s,5warnings. Prior vendor-path meaningful red1failure;
green44/0/0/0 in45.69s with1deselected before bundle-measurement addition.
Fresh full CI595865f observed685passed/1failed/0errors/0skipped: the legacy
blanket PYTHONPATH prohibition was stale. Required XML checker did not run after
that suite failure. Its successor93de21f asserts independently enumerated code/
installed metadata roots, exact environment, malicious inherited path/secret
rejection, temporary directory and eight-second timeout. Successor93de21f subsequently passed8/8; current79d6caf also passed8/8 with
API686 zero required skips and all14 current UI screenshots retained.

Failed native deployments, initial ASGI handler discovery failure, missing
psycopg vendor imports, the canceled misclassified first deployment, metadata
KeyError before activation and pause400 remain retained. Automatic approval
review rejected removing the native success assertion; that patch was not applied.
Independent duration evidence retained the failed native gate until the fix passed.

- [Final checkpoint](../../artifacts/cloudflare/CF00-hosted-preview-checkpoint.json)
- [Native/protection/duration](../../artifacts/cloudflare/CF00-hosted-native-and-duration.json)
- [Actual Queue/Workflow/API/PG](../../artifacts/cloudflare/CF00-hosted-operational.json)
- [Shutdown and platform pause limit](../../artifacts/cloudflare/CF00-hosted-shutdown.json)
- [Source/deployment/overlay manifest](../../artifacts/cloudflare/CF00-hosted-deployment-manifest.json)
- [Failed full-CI assertion](../../artifacts/cloudflare/CF00-legacy-isolation-ci-red.json)

### Variable placement used, with no secret values

| Location | Variables/binding and verified rule |
| --- | --- |
| App function |BUYEROS_INTERNAL_API_URL injected by runtime app→api service binding; never manually set or used during builds/middleware. |
| Worker |WORKER_API_ORIGIN/WORKER_API_ALLOWED_ORIGINS exact protected release-preview origin; WORKER_CURRENT_KEY_ID and newly generated server-only WORKER_CURRENT_SECRET. Optional WORKER_API_PROTECTION_BYPASS is header-only to that exact origin, stripped by gateway. No database/provider/identity secret in Worker. After shutdown origin invalid, allowlist empty, executionfalse. |
| API |BUYEROS_WORKER_CURRENT_KEY_ID/SECRET match distinct operational identity. Distinct preview diagnostic key/secret used only during native phase; diagnostic absent in release API. No browser/public secret. |
| API/PG |BUYEROS_DATABASE_URL restricted API DSN; BUYEROS_EXECUTION_DATABASE_URL and BUYEROS_CHECKPOINT_DATABASE_URL restricted worker TLS DSN. Exact compiled host/database/role validation; runtime roles now NOLOGIN. No migration/admin DSN remotely. |
| Operator only |Owner DSN only in ignored private local file and short-lived initialization/CAS process. One migration owner; no production/shared test override. |
| Gates |Paid admission/dispatch, R2 and Celeryfalse throughout; Cloudflare only briefly enabled at selected preview epoch2 for one ID-only probe. Cron always empty. All gatesoff/epoch3 afterward. Delivery remains403 DELIVERY_DISABLED. |

## Remaining production activation decision

CF00 isolated hosted fixture feasibility is complete. Production remains pending
independent review and an exact inspected role/schema/drain/epoch, quota/plan,
locality, alert/stop and rollback proposal. The continuous minute polling model
still exceeds the observed Neon Free monthly compute allowance; the two-hour
preview result does not approve a production upgrade or prove live provider
economics. Provider/R2/policy/pilot and real staff/accessibility checks remain
separate gates. Retain one API/migration owner and unknown holds; never infer
production authority from this preview approval. No merge/product-live claim.
