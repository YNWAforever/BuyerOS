import { readFileSync } from 'node:fs';
import { cloudflareTest } from '@cloudflare/vitest-plugin';
import { defineConfig } from 'vitest/config';
import { z } from 'zod';

const fixture = z.object({
  origin: z.string().url(), jobs: z.array(z.object({
    v: z.literal(1), workspace_id: z.string().uuid(), outbox_id: z.string().uuid(),
    generation: z.number().int().positive(), runtime_epoch: z.number().int().positive(),
  }).strict()).length(10),
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
      RUNTIME_EPOCH: String(fixture.jobs[0].runtime_epoch), WORKER_API_ORIGIN: fixture.origin,
      WORKER_API_ALLOWED_ORIGINS: JSON.stringify([fixture.origin]), WORKER_CURRENT_KEY_ID: 'fictional-key',
      WORKER_CURRENT_SECRET: 'fictional-cf05-secret-32-bytes-only',
      CF_TEST_JOBS: JSON.stringify(fixture.jobs),
    } },
  })],
  test: { include: ['services/cloudflare-jobs/tests/operating.integration.ts'], testTimeout: 150_000 },
});
