import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  globalTeardown: './tests/e2e/teardown.ts',
  use: {
    baseURL: 'http://localhost:5173',
    browserName: 'chromium',
  },
  webServer: [
    {
      command: 'uv run --frozen python tools/serve_e2e_fixture.py',
      cwd: 'services/api',
      url: 'http://127.0.0.1:8000/health/live',
      env: { BUYEROS_STRICT_INTEGRATION: '1' },
      timeout: 300_000,
      reuseExistingServer: false,
    },
    {
      command: 'pnpm dev',
      url: 'http://localhost:5173',
      env: { BUYEROS_API_BASE_URL: '' },
      timeout: 300_000,
      reuseExistingServer: false,
    },
  ],
});
