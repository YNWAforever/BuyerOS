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

const {loadLive}=await loadModule('services/live/read.ts');

function fakeStore(){return {touched:false,get companies(){this.touched=true;throw new Error('demo store consulted');}};}
function authed(){const s=new SessionScope({mode:'live',actor:'a'});s.setToken('tok');s.next({workspace:'w1'});return s;}

await test('live failure surfaces the error with zero data and never touches the demo store',async()=>{
  const store=fakeStore();
  const client=live.createLiveClient(errorResponder(503,{code:'PROVIDER_UNAVAILABLE',message:'down',request_id:'r',retryable:true}));
  const result=await loadLive({client,session:authed(),section:'overview',path:'/v1/workspaces',store});
  assert.equal(result.value,undefined);
  assert.equal(store.touched,false);
  assert.equal(result.error.code,'PROVIDER_UNAVAILABLE');
  assert.equal(result.availability,'transient');
});

await test('a 501 from a supported section marks it unavailable rather than failing',async()=>{
  // section 'overview' IS live-supported, so the 501 must come from the response, not from availability.
  const client=live.createLiveClient(errorResponder(501,{code:'NOT_IMPLEMENTED',message:'no',request_id:'r',retryable:false}));
  const result=await loadLive({client,session:authed(),section:'overview',path:'/v1/workspaces',store:fakeStore()});
  assert.equal(result.availability,'unavailable');
  assert.equal(result.value,undefined);
});

await test('a section with no backing operation is unavailable without a request',async()=>{
  let calls=0;
  const client={request:async()=>{calls++;return {};}};
  const result=await loadLive({client,session:authed(),section:'discovery',path:'/v1/x',store:fakeStore()});
  assert.equal(result.availability,'unavailable');
  assert.equal(calls,0);
});

await test('a response whose scope changed underneath is discarded',async()=>{
  const session=authed();
  let release;const gate=new Promise(r=>{release=r;});
  const client={request:async()=>{await gate;return {items:[{id:'b-1',name:'A',note:null}]};}};
  const pending=loadLive({client,session,section:'overview',path:'/v1/workspaces',store:fakeStore()});
  session.next({workspace:'B'});
  release();
  const result=await pending;
  assert.equal(result.value,undefined);
  assert.equal(result.discarded,true);
});

await test('no token means not_configured and no request is sent',async()=>{
  let calls=0;
  const client={request:async()=>{calls++;return {};}};
  const session=new SessionScope({mode:'live',actor:'a'});
  session.next({workspace:'w1'});
  const result=await loadLive({client,session,section:'overview',path:'/v1/workspaces',store:fakeStore()});
  assert.equal(result.availability,'not_configured');
  assert.equal(calls,0);
});

await test('each API failure code maps to its own state',async()=>{
  const cases=[[401,'UNAUTHENTICATED','denied'],[403,'PERMISSION_DENIED','denied'],[404,'NOT_FOUND','not_found'],[503,'PROVIDER_UNAVAILABLE','transient'],[501,'NOT_IMPLEMENTED','unavailable']];
  for(const [status,code,expected] of cases){
    const client=live.createLiveClient(errorResponder(status,{code,message:'m',request_id:'r',retryable:status===503}));
    const result=await loadLive({client,session:authed(),section:'overview',path:'/v1/workspaces',store:fakeStore()});
    assert.equal(result.availability,expected,code);
    assert.equal(result.value,undefined,code);
  }
});

await test('a 401 is a sign-in requirement, never not_configured',async()=>{
  // not_configured means "live is off and no request was made"; a 401 means a token was rejected.
  const client=live.createLiveClient(errorResponder(401,{code:'UNAUTHENTICATED',message:'m',request_id:'r',retryable:false}));
  const result=await loadLive({client,session:authed(),section:'overview',path:'/v1/workspaces',store:fakeStore()});
  assert.equal(result.availability,'denied');
  assert.notEqual(result.availability,'not_configured');
});

