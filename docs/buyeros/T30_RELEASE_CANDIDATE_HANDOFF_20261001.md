# T30 release candidate handoff — 2026-10-01 HK

## Current facts

| Fact | Evidence |
| --- | --- |
| Code implemented | Stored retained recipients on the existing zero-cost grounded draft route, current policy/contact/actor checks at execution, recipient expiry at exact approval, canonical buyer-type roundtrip, and translated scope/list/dossier controls. One domain API and one Alembic owner. |
| Fixture verified | Full UI-created project to outcome journeys pass in en/zh-HK from initial desktop1280×800 and mobile390×844. OIDC, search and existing contact input are fictional. Optional paid lookup remains disabled. |
| Integration verified | Actual owned disposable PostgreSQL16, Valkey8, dispatcher and Celery consume HTTP-admitted research and draft intents. Required API577 and worker174 have zero failures/errors/skips. Current worker suite covers restart/replay and recipient/policy/member races. |
| Live identity | The user confirmed FIMMICK and admin role visible after sign-in. The separately approved exact production four-row setup has readback evidence. The agent did not observe an authenticated domain API trace or a complete deployed staff journey. |
| Externally blocked | Manual screen-reader/non-text review, external restore journal custody/completeness, continuous external worker/Valkey, private R2, named data-policy/provider economics and exact bounded pilot approval. |
| Deployed | Read-only production-alias metadata at2026-09-30T20:14:58Z: READY, dpl_GEgeCkt2iBUhvvLDEXD7yn74y1Q3, source62d40bc7687477f42e971ae5143485806630f1a6. This candidate has not been deployed to production. |

