# Exact commands / environment

Cwd C:/Users/laich/.codex/worktrees/neon-auth-compatibility-local-20261004/BuyerOS. Windows PowerShell, Node24.18.0, Playwright1.63.0, pinned SDK0.5.0-beta. Each shell result was collected and read; logs are byte-exact captures. Helpers required scoped local sandbox escalation after a deny-read ACL helper setup error, not an application error or external mutation approval.

~~~powershell
# Meaningful runtime RED (including improved missing-manifest assertion before implementation)
node --test tests/neon-real-runtime.test.mjs
# red.log29fail; red-verified.log29fail; red-final.log30fail,0pass0skip.
# green-attempt1.log30pass0fail0skip,800.5488ms.

node --test tests/neon-real-runtime.test.mjs tests/neon-counted-proxy.test.mjs tests/neon-real-preflight.test.mjs tests/neon-compatibility-harness.test.mjs tests/neon-compatibility-discovery.test.mjs tests/api-types-generation.test.mjs tests/audit-auth-render.test.mjs tests/vercel-services.test.mjs
# related-node.log110pass12976.1572ms; related-node-final.log110pass13491.6775ms;0fail/skip/cancelled/todo;exit0.

& node_modules/.bin/tsc.cmd --noEmit
# types-red.log: TS2578/exit2 (any SDK return); types-green.log and types-final.log: exit0.

& node_modules/.bin/eslint.cmd scripts/neon-real-preflight.mjs scripts/neon-real-target.mjs scripts/neon-real-runtime.mjs scripts/neon-real-runtime.d.mts scripts/serve-neon-compatibility.mjs scripts/neon-counted-teardown.mjs tests/neon-real-runtime.test.mjs tests/neon-real-runtime.types.ts tests/fixtures/neon-real-runtime/overlay/lib/neon-real-runtime/server.ts 'tests/fixtures/neon-real-runtime/overlay/app/api/auth/[...path]/route.ts' tests/fixtures/neon-real-runtime/overlay/proxy.ts playwright.neon-runtime-regression.config.ts --max-warnings 0
# lint-final.log exit0, no warnings. Initial lint.log omitted unchanged runner/teardown before their later repair; also exit0.

$env:BUYEROS_N00_TARGET='portable'
$env:BUYEROS_N00_RUN_ID='7f2d941e8c63'
& node_modules/.bin/playwright.cmd test --config playwright.neon-runtime-regression.config.ts tests/e2e/audit-neon-compat.spec.ts
# First original cleanup logic: portable-ui.log/xml;6pass1fail0skip,76.717208s;globalerror1,exit1.

$env:BUYEROS_N00_RUN_ID='5bdaf49c6e02'
& node_modules/.bin/playwright.cmd test --config playwright.neon-runtime-regression.config.ts tests/e2e/audit-neon-compat.spec.ts
# Poll-only correction still fails5s native bound: portable-ui-attempt2.log;6pass1fail0skip,53.492132s;globalerror1,exit1.

$env:BUYEROS_N00_RUN_ID='e94f786ad235'
& node_modules/.bin/playwright.cmd test --config playwright.neon-runtime-regression.config.ts tests/e2e/audit-neon-compat.spec.ts
# Measured timeout correction: portable-ui-final.log;6pass1fail0skip,55.428903999999996s;globalerror0,exit1.

$env:BUYEROS_N00_TARGET='vercel'
$env:BUYEROS_N00_RUN_ID='c07e49d328af'
& node_modules/.bin/playwright.cmd test --config playwright.neon-runtime-regression.config.ts tests/e2e/audit-neon-compat.spec.ts
# vercel-ui-final.log;6pass1fail0skip,19.568469s;globalerror0,exit1.

node scripts/generate-api-types.mjs --check
# contracts.log: API types match the OpenAPI contract;exit0.
node scripts/neon-real-preflight.mjs check docs/buyeros/runbooks/neon-auth-n00-real-target.template.json
# null-target.log: expected exit1/N00_REAL_TARGET_REQUIRED; not a pass or zero-test acceptance.

# Node spawnSync with fixtureChildEnvironment(process.env), cwd services/api:
services/api/.venv/Scripts/python.exe -m alembic heads
# alembic-heads.log single0037_bulk_manifests(head),exit0; no DB environment/connection/migration.

git diff --cached --check
git commit -m 'test(N00): prepare strict request-time Neon runtime'
git apply --reverse --check --binary test-results/neon-real-runtime/rollback-source.patch
# Source hygiene0; commit790a1b2; reverse applicability0, not applied.
~~~

Actual owned-process timing diagnostics were executed as PowerShell single-quoted here-strings piped to `node --input-type=module -`. Each spawned only fresh owned processes and called `execFile('taskkill',['/PID',String(child.pid),'/T','/F'],...)` concurrently with recorded exact PIDs. `owned-child-diagnostic.json`: one Node timer child; taskkill5s/explicit fixture env,0.6s measured. `owned-built-child-diagnostic.json`: fresh uv diagnostic + actual local Wrangler portable output,25s bound/explicit fixture env,1.5s measured. `owned-sanitized-child-diagnostic.json`: same targets after clearing the parent env with fixtureChildEnvironment,15s native bound/default inherited env,8.5s measured. These are local process diagnostics, not provider checks. Target command arguments match runner uv/wrangler launch; readiness used loopback TCP only. Original decoded native stdout/stderr is retained without reinterpretation.

Recovery used native PowerShell end-to-end: Resolve-Path/System.IO.Path absolute-temp containment checks, exact fixture-owner nonce/PID marker, non-reparse checks, absent recorded PIDs, purely fictional journal IDs and0pending/unknown, Copy-Item each owned file and compare Get-FileHash, then Remove-Item -LiteralPath checked-root -Recurse -Force. Only two failed-attempt roots were deleted; original snapshots/raw failures remain. Get-NetTCPConnection confirmed no44890/44891/44892/44894 listeners. No real resources/accounts/DB/paid changes.

Preservation: SHA256 manifest verification of691prior payloads; prior660N00 payloads compared to committed HEAD bytes; source Git-byte normalization kept separately from raw tested hashes. All89/2214archive members and9fictionaloverlay hashes match actual emitted source/output. Four DB guards/generatedcontract/master/84operation ledger unchanged;24other tasks/97cases/all98original15fields and legacyTregistry preserved. Source/rollback checks use BASE535e12..SOURCE790a1b2. No new build or original UI assertion relaxation. Fresh current source commit does not relabel previous compiled output provenance.

Public documentation reads: Invoke-WebRequest official `.md` endpoints (HTTP200) after tool open400 unsupported markdown content; hashes/URLs only in PUBLIC_DOC_REFERENCES. These are not Neon auth checks. No provider/readback/account/Google call occurred in this local slice.
