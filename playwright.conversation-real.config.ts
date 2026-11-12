import {defineConfig} from '@playwright/test';

// Vercel deployment protection: the optional BUYEROS_QA_PROTECTION_BYPASS token
// is exchanged for the bypass cookie once by tests/e2e/qa-protection.fixture.ts.
// It is deliberately NOT configured as a context-wide header: that would attach
// the token to every browser request, including cross-origin redirects/assets.
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
