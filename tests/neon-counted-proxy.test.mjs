import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createServer} from 'node:http';
import {mkdtempSync,readFileSync,readdirSync,rmSync,realpathSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve,relative} from 'node:path';
import {RealRunJournal} from '../scripts/neon-real-preflight.mjs';
import {createOwnedAuthServer,createCountedAuthProxy} from '../scripts/neon-counted-proxy.mjs';
async function listen(server) {await new Promise((ok,bad)=>{server.once('error',bad);server.listen(0,'127.0.0.1',ok);});return 'http://127.0.0.1:'+server.address().port;}
async function close(server) {if(server?.listening){server.closeAllConnections();await new Promise(ok=>server.close(ok));}}
function fixture(t) {
 const root=mkdtempSync(join(tmpdir(),'buyeros-n00-real-')),servers=[],created=Date.now(),stamp=new Date(created).toISOString();
 t.after(async()=>{for(const server of servers.reverse())await close(server);assert.equal(realpathSync(root),resolve(root));assert.ok(relative(resolve(tmpdir()),root).startsWith('buyeros-n00-real-'));rmSync(root,{recursive:true,force:true});});
 const run=RealRunJournal.create(root,{approvalReference:'fixture-only-no-external-authority',approvedAt:stamp});
 const target={schemaVersion:1,proposal:'buyeros-neon-auth-n00-20261004',sourceSha:'a94bdf4951a1fcf418df828fee15ac01baae9ba6',projectId:'unit-isolated-12345678',branchId:'br-unit-12345678',authId:'auth-unit-12345678',orgId:'org-soft-sunset-25251479',name:'buyeros-neon-auth-n00-20261004',regionId:'aws-ap-southeast-1',creationMode:'new-empty',createdAt:stamp,expiresAt:new Date(created+2*60*60_000).toISOString(),readback:{projectId:'unit-isolated-12345678',branchId:'br-unit-12345678',authId:'auth-unit-12345678',orgId:'org-soft-sunset-25251479',name:'buyeros-neon-auth-n00-20261004',regionId:'aws-ap-southeast-1',observedAt:stamp,subscription:'free_v3',emailDeliveryEnabled:false,emailPasswordEnabled:false,emailHooksEnabled:false,methods:['google'],trustedOrigins:['http://localhost:44890']},auth:{baseUrl:'https://unit.fixture.invalid/neondb/auth',issuer:'https://unit.fixture.invalid',audience:'unit-audience',jwksUrl:'https://unit.fixture.invalid/neondb/auth/jwks',algorithm:'EdDSA',keyType:'OKP',curve:'Ed25519'}};
 run.bindTarget(target,created);return {root,run,servers,created,target};
}
async function wire(t,handler,options={}) {const f=fixture(t),backend=createOwnedAuthServer(handler);f.servers.push(backend);await listen(backend);const proxy=createCountedAuthProxy({backend,journal:f.run,...options});f.servers.push(proxy);return {...f,backend,proxy,url:await listen(proxy)};}

