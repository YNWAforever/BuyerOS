import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir: './tests/e2e', testMatch: 'marketing-intake.spec.ts', workers: 1, retries: 0, timeout: 60_000,
  reporter: [['list'], ['json', {outputFile: 'outputs/marketing-full/browser-intake.json'}]],
  outputDir: 'outputs/marketing-full/intake-browser-results',
  use: {baseURL: 'http://127.0.0.1:5195', browserName: 'chromium',
    launchOptions: process.env.MARKETING_CHROMIUM ? {executablePath: process.env.MARKETING_CHROMIUM, args: ['--no-sandbox']} : {}, trace: 'retain-on-failure'},
  webServer: {command: 'node tests/e2e/fixtures/marketing-local-app.mjs', url: 'http://127.0.0.1:5195/en/demo', reuseExistingServer: false,
    timeout: 120_000, env: {XDG_CONFIG_HOME: '/workspace/BuyerOS/.sites-runtime/xdg', MARKETING_FIXTURE_CONFIG: process.env.MARKETING_FIXTURE_CONFIG ?? '', MARKETING_FIXTURE_RUNTIME: process.env.MARKETING_FIXTURE_RUNTIME ?? 'dev'}},
});
