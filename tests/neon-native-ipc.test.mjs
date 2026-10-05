import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {createFixtureExecutionBoundary} from '../scripts/neon-execution-boundary.mjs';
import {RealRunJournal} from '../scripts/neon-real-preflight.mjs';
import {executionFixture} from './fixtures/neon-execution/fixture.mjs';
const native=await import('../scripts/neon-native-ipc.mjs').catch(error=>{if(error.code!=='ERR_MODULE_NOT_FOUND')throw error;return {};});
const req=(method='GET',path='/fixture/auth/token',body='',headers={})=>({channel:'cli',method,path,body,headers});
async function setup(t){assert.equal(typeof native.runFixtureNativeSession,'function','private counted native IPC is missing');const f=await executionFixture();t.after(()=>f.cleanup());return {...f,execution:createFixtureExecutionBoundary({backend:f.backend,journal:f.journal})};}

test('native worker IPC reserves before physical auth and unknown intent stays held after a new container/journal',async t=>{
 const f=await setup(t),first=await native.runFixtureNativeSession({execution:f.execution,journal:f.journal,requests:[req(),req('POST','/fixture/auth/commit','{"one":"intent"}')],parentEnvironment:{...process.env,NEON_API_KEY:'forbidden-secret',DATABASE_URL:'forbidden-secret',HTTPS_PROXY:'https://forbidden.invalid'}});
 assert.deepEqual(first.receipts.map(x=>[x.status,x.outcome]),[[200,'accepted'],[503,'unknown']]);assert.equal(first.environment_clean,true);assert.equal(first.positive_control.http_requests,3);assert.equal(first.positive_control.native_tcp_connected,true);assert.equal(first.cleanup.complete,true);assert.equal(first.cleanup.containers_absent.length,3);assert.equal(first.cleanup.network_absent,true);assert.equal(f.model.commits,1);assert.equal(f.model.hits.length,2);assert.equal(f.journal.snapshot().requests.length,2);
 for(const entry of f.journal.snapshot().requests){assert.doesNotMatch(readFileSync(join(f.root,entry.evidenceRef),'utf8'),/forbidden-secret|fictional.a.b/);}
 const restarted=new RealRunJournal(f.root),execution=createFixtureExecutionBoundary({backend:f.backend,journal:restarted}),second=await native.runFixtureNativeSession({execution,journal:restarted,requests:[req('POST','/fixture/auth/commit','{"one":"intent"}',{Authorization:'fictional-renewed-token'})]});
 assert.equal(second.receipts[0].error,'N00_EXECUTION_HELD_INTENT');assert.equal(second.cleanup.complete,true);assert.equal(f.model.commits,1);assert.equal(restarted.snapshot().requests.length,2);assert.equal(restarted.snapshot().requests[1].outcome,'unknown');
});

test('native runner rejects injected dispatch owner and foreign journal before any Docker resources',async t=>{
 const f=await setup(t);await assert.rejects(native.runFixtureNativeSession({execution:{dispatch:()=>{throw new Error('uncontained');}},journal:f.journal,requests:[req()]}),/CLEANUP_BOUNDARY/);
 const other=await executionFixture();t.after(()=>other.cleanup());await assert.rejects(native.runFixtureNativeSession({execution:f.execution,journal:other.journal,requests:[req()]}),/CLEANUP_BOUNDARY/);assert.equal(f.model.hits.length,0);
});


test('isolated native worker cannot bypass IPC through raw HTTP, fetch, TCP or a subprocess',async t=>{
 const f=await setup(t),report=await native.runFixtureNativeSession({execution:f.execution,journal:f.journal,requests:[req()]});
 t.diagnostic(JSON.stringify({fixture_only:true,positive_control:report.positive_control,direct_http_requests:report.direct_http_requests,probes:report.probes,worker_policy:report.worker_policy,cleanup:report.cleanup}));
 assert.equal(report.positive_control.http_requests,3);assert.equal(report.positive_control.native_tcp_connected,true);assert.equal(report.direct_http_requests,0);assert.deepEqual(report.probes,{http_connected:false,fetch_connected:false,tcp_connected:false,subprocess_connected:false});assert.equal(report.worker_policy.network,'none');assert.equal(report.worker_policy.read_only,true);assert.equal(report.worker_policy.user,'node');assert.deepEqual(report.worker_policy.cap_drop,['ALL']);assert.equal(report.worker_policy.published_ports,0);assert.equal(report.worker_policy.mounts,0);assert.equal(report.cleanup.complete,true);assert.equal(report.receipts[0].status,200);assert.equal(f.model.hits.length,1);assert.equal(f.journal.snapshot().requests.length,1);
});
