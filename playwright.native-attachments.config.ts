import {defineConfig} from '@playwright/test';
export default defineConfig({
  globalTeardown:'./tests/e2e/teardown.ts',testDir:'./tests/e2e',testMatch:'native-attachments.spec.ts',workers:1,timeout:120_000,
  outputDir:'test-results/native-attachments/browser',
  reporter:[['list'],['junit',{outputFile:'test-results/native-attachments.xml'}]],
  use:{baseURL:'http://localhost:5173',browserName:'chromium',viewport:{width:1120,height:800},trace:'retain-on-failure'},
  webServer:[
    {command:'uv run --frozen python tools/serve_e2e_fixture.py',cwd:'services/api',url:'http://127.0.0.1:8000/health/live',timeout:300_000,reuseExistingServer:false,
      env:{BUYEROS_STRICT_INTEGRATION:'1',BUYEROS_E2E_SEED_BUYERS:'1',BUYEROS_PRIVATE_OBJECT_BACKEND:'postgres',BUYEROS_CLOUDFLARE_EXECUTION_ENABLED:'false',BUYEROS_CORS_ORIGINS:'["http://localhost:5173"]'}},
    {command:process.env.BUYEROS_NATIVE_REUSE_BUILD==='1'?'node scripts/serve-built-ui-fixture.mjs':'node scripts/run-vercel.mjs build && node scripts/serve-built-ui-fixture.mjs',url:'http://localhost:5173',timeout:300_000,reuseExistingServer:false,
      env:{BUYEROS_STRICT_INTEGRATION:'1',BUYEROS_TEST_DATABASE_URL:'',BUYEROS_DATABASE_URL:'',BUYEROS_EXECUTION_DATABASE_URL:'',BUYEROS_RUNTIME_ADMIN_DATABASE_URL:'',DATABASE_URL:'',CLOUDFLARE_API_TOKEN:'',BUYEROS_REUSE_TEST_SERVER:'',
        BUYEROS_API_BASE_URL:'/',BUYEROS_AUTH0_ISSUER:'https://oidc.buyeros.test/',BUYEROS_AUTH0_CLIENT_ID:'fixture-public-client',BUYEROS_AUTH0_AUDIENCE:'fixture-api'}},
  ],
});
