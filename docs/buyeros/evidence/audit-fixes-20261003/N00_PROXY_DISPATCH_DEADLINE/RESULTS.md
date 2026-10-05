# N00 / F20 / NA01 — counted proxy ingress and physical dispatch deadline

Reviewed source `9e1ef78d4ae61429dee0d4b6fd62de9cbfdd7c92`, BASE233848b263cfdefc49d6dc5f53df2d534afdba16, branch codex/n00-proxy-dispatch-deadline, checked `2026-10-05T08:08:51.042633+00:00`. **Full N00/NA01/F20 OPEN; deployed SHA NULL.** Author review only, independent review pending. Local harness repair; Auth0/domain API/UI/schema/roles unchanged; no external/provider/account/email/push/deploy action.

## Reproduced issue and smallest fix

Native Node HTTP streamed-body RED observed: an already reserved request completed its body after target expiry and still returned200; continuous body trickle reset the idle timer and returned200; a physical write with100ms remaining TTL used the full1000ms timeout and returned200 after180ms. These failed expected403/408/503 respectively. Timely-body positive control passed.

Replace resettable ingress idle timeout with an absolute body collection deadline and bounded bytes. Recheck journal TTL immediately before physical dispatch; clamp its signal deadline to min(configured upstream timeout, remaining target TTL). Pre-dispatch body/expiry rejection records rejected with zero upstream hops; post-dispatch uncertainty retains unknown hold. Restart/renewed channel/query/token semantics and 200-total/20-cleanup reserve unchanged. Body timeout responds408 and closes the incomplete request connection. No code grants identity or workspace authority.

Three files/105insertions/8deletions: scripts/neon-counted-proxy.mjs, tests/neon-proxy-deadline.test.mjs, focused plan. [Source patch](source.patch); [author review](reports/source-review.json). The named four native HTTP tests exercise real owned servers and fresh persisted journals, no mocked backend fetch. Original302/body/status/timeouts and DB guards unchanged. No migration; read-only Alembic heads0037_bulk_manifests. Separate peerQ13 proposed0038 unmerged.

## Fresh results

|Check|Pass|Fail|Skip|Evidence|
|---|---:|---:|---:|---|
|First RED (timely control included)|1|2|0|reports/red.log/.xml|
|Complete RED (remainingTTL added)|1|3|0|reports/red-final.log/.xml|
|Focused deadline + original counted proxy|28|0|0|reports/focused-green.log/.xml|
|All29 rootMJS suites|304reported /303JUnit leaves|0|0|reports/root-green.log/.xml|
|STRICT owned EdDSA diagnostic|8|0|0|reports/crypto.log/.xml|
|Portable actual retained SDK output + fresh proxy/browser|6|0|0|reports/portable-ui.log/.xml|
|Vercel actual retained SDK output + fresh proxy/browser|6|0|0|reports/vercel-ui.log/.xml|

Root106071.156ms; focused7845.584ms; crypto1.61s/one existing asyncio deprecation warning; UIportable17.345563s/vercel8.442168s, zero JUnit/global errors. Types/scoped ESLint/generated types/routes exit0;84operations=70+14, no operation/ledger changes. Root reported count includes one nested parent. Focused28 is a subset of root304, not additional unique cases.

This protocol slice needs no domain DB suite: direct protocol/crypto DBconnections0, no required DB skip. Whole root runs its existing guarded disposable test subprocesses; its304 is Node counts, not a new API/SQL count. All required assertions ran; no0-test/skip was counted pass. No new auth integration, provider accuracy, production performance or full staff journey result inferred.

## Built-output provenance and accounting

No new build. SDK0.5.0-beta/framework pins unchanged. Reused actual compiled base2eb4b388a4d669a80bd3f205804d97e3f3a81267 from historical c756596406f41884f61a3b64c8549f569e34cfa4 checkpoint.14 compiled overlays unchanged; archiveSHA matches immutable N00_UNKNOWN_WRITE_RECOVERY reuse proof; every actual output byte compared to its frozen archive:95portable and2625Vercel files (2220 regular members +405 hard links). [Exact reuse evidence](reports/build-reuse.json); [verification script/log](reports/verify-build-reuse.py). Current proxy is a host-side script imported at runtime, not embedded in those compiled artifacts. Do not call this a fresh current-source build. Root SSR uses the retained normal main artifact from5aaf649; application/API/UI source unchanged in this follow-up.

Each UI run has38durable reservations,37physical owned-loopback Auth hops,35accepted/2rejected/1unknown/0pending,0external Auth requests. Locally_rejected2 includes the forwarded refused redirect and one held retry; it is not received minus forwarded. Expected sign-out unknown hold survives UI retry. Original ownership-guarded teardown proves private root/configuration/journal removal and actual OS child absence. [Portable receipts](runtime/portable/budget.json), [Vercel receipts](runtime/vercel/budget.json); cleanup.json and child-cleanup.json under each. Fresh fictional screenshots under screenshots/; this UI explicitly says its subject is not a BuyerOS user or role. No true Google/account/session/provider result.

## Exact executed commands

Cwd is the isolated worktree unless noted. Crypto/UI set PYTHONUTF8=1,BUYEROS_STRICT_INTEGRATION=1, unset DATABASE_URL/BUYEROS_TEST_DATABASE_URL. All targets loopback/fixture.invalid; real targets/credentials unused.

