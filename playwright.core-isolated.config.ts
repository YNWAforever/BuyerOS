import {defineConfig} from '@playwright/test';

const reuse=process.env.BUYEROS_REUSE_TEST_SERVER==='1';
if(!process.env.BUYEROS_POLICY_TARGET_RECEIPT||!process.env.BUYEROS_TEST_DATABASE_URL){
  throw new Error('Use services/api/tools/run_core_isolated.py to allocate and verify this run\'s disposable target');
}
export default defineConfig({
  testDir:'./tests/e2e',testMatch:'core-isolated.spec.ts',workers:1,
  outputDir:process.env.BUYEROS_CORE_OUTPUT_DIR||'test-results/core-isolated',
  reporter:[['list'],['junit',{outputFile:process.env.BUYEROS_CORE_JUNIT||'test-results/core-isolated.xml'}]],
  use:{baseURL:'http://localhost:5173',browserName:'chromium',
    launchOptions:process.env.BUYEROS_CORE_CHROMIUM?{executablePath:process.env.BUYEROS_CORE_CHROMIUM}:undefined},
  webServer:[
    {command:'.venv/bin/python tools/serve_e2e_fixture.py',cwd:'services/api',
      url:'http://127.0.0.1:8000/health/live',timeout:300_000,reuseExistingServer:reuse,
      env:{BUYEROS_STRICT_INTEGRATION:'1',BUYEROS_E2E_SEED_RUNS:'1',
        BUYEROS_E2E_SEED_BUYERS:'1',BUYEROS_E2E_SEED_DRAFTS:'1',
        BUYEROS_CORS_ORIGINS:'["http://localhost:5173"]'}},
    {command:'corepack pnpm dev',url:'http://localhost:5173',timeout:300_000,reuseExistingServer:reuse,
      env:{BUYEROS_API_BASE_URL:'http://127.0.0.1:8000',BUYEROS_AUTH0_ISSUER:'https://oidc.buyeros.test/',
        BUYEROS_AUTH0_CLIENT_ID:'fixture-public-client',BUYEROS_AUTH0_AUDIENCE:'fixture-api'}},
  ],
});
