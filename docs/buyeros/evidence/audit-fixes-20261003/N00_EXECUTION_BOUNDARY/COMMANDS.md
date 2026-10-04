# Exact commands and environment

Cwd C:/Users/laich/.codex/worktrees/neon-auth-compatibility-local-20261004/BuyerOS. Windows PowerShell; Node24.18.0/Python3.14.6/pinned SDK0.5.0-beta. No new application builds. Browser1120x800 Chromium, workers1/retries0/serviceWorkers blocked; route allowlist only owned random127.0.0.1 origins. Fixed Node fixture helper only,5s bound; no neonctl/real provider CLI credential inherited.

```text
node --test --test-concurrency=1 --test-reporter=tap tests/neon-execution-boundary.test.mjs
node --test --test-concurrency=1 --test-reporter=tap tests/neon-real-runtime.test.mjs tests/neon-counted-proxy.test.mjs tests/neon-real-preflight.test.mjs tests/neon-compatibility-harness.test.mjs tests/neon-compatibility-discovery.test.mjs tests/neon-runtime-probe.test.mjs tests/neon-runtime-cleanup.test.mjs tests/neon-runtime-flow.test.mjs tests/neon-real-diagnostic.test.mjs tests/neon-execution-boundary.test.mjs tests/api-types-generation.test.mjs tests/audit-auth-render.test.mjs tests/vercel-services.test.mjs
$cases=@(rg --files tests -g '*.test.mjs' | Sort-Object)
node --test --test-concurrency=1 --test-reporter=tap @cases
node node_modules/@playwright/test/cli.js test --config playwright.neon-execution.config.ts
services/api/.venv/Scripts/python.exe -m pytest -q tests/fixtures/neon-runtime-flow/test_verify.py --junitxml=test-results/neon-execution/crypto.xml
node node_modules/typescript/bin/tsc --noEmit
node scripts/generate-api-types.mjs --check
services/api/.venv/Scripts/python.exe scripts/generate-operation-routes.py --check
./.venv/Scripts/python.exe -m alembic heads # cwd services/api, read-only
```

Scoped ESLint --max-warnings=0 covers the ten paths in SOURCE_HASHES.json; final reporter checked separately. Full30-file suite list/raw TAP captured; exact five failures recorded. No DB suite applies to this protocol/owned-model slice; zero DB connections/skips. One existing Python deprecation warning and Playwright NO_COLOR/FORCE_COLOR warnings retained. Durations are Windows fixture conditions, not performance/SLA acceptance.
