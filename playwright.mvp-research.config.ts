import {defineConfig} from '@playwright/test';

const reuse=process.env.BUYEROS_REUSE_TEST_SERVER==='1';
export default defineConfig({
  globalTeardown:'./tests/e2e/teardown.ts',
  testDir:'./tests/e2e',testMatch:'mvp-a-research.spec.ts',workers:1,
  use:{baseURL:'http://localhost:5173',browserName:'chromium',viewport:{width:1280,height:800}},
  webServer:[
    {command:'uv run --frozen python tools/serve_e2e_fixture.py',cwd:'services/api',
      url:'http://127.0.0.1:8000/health/live',timeout:600_000,reuseExistingServer:reuse,
      env:{BUYEROS_STRICT_INTEGRATION:'1',BUYEROS_E2E_SEED_RUNS:'1',BUYEROS_E2E_SEED_T30_DRAFT:'1',
        BUYEROS_CORS_ORIGINS:'["http://localhost:5173"]'}},
    {command:process.env.BUYEROS_E2E_FRONTEND==='vercel-built'?'node scripts/serve-built-ui-fixture.mjs':'pnpm dev',url:'http://localhost:5173',timeout:600_000,reuseExistingServer:reuse,
      env:{BUYEROS_API_BASE_URL:'http://127.0.0.1:8000',
        BUYEROS_AUTH0_ISSUER:'https://oidc.buyeros.test/',
        BUYEROS_AUTH0_CLIENT_ID:'fixture-public-client',BUYEROS_AUTH0_AUDIENCE:'fixture-api'}},
  ],
});
