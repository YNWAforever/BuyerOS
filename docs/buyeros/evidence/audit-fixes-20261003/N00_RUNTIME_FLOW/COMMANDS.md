# Exact commands/environments

Cwd: C:\Users\laich\.codex\worktrees\neon-auth-compatibility-local-20261004\BuyerOS. PowerShell. Fixture child env allowlist removes inherited DB/Auth0/provider config; BUYEROS_STRICT_INTEGRATION=1.

```text
node scripts/neon-compatibility-harness.mjs runtime-flow
node scripts/neon-compatibility-harness.mjs runtime-flow-final
node --test --test-concurrency=1 tests/neon-real-runtime.test.mjs tests/neon-counted-proxy.test.mjs tests/neon-real-preflight.test.mjs tests/neon-compatibility-harness.test.mjs tests/neon-compatibility-discovery.test.mjs tests/neon-runtime-probe.test.mjs tests/neon-runtime-cleanup.test.mjs tests/neon-runtime-flow.test.mjs tests/neon-real-diagnostic.test.mjs tests/api-types-generation.test.mjs tests/audit-auth-render.test.mjs tests/vercel-services.test.mjs
services/api/.venv/Scripts/python.exe -m pytest -q tests/fixtures/neon-runtime-flow/test_verify.py --junitxml=test-results/neon-runtime-flow/crypto-final.xml
node node_modules/typescript/bin/tsc --noEmit
node scripts/generate-api-types.mjs --check
services/api/.venv/Scripts/python.exe scripts/generate-operation-routes.py --check
services/api/.venv/Scripts/python.exe -m alembic heads # cwd services/api
node node_modules/@playwright/test/cli.js test --config playwright.neon-runtime-flow.config.ts
```

Build env seed buyeros-audit-ui-deps-052d6a686de9/owner052d6a686de9; frozen install and actual build commands in build-runtime.json captures. Final UI env BUYEROS_N00_TARGET=vercel/portable, BUYEROS_N00_FLOW_PROFILE=runtime-flow-final, BUYEROS_N00_RUN_ID=5105aabbccdd/6105aabbccdd. Runtime target/secrets generated after build; no real target/account. Exact lint args/status/durations in source-final-checks.json; all RED/failed and GREEN captures indexed. Serial CLI0; parallel CLI1 retained. No SLA/live-fixture claim.
