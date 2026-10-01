import {defineConfig} from '@playwright/test';

if (process.env.BUYEROS_TEST_DATABASE_URL || process.env.BUYEROS_REUSE_TEST_SERVER === '1') {
  throw new Error('Cloudflare acceptance owns a fresh local stack; inherited DB/server targets are forbidden');
}
export default defineConfig({
  testDir:'./tests/e2e', testMatch:'cloudflare-journey.spec.ts', workers:1,
  globalTeardown:'./tests/e2e/fixtures/cloudflare-teardown.ts',
  outputDir:'test-results/cloudflare',
  use:{baseURL:'http://localhost:5173',browserName:'chromium',viewport:{width:1280,height:800}},
  webServer:[
    {command:'uv run --frozen python tools/serve_cloudflare_e2e.py',cwd:'services/api',
      url:'http://127.0.0.1:8000/health/live',timeout:600_000,reuseExistingServer:false,
      env:{BUYEROS_STRICT_INTEGRATION:'1',BUYEROS_E2E_SEED_RUNS:'1',BUYEROS_E2E_SEED_T30_DRAFT:'1',BUYEROS_E2E_SEED_BUYERS:'1',BUYEROS_E2E_BUYER_COUNT:'101',BUYEROS_E2E_SEED_QUOTES:'1',BUYEROS_E2E_SEED_CONFIRM:'1',
        BUYEROS_CORS_ORIGINS:'["http://localhost:5173"]'}},
    {command:'node scripts/serve-cloudflare-fixture.mjs',url:'http://127.0.0.1:8788/health',
      timeout:600_000,reuseExistingServer:false},
    {command:'node scripts/serve-built-ui-fixture.mjs',url:'http://localhost:5173',timeout:600_000,reuseExistingServer:false,
      env:{BUYEROS_API_BASE_URL:'http://127.0.0.1:8000',BUYEROS_AUTH0_ISSUER:'https://oidc.buyeros.test/',
        BUYEROS_AUTH0_CLIENT_ID:'fixture-public-client',BUYEROS_AUTH0_AUDIENCE:'fixture-api'}},
  ],
});
