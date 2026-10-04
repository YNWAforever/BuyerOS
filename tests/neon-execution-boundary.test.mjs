import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createServer} from 'node:http';
import {readFileSync,readdirSync,writeFileSync} from 'node:fs';
import {join} from 'node:path';
import {createAuthClient} from '@neondatabase/auth';
import {RealRunJournal,validateRealTarget} from '../scripts/neon-real-preflight.mjs';
import {executionFixture,listen} from './fixtures/neon-execution/fixture.mjs';
const boundary=await import('../scripts/neon-execution-boundary.mjs').catch(error=>{if(error.code!=='ERR_MODULE_NOT_FOUND')throw error;return {};});
const cleanup=await import('../scripts/neon-execution-cleanup.mjs').catch(error=>{if(error.code!=='ERR_MODULE_NOT_FOUND')throw error;return {};});
async function wire(t,handler,options={}) {assert.equal(typeof boundary.createFixtureExecutionBoundary,'function');const f=await executionFixture(handler);t.after(()=>f.cleanup());return {...f,execution:boundary.createFixtureExecutionBoundary({backend:f.backend,journal:f.journal,...options})};}
const request=(channel='sdk',path='/fixture/auth/token',method='GET',body='')=>({channel,path,method,body});
function evidence(f) {return readdirSync(f.root).filter(p=>p.endsWith('.json')).map(p=>readFileSync(join(f.root,p),'utf8')).join('\n');}

