import {randomUUID} from 'node:crypto';
import {defineConfig} from '@playwright/test';
const target=process.env.BUYEROS_N00_TARGET;
if(!['portable','vercel'].includes(target??''))throw new Error('Choose an actual N00 built target: portable or vercel');
const runId=process.env.BUYEROS_N00_RUN_ID??randomUUID().replaceAll('-', '').slice(0,12);
export default defineConfig({globalTeardown:'./scripts/neon-counted-teardown.mjs',metadata:{n00Target:target,n00RunId:runId},testDir:'./tests/e2e',testMatch:'audit-neon-compat.spec.ts',workers:1,timeout:45_000,
 outputDir:`test-results/neon-compatibility/${target}-ui`,reporter:[['list'],['junit',{outputFile:`test-results/neon-compatibility/${target}-ui.xml`}]],
 use:{baseURL:'http://localhost:44890',browserName:'chromium',viewport:{width:1120,height:800},trace:'retain-on-failure'},
 webServer:{command:'node scripts/serve-neon-compatibility.mjs',url:'http://localhost:44890/',timeout:90_000,reuseExistingServer:false,env:{BUYEROS_N00_TARGET:target!,BUYEROS_N00_RUN_ID:runId}}});
