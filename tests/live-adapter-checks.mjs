import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';

let checks=0;
// Async by necessity: several checks await a deferred response. A sync harness would let those
// assertions run after the summary and turn a failure into an unhandled rejection.
async function test(name,fn){await fn();checks++;console.log('PASS '+name);}
const mode=await loadModule('services/live/mode.ts');

await test('apiBaseUrl absent or blank resolves to demo',()=>{
  assert.equal(mode.resolveMode(undefined),'demo');
  assert.equal(mode.resolveMode(null),'demo');
  assert.equal(mode.resolveMode(''),'demo');
  assert.equal(mode.resolveMode('   '),'demo');
});

await test('a configured apiBaseUrl resolves to live',()=>{
  assert.equal(mode.resolveMode('https://api.example.test'),'live');
});

await test('demo mode makes every section available, live mode does not',()=>{
  const sections=['overview','discovery','lists','outreach','results','settings'];
  for(const s of sections)assert.equal(mode.availabilityFor('demo',s),'available');
  assert.equal(mode.availabilityFor('live','overview'),'available');
  for(const s of ['discovery','lists','outreach','results'])assert.equal(mode.availabilityFor('live',s),'unavailable');
});

await test('live without a ready session reports not_configured, never available',()=>{
  assert.equal(mode.availabilityFor('live','overview',false),'not_configured');
  assert.equal(mode.availabilityFor('live','overview',true),'available');
});

await test('unavailable and not_configured are distinct states',()=>{
  assert.notEqual(mode.availabilityFor('live','outreach'),mode.availabilityFor('live','overview',false));
});

const map=await loadModule('services/live/mapping.ts');

await test('workspaces map to the narrow model',()=>{
  const payload={items:[{id:'ws-1',name:'Acme',roles:['viewer'],data_mode:'live'}],offset:0,limit:1,total:1};
  assert.deepEqual(map.toWorkspaces(payload),[{id:'ws-1',name:'Acme',roles:['viewer']}]);
});

await test('projects map to the narrow model',()=>{
  const payload={items:[{id:'p-1',name:'Sensors',status:'active'}],offset:0,limit:1,total:1};
  assert.deepEqual(map.toProjects(payload),[{id:'p-1',name:'Sensors',status:'active'}]);
});

await test('icp versions map approved_at to approvedAt and keep the hash',()=>{
  const payload={items:[{id:'i-1',number:2,content_hash:'sha256:aa',status:'approved',approved_at:'2026-09-01T00:00:00Z'}],offset:0,limit:1,total:1};
  assert.deepEqual(map.toIcpVersions(payload),[{id:'i-1',number:2,contentHash:'sha256:aa',status:'approved',approvedAt:'2026-09-01T00:00:00Z'}]);
});

await test('buyers map to the narrow model and keep a null note as null',()=>{
  const payload={items:[{id:'b-1',name:'Example GmbH',note:null}],offset:0,limit:1,total:1};
  assert.deepEqual(map.toBuyers(payload),[{id:'b-1',name:'Example GmbH',note:null}]);
});

await test('a missing required field raises instead of becoming an empty value',()=>{
  assert.throws(()=>map.toBuyers({items:[{id:'b-1',note:null}],offset:0,limit:1,total:1}),map.MapError);
  assert.throws(()=>map.toWorkspaces({items:[{name:'no id'}]}),map.MapError);
  assert.throws(()=>map.toBuyers({items:null}),map.MapError);
  assert.throws(()=>map.toBuyers(undefined),map.MapError);
});

await test('every mapper enforces its required fields',()=>{
  assert.throws(()=>map.toProjects({items:[{id:'p-1',name:'Sensors'}]}),map.MapError);
  assert.throws(()=>map.toIcpVersions({items:[{id:'i-1',content_hash:'h',status:'s'}]}),map.MapError);
  assert.throws(()=>map.toBuyers({items:['not-an-object']}),map.MapError);
});

await test('a workspace missing roles raises rather than defaulting to an empty list',()=>{
  assert.throws(()=>map.toWorkspaces({items:[{id:'w-1',name:'Acme'}]}),map.MapError);
  assert.throws(()=>map.toWorkspaces({items:[{id:'w-1',name:'Acme',roles:['viewer',7]}]}),map.MapError);
});

await test('a version without an approval date maps to null, not an error',()=>{
  assert.deepEqual(
    map.toIcpVersions({items:[{id:'i-1',number:1,content_hash:'h',status:'saved'}]}),
    [{id:'i-1',number:1,contentHash:'h',status:'saved',approvedAt:null}],
  );
});

await test('an empty page is empty, not an error',()=>{
  assert.deepEqual(map.toBuyers({items:[],offset:0,limit:0,total:0}),[]);
});

const live=await loadModule('services/live/client.ts');