test('all SDK/browser/CLI physical hops are durably reserved before the backend receives them',async t=>{
 const f=await wire(t,(_req,res,{journal,model})=>{assert.equal(journal.snapshot().requests.length,model.hits.length);assert.equal(journal.snapshot().requests.at(-1).outcome,'pending');res.end('{}');return true;});
 for(const channel of ['sdk','browser','cli'])assert.equal((await f.execution.dispatch(request(channel))).status,200);
 assert.equal(f.model.hits.length,3);assert.deepEqual(f.journal.snapshot().requests.map(v=>v.outcome),['accepted','accepted','accepted']);
 const receipts=f.journal.snapshot().requests.map(v=>JSON.parse(readFileSync(join(f.root,v.evidenceRef),'utf8')));assert.deepEqual(receipts.map(v=>v.channel),['sdk','browser','cli']);
});
test('an unowned server, real target or unknown caller/path is refused before dispatch',async t=>{
 const f=await wire(t),unowned=createServer();f.servers.push(unowned);await listen(unowned);
 assert.throws(()=>boundary.createFixtureExecutionBoundary({backend:unowned,journal:f.journal}),/OWNED/);
 const real=structuredClone(f.target);real.auth.baseUrl='https://auth.example.com/auth';real.auth.jwksUrl='https://auth.example.com/auth/jwks';const state=f.journal.snapshot();const original=readFileSync(join(f.root,'journal.json'),'utf8');state.target=validateRealTarget(real);writeFileSync(join(f.root,'journal.json'),JSON.stringify(state));assert.throws(()=>boundary.createFixtureExecutionBoundary({backend:f.backend,journal:f.journal}),/FIXTURE_TARGET/);writeFileSync(join(f.root,'journal.json'),original);
 for(const value of [request('unknown'),request('sdk','https://production.invalid'),request('sdk','/fixture/auth/%2e%2e'),request('sdk','/fixture/control/project/nameless-bar-15324691','DELETE')])await assert.rejects(f.execution.dispatch(value));
 assert.equal(f.model.hits.length,0);assert.equal(f.journal.snapshot().requests.length,0);
});
test('redirects remain manual and each explicitly followed hop consumes another reservation',async t=>{
 const f=await wire(t);const first=await f.execution.dispatch(request('browser','/fixture/auth/redirect'));assert.equal(first.status,302);assert.equal(first.location,'/fixture/auth/token');assert.equal(f.model.hits.length,1);
 assert.equal((await f.execution.dispatch(request('browser',first.location))).status,200);assert.equal(f.model.hits.length,2);assert.equal(f.journal.snapshot().requests.length,2);
});
test('a foreign redirect cannot cause an uncounted request',async t=>{
 const f=await wire(t,(_req,res)=>{res.statusCode=302;res.setHeader('Location','https://foreign.fixture.invalid/auth');res.end();return true;});await assert.rejects(f.execution.dispatch(request()),/REDIRECT_REFUSED/);assert.equal(f.model.hits.length,1);assert.equal(f.journal.snapshot().requests[0].outcome,'unknown');
});
test('commit with lost response is held across channel changes and journal restart',async t=>{
 const f=await wire(t);const first=await f.execution.dispatch(request('sdk','/fixture/auth/commit','POST','{"one":"intent"}'));assert.equal(first.outcome,'unknown');assert.equal(f.model.commits,1);
 const recovered=boundary.createFixtureExecutionBoundary({backend:f.backend,journal:new RealRunJournal(f.root)});
 await assert.rejects(recovered.dispatch(request('browser','/fixture/auth/commit','POST','{"one":"intent"}')),/HELD_INTENT/);await assert.rejects(recovered.dispatch(request('cli','/fixture/auth/commit','POST','{"one":"intent"}')),/HELD_INTENT/);
 assert.equal(f.model.commits,1);assert.equal(f.journal.snapshot().requests.length,1);
});
test('concurrent identical writes cannot dispatch twice',async t=>{
 let release;const f=await wire(t,async(req,res)=>{if(req.method==='POST'){await new Promise(ok=>{release=ok;});res.end('{}');return true;}});
 const first=f.execution.dispatch(request('sdk','/fixture/auth/one','POST','same'));while(!release)await new Promise(ok=>setTimeout(ok,10));await assert.rejects(f.execution.dispatch(request('cli','/fixture/auth/one','POST','same')),/HELD_INTENT/);release();assert.equal((await first).status,200);assert.equal(f.model.hits.length,1);
});
test('the 180-check stop retains 20 cleanup/reconciliation reservations across restart',async t=>{
 const f=await wire(t);for(let i=0;i<180;i++){f.journal.reserveRequest('auth','earlier-'+i);f.journal.settleRequest('earlier-'+i,'accepted','historical-fixture.json');}
 await assert.rejects(f.execution.dispatch(request()),/BUDGET/);assert.equal(f.model.hits.length,0);
 for(let i=0;i<20;i++)assert.equal((await f.execution.dispatch(request('control','/fixture/control/target'))).status,200);
 await assert.rejects(f.execution.dispatch(request('control','/fixture/control/target')),/BUDGET/);assert.equal(new RealRunJournal(f.root).snapshot().requests.length,200);assert.equal(f.model.hits.length,20);
});
test('TTL refuses new auth but allows exact cleanup readback after expiry',async t=>{
 const f=await wire(t),late=Date.parse(f.target.expiresAt)+1;const execution=boundary.createFixtureExecutionBoundary({backend:f.backend,journal:f.journal,now:()=>late});await assert.rejects(execution.dispatch(request()),/EXPIRED/);assert.equal((await execution.dispatch(request('control','/fixture/control/target'))).status,200);assert.equal(f.model.hits.length,1);
});
test('bodies and response bytes are bounded without returning or persisting secrets',async t=>{
 const f=await wire(t,(_req,res)=>{res.end('s'.repeat(1048577));return true;});await assert.rejects(f.execution.dispatch(request('sdk','/fixture/auth/token','POST','s'.repeat(32769))),/BODY_LIMIT/);assert.equal(f.model.hits.length,0);
 const result=await f.execution.dispatch(request());assert.equal(result.outcome,'unknown');assert.equal(result.body,'');assert.doesNotMatch(evidence(f),/s{100}/);
});
test('receipt failure preserves pending reservation and fails closed after restart',async t=>{
 const f=await wire(t,(_req,res,{journal})=>{writeFileSync(join(journal.root,'execution-http-1.json'),'corrupt',{flag:'wx'});res.end('{}');return true;});await assert.rejects(f.execution.dispatch(request('sdk','/fixture/auth/one','POST','x')),/EVIDENCE/);assert.equal(f.journal.snapshot().requests[0].outcome,'pending');
 const recovered=boundary.createFixtureExecutionBoundary({backend:f.backend,journal:new RealRunJournal(f.root)});await assert.rejects(recovered.dispatch(request('cli','/fixture/auth/two','POST','y')),/HELD_INTENT/);assert.equal(f.model.hits.length,1);
});
test('official pinned SDK token request crosses the same durable gateway once',async t=>{
 const f=await wire(t);assert.equal(typeof boundary.createFixtureExecutionGateway,'function');const gateway=boundary.createFixtureExecutionGateway({execution:f.execution,nonce:'a'.repeat(43)});f.servers.push(gateway);const url=await listen(gateway);const client=createAuthClient(url+'/sdk/auth');const result=await client.token({fetchOptions:{headers:{'x-n00-owner':'a'.repeat(43)}}});assert.equal(result.data.token,'fictional.a.b');assert.equal(f.model.hits.length,1);assert.equal(f.journal.snapshot().requests.length,1);
});
test('fixed Node CLI helper uses the owned gateway and strips inherited credentials',async t=>{
 const f=await wire(t);assert.equal(typeof boundary.runFixtureCli,'function');const gateway=boundary.createFixtureExecutionGateway({execution:f.execution,nonce:'b'.repeat(43)});f.servers.push(gateway);await listen(gateway);
 const result=await boundary.runFixtureCli({gateway,nonce:'b'.repeat(43),request:request('cli'),parentEnvironment:{...process.env,DATABASE_URL:'forbidden-secret',NEON_API_KEY:'forbidden-secret',HTTPS_PROXY:'https://forbidden.invalid'}});assert.equal(result.status,200);assert.equal(result.environment_clean,true);assert.equal(f.model.hits.length,1);assert.doesNotMatch(evidence(f),/forbidden-secret|fictional.a.b/);
});

