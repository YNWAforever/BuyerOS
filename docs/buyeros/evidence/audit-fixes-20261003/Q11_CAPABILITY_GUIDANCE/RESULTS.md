# Q11 capability responsibility and next-action guidance — local checkpoint

Reviewed source `5aaf6492ec10078e4f1a4fa5b17efd41c5673eba`, parent `f53ebec2a02a354edf6a8a858c4ca2e10f7f5fca`, branch `codex/q11-capability-guidance`, checked `2026-10-05T06:46:36.763406+00:00`. Author review only; independent review pending. **Full Q11/F10/F13/N00 remain OPEN. Not deployed.** Existing evidence and original pack remain unchanged.

## Changes and ownership

- Generated Capability now requires bounded `owner_role` (1–80) and `next_action` (1–512). These are operational responsibility and read-only guidance, with no membership role, access grant, named contact or activation authorization.
- Existing API returns Release owner and provider verification next step; mailbox/CRM advise keeping delivery disabled and using authorized export/manual outcomes. All existing capabilities stay unconfigured/disabled and billable false. No provider, auth, role or economic change; delivery403 retained.
- UI uses generated Capability/Readiness and typed operations, renders status/reason/check time/responsible role/action in en/zh-HK, admin-only readiness with SRE responsibility, technical codes under details, GET-only refresh. Captured actor/generation rejects stale A→B→A responses and hides the old state during a pending new scope. Malformed/contradictory ready data stays unknown.
- Compiler excludes archival evidence and ignored output directories only. Fresh showConfig includes277 real source/test files, including the new UI test and SDK type assertions. No real test exclusion or assertion/timeout guard weakened.
- Eight changed source/test files are listed in [source review](reports/source-review.json); [source patch](source.patch). One domain API and migration owner retained. No migration; read-only heads returns0037_bulk_manifests. The separate Q13 proposed0038 remains unmerged.

## Red → green, exact counts

| Check | Result | Evidence |
| --- | --- | --- |
| API regression before implementation | 0pass/1fail/0skip; missing owner_role | reports/api-red.log + .xml |
| Actual UI regression before implementation | 0pass/1fail/0skip; expected5 responsible roles, got0 | reports/ui-red.log + .xml |
| Author-review contradiction regression | 0pass/1fail/0skip; Ready despite provider blockers | reports/review-red.log + .xml |
| Required API/tenant/RLS/health | 19pass/0fail/error/skip;9.650s;7 existing deprecations | reports/api-green.log + .xml |
| Related Operations + first4 guidance, intermediate source | 15pass/0fail/error/skip;2.8min | reports/ui-green-first.log + .xml |
| Final5 guidance browser cases | 5pass/0fail/error/skip;55.179936s | reports/ui-final.log + .xml |
| All28 rootMJS suites, final source | 300reported pass,299JUnit leaf cases;0fail/error/skip;67414.0489ms | reports/root-node.log + .xml |
| Genuine normal Vercel build | exit0, frozen install, no Neon overlay | reports/vercel-build.log;build-runtime.json |
| Actual emitted Linux / Windows SSR | 3pass each,0fail/error/skip | reports/vercel-render-*.log + .xml |
| TypeScript / source ESLint | exit0 each | reports/types-final.log;lint-final.log |
| Generated contracts / route inventory | exit0,84=70original+14extensions,0 new ops | reports/contract-types.log;contract-routes.log |

API result covers final backend/contract; neither changed after that19-case run. The final contradiction fix and readiness localization are frontend-only. Intermediate15 and final5 are separate runs, not20 unique or a fresh16-case combined run. Root report counts one nested parent in addition to299 leaf cases.

## Executed commands and isolation

Commands ran from the isolated worktree; API cwd is services/api. Fixture DSNs and auth issuer/audience were unset before API/Playwright; BUYEROS_STRICT_INTEGRATION=1. Existing guard accepts only owned Docker or loopback buyeros_test_* and remained intact. Required DB suites did execute with zero skip. Python/worker frozen dependencies and actual DB-backed HTTP fixture were used; provider interception is labeled fixture evidence.

