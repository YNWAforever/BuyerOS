import {defineConfig} from '@playwright/test';
// Real emitted function + unpatched SDK with synthetic loopback protocol only.
// This owns the server; no reused endpoint, credentials, external account or database.
export default defineConfig({testDir:'./tests/e2e',testMatch:['neon-session-production.spec.ts','neon-security-production.spec.ts'],workers:1,timeout:30_000,
 outputDir:'test-results/neon-session',reporter:[['list'],['junit',{outputFile:'test-results/neon-session.xml'}]],
 use:{baseURL:'https://c61-session.example.test',browserName:'chromium',viewport:{width:1120,height:800},trace:'retain-on-failure'},
 webServer:{command:'node tests/e2e/fixtures/neon-built-server.mjs',url:'http://127.0.0.1:5189/__owned_health',timeout:30_000,reuseExistingServer:false},
});
