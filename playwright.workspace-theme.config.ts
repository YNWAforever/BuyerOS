import {defineConfig} from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'workspace-theme.spec.ts',
  workers: 1,
  retries: 0,
  timeout: 120_000,
  outputDir: 'test-results/workspace-theme',
  reporter: [['list'], ['json', {outputFile: 'test-results/workspace-theme.json'}]],
  use: {
    baseURL: 'http://127.0.0.1:5197',
    browserName: 'chromium',
    launchOptions: process.env.WORKSPACE_CHROMIUM ? {executablePath: process.env.WORKSPACE_CHROMIUM} : {},
    trace: 'retain-on-failure',
  },
  webServer: process.env.WORKSPACE_EXTERNAL_SERVER === '1' ? undefined : {
    command: 'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5197',
    url: 'http://127.0.0.1:5197/app',
    reuseExistingServer: false,
    timeout: 120_000,
    env: {BUYEROS_API_BASE_URL: '', BUYEROS_INTERNAL_API_URL: '', BUYEROS_AUTH_PROVIDER: 'auth0',
      BUYEROS_NEON_AUTH_ROUTE_ENABLED: '0', WRANGLER_SEND_METRICS: 'false', CLOUDFLARE_CF_FETCH_ENABLED: 'false'},
  },
});