test('proxy refuses arbitrary URLs, unowned servers and unbound journals before any request',async t=>{
 const f=fixture(t),external=createServer();f.servers.push(external);await listen(external);
 assert.throws(()=>createCountedAuthProxy({backend:external,journal:f.run}),/OWNED/);
 assert.throws(()=>createCountedAuthProxy({backend:'https://production.invalid',journal:f.run}),/OWNED/);
 const freshRoot=mkdtempSync(join(tmpdir(),'buyeros-n00-real-'));t.after(()=>{assert.equal(realpathSync(freshRoot),resolve(freshRoot));assert.ok(relative(resolve(tmpdir()),freshRoot).startsWith('buyeros-n00-real-'));rmSync(freshRoot,{recursive:true,force:true});});const unbound=RealRunJournal.create(freshRoot,{approvalReference:'fixture-only-no-external-authority',approvedAt:new Date().toISOString()});
 const owned=createOwnedAuthServer((_req,res)=>res.end('{}'));f.servers.push(owned);await listen(owned);assert.throws(()=>createCountedAuthProxy({backend:owned,journal:unbound}),/BOUND_TARGET/);assert.equal(f.run.snapshot().requests.length,0);
});
test('HTTP reservation is durable and pending before the owned backend receives the request',async t=>{
 let run,received=0;
 const f=await wire(t,(_req,res)=>{received++;assert.equal(run.snapshot().requests.length,1);assert.equal(run.snapshot().requests[0].outcome,'pending');res.setHeader('Content-Type','application/json');res.end('{"ok":true}');});run=f.run;
 const response=await fetch(f.url+'/fixture/auth/get-session');assert.equal(response.status,200);assert.deepEqual(await response.json(),{ok:true});assert.equal(received,1);
 const record=run.snapshot().requests[0];assert.equal(record.outcome,'accepted');const evidence=JSON.parse(readFileSync(join(f.root,record.evidenceRef),'utf8'));assert.equal(evidence.status,200);assert.equal(evidence.fixture_only,true);
});
test('SDK origin, session/challenge cookies and JWT headers survive relay without entering evidence',async t=>{
 const f=await wire(t,(req,res)=>{assert.equal(req.headers.origin,'http://localhost:44890');assert.equal(req.headers.cookie,'session=fictional');assert.equal(req.headers['x-neon-auth-middleware'],'true');res.setHeader('Set-Cookie',['session=fictional; HttpOnly; Secure; SameSite=Lax','challenge=fictional; HttpOnly; Secure; SameSite=Lax']);res.setHeader('set-auth-jwt','fictional-sensitive-token');res.end('{}');});
 const response=await fetch(f.url+'/fixture/auth/get-session?neon_auth_session_verifier=fictional-sensitive-verifier',{headers:{Origin:'http://localhost:44890',Cookie:'session=fictional','x-neon-auth-middleware':'true'}});assert.equal(response.status,200);assert.equal(response.headers.getSetCookie().length,2);assert.equal(response.headers.get('set-auth-jwt'),'fictional-sensitive-token');await response.text();
 const bytes=readdirSync(f.root).filter(p=>p.endsWith('.json')).map(p=>readFileSync(join(f.root,p),'utf8')).join('');assert.doesNotMatch(bytes,/fictional-sensitive|session=fictional|neon_auth_session_verifier/);
});
test('approved local callback302 is preserved manually, and an external redirect is blocked',async t=>{
 let received=0;const f=await wire(t,(req,res)=>{received++;res.statusCode=302;res.setHeader('Location',req.url.includes('outside')?'https://unapproved.fixture.invalid/callback':'http://localhost:44890/compat/return?neon_auth_session_verifier=fictional');res.end();});
 const valid=await fetch(f.url+'/fixture/auth/callback/google',{redirect:'manual'});assert.equal(valid.status,302);assert.equal(valid.headers.get('location'),'http://localhost:44890/compat/return?neon_auth_session_verifier=fictional');await valid.text();
 const blocked=await fetch(f.url+'/fixture/auth/callback/outside',{redirect:'manual'});assert.equal(blocked.status,502);assert.equal(blocked.headers.get('location'),null);await blocked.text();assert.equal(received,2);assert.equal(f.run.snapshot().requests.length,2);
});
test('committed POST with a lost response is not replayed after proxy and journal restart',async t=>{
 let commits=0;const f=await wire(t,async(req,res)=>{if(req.method==='POST'){for await(const chunk of req)assert.ok(chunk.length>0);commits++;req.socket.destroy();}else res.end('{"readback":true}');});
 const post={method:'POST',body:'{"fixture":"one-intent"}',headers:{'Content-Type':'application/json'}};
 const first=await fetch(f.url+'/fixture/auth/sign-in/social',post);assert.equal(first.status,503);await first.text();assert.equal(commits,1);assert.equal(f.run.snapshot().requests[0].outcome,'unknown');
 await close(f.proxy);const restarted=createCountedAuthProxy({backend:f.backend,journal:new RealRunJournal(f.root)});f.servers.push(restarted);const url=await listen(restarted);
 const retry=await fetch(url+'/fixture/auth/sign-in/social',post);assert.equal(retry.status,409);await retry.text();assert.equal(commits,1);assert.equal(f.run.snapshot().requests.length,2);
 const readback=await fetch(url+'/fixture/auth/get-session');assert.equal(readback.status,200);await readback.text();assert.equal(f.run.snapshot().requests.length,3);
});
test('budget exhaustion refuses dispatch and keeps cleanup reserve after restart',async t=>{
 let received=0;const f=await wire(t,(_req,res)=>{received++;res.end('{}');});
 for(let i=0;i<180;i++)f.run.reserveRequest('auth','pre-counted-'+i);
 const response=await fetch(f.url+'/fixture/auth/get-session');assert.equal(response.status,429);await response.text();assert.equal(received,0);assert.equal(new RealRunJournal(f.root).snapshot().requests.length,180);
 assert.equal(f.run.reserveRequest('cleanup','fixture-cleanup').sequence,181);
});
test('expired target and over-size body fail closed without dispatching upstream',async t=>{
 let received=0;const f=await wire(t,(_req,res)=>{received++;res.end('{}');},{now:()=>Date.now()+2*60*60_000});
 const expired=await fetch(f.url+'/fixture/auth/get-session');assert.equal(expired.status,403);await expired.text();assert.equal(received,0);
 await close(f.proxy);const bounded=createCountedAuthProxy({backend:f.backend,journal:f.run});f.servers.push(bounded);const url=await listen(bounded);
 const large=await fetch(url+'/fixture/auth/sign-in/social',{method:'POST',body:'x'.repeat(32*1024+1)});assert.equal(large.status,413);await large.text();assert.equal(received,0);
});
test('POST server500 retains an unknown write and timeout is bounded without automatic retry',async t=>{
 let received=0;const f=await wire(t,async(req,res)=>{for await(const chunk of req)assert.ok(chunk.length>0);received++;if(req.url.includes('slow')){setTimeout(()=>res.end('{}'),180).unref();}else{res.statusCode=500;res.end('{}');}},{timeoutMs:40});
 const error=await fetch(f.url+'/fixture/auth/sign-in/social',{method:'POST',body:'{"intent":"a"}'});assert.equal(error.status,500);await error.text();assert.equal(f.run.snapshot().requests[0].outcome,'unknown');
 const timed=await fetch(f.url+'/fixture/auth/slow',{method:'POST',body:'{"intent":"b"}'});assert.equal(timed.status,503);await timed.text();assert.equal(received,2);assert.equal(f.run.snapshot().requests[1].outcome,'unknown');
 const again=await fetch(f.url+'/fixture/auth/slow',{method:'POST',body:'{"intent":"b"}'});assert.equal(again.status,409);await again.text();assert.equal(received,2);
});

