import {neonFixtureEnvironment} from './tests/e2e/fixtures/neon-fixture-protocol.mjs';
import {defineConfig} from '@playwright/test';
/** Browser-only fixture issuer/API interception. No auth bypass or fixture auth is shipped by the app. */
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'live-auth-scope.spec.ts',
  use: {baseURL: 'http://localhost:5173', browserName: 'chromium'},
  webServer: [{
    command: 'node scripts/run-vercel.mjs dev --host 127.0.0.1 --port 5173', url: 'http://localhost:5173', timeout: 300_000, reuseExistingServer: process.env.BUYEROS_REUSE_TEST_SERVER === '1',
    env: {
      ...neonFixtureEnvironment,BUYEROS_API_BASE_URL: 'https://api.buyeros.test',
      },
  }],
});