```powershell
# RED API (one expected missing field)
uv run --frozen pytest -q tests/test_api_health.py::test_capabilities_include_bounded_responsibility_and_next_action --junitxml=../../test-results/q11-capability-guidance/api-red.xml
# GREEN required API
uv run --frozen pytest -q tests/test_api_routes_contract.py tests/test_api_tenant_isolation.py tests/test_api_health.py --junitxml=../../test-results/q11-capability-guidance/api-green.xml
# UI red: -g 'provider responsibility'; review red: -g 'ready label contradicting'
node node_modules/@playwright/test/cli.js test tests/e2e/audit-readiness-guidance.spec.ts -c test-results/q11-capability-guidance/ui.config.ts
# Intermediate dependent run selected audit-operations.spec.ts plus the first4 guidance cases
node node_modules/@playwright/test/cli.js test tests/e2e/audit-operations.spec.ts tests/e2e/audit-readiness-guidance.spec.ts -c test-results/q11-capability-guidance/ui.config.ts
node node_modules/typescript/bin/tsc --noEmit
node node_modules/eslint/bin/eslint.js features/live/operations.tsx features/live/locale.ts tests/e2e/audit-readiness-guidance.spec.ts --max-warnings=0
node scripts/generate-api-types.mjs --write
node scripts/generate-api-types.mjs --check
uv run --frozen --project services/api python scripts/generate-operation-routes.py --check
node test-results/q11-capability-guidance/quarantine-prior-output.mjs
node test-results/q11-capability-guidance/build-linux.mjs
node --test --test-reporter=spec --test-reporter-destination=test-results/q11-capability-guidance/vercel-render-windows.log --test-reporter=junit --test-reporter-destination=test-results/q11-capability-guidance/vercel-render-windows.xml tests/vercel-render.test.mjs
$taskTests=@(Get-ChildItem -LiteralPath tests -Filter '*.test.mjs' -File | Sort-Object Name | ForEach-Object { 'tests/'+$_.Name })
node --test --test-concurrency=1 --test-reporter=spec --test-reporter-destination=test-results/q11-capability-guidance/root-node.log --test-reporter=junit --test-reporter-destination=test-results/q11-capability-guidance/root-node.xml @taskTests
# Read-only, cwd services/api
uv run --frozen alembic heads
git diff --cached --check
git apply --reverse --check test-results/q11-capability-guidance/source.patch
```

The report destinations/configuration are retained. UI teardown wrapper invokes unchanged ownership-guarded original teardown then proves owned DB/frontend absence; two named containers and markers are absent. Docker build validates the read-only seed volume owner, uses Node22.23.2 bookworm-slim,4CPU/6GiB, bounded setup240s/install120s/build180s. Network disconnected before build/SSR; recorded networks=[]; no provider/deployment action. Native Windows host Node24.18.0; Python3.14.6/uv0.11.27. [Runtime](reports/build-runtime.json), [cleanup](reports/build-cleanup.json), [UI cleanup](reports/ui-cleanup.json).

Prior2611-file output was hash-verified and moved inside this worktree to `test-results/q11-capability-guidance/prior-main-output`, preserving it. New genuine output has2611 regular files; exported archive27690146bytes/hash is in build-output.json. GNU hard-dereference exports regular files/directories only; path/type checks precede native extraction. Archives/compiled trees remain ignored rather than committed. All271 build inputs match source5aaf649 content,229 with Git text line-end conversion only. [Input hashes](reports/build-inputs.json), [output hashes](reports/build-output.json), [source match](reports/source-review.json).

First generator call without --write/--check exited2 usage; corrected --write passed. First tsc exited2 because prior archived .ts helpers and ignored scratch configs were swept into compilation; targeted archive-only exclusions fixed this. Exact failures are retained in generate.log/types-first.log. Nothing is counted as pass from0 tests or skip. No newly measured production latency/load/accuracy result; root runtime and build timing are environment evidence only.

## Case / finding / release boundary

| ID | Current disposition |
| --- | --- |
| R05 / F13 | Local current-status and capability responsibility/action subset verified; final5 supplementary tests use R05. Full release/deployed comparison remains partial/open. Other97 tracker rows unchanged. The84-operation ledger retains its denominator, definitions and deployed states; only getCapabilities/getReadiness append these local contract/UI results, other82 rows unchanged. |
| R01/R02/R03/R04/R06 | No fresh production schema/runtime/selector/epoch/outbox/recovery/live evidence; existing state retained. |
| F10 | Still open: no selected live adapter/price/quota/worker/canary verification or provider calls. |
| F20 / NA01 / N00 | Auth0 retained; real Neon/Google/Admin cleanup, original302 and full native accounting/containment plus independent review remain open. |
| F18 / Q10 | No new performance/SQL gate claim; previous failed scaling baseline retained; separate Q13 current-auth implementation unmerged. |
| Q16/Q17 | OperationalError alone still insufficient; no underlying root cause or guessed fix. |

Code implemented; fictional browser fixtures verified; actual local API/PostgreSQL/RLS/build/SSR integration verified. Externally blocked/live recovery/provider/auth/pilot gates are separate. No deployed SHA proven this round. The rest of98 cases/25 tasks and legacy programme retain their own evidence; this does not verify eight modules live.

## Preservation, review and rollback

3200 original artifacts and3370 all prior tracked input/evidence artifacts verified unchanged; three foreign worktrees unchanged including dirty193 paths and separateQ13. New SHA manifest covers this group. Source reverse-apply check passed; no actual production rollback run. Independently review source/contract/scope/error behavior before publication; no agent review or fabricated owner approval.

Revert the following metadata commit, then `5aaf6492ec10078e4f1a4fa5b17efd41c5673eba` as one API/contract/UI/test unit. No DB or business data undo and no auth cutover. New UI against an older API safely shows unavailable due to missing fields; publish coordinated API/UI only after its own authorization. Local build rollback: hash-check owned new output, move it aside inside worktree, then restore the preserved prior output; never delete shared artifacts.

Next local eligibility: N00 remaining local original-redirect/native containment/accounting gap audit; actual Neon/provider/production work still needs its own concrete evidence and authorization. No credential absence blocks another independent local repair. Actual external activation requires an exact reviewable target/configuration/test/cleanup decision; old preview approvals are not reused.
