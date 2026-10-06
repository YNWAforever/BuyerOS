import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createServer} from 'node:http';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {RealRunJournal} from '../scripts/neon-real-preflight.mjs';
import {createFixtureExecutionBoundary,createFixtureExecutionGateway} from '../scripts/neon-execution-boundary.mjs';
import {executionFixture,listen,close} from './fixtures/neon-execution/fixture.mjs';
const adapter=await import('../scripts/neon-api-request-context.mjs').catch(error=>{if(error.code!=='ERR_MODULE_NOT_FOUND')throw error;return {};});
const nonce='fictional-api-context-owner-'.padEnd(43,'x');
const call=(path='/fixture/auth/token',method='GET',body='',headers={})=>({path,method,body,headers});
async function wire(t,handler,options={}){assert.equal(typeof adapter.createFixtureApiRequestContext,'function','counted APIRequestContext adapter is missing');const f=await executionFixture(handler);t.after(()=>f.cleanup());f.execution=createFixtureExecutionBoundary({backend:f.backend,journal:f.journal,...options});f.gateway=createFixtureExecutionGateway({execution:f.execution,nonce});f.servers.push(f.gateway);await listen(f.gateway);f.options={gateway:f.gateway,execution:f.execution,journal:f.journal,nonce};f.client=await adapter.createFixtureApiRequestContext(f.options);t.after(()=>f.client.dispose());return f;}

test('API request context persists each manual auth hop before HTTP and forwards only explicit in-memory headers',async t=>{
 const pending=[],received=[];const f=await wire(t,(req,res,{journal})=>{pending.push(journal.snapshot().requests.at(-1)?.outcome);received.push({cookie:req.headers.cookie??null,bearer:req.headers.authorization??null});if(req.url==='/fixture/auth/redirect'){res.statusCode=302;res.setHeader('Location','/fixture/auth/token');res.setHeader('Set-Cookie','fixture_session=fictional-private; Path=/');res.end();return true;}});
 const first=await f.client.dispatch(call('/fixture/auth/redirect'));assert.equal(first.status,302);assert.equal(first.location,'/fixture/auth/token');assert.equal(f.model.hits.length,1);assert.equal(f.journal.snapshot().requests.length,1);
 const second=await f.client.dispatch(call(first.location,'GET','',new Headers({Authorization:'fictional-memory-bearer'})));assert.equal(second.status,200);assert.equal(second.fixture_only,true);assert.equal(second.external_verified,false);assert.equal(JSON.parse(second.body).token,'fictional.a.b');assert.deepEqual(pending,['pending','pending']);assert.deepEqual(received,[{cookie:null,bearer:null},{cookie:null,bearer:'fictional-memory-bearer'}]);assert.deepEqual(f.journal.snapshot().requests.map(v=>v.outcome),['accepted','accepted']);
 for(const v of f.journal.snapshot().requests)assert.doesNotMatch(readFileSync(join(f.root,v.evidenceRef),'utf8'),/fictional-memory-bearer|fictional-private|fictional.a.b/);
});

test('API context backend unknown intent stays held across fresh context and journal with renewed bearer',async t=>{
 const f=await wire(t),first=await f.client.dispatch(call('/fixture/auth/commit','POST','{"one":"intent"}'));assert.equal(first.outcome,'unknown');assert.equal(first.status,503);assert.equal(f.model.commits,1);await f.client.dispose();
 const journal=new RealRunJournal(f.root),execution=createFixtureExecutionBoundary({backend:f.backend,journal}),gateway=createFixtureExecutionGateway({execution,nonce});f.servers.push(gateway);await listen(gateway);const second=await adapter.createFixtureApiRequestContext({gateway,execution,journal,nonce});t.after(()=>second.dispose());
 await assert.rejects(second.dispatch(call('/fixture/auth/commit','POST','{"one":"intent"}',{Authorization:'fictional-renewed-bearer'})),/HELD_INTENT/);assert.equal(f.model.commits,1);assert.equal(f.model.hits.length,1);assert.equal(journal.snapshot().requests.length,1);assert.equal(journal.snapshot().requests[0].outcome,'unknown');
});

test('lost gateway response never autoretries an accepted write and restart retains the hold',async t=>{
 const f=await wire(t,(req,res,{model})=>{if(req.url!=='/fixture/auth/accepted')return;model.commits++;res.statusCode=202;res.end('{"accepted":true}');return true;});let wires=0;
 f.gateway.prependListener('request',(_req,res)=>{wires++;const end=res.end.bind(res);res.end=(...args)=>{if(wires===1){res.destroy();return res;}return end(...args);};});
 await assert.rejects(f.client.dispatch(call('/fixture/auth/accepted','POST','{"one":"intent"}')),/TRANSPORT_UNKNOWN/);assert.equal(wires,1);assert.equal(f.model.commits,1);assert.equal(f.journal.snapshot().requests[0].outcome,'accepted');await f.client.dispose();
 const journal=new RealRunJournal(f.root),execution=createFixtureExecutionBoundary({backend:f.backend,journal}),gateway=createFixtureExecutionGateway({execution,nonce});f.servers.push(gateway);await listen(gateway);const restarted=await adapter.createFixtureApiRequestContext({gateway,execution,journal,nonce});t.after(()=>restarted.dispose());await assert.rejects(restarted.dispatch(call('/fixture/auth/accepted','POST','{"one":"intent"}',{Authorization:'fictional-renewed-bearer'})),/HELD_INTENT/);assert.equal(f.model.commits,1);assert.equal(journal.snapshot().requests.length,1);
});