test('read-only fixture budget inspection exposes counts without auth traffic or credential data',async t=>{
 let received=0;const f=await wire(t,(_req,res)=>{received++;res.end('{}');});
 const response=await fetch(f.url+'/n00-fixture-budget');assert.equal(response.status,200);const report=await response.json();
 assert.equal(report.fixture_only,true);assert.equal(report.reserved,0);assert.equal(report.forwarded,0);assert.equal(report.limit,200);assert.equal(report.cleanup_reserve,20);assert.equal(received,0);assert.equal(f.run.snapshot().requests.length,0);
 assert.doesNotMatch(JSON.stringify(report),/COOKIE_SECRET|session=|fixture-http-|neon_auth_session_verifier/);
});

test('concurrent identical fixture POSTs share the in-flight barrier before upstream acceptance is known',async t=>{
 let release,notify,received=0;const started=new Promise(ok=>{notify=ok;});
 const f=await wire(t,async(req,res)=>{for await(const chunk of req)assert.ok(chunk.length>0);received++;if(received===1){release=()=>res.end('{}');notify();}else res.end('{}');});
 const post={method:'POST',body:'{"same":"fixture-intent"}'};const first=fetch(f.url+'/fixture/auth/sign-in/social',post);await started;
 try {const second=await fetch(f.url+'/fixture/auth/sign-in/social',post);assert.equal(second.status,409);await second.text();assert.equal(received,1);}
 finally {release();const response=await first;assert.equal(response.status,200);await response.text();}
});

test('fixture cleanup control requires the exact local owner nonce and never forwards to backend',async t=>{
 let stops=0,received=0;const owner='aabbccddeeff';const f=await wire(t,(_req,res)=>{received++;res.end('{}');},{stopNonce:owner,onStop:()=>{stops++;}});
 const refused=await fetch(f.url+'/n00-fixture-stop',{method:'POST',headers:{'X-N00-Owner':'different'}});assert.equal(refused.status,403);await refused.text();assert.equal(stops,0);
 const accepted=await fetch(f.url+'/n00-fixture-stop',{method:'POST',headers:{'X-N00-Owner':owner}});assert.equal(accepted.status,200);await accepted.text();assert.equal(stops,1);assert.equal(received,0);assert.equal(f.run.snapshot().requests.length,0);
});