test('cleanup verifies exact ownership and absence after each deletion in identity/auth/project order',async t=>{
 const f=await wire(t);assert.equal(typeof cleanup.runFixtureCleanup,'function');f.journal.bindIdentity(f.identity);const result=await cleanup.runFixtureCleanup({execution:f.execution,journal:f.journal});assert.equal(result.complete,true);assert.deepEqual(result.absent,['identity','auth','project']);assert.deepEqual(f.model.hits.filter(v=>v[0]==='DELETE').map(v=>v[1].split('/')[3]),['identity','auth','project']);assert.equal(f.model.hits.length,10);assert.equal(f.journal.snapshot().requests.length,10);assert.equal(result.external_verified,false);
});
test('unknown deletion never blindly retries; fresh absence lets restarted cleanup continue',async t=>{
 const f=await wire(t);assert.equal(typeof cleanup.runFixtureCleanup,'function');f.journal.bindIdentity(f.identity);f.model.loseDelete='identity';const first=await cleanup.runFixtureCleanup({execution:f.execution,journal:f.journal});assert.equal(first.complete,false);assert.equal(first.blocked,'unknown-delete');assert.equal(f.model.hits.filter(v=>v[0]==='DELETE').length,1);
 const restarted=boundary.createFixtureExecutionBoundary({backend:f.backend,journal:new RealRunJournal(f.root)});const second=await cleanup.runFixtureCleanup({execution:restarted,journal:new RealRunJournal(f.root)});assert.equal(second.complete,true);assert.equal(f.model.hits.filter(v=>v[0]==='DELETE').length,3);assert.equal(f.journal.snapshot().requests.filter(v=>v.outcome==='unknown').length,1);
});
test('unknown deletion still present blocks every later dependent deletion and retry',async t=>{
 const f=await wire(t);assert.equal(typeof cleanup.runFixtureCleanup,'function');f.journal.bindIdentity(f.identity);f.model.rejectDelete='identity';assert.equal((await cleanup.runFixtureCleanup({execution:f.execution,journal:f.journal})).blocked,'unknown-delete');assert.equal((await cleanup.runFixtureCleanup({execution:f.execution,journal:f.journal})).blocked,'held-delete');assert.equal(f.model.hits.filter(v=>v[0]==='DELETE').length,1);assert.equal(f.model.resources.get('project').exists,true);
});
test('mismatched provider readback prevents every deletion',async t=>{
 const f=await wire(t);assert.equal(typeof cleanup.runFixtureCleanup,'function');f.model.readbackPatch={projectId:'nameless-bar-15324691'};await assert.rejects(cleanup.runFixtureCleanup({execution:f.execution,journal:f.journal}),/READBACK/);assert.equal(f.model.hits.filter(v=>v[0]==='DELETE').length,0);
});
test('cleanup after TTL still counts every readback/deletion and never touches an unbound identity',async t=>{
 const f=await wire(t);assert.equal(typeof cleanup.runFixtureCleanup,'function');const late=Date.parse(f.target.expiresAt)+10;f.model.clock=()=>late;const execution=boundary.createFixtureExecutionBoundary({backend:f.backend,journal:f.journal,now:()=>late});const result=await cleanup.runFixtureCleanup({execution,journal:f.journal,now:()=>late});assert.equal(result.complete,true);assert.deepEqual(result.absent,['auth','project']);assert.equal(f.model.resources.get('identity').exists,true);assert.equal(f.model.hits.length,7);
});


