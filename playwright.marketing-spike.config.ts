import {defineConfig} from '@playwright/test';
import {fileURLToPath} from 'node:url';

// Dedicated local runtime: no database, real identity or provider configuration.
const port = 5193;
const runtime = process.env.MARKETING_SPIKE_RUNTIME ?? 'dev';
const commands: Record<string, string> = {
  dev: `node node_modules/vite/bin/vite.js --host 127.0.0.1 --port ${port}`,
  'vercel-dev': `node scripts/run-vercel.mjs dev --host 127.0.0.1 --port ${port}`,
  'cloudflare-built': `node --import ./scripts/sites-env.mjs ./node_modules/wrangler/bin/wrangler.js dev --config dist/server/wrangler.json --local --persist-to .wrangler/state --ip 127.0.0.1 --inspector-port 0 --port ${port}`,
  'vercel-built': 'node tests/e2e/fixtures/marketing-spike-built-server.mjs',
};
if (!commands[runtime]) throw new Error('Unknown marketing spike runtime');
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'marketing-layout-spike.spec.ts',
  workers: 1,
  retries: 0,
  reporter: [['list'], ['json', {outputFile: 'outputs/marketing-spike/browser-results.json'}]],
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    browserName: 'chromium',
    launchOptions: process.env.MARKETING_SPIKE_CHROMIUM ? {executablePath: process.env.MARKETING_SPIKE_CHROMIUM, args: ['--no-sandbox']} : {},
    trace: 'retain-on-failure',
  },
  webServer: process.env.MARKETING_SPIKE_EXTERNAL_SERVER === '1' ? undefined : {
    command: commands[runtime],
    url: `http://127.0.0.1:${port}/app`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      XDG_CONFIG_HOME: fileURLToPath(new URL('./.sites-runtime/xdg', import.meta.url)),
      BUYEROS_API_BASE_URL: '/', BUYEROS_INTERNAL_API_URL: '',
      BUYEROS_AUTH_PROVIDER: 'auth0', BUYEROS_NEON_AUTH_ROUTE_ENABLED: '0',
      BUYEROS_AUTH0_ISSUER: 'https://oidc.marketing-spike.test/',
      BUYEROS_AUTH0_CLIENT_ID: 'synthetic-public-client',
      BUYEROS_AUTH0_AUDIENCE: 'synthetic-api',
    },
  },
});
