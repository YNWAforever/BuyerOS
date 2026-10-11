import {defineConfig} from '@playwright/test';
// Native browser defaults, source module + local timers; no app/live acceptance.
export default defineConfig({
  testDir:'./tests/e2e',testMatch:['job-poller-connectivity.spec.ts'],workers:1,timeout:30_000,
  outputDir:'test-results/job-poller',
  reporter:[['list'],['junit',{outputFile:'test-results/job-poller.xml'}]],
  use:{browserName:'chromium',trace:'retain-on-failure'},
});