```powershell
# RED before implementation
node --test --test-reporter=spec --test-reporter-destination=test-results/n00-proxy-dispatch-deadline/red-final.log --test-reporter=junit --test-reporter-destination=test-results/n00-proxy-dispatch-deadline/red-final.xml tests/neon-proxy-deadline.test.mjs
# GREEN
node --test --test-concurrency=1 --test-reporter=spec --test-reporter-destination=test-results/n00-proxy-dispatch-deadline/focused-green.log --test-reporter=junit --test-reporter-destination=test-results/n00-proxy-dispatch-deadline/focused-green.xml tests/neon-proxy-deadline.test.mjs tests/neon-counted-proxy.test.mjs
$taskTests=@(Get-ChildItem -LiteralPath tests -Filter '*.test.mjs' -File | Sort-Object Name | ForEach-Object {'tests/'+$_.Name})
node --test --test-concurrency=1 --test-reporter=spec --test-reporter-destination=test-results/n00-proxy-dispatch-deadline/root-green.log --test-reporter=junit --test-reporter-destination=test-results/n00-proxy-dispatch-deadline/root-green.xml @taskTests
services/api/.venv/Scripts/python.exe -m pytest -q tests/fixtures/neon-runtime-flow/test_verify.py --junitxml=test-results/n00-proxy-dispatch-deadline/crypto.xml
node node_modules/typescript/bin/tsc --noEmit
node node_modules/eslint/bin/eslint.js scripts/neon-counted-proxy.mjs tests/neon-proxy-deadline.test.mjs --max-warnings=0
node scripts/generate-api-types.mjs --check
uv run --frozen --project services/api python scripts/generate-operation-routes.py --check
python test-results/n00-proxy-dispatch-deadline/verify-build-reuse.py
# Actual retained outputs; sequential, with ownership-bound nonces
$env:BUYEROS_N00_FLOW_PROFILE='runtime-flow-final'
$env:BUYEROS_N00_TARGET='portable'; $env:BUYEROS_N00_RUN_ID='2314a4a2e7e8'
node node_modules/@playwright/test/cli.js test --config playwright.neon-runtime-flow.config.ts tests/e2e/audit-neon-runtime-flow.spec.ts
$env:BUYEROS_N00_TARGET='vercel'; $env:BUYEROS_N00_RUN_ID='5d6402f65c01'
node node_modules/@playwright/test/cli.js test --config playwright.neon-runtime-flow.config.ts tests/e2e/audit-neon-runtime-flow.spec.ts
# Read-only, cwd services/api
.venv/Scripts/python.exe -m alembic heads
git diff --cached --check
git apply --reverse --check test-results/n00-proxy-dispatch-deadline/source.patch
```

Windows/Node24.18.0/Python3.14.6, Chromium1120x800. No timer/budget allowance increased. Native body trickle deadline100ms; TTL-crossing uses a controlled clock after durable admission; physical remainingTTL100ms vs response180ms; positive control verifies bytes/header/one-hop persistence. Existing40ms upstream timeout regressions remain intact. Timing is test-condition evidence, not a production latency benchmark. Retained compiled image was Node22.23.2 bookworm-slim; no Docker build this follow-up.

## Case/findings and remaining limits

NA01/F20 remain partial local diagnostic/rehearsal evidence. The three deadline failures are locally fixed; latest four native cases and both fresh built-output fixture flows pass. All other97 cases/24 audit task objects and legacy31 task objects retain their own evidence.84operation definitions/ledger unchanged.3433prior input/evidence files and three foreign worktrees, including193dirty paths and peerQ13, preserved; original pack unmodified.

Original strict302 callback assertion is unchanged and **not rerun this slice**; its prior failure remains carried/open. Real Neon/Google/Managed Admin cleanup/schema/absence, full native browser/CLI containment/accounting and independent/human review remain OPEN. Do not bypass N01/N02 prerequisites or link by email. F10/F18/F21/fullQ11 and live staff/recovery/provider gates are not closed by this change. Auth0, canonical users.id/memberships/owner/approval/audit/job actor/RLS and independent Cloudflare HMAC retained; delivery403.

Code implemented: local harness only. Fictional fixtures verified: four native HTTP tests and twelve SDK/browser cases. Actual local integration verified: owned HTTP, fsynced journal/restart, pinned SDK/built output/EdDSA diagnostic. External/live/deployed: none; deployedSHA NULL. Independent review: pending, no agents or forged owner approval.

## Rollback and next eligibility

Source reverse-apply applicability exit0; no actual production rollback run. Revert the following metadata commit then `9e1ef78d4ae61429dee0d4b6fd62de9cbfdd7c92`. No DB/business data undo or auth cutover. Existing admitted/unknown journals must remain intact and reconcile; never erase holds to re-enable a retry. Public release additionally needs the unchanged real/integration/owner gates; tests alone do not authorize it.

Next local work: remaining N00 native browser/CLI containment gap audit/preparation. Fresh real-target/Auth/one human Google identity/cleanup requires exact bounded authorization; prior projects/approvals are not reused. No automatic admin grant is proposed. The original real-roundtrip runbook is a historical, unapproved proposal whose target/quota/config/cleanup readbacks need refresh before external execution.
