import {neonFixtureEnvironment} from './tests/e2e/fixtures/neon-fixture-protocol.mjs';
import {defineConfig} from '@playwright/test';
/** Real browser CORS against a disposable PostgreSQL API with a fake principal. */
const reuse = process.env.BUYEROS_REUSE_TEST_SERVER === '1';
export default defineConfig({
  globalTeardown:'./tests/e2e/teardown.ts',
  testDir:'./tests/e2e', testMatch:'live-cors-errors.spec.ts',
  use:{baseURL:'http://localhost:5173',browserName:'chromium'},
  webServer:[
    {command:'uv run --frozen python tools/serve_e2e_fixture.py',cwd:'services/api',url:'http://127.0.0.1:8000/health/live',timeout:600_000,reuseExistingServer:reuse,
      env:{BUYEROS_STRICT_INTEGRATION:'1',BUYEROS_CORS_ORIGINS:'["http://localhost:5173"]'}},
    {command:'node scripts/run-vercel.mjs dev --host 127.0.0.1 --port 5173',url:'http://localhost:5173',timeout:600_000,reuseExistingServer:reuse,
      env:{...neonFixtureEnvironment,BUYEROS_API_BASE_URL:'http://127.0.0.1:8000',}},
  ],
});