Reviewed candidate source: **PUBLICATION_PENDING**. Existing draft [PR9](https://github.com/YNWAforever/BuyerOS/pull/9), branch codex/fix-vercel-tslib-ssr, base main. Starting source479141f5f04455cdc19c786cb40a3a0fd9f4b4d2. No reset, merge, owner approval fabrication, new production mutation or paid/provider/delivery activation. Source review was performed inline by the author; no subagent or independent review is claimed.

## Exact current commands and outputs

Clear inherited BUYEROS_TEST_DATABASE_URL before these disposable suites; set BUYEROS_STRICT_INTEGRATION=1. Each browser configuration starts its own owned fixture and is run sequentially. Local versions: Node24.18.0, pnpm11.25.0, Python3.14.6; hosted CI uses Python3.12. Logs below are exact final summaries; JUnit checker separately verifies failure/error/skip counts.

| Working directory / command | Exact final output | Required checker |
| --- | --- | --- |
| services/api: .venv/Scripts/python.exe -m pytest -q --junitxml=$TEMP/buyeros-t30-api-full-green-20261001.xml | 577 passed, 110 warnings in220.26s | passed=577 failed=0 errors=0 skipped=0 |
| services/worker: .venv/Scripts/python.exe -m pytest -q --junitxml=$TEMP/buyeros-t30-worker-full-20261001.xml | 174 passed, 4 warnings in86.36s | passed=174 failed=0 errors=0 skipped=0 |
| services/api: .venv/Scripts/python.exe -m pytest -q tests/test_draft_approval_migration.py --junitxml=$TEMP/buyeros-t30-rollback-guards-20261001.xml | 3 passed, 12 warnings in8.91s | passed=3 failed=0 errors=0 skipped=0 |
| root: pnpm.cmd exec playwright test --config playwright.mvp-research.config.ts tests/e2e/mvp-a-research.spec.ts --reporter=line,junit | 4 passed (4.8m) | passed=4 failed=0 errors=0 skipped=0 |
| root: pnpm.cmd exec playwright test --config playwright.workbench.config.ts tests/e2e/daily-workbench.spec.ts --reporter=line,junit | 8 passed (2.8m) | passed=8 failed=0 errors=0 skipped=0 |
| root: pnpm.cmd exec playwright test --config playwright.live-zoom.config.ts tests/e2e/api-browser-zoom.spec.ts --reporter=line,junit | 2 passed (2.1m) | passed=2 failed=0 errors=0 skipped=0 |
| root: pnpm.cmd exec playwright test --config playwright.buyer.config.ts tests/e2e/buyer-results.spec.ts --workers=1 --reporter=line,junit | 1 passed (2.3m) | passed=1 failed=0 errors=0 skipped=0 |
| root: pnpm.cmd exec playwright test --config playwright.buyer-management.config.ts tests/e2e/buyer-management.spec.ts --workers=1 --reporter=line,junit | 3 passed (2.0m) | passed=3 failed=0 errors=0 skipped=0 |
| root: pnpm.cmd exec playwright test --config playwright.mvp.config.ts tests/e2e/mvp-a-journey.spec.ts --reporter=line,junit | 1 passed (2.5m) | passed=1 failed=0 errors=0 skipped=0 |

For each retained XML: services/api/.venv/Scripts/python.exe scripts/check-required-tests.py --junit artifacts/t30-tests/FILE.xml. The earlier bilingual desktop2/2 XML is historical intermediate evidence, not additional unique full journeys. The original named acceptance1/1 uses seeded addressed data and is narrower than the four newly UI-created projects.

Static gates: node tests/domain-checks.mjs11/11; node tests/live-adapter-checks.mjs74/74; node tests/live-auth-checks.mjs8/8 total including cryptographic checks; node --test tests/api-types-generation.test.mjs1/1; node --test tests/vercel-services.test.mjs5/5; services/api: .venv/Scripts/python.exe ../../scripts/generate-operation-routes.py --check78 operations. pnpm.cmd exec tsc --noEmit, pnpm.cmd lint, pnpm.cmd build and git diff --check exit0. The build retains its nonfatal >500kB chunk advisory. Local raw summaries and hashes: [output](../../artifacts/t30-local-test-output-20261001.txt), [manifest](../../artifacts/t30-verification-20261001.json), [JUnit](../../artifacts/t30-tests/).

Hosted CI: **PUBLICATION_PENDING**. The workflow adds a separate owned-container continuity job, runs4 continuous cases plus8 workbench,1 pagination,3 management and1 original seeded regression, requires zero failures/errors/skips and retains each suite before the next fixture cleans test-results. The separate actual-zoom job also requires its JUnit gate. CI covers the Vercel build/emitted renderer. Hosted results are not inferred from local results.

## Meaningful failures and repairs

- Addressed admission503, ignored worker recipient context, absent canonical contact detail, unsupported display-label buyer type422, missing UI recipient selector, revoked actor materializing a draft and expired-recipient approval201 were reproduced before the corresponding fixes.
- zh-HK list and project accessible names failed before localization. Literal independent language expectations verify the actual UI and downloaded text.
- A valid retained contact correctly stopped the rollback at0032 before0028. The regression now separately proves both guards without deleting dates/history.
- A duplicate fictional contact violated the real canonical-company uniqueness rule. The fixture reuses and verifies its unchanged eligible input.
- Initial full matrix2 passed/2 failed and workbench7 passed/1 failed captured429 from counters carried between independent fictional cases. Only initial named fake-actor windows are reset under the exact owned-container guard. Limits remain active throughout each case; production limiter values are unchanged. These were fixture isolation failures, not provider/live failures.

## Audit A01–A18 closure

Classification compares current source with audit baseline5e61f401bf1bcdf80ea1ce254dd9c62e8eedbab0, which was not reset onto this checkout. Fixture closure and external release gates remain separate.

| Finding | Classification | Evidence / remaining scope |
| --- | --- | --- |
| A01 login/workspace | already fixed with evidence — approved setup readback and human UI confirmation; agent API trace open | Exact approved Neon FIMMICK/User/active workspace_admin/AuditEvent readback passed. The user confirmed FIMMICK and admin role visible on2026-10-01 HK after sign-in. Auth0 public SPA/API/PKCE configuration and deployed entry are verified; the authenticated bearer trace/full live staff journey was not observed by the agent. |
| A02 cross-domain API | source changed — Same-origin bound API proxy deployed; authenticated round trip open | T06 disposable browser CORS/bearer checks passed3/3. Vercel app now proxies same-origin /v1 to its internal FastAPI binding; live anonymous /v1/workspaces401 is verified on deployed62d40bc. No authenticated staff API/database round trip is proven. |
| A03 ICP replay/numbering | already fixed with evidence — Already fixed with fixture evidence | T02 retried save returns one immutable version; two different-key concurrent saves allocate numbers 1 and 2 under the Project lock. |
| A04 ICP validation | already fixed with evidence — Already fixed with fixture evidence | T02 typed body rejects malformed/nested/oversize fields with zero rows; malformed JSON and unexpected 500 use sanitized request-ID envelopes. |
| A05 offer persistence | already fixed with evidence | T07 offer creation/edit/reload/partial-save recovery and current T30 four en/zh-HK desktop/mobile UI-created projects preserve actual typed product/value facts. Fake OIDC is used for fixture journeys; real FIMMICK/admin visibility is human-confirmed, full deployed continuity unverified. |
| A06 approval context/version | already fixed with evidence | T03 exact version/hash/basis guards and current T30 reviewer approvals of edited v2 pass in all four locale/layout cases. Same-project researched buyer is later recipient-bound and approved at its exact context; expiry/policy/member races fail closed. Full deployed journey unverified. |
| A07 scope races | already fixed with evidence — Disposable fixture and UI verified; live activation open | T05 A→B→A discard, T06 immutable write context, and T07 response-lost same-action replay plus reload/project-only recovery passed. Real network interruption in a deployed environment remains unverified. |
| A08 project idempotency fingerprint | already fixed with evidence — Already fixed with evidence | T01 real-DB tests prove same-key different target and changed If-Match return 409; first result replay and 20 concurrent requests pass. |
| A09 lock order/stale profile | already fixed with evidence — Already fixed with fixture evidence | T03 repeats approve/update/archive races over independent PostgreSQL connections; Project→ICP lock order, stale rejection and one active pointer pass. |
| A10 snapshot and pagination | already fixed with evidence — Fixed in disposable integration; live activation open | T08 actor/project/expiry/filter guards, bounded SQL snapshot and page reads, 8/12/24 browser pagination, stable insert/tie ordering and dossier source tabs passed. Fake identity and fictional evidence; no deployed claim. |
| A11 demo-only controls | source changed | Current T30 four full API/DB/Valkey/Celery fixture journeys create/edit offer, approve ICP, research and use persisted review/list/assignment, grounded addressed draft, exact approval, authorized export, outcome and refresh. Optional contact input/search/OIDC are fictional; live provider and deployed full-journey proof remain open. |
| A12 maintenance/bulk | already fixed with evidence | T09/T10 durable note/list/review/policy and T11 101-row assignment/progress/retry/cancel browser evidence are recorded. T26 failure reports use audited expiring export authorization; 50-row crash/resume/current-version retry/actor-access/pending-cancel are DB verified. Current T30 list/assignment and viewer denial pass4/4. Live worker/provider and deployed authorization remain open. |
| A13 operations/recovery | still open — Disposable recovery verified; deployed recovery open | T11/T12 durable jobs, pagination, audit and heartbeat, T15 Celery/Valkey broker delivery, T19/T20 checkpoint/restart and T23 unknown-hold reconciliation have local crash/retry evidence. T28 retention/backup intent replay and switches are implemented; a two-container older-backup fixture journal replay passed 10/10 with reads disabled, RLS and ledger checks. External journal custody/completeness, physical deletion and deployed recovery remain open. |
| A14 worker completion/dispatch | source changed — Fixture integration fixed; deployed proof open | T15 dispatcher cycle, ready claim, lease/fence and separate Celery/Valkey delivery passed on disposable services. T16–T20 add persisted retrieval, evidence/fit graph, checkpoint and restart recovery. No live provider or deployed worker claim follows from these fixture tests. |
| A15 performance | still open — disposable measurements and pool fix; release proof open | Post-rate-pool T29 10k/100 ASGI read P95 39.377ms sequential and 244.895ms across ten distinct fixture staff, 11 SQL/request and 10 DB connections. Persisted buyer PATCH/admission P95 60.865/168.524ms; 100-workspace Valkey broker publish P95 2.280s. One-slot 500 red then 2/2 green; hosted PR CI strict API 569/569 passed on `f8eaec7`, and current T30 local strict API577/577 and worker174/174 passed with zero skips after Docker recovery; these gates are not new performance measurements. Worker consumption and production latency remain unverified. |
| A16 locale/routes/a11y | still open | Current workbench8/8 and continuous journey4/4 pass with fake OIDC/owned PostgreSQL: en/zh-HK desktop/mobile, translated scope/list/dossier controls, locale and scope recovery, partial failure, no page overflow and measured text/control contrast. Eight final export/outcome screenshots were visually inspected. Current actual Chromium200% API-backed zoom passes2/2 over six routes in en/zh-HK. Manual screen-reader and remaining non-text elements are unverified. |
| A17 progress/test truth | still open | Current local required API577/577, worker174/174, rollback3/3 and full fixture continuity4/4 have retained zero-skip JUnit evidence; workbench8/8 passes. Current six-job CI awaits publication; earlier479141f five-job CI is verified. Production source62d40bc and anonymous acceptance4/4 are proven; authenticated deployed full staff/provider/pilot evidence remains open. |
| A18 activation safety | still open — fixture guards and specifically approved initial setup verified; live pilot activation open | Membership/RLS, fail-closed policy, unknown holds, exact approval/export revocation, permanent delivery403 and recovery switches have fixture evidence. Approved Neon/Auth0/source62d40bc deployment and exact four-row FIMMICK administrator setup are verified; the user confirmed workspace/admin visibility. No provider spend/pilot approval was inferred; policy, provider, continuous worker/Valkey and R2 activation remain open. |

## Operation coverage

[API_OPERATION_STATUS.csv](remaining/API_OPERATION_STATUS.csv) has78 unique operations: all70 original supplied operations are present, zero missing; extensions are assignBuyerOwners, cancelAsyncJob, exportBulkFailures, listAsyncJobs, listMemberships, listOfferDocuments, retryFailedAsyncJob and updateMembership. Every deployed disposition remains unverified; an implemented handler or fixture response is not evidence of deployed operation acceptance. disabledDeliveryBoundary deliberately returns403 DELIVERY_DISABLED, including approved drafts. Paid/unselected capabilities fail closed and never return demo rows.

## Screenshots

Eight final principal full-page screenshots were inspected: en/zh-HK × desktop/mobile × approved export/persisted outcome. Paths: artifacts/t30-screenshots/t30-continuity-LOCALE-LAYOUT-approved-export-fixture.png and ...-outcome-fixture.png. Four additional mobile-readback screenshots are retained. These show fictional accounts/data; no screenshot is presented as a production staff journey. Current actual Chromium200% zoom2/2 is evidenced by JUnit and its assertions across six routes; older T29 zoom screenshots retain their own source attribution. Actual screen-reader use and remaining non-text checks are not claimed.

## Migration, restore and rollback

Sole Alembic head0033_api_rate_windows; no new migration or overwritten revision. Current rollback guard3/3 proves real-chain refusal at0032 while contact expiry is retained, independent0028 refusal while approval history is retained, and preservation of head/history. Earlier T28 older-backup replay10/10 used two disposable containers, fixture journal, disabled reads and RLS/ledger checks. External journal custody/completeness and object deletion remain open. No production rollback was performed.

To undo this application slice after an authorized rollout: stop new admission/paid dispatch, keep safe reads/reconciliation, revert the compatible application code and retain ledger/outbox/history and unknown holds. Do not reset the database, clear Valkey or discard accepted-unknown work. The migration owner and runtime credentials remain separate.

## Performance conditions and results

Historical post-rate-pool T29 artifacts used Windows11, in-process FastAPI ASGI on one persistent event loop, fictional OIDC, owned PostgreSQL16/Valkey8,10k buyers/100 workspaces/projects/ICP revisions,1k-item actor-bound snapshots,100-row pages,30 sequential reads and10 distinct concurrent staff. Read P95 sequential39.377ms / distinct concurrent244.895ms,11 SQL/read and10 connections. Twenty persisted note mutations and20 admissions had P95 60.865ms/168.524ms. One100-workspace broker cycle progressed all and published100 unique intents with ready-to-publish P95 2.280s. No worker consumed that benchmark's messages. See [performance-baseline.md](performance-baseline.md) and its original artifact hashes/source conditions. No current T30 performance rerun, deployed latency, provider latency or production capacity claim is made.

## Remaining activation decisions

The next concrete application activation decision is whether to deploy the reviewed candidate SHA to the existing BuyerOS Vercel project. Earlier deployment approval applied to source62d40bc and does not authorize this newer candidate. Exact configuration remains: app public catch-all, same-origin /v1 app proxy, internal FastAPI service, calling app binding BUYEROS_INTERNAL_API_URL injected by Vercel, external continuous Celery worker/dispatcher plus one Valkey. No binding value is set manually and no worker HTTP service is invented. Preserve the nine saved production settings; no migration is needed for this slice.

Candidate deployment approval would authorize no paid provider or pilot. A later pilot needs named workspace/users/markets/purposes/retention, search/model/contact adapters and terms/current prices, fixed-point caps/time window/stop thresholds, continuous worker/Valkey and private R2 configuration, external recovery evidence and actual staff acceptance. Unknown provider acceptance must retain holds and reconcile. PILOT_EXECUTION_RECORD remains NOT RUN with no fabricated owner signatures. Mailbox/CRM/sending remain disconnected; delivery stays disabled. See [release.md](runbooks/release.md) for exact variable names and staged checks.

## Changed files

See [remaining/CHANGED_FILES.md](remaining/CHANGED_FILES.md) for the exact current path inventory. Reviewed source and hosted CI results are filled only after publication.
