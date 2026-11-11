import {defineConfig} from '@playwright/test';

// Real authenticated conversation-studio QA against a deployed branch preview.
// No webServer and no request mocks: identity and data come from the QA workspace.
export default defineConfig({
  testDir:'./tests/e2e',
  testMatch:'conversation-real-qa.spec.ts',
  fullyParallel:false,
  workers:1,
  retries:0,
  timeout:120_000,
  expect:{timeout:15_000},
  outputDir:'artifacts/conversation-qa/artifacts',
  reporter:[
    ['list'],
    ['junit',{outputFile:'artifacts/conversation-qa/results.xml'}],
  ],
  use:{
    browserName:'chromium',
    headless:true,
    baseURL:process.env.BUYEROS_QA_ORIGIN,
    trace:'retain-on-failure',
    screenshot:'only-on-failure',
    video:'off',
  },
});
