import { readFileSync } from 'node:fs';
import { cloudflareTest } from '@cloudflare/vitest-plugin';
import { defineConfig } from 'vitest/config';
import { z } from 'zod';

const fixture = z.object({
  origin: z.string().url(), job: z.object({
    v: z.literal(1), workspace_id: z.string().uuid(), outbox_id: z.string().uuid(),
    generation: z.number().int().positive(), runtime_epoch: z.number().int().positive(),
  }).strict(),
}).strict().parse(JSON.parse(readFileSync(process.env.BUYEROS_CF_TEST_CONTEXT ?? '', 'utf8')));
const origin = new URL(fixture.origin);
if (origin.protocol !== 'http:' || origin.hostname !== '127.0.0.1' || origin.pathname !== '/' || origin.username || origin.password || origin.search || origin.hash) {
  throw new Error('owned local API fixture must be an exact loopback origin');
}
// Fixed fictional machine key. No database or operator credentials enter Workers.
process.env.WORKER_CURRENT_SECRET = 'fictional-cf05-secret-32-bytes-only';
export default defineConfig({
  plugins: [cloudflareTest({
    wrangler: { configPath: 'services/cloudflare-jobs/wrangler.jsonc' },
    miniflare: { bindings: {
      EXECUTION_ENABLED: 'true', LOCAL_TEST_MODE: 'true',
      RUNTIME_EPOCH: String(fixture.job.runtime_epoch), WORKER_API_ORIGIN: fixture.origin,
      WORKER_API_ALLOWED_ORIGINS: JSON.stringify([fixture.origin]), WORKER_CURRENT_KEY_ID: 'fictional-key',
      WORKER_CURRENT_SECRET: 'fictional-cf05-secret-32-bytes-only',
      CF_TEST_JOB: JSON.stringify(fixture.job),
    } },
  })],
  test: { include: ['services/cloudflare-jobs/tests/platform-pg.integration.ts'], testTimeout: 60_000 },
});
