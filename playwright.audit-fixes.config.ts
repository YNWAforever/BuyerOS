import {defineConfig} from '@playwright/test';
// Owned loopback HTTP/Postgres fixture; never reuse a running/shared/live server.
export default defineConfig({
  globalTeardown:'./tests/e2e/audit-teardown.ts',
  testDir:'./tests/e2e',testMatch:'audit-*.spec.ts',
  // N00 runs actual built outputs with separate loopback ports and no workbench DB.
  testIgnore:'audit-neon-*.spec.ts',workers:1,timeout:60_000,
  outputDir:'test-results/audit-fixes',
  reporter:[['list'],['junit',{outputFile:'test-results/audit-fixes.xml'}]],
  use:{baseURL:'http://localhost:5173',browserName:'chromium',viewport:{width:1120,height:800},trace:'retain-on-failure'},
  webServer:[
    {command:'uv run --frozen python tools/serve_e2e_fixture.py',cwd:'services/api',url:'http://127.0.0.1:8000/health/live',timeout:600_000,reuseExistingServer:false,
      env:{BUYEROS_STRICT_INTEGRATION:'1',BUYEROS_E2E_SEED_BUYERS:'1',BUYEROS_E2E_SEED_RUNS:'1',BUYEROS_E2E_SEED_DRAFTS:'1',BUYEROS_CORS_ORIGINS:'["http://localhost:5173"]'}},
    {command:process.platform==='win32'?'node scripts/serve-audit-ui-fixture.mjs':'pnpm dev',url:'http://localhost:5173',timeout:600_000,reuseExistingServer:false,
      env:{BUYEROS_DEPLOY_TARGET:'vercel',BUYEROS_INTERNAL_API_URL:'http://127.0.0.1:8000',BUYEROS_API_BASE_URL:'/',BUYEROS_AUTH0_ISSUER:'https://oidc.buyeros.test/',
        BUYEROS_AUTH0_CLIENT_ID:'fixture-public-client',BUYEROS_AUTH0_AUDIENCE:'fixture-api'}},
  ],
});
