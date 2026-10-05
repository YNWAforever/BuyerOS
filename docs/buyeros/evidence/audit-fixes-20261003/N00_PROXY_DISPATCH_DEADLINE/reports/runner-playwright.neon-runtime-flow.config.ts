import {randomUUID} from 'node:crypto';
import {defineConfig} from '@playwright/test';
const target=process.env.BUYEROS_N00_TARGET,baseline=process.env.BUYEROS_N00_FLOW_BASELINE==='yes';
const profile=process.env.BUYEROS_N00_FLOW_PROFILE??'runtime-flow-final';
if(!['runtime-flow','runtime-flow-final'].includes(profile))throw new Error('N00_FLOW_BUILD_PROFILE');
const runId=process.env.BUYEROS_N00_RUN_ID??randomUUID().replaceAll('-','').slice(0,12);
if(!['portable','vercel'].includes(target??'')||!/^[a-f0-9]{12}$/.test(runId))throw new Error('N00_FLOW_SCOPE');
export default defineConfig({testDir:'./tests/e2e',testMatch:'audit-neon-runtime-flow.spec.ts',workers:1,timeout:45_000,
 metadata:baseline?{n00Target:target,n00RunId:runId,n00ProbeScenario:'valid'}:{n00Target:target,n00RunId:runId},
 globalTeardown:baseline?'./scripts/neon-runtime-probe-teardown.mjs':'./scripts/neon-runtime-flow-teardown.mjs',
 outputDir:`test-results/neon-runtime-flow/${baseline?'baseline-':''}${target}-${runId}-ui`,
 reporter:[['list'],['junit',{outputFile:`test-results/neon-runtime-flow/${baseline?'baseline-':''}${target}-${runId}-ui.xml`}]],
 use:{baseURL:`http://localhost:${baseline?44900:44890}`,browserName:'chromium',viewport:{width:1120,height:800},trace:'retain-on-failure'},
 webServer:{command:baseline?'node scripts/serve-neon-runtime-probe.mjs':'node scripts/serve-neon-runtime-flow.mjs',url:`http://localhost:${baseline?44900:44890}/`,timeout:240_000,reuseExistingServer:false,
 env:{BUYEROS_N00_TARGET:target!,BUYEROS_N00_RUN_ID:runId,BUYEROS_N00_PROBE_SCENARIO:'valid',BUYEROS_N00_FLOW_PROFILE:profile}}});
