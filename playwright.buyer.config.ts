import {neonFixtureEnvironment} from './tests/e2e/fixtures/neon-fixture-protocol.mjs';
import {defineConfig} from '@playwright/test';
/** T08 real HTTP/browser flow over disposable PostgreSQL and test-only principals. */
const reuse=process.env.BUYEROS_REUSE_TEST_SERVER==='1';
export default defineConfig({
  globalTeardown:'./tests/e2e/teardown.ts',
  testDir:'./tests/e2e',testMatch:['buyer-results.spec.ts','buyer-source-checks.spec.ts'],workers:1,
  use:{baseURL:'http://localhost:5173',browserName:'chromium',viewport:{width:1024,height:800}},
  webServer:[
    {command:'uv run --frozen python tools/serve_e2e_fixture.py',cwd:'services/api',url:'http://127.0.0.1:8000/health/live',timeout:600_000,reuseExistingServer:reuse,
      env:{BUYEROS_STRICT_INTEGRATION:'1',BUYEROS_E2E_SEED_BUYERS:'1',BUYEROS_CORS_ORIGINS:'["http://localhost:5173"]'}},
    {command:process.env.BUYEROS_E2E_FRONTEND==='vercel-built'?'node scripts/serve-built-ui-fixture.mjs':process.env.BUYEROS_E2E_FRONTEND==='next'?'pnpm exec next dev --webpack --hostname 127.0.0.1 --port 5173':'node scripts/run-vercel.mjs dev --host 127.0.0.1 --port 5173',url:'http://localhost:5173',timeout:600_000,reuseExistingServer:reuse,
      env:{...neonFixtureEnvironment,BUYEROS_API_BASE_URL:'http://127.0.0.1:8000',}},
  ],
});
