import {defineConfig} from '@playwright/test';
/** Browser-only fixture issuer/API interception. No auth bypass or fixture auth is shipped by the app. */
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'live-auth-scope.spec.ts',
  use: {baseURL: 'http://localhost:5173', browserName: 'chromium'},
  webServer: [{
    command: 'pnpm dev', url: 'http://localhost:5173', timeout: 300_000, reuseExistingServer: process.env.BUYEROS_REUSE_TEST_SERVER === '1',
    env: {
      BUYEROS_API_BASE_URL: 'https://api.buyeros.test',
      BUYEROS_AUTH0_ISSUER: 'https://oidc.buyeros.test/',
      BUYEROS_AUTH0_CLIENT_ID: 'fixture-public-client',
      BUYEROS_AUTH0_AUDIENCE: 'fixture-api',
    },
  }],
});