await test('a 404 is not_found, never denied',async()=>{
  // A non-enumerating 404 for a foreign resource is "not found", not "refused".
  const client=live.createLiveClient(errorResponder(404,{code:'NOT_FOUND',message:'m',request_id:'r',retryable:false}));
  const result=await loadLive({client,session:authed(),section:'overview',path:'/v1/workspaces',store:fakeStore()});
  assert.equal(result.availability,'not_found');
  assert.notEqual(result.availability,'denied');
});

await test('a cancelled request is discarded, not an error',async()=>{
  const client=live.createLiveClient(async()=>{const e=new Error('aborted');e.name='AbortError';throw e;});
  const result=await loadLive({client,session:authed(),section:'overview',path:'/v1/workspaces',store:fakeStore()});
  assert.equal(result.discarded,true);
  assert.equal(result.error,undefined);
});

await test('the read attaches to the session controller signal',async()=>{
  let seen;
  const client={request:async(args)=>{seen=args.signal;return {items:[]};}};
  const session=authed();
  await loadLive({client,session,section:'overview',path:'/v1/workspaces',store:fakeStore()});
  assert.equal(seen,session.controller().signal);
});

const storage=await loadModule('services/live/storage.ts');

await test('live mode refuses to read or write any demo storage key',()=>{
  const calls=[];
  const fake={getItem:k=>{calls.push('get:'+k);return null;},setItem:(k)=>{calls.push('set:'+k);}};
  storage.readDemoState(fake,'live');
  storage.writePrefs(fake,'live',{locale:'en'});
  assert.deepEqual(calls,[]);
});

await test('demo mode still reads and writes its own keys',()=>{
  const calls=[];
  const fake={getItem:k=>{calls.push('get:'+k);return null;},setItem:(k)=>{calls.push('set:'+k);}};
  storage.readDemoState(fake,'demo');
  storage.writePrefs(fake,'demo',{locale:'zh-HK'});
  assert.ok(calls.some(c=>c==='get:buyeros-demo-v1'));
  assert.ok(calls.some(c=>c==='set:buyeros-prefs-v1'));
});

await test('no token-shaped value is ever written to storage',()=>{
  const written=[];
  const fake={getItem:()=>null,setItem:(k,v)=>{written.push([k,String(v)]);}};
  storage.writePrefs(fake,'demo',{locale:'en'});
  assert.equal(written.some(([,v])=>/bearer|eyJ|token/i.test(v)),false);
});

await test('live requests are addressed to the configured API base URL',async()=>{
  // Without this the live path would silently call the app's own origin.
  const seen=[];
  const client=live.createLiveClient(async(url)=>{seen.push(String(url));return {ok:true,json:async()=>({data:{},request_id:'r',data_mode:'live'})};},'https://api.example.test/');
  await client.request({path:'/v1/workspaces',scope:'s1'});
  assert.equal(seen[0],'https://api.example.test/v1/workspaces');
});

await test('with no base URL the path is used as-is',async()=>{
  const seen=[];
  const client=live.createLiveClient(async(url)=>{seen.push(String(url));return {ok:true,json:async()=>({data:{},request_id:'r',data_mode:'live'})};});
  await client.request({path:'/v1/workspaces',scope:'s1'});
  assert.equal(seen[0],'/v1/workspaces');
});

const ws=await loadModule('services/live/workspace-logic.ts');

await test('demo-only effects are enabled only in demo mode',()=>{
  assert.equal(ws.demoEffectsEnabled('demo'),true);
  assert.equal(ws.demoEffectsEnabled('live'),false);
});

await test('the empty live store contains no companies and no demo identifiers',()=>{
  const s=ws.emptyStore();
  assert.deepEqual(s.companies,[]);
  assert.equal(s.budget,0);
  assert.equal(s.locale,'en');
});

await test('the banner label states the real mode and cannot be made to claim live',()=>{
  // Pin the leading mode word: the demo banner legitimately mentions "live" in
  // "No live services connected", so a substring test would be meaningless.
  assert.match(ws.modeBanner('demo'),/^demo mode\b/i);
  assert.match(ws.modeBanner('live'),/^live mode\b/i);
});

console.log(`${checks} live adapter checks passed`);
