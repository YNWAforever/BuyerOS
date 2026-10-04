# Exact commands / environment

Cwd C:/Users/laich/.codex/worktrees/neon-auth-compatibility-local-20261004/BuyerOS. Scoped local escalations were required by sandbox ACL setup/worktree placement; no external activation approval was reused.

~~~powershell
node --test tests/neon-runtime-probe.test.mjs
# unit-red:10tests1pass9fail0skip; unit-green plus original harness:32pass.
node --test tests/neon-runtime-cleanup.test.mjs
# cleanup-unit-red6fail0skip; cleanup-unit-green6pass0skip.

$env:BUYEROS_N00_SEED_VOLUME='buyeros-audit-ui-deps-052d6a686de9'
$env:BUYEROS_N00_SEED_OWNER='052d6a686de9'
node scripts/neon-compatibility-harness.mjs runtime-probe
node scripts/neon-compatibility-harness.mjs runtime-probe-retry
node scripts/neon-compatibility-harness.mjs runtime-probe-dispatcher
# Each profile: corepack pnpm build; node scripts/run-vercel.mjs build.
# All6 actual commands exit0, separate clean outputs/archives/logs. <=300s each.

$env:BUYEROS_N00_TARGET='vercel'
$env:BUYEROS_N00_PROBE_BASELINE='yes'
$env:BUYEROS_N00_RUN_ID='0c2d4e6f8012'
node node_modules/@playwright/test/cli.js test --config playwright.neon-runtime-built.config.ts
# Meaningful old-outputRED3fail0skip. Baseline flag absent for all later invocations.
# The same command with env below selects actual new emitted outputs, not Vite dev.
~~~

|Target|Scenario|Nonce|Cases|CLI exit|Global errors|
|---|---|---|---:|---:|---:|
|portable|valid|7c2d4e6f8012|3|0|0|
|vercel|valid|8c2d4e6f8012|3|0|0|
|portable|missing|9c2d4e6f8012|1|0|0|
|portable|mismatch|ac2d4e6f8012|1|0|0|
|portable|expired|bc2d4e6f8012|1|0|0|
|vercel|missing|cc2d4e6f8012|1|0|0|
|vercel|mismatch|dc2d4e6f8012|1|0|0|
|vercel|expired|ec2d4e6f8012|1|0|0|

For each row set BUYEROS_N00_TARGET, BUYEROS_N00_PROBE_SCENARIO and BUYEROS_N00_RUN_ID, then run the identical Playwright command. No test skipped or expected-fail. Run portable valid7c first; sequential loop: Vercel valid8c, portable missing9c/mismatchac/expiredbc, Vercel missingcc/mismatchdc/expiredec. Each exact report/log/response attachment and owner marker is mapped in CAPTURE_MAP.

Earlier attempts retained: vercelvalid1c/2c startup errors (0 executed cases; not passing), vercelvalid3c3pass/exit0, portablevalid4c/6c each3pass/globalerror1/exit1, portablemissing5c1pass/exit0. First two profiles' dispatcher500, bare-reexport trial, EPERM syscall, manual/native cleanup and read-only Restart Manager0locks are separate facts. Final code preserves owner through transient retries; portable7c reports actualEBUSY then success. Native cleanup15s/stop18s/root10s/global35s. No broad temp/process cleanup.

~~~powershell
node --test tests/neon-real-runtime.test.mjs tests/neon-counted-proxy.test.mjs tests/neon-real-preflight.test.mjs tests/neon-compatibility-harness.test.mjs tests/neon-compatibility-discovery.test.mjs tests/neon-runtime-probe.test.mjs tests/neon-runtime-cleanup.test.mjs tests/api-types-generation.test.mjs tests/audit-auth-render.test.mjs tests/vercel-services.test.mjs
# related-node-with-cleanup:126pass0fail0skip0cancelled0todo;12046.3406ms,exit0.
node node_modules/typescript/bin/tsc --noEmit
# types-acceptance.log exit0; initial types-final.logTS2554/exit2 retained, randomUUID fixes local config typing.
node node_modules/eslint/bin/eslint.js scripts/neon-compatibility-harness.mjs scripts/neon-runtime-cleanup.mjs scripts/neon-runtime-probe.mjs scripts/neon-runtime-probe.d.mts scripts/serve-neon-runtime-probe.mjs scripts/neon-runtime-node-bridge.mjs scripts/neon-runtime-probe-teardown.mjs tests/neon-runtime-probe.test.mjs tests/neon-runtime-cleanup.test.mjs tests/fixtures/neon-runtime-probe tests/fixtures/neon-real-runtime/overlay/app/api/n00-runtime/route.ts tests/e2e/audit-neon-runtime-built.spec.ts playwright.neon-runtime-built.config.ts --max-warnings=0
# lint-acceptance exit0,zero warnings.
node scripts/generate-api-types.mjs --check
# contracts exit0/API types match OpenAPI.
# Node spawnSync absolute services/api/.venv/Scripts/python.exe, cwd services/api,
# fixtureChildEnvironment allowlist, args -m alembic heads:
# alembic-heads-green single0037_bulk_manifests,exit0; no DB env/connection.
# First relative executable-path attempt ENOENT/null exit is retained, not passing.
git ls-remote origin refs/heads/main
# a78859fe474f5722be3755b10e2586436b53bf97,read-only.
git diff --cached --check
git commit -m 'test(N00): verify runtime-only SDK kernel on built outputs'
git apply --reverse --check --binary test-results/neon-runtime-built/rollback-source.patch
# source hygiene0; sourcee683a89; reversecheck0only,not applied.
~~~

Preservation Python compares943prior payload SHA256 and all old/new archive regular members against emitted files. On Windows extended paths are required for a266-character file; initial FileNotFoundError retained, no member excluded. Failed roots are recovered only after native absolute containment/non-reparse/exact owner record/recorded process and port absence checks; private configuration is never exported. Later PID-only bookkeeping detects a recycled childPID; identity is compared against ownership/cleanup time, never killed. All14owned roots removed. Eight current CLI exits0 and every report nonzero-test; secret hashes only, globalfetch forwarded0, no external auth request.
