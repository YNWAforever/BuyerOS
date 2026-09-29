import { defineConfig } from '@playwright/test';

const externalBaseURL = process.env.BUYEROS_RESPONSIVE_BASE_URL;

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'responsive-accessibility.spec.ts',
  use: { baseURL: externalBaseURL ?? 'http://localhost:5173', browserName: 'chromium' },
  webServer: externalBaseURL ? undefined : {
    command: 'pnpm dev',
    url: 'http://localhost:5173',
    env: { BUYEROS_API_BASE_URL: '' },
    timeout: 600_000,
    reuseExistingServer: process.env.BUYEROS_REUSE_TEST_SERVER === '1',
  },
});
