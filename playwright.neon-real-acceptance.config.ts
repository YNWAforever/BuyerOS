import {defineConfig} from '@playwright/test';
// Separate from synthetic built protocol suites. No webServer or identity routes.
export default defineConfig({
  testDir:'./tests/e2e',testMatch:'neon-real-acceptance.spec.ts',workers:1,retries:0,timeout:60_000,
  outputDir:'artifacts/repair/neon-real-private',
  reporter:[['list'],['junit',{outputFile:'artifacts/repair/neon-real.xml'}]],
  use:{browserName:'chromium',trace:'off',screenshot:'off',video:'off'},
});
