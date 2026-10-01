import { cloudflareTest } from '@cloudflare/vitest-plugin';
import { defineConfig } from 'vitest/config';

// Explicit local fixture key; never inherit an operator's machine credential.
process.env.WORKER_CURRENT_SECRET = 'fictional-cf05-secret-32-bytes-only';

export default defineConfig({
  plugins: [cloudflareTest({
    wrangler: { configPath: 'services/cloudflare-jobs/wrangler.jsonc' },
    miniflare: { bindings: {
      EXECUTION_ENABLED: 'true', WORKER_API_ORIGIN: 'https://fixture.invalid',
      WORKER_API_ALLOWED_ORIGINS: '["https://fixture.invalid"]', WORKER_CURRENT_KEY_ID: 'fictional-key',
      WORKER_CURRENT_SECRET: 'fictional-cf05-secret-32-bytes-only',
    } },
  })],
  test: {
    setupFiles: ['services/cloudflare-jobs/tests/setup.ts'],
    include: ['services/cloudflare-jobs/tests/**/*.test.ts'],
    testTimeout: 30_000,
  },
});