test('cleanup refuses an injected transport and a different journal even with matching-looking metadata',async t=>{
 const f=await wire(t);const fake={report:()=>({fixture_only:true,journal:f.journal.snapshot()}),dispatch:()=>{throw new Error('uncontained-dispatch');}};await assert.rejects(cleanup.runFixtureCleanup({execution:fake,journal:f.journal}),/CLEANUP_BOUNDARY/);assert.equal(f.model.hits.length,0);
 const other=await executionFixture();t.after(()=>other.cleanup());await assert.rejects(cleanup.runFixtureCleanup({execution:f.execution,journal:other.journal}),/CLEANUP_BOUNDARY/);assert.equal(f.model.hits.length,0);
});
test('wrong gateway nonce and cross-origin writes cannot consume provider budget',async t=>{
 const f=await wire(t),gateway=boundary.createFixtureExecutionGateway({execution:f.execution,nonce:'g'.repeat(43)});f.servers.push(gateway);const url=await listen(gateway);
 for(const headers of [{'x-n00-owner':'wrong'},{'x-n00-owner':'g'.repeat(43),Origin:'https://foreign.invalid'}]){const response=await fetch(url+'/dispatch',{method:'POST',headers,body:JSON.stringify(request('browser'))});assert.equal(response.status,403);await response.text();}assert.equal(f.model.hits.length,0);assert.equal(f.journal.snapshot().requests.length,0);
});
test('expired or mismatched existence receipt blocks cleanup before any deletion',async t=>{
 const f=await wire(t,(req,res,{target})=>{if(req.url.startsWith('/fixture/control/auth/')){res.end(JSON.stringify({kind:'auth',id:target.authId,projectId:target.projectId,authId:target.authId,orgId:target.orgId,exists:true,observedAt:new Date(Date.parse(target.createdAt)-1).toISOString()}));return true;}});await assert.rejects(cleanup.runFixtureCleanup({execution:f.execution,journal:f.journal}),/READBACK/);assert.equal(f.model.hits.filter(v=>v[0]==='DELETE').length,0);
});

test('CLI refuses an absent or unowned gateway before spawning a subprocess',()=>{
 assert.throws(()=>boundary.runFixtureCli({gateway:undefined,request:request('cli')}),/CLI_OWNER/);
 const fake={listening:true,address:()=>({address:'127.0.0.1',port:1})};assert.throws(()=>boundary.runFixtureCli({gateway:fake,request:request('cli')}),/CLI_OWNER/);
});