test('unexpected gateway wire redirect cannot leak owner nonce to a foreign owned sink',async t=>{
 const f=await wire(t);let sinkHits=0;const sink=createServer((_req,res)=>{sinkHits++;res.end('{}');});f.servers.push(sink);const sinkUrl=await listen(sink);
 f.gateway.prependListener('request',(_req,res)=>{const end=res.end.bind(res);res.end=()=>{res.statusCode=302;res.setHeader('Location',sinkUrl+'/leak');return end();};});
 await assert.rejects(f.client.dispatch(call()),/WIRE_REDIRECT_REFUSED/);assert.equal(sinkHits,0);assert.equal(f.model.hits.length,1);assert.equal(f.journal.snapshot().requests.length,1);
});

test('unowned gateway, foreign journal, bad nonce and injected raw context are refused before HTTP',async t=>{
 const f=await wire(t),other=await executionFixture();t.after(()=>other.cleanup());
 const bad=[{...f.options,gateway:createServer()},{...f.options,journal:other.journal},{...f.options,nonce:'wrong'},{...f.options,requestContext:{fetch:()=>{throw new Error('uncontained');}}}];for(const options of bad)await assert.rejects(adapter.createFixtureApiRequestContext(options),/N00_/);assert.equal(f.model.hits.length,0);assert.equal(f.journal.snapshot().requests.length,0);
});

test('invalid, administrative and oversized requests are refused before even the gateway wire',async t=>{
 const f=await wire(t);let wires=0;f.gateway.on('request',()=>{wires++;});
 const bad=[call(f.url+'/fixture/auth/token'),call('/fixture/auth/../token'),call('/fixture/auth/admin/remove-user','POST','{"userId":"fictional-execution-identity"}'),call('/fixture/control/target'),call('/fixture/auth/token','GET','not-empty'),call('/fixture/auth/token','POST','x'.repeat(32769)),call('/fixture/auth/token','POST','"'.repeat(16400)),call('/fixture/auth/token','PUT'),{...call(),channel:'control'}];for(const input of bad)await assert.rejects(f.client.dispatch(input),/N00_/);assert.equal(wires,0);assert.equal(f.model.hits.length,0);assert.equal(f.journal.snapshot().requests.length,0);
});

test('API context keeps the original auth budget and cleanup reserve intact',async t=>{
 const f=await wire(t);for(let i=0;i<180;i++){f.journal.reserveRequest('auth','previous-'+i);f.journal.settleRequest('previous-'+i,'accepted','historical-fixture.json');}
 await assert.rejects(f.client.dispatch(call()),/BUDGET/);assert.equal(f.model.hits.length,0);assert.equal(f.journal.snapshot().requests.length,180);
});

test('disposed or rebound owned gateway cannot be silently adopted by an old API context',async t=>{
 const f=await wire(t);await close(f.gateway);await listen(f.gateway);await assert.rejects(f.client.dispatch(call()),/BOUND_GATEWAY/);assert.equal(f.model.hits.length,0);await f.client.dispose();await f.client.dispose();await assert.rejects(f.client.dispatch(call()),/DISPOSED/);assert.equal(f.journal.snapshot().requests.length,0);
});



for(const phase of ['body','dispose'])test(`gateway ownership changing during ${phase} rejects the stale receipt`,{timeout:10000},async t=>{
 const {request}=await import('@playwright/test');
 const f=await wire(t),url='http://127.0.0.1:'+f.gateway.address().port,probe=await request.newContext();t.after(()=>probe.dispose());const sample=await probe.get(url+'/');const prototype=Object.getPrototypeOf(sample),original=prototype[phase];await sample.dispose();
 let entered,release;const blocked=new Promise(ok=>{entered=ok;}),resume=new Promise(ok=>{release=ok;});
 // Delegate the real public APIResponse method; pause its result only at this owned wire boundary.
 prototype[phase]=async function(...args){const value=await original.apply(this,args);if(this.url()===url+'/dispatch'){entered();await resume;}return value;};
 t.after(()=>{release();prototype[phase]=original;});
 try{const pending=f.client.dispatch(call());await blocked;await close(f.gateway);release();await assert.rejects(pending,/GATEWAY/);assert.equal(f.model.hits.length,1);assert.equal(f.journal.snapshot().requests.length,1);}finally{release();prototype[phase]=original;}
});
