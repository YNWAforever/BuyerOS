import {defineConfig} from '@playwright/test';
import {fileURLToPath} from 'node:url';

const runtime = process.env.MARKETING_TEST_RUNTIME ?? 'dev';
const commands: Record<string, string> = {
  dev: 'node scripts/run-vercel.mjs dev --host 127.0.0.1 --port 5195',
  built: 'node tests/e2e/fixtures/marketing-site-built-server.mjs',
};
if (!commands[runtime]) throw new Error('Unknown marketing site test runtime');
export default defineConfig({
  testDir: './tests/e2e', testMatch: 'marketing-site.spec.ts', workers: 1, retries: 0,
  timeout: 120_000,
  reporter: [['list'], ['json', {outputFile: 'outputs/marketing-full/browser-results.json'}]],
  outputDir: 'outputs/marketing-full/test-results',
  use: {baseURL: 'http://127.0.0.1:5195', browserName: 'chromium',
    launchOptions: process.env.MARKETING_CHROMIUM ? {executablePath: process.env.MARKETING_CHROMIUM, args: ['--no-sandbox']} : {},
    trace: 'retain-on-failure'},
  webServer: process.env.MARKETING_EXTERNAL_SERVER === '1' ? undefined : {
    command: commands[runtime], url: 'http://127.0.0.1:5195/app', reuseExistingServer: false, timeout: 120_000,
    env: {XDG_CONFIG_HOME: fileURLToPath(new URL('./.sites-runtime/xdg', import.meta.url)),
      BUYEROS_API_BASE_URL: '/', BUYEROS_INTERNAL_API_URL: '', BUYEROS_AUTH_PROVIDER: 'auth0', BUYEROS_NEON_AUTH_ROUTE_ENABLED: '0',
      BUYEROS_AUTH0_ISSUER: 'https://oidc.marketing-spike.test/', BUYEROS_AUTH0_CLIENT_ID: 'synthetic-public-client', BUYEROS_AUTH0_AUDIENCE: 'synthetic-api',
      MARKETING_ENABLED: '0', MARKETING_SYNTHETIC_MODE: '0', MARKETING_SITE_URL: 'http://127.0.0.1:5195'},
  },
});