function responder(handler){return async (url,init)=>{await handler(url,init);return {status:200,ok:true,json:async()=>({data:{ok:true},request_id:'r-1',data_mode:'live'})};};}
function errorResponder(status,body){return async ()=>({status,ok:false,json:async()=>body});}

await test('a success unwraps data and sends the bearer only when a token is present',async()=>{
  const seen=[];
  const client=live.createLiveClient(responder((url,init)=>seen.push(init.headers)));
  const out=await client.request({path:'/v1/workspaces',scope:'s1',token:'tok-1'});
  assert.deepEqual(out,{ok:true});
  assert.equal(seen[0].Authorization,'Bearer tok-1');
  await client.request({path:'/v1/workspaces',scope:'s1'});
  assert.equal(seen[1].Authorization,undefined);
});

await test('an error envelope becomes a typed LiveError keyed by code',async()=>{
  const client=live.createLiveClient(errorResponder(503,{code:'PROVIDER_UNAVAILABLE',message:'down',request_id:'r-9',retryable:true}));
  await assert.rejects(()=>client.request({path:'/v1/workspaces',scope:'s1'}),e=>{
    assert.ok(e instanceof live.LiveError);
    assert.equal(e.code,'PROVIDER_UNAVAILABLE');
    assert.equal(e.status,503);
    assert.equal(e.retryable,true);
    assert.equal(e.requestId,'r-9');
    return true;
  });
});

await test('a non-envelope body still yields a typed error, never a crash',async()=>{
  const client=live.createLiveClient(errorResponder(500,'<html>oops</html>'));// json() will throw
  await assert.rejects(()=>client.request({path:'/v1/workspaces',scope:'s1'}),e=>e instanceof live.LiveError&&e.status===500);
});

await test('an aborted request surfaces as LiveCancelled, not as an error toast',async()=>{
  const client=live.createLiveClient(async()=>{const e=new Error('aborted');e.name='AbortError';throw e;});
  await assert.rejects(()=>client.request({path:'/v1/workspaces',scope:'s1'}),e=>e instanceof live.LiveCancelled);
});

await test('a network failure is a retryable error, not a cancellation',async()=>{
  // read.ts classifies on retryable/status, so this branch must be pinned, not merely implemented.
  const client=live.createLiveClient(async()=>{throw new TypeError('failed to fetch');});
  await assert.rejects(()=>client.request({path:'/v1/workspaces',scope:'s1'}),e=>{
    assert.ok(e instanceof live.LiveError);
    assert.equal(e.code,'NETWORK_ERROR');
    assert.equal(e.status,0);
    assert.equal(e.retryable,true);
    return true;
  });
});

const {SessionScope,scopeKey}=await loadModule('services/live/session.ts');

await test('scopeKey encodes mode, actor, workspace and project',()=>{
  assert.equal(scopeKey({mode:'live',actor:'a',workspace:'w',project:'p'}),'live:a:w:p');
  assert.equal(scopeKey({mode:'demo',actor:'',workspace:null,project:null}),'demo::-:-');
});

await test('changing workspace advances the identity and aborts the previous controller',()=>{
  const session=new SessionScope({mode:'live',actor:'a'});
  const first=session.next({workspace:'w1'});
  assert.equal(first.previous.signal.aborted,true);
  assert.equal(session.isCurrent(first.identity),true);
  const second=session.next({workspace:'w2'});
  assert.equal(second.previous,first.controller);
  assert.equal(second.previous.signal.aborted,true);
  assert.equal(session.isCurrent(first.identity),false);
});

await test('a stale identity is not current, so a late response can be discarded',()=>{
  const session=new SessionScope({mode:'live',actor:'a'});
  const stale=session.next({workspace:'w1'}).identity;
  session.next({workspace:'w2'});
  assert.equal(session.isCurrent(stale),false);
});

await test('returning to a previously visited workspace is a NEW scope, not the old one',()=>{
  const session=new SessionScope({mode:'live',actor:'a'});
  const firstA=session.next({workspace:'A'}).identity;
  session.next({workspace:'B'});
  const secondA=session.next({workspace:'A'}).identity;
  // Same value key, different generation: the earlier visit's response must not be accepted.
  assert.equal(scopeKey(session.current()),'live:a:A:-');
  assert.notEqual(firstA,secondA);
  assert.equal(session.isCurrent(firstA),false);
  assert.equal(session.isCurrent(secondA),true);
});

await test('the token lives in the session and survives a scope change',()=>{
  // The token identifies the actor, not the scope: switching workspace must not force
  // re-authentication. `next()` therefore keeps it; only an explicit setToken clears it.
  const session=new SessionScope({mode:'live',actor:'a'});
  session.setToken('tok');
  assert.equal(session.token(),'tok');
  session.next({workspace:'w2'});
  assert.equal(session.token(),'tok');
  session.setToken(undefined);
  assert.equal(session.token(),undefined);
});

console.log(`${checks} live adapter checks passed`);
