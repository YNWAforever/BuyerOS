import {randomUUID} from 'node:crypto';
import {defineConfig} from '@playwright/test';
const target=process.env.BUYEROS_N00_TARGET;
const scenario=process.env.BUYEROS_N00_PROBE_SCENARIO??'valid';
const baseline=process.env.BUYEROS_N00_PROBE_BASELINE==='yes';
const runId=process.env.BUYEROS_N00_RUN_ID??randomUUID().replaceAll('-', '').slice(0,12);
if(!['portable','vercel'].includes(target??'')||!['valid','missing','mismatch','expired'].includes(scenario)||!/^[a-f0-9]{12}$/.test(runId))throw new Error('N00 runtime probe scope refused');
if(baseline&&scenario!=='valid')throw new Error('N00 baseline requires valid scenario');
const label=`${baseline?'baseline-':''}${target}-${scenario}-${runId}`;
export default defineConfig({testDir:'./tests/e2e',testMatch:'audit-neon-runtime-built.spec.ts',workers:1,timeout:45_000,
 globalTeardown:baseline?'./scripts/neon-counted-teardown.mjs':'./scripts/neon-runtime-probe-teardown.mjs',metadata:{n00Target:target,n00RunId:runId,n00ProbeScenario:scenario},
 outputDir:`test-results/neon-runtime-built/${label}-ui`,reporter:[['list'],['junit',{outputFile:`test-results/neon-runtime-built/${label}-ui.xml`}]],
 use:{baseURL:`http://localhost:${baseline?44890:44900}`,browserName:'chromium',viewport:{width:1120,height:800},trace:'retain-on-failure'},
 webServer:{command:baseline?'node scripts/serve-neon-compatibility.mjs':'node scripts/serve-neon-runtime-probe.mjs',url:`http://localhost:${baseline?44890:44900}/`,timeout:90_000,reuseExistingServer:false,
 env:{BUYEROS_N00_TARGET:target!,BUYEROS_N00_RUN_ID:runId,BUYEROS_N00_PROBE_SCENARIO:scenario}}});
