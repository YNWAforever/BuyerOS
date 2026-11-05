import {defineConfig} from '@playwright/test';
const evidence=process.env.SALES_TEST_EVIDENCE_DIR ?? '.superpowers/sdd/2026-11-05-guided-sales-skills-xverum/task-13-fix1-evidence';
export default defineConfig({testDir:'tests/e2e',testMatch:'sales-skills.spec.ts',workers:1,timeout:30000,use:{baseURL:'http://127.0.0.1:4397',headless:true},webServer:{command:'node tests/sales-skills-browser-server.mjs',url:'http://127.0.0.1:4397/fixture',reuseExistingServer:false},reporter:[['list'],['json',{outputFile:`${evidence}/browser-results-${Date.now()}.json`}]],outputDir:`${evidence}/browser-artifacts/${Date.now()}`});

