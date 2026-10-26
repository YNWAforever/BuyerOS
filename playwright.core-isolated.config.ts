import {neonFixtureEnvironment} from './tests/e2e/fixtures/neon-fixture-protocol.mjs';
import {defineConfig} from '@playwright/test';

const reuse=process.env.BUYEROS_REUSE_TEST_SERVER==='1';
const ownedTarget=Boolean(process.env.BUYEROS_POLICY_TARGET_RECEIPT&&process.env.BUYEROS_TEST_DATABASE_URL);
export default defineConfig({
  globalSetup:'./tests/e2e/core-isolated-setup.ts',
  // The owned runner proves and removes its container. Direct Playwright still
  // uses the shared teardown so an interrupted fixture cannot be adopted later.
  ...(ownedTarget?{}:{globalTeardown:'./tests/e2e/teardown.ts'}),
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
    {command:'node scripts/run-vercel.mjs dev --host 127.0.0.1 --port 5173',url:'http://localhost:5173',timeout:300_000,reuseExistingServer:reuse,
      env:{...neonFixtureEnvironment,BUYEROS_API_BASE_URL:'http://127.0.0.1:8000',}},
  ],
});
