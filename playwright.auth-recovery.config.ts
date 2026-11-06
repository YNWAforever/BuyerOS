import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests/e2e',testMatch:'auth-recovery.spec.ts',workers:1,timeout:30_000,
 outputDir:'test-results/auth-recovery',reporter:[['list'],['junit',{outputFile:'test-results/auth-recovery.xml'}]],
 use:{baseURL:'https://c61-session.example.test',browserName:'chromium',viewport:{width:1120,height:800}},
 webServer:{command:'node tests/e2e/fixtures/neon-built-server.mjs',url:'http://127.0.0.1:5189/__owned_health',timeout:30_000,reuseExistingServer:false},
});
