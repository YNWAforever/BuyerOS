import {defineConfig} from '@playwright/test';

// Vercel deployment protection: preview deployments answer 401 unless the caller
// presents the project's automation bypass token. Set BUYEROS_QA_PROTECTION_BYPASS
// (Vercel Project Settings → Deployment Protection → Protection Bypass for
// Automation) to test a protected preview; leave it unset for an unprotected alias.
const protectionBypass=process.env.BUYEROS_QA_PROTECTION_BYPASS?.trim();

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
    // `x-vercel-set-bypass-cookie` makes the browser carry the bypass across the
    // navigation and the sign-in redirects, so no token is echoed into the app.
    ...(protectionBypass
      ?{extraHTTPHeaders:{'x-vercel-protection-bypass':protectionBypass,
          'x-vercel-set-bypass-cookie':'true'}}
      :{}),
  },
});
