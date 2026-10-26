import test from 'node:test';
import assert from 'node:assert/strict';
import {getEventListeners} from 'node:events';
import {loadModule} from './ts-loader.mjs';

const {createLiveClient, LiveCancelled, LiveError}=await loadModule('services/live/client.ts');
const flush=()=>new Promise(setImmediate);
const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};};
const ok=()=>Response.json({data_mode:'live',request_id:'fixture',data:{saved:true}});
function observe(promise){
  const result={};
  promise.then(value=>{result.value=value;},error=>{result.error=error;});
  return result;
}
function timeout(result){
  assert.ok(result.error instanceof LiveError,'the request must settle with a typed error');
  assert.equal(result.error.code,'REQUEST_TIMEOUT');
  assert.equal(result.error.status,0);
  assert.equal(result.error.retryable,true);
}
function clock(t){t.mock.timers.enable({apis:['setTimeout']});}

test('a stalled read aborts at 30 seconds and releases the caller even when fetch ignores abort',async t=>{
  clock(t);let signal,calls=0;
  const client=createLiveClient(async(_url,init)=>{calls++;signal=init.signal;return new Promise(()=>{});});
  const result=observe(client.request({path:'/v1/workspaces',scope:'A',token:'fixture'}));
  t.mock.timers.tick(29_999);await flush();assert.equal(result.error,undefined);
  t.mock.timers.tick(1);await flush();timeout(result);assert.equal(signal.aborted,true);
  assert.equal(calls,1);
});

test('transport AbortError from a deadline remains a visible timeout rather than silent cancellation',async t=>{
  clock(t);
  const client=createLiveClient(async(_url,init)=>new Promise((_resolve,reject)=>{
    init.signal.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError')),{once:true});
  }));
  const result=observe(client.request({path:'/v1/fixture',scope:'A'}));
  t.mock.timers.tick(30_000);await flush();timeout(result);
});

test('a timed-out idempotent write is not replayed and can be reconciled with the same intent',async t=>{
  clock(t);const requests=[];
  const client=createLiveClient(async(_url,init)=>{requests.push(init);return requests.length===1?new Promise(()=>{}):ok();});
  const command={path:'/v1/drafts/fixture',method:'PATCH',scope:'A',token:'fixture',idempotencyKey:'same-command',ifMatch:'v1',body:{body:'edited'}};
  const result=observe(client.request(command));
  t.mock.timers.tick(30_000);await flush();assert.equal(result.error,undefined);
  t.mock.timers.tick(90_000);await flush();timeout(result);assert.equal(requests.length,1);
  assert.equal(requests[0].signal.aborted,true);
  assert.deepEqual(await client.request(command),{saved:true});
  assert.equal(requests.length,2);
  assert.equal(requests[1].headers['Idempotency-Key'],'same-command');
  assert.equal(requests[1].headers['X-BuyerOS-If-Match'],'v1');
  assert.equal(requests[1].body,requests[0].body);
});

for(const mode of ['json success','json error','text success','text error'])test(`the deadline includes a stalled ${mode} body`,async t=>{
  clock(t);let signal;
  const error=mode.endsWith('error'),text=mode.startsWith('text');
  const client=createLiveClient(async(_url,init)=>{
    signal=init.signal;
    return new Response(new ReadableStream({start(controller){controller.enqueue(new TextEncoder().encode(text&&!error?'partial':'{'));}}),
      {status:error?503:200,headers:{'Content-Type':text&&!error?'text/plain':'application/json'}});
  });
  const args={path:'/v1/export',scope:'A'};
  const result=observe(text?client.requestContent(args):client.request(args));
  await flush();t.mock.timers.tick(30_000);await flush();timeout(result);
  assert.equal(signal.aborted,true);
});

for(const text of [false,true])test(`caller cancellation releases a stalled ${text?'export':'JSON request'} without an error toast`,async t=>{
  clock(t);const own=new AbortController();let signal;
  const client=createLiveClient(async(_url,init)=>{signal=init.signal;return new Promise(()=>{});});
  const args={path:'/v1/fixture',scope:'A',signal:own.signal};
  const result=observe(text?client.requestContent(args):client.request(args));
  own.abort();await flush();assert.ok(result.error instanceof LiveCancelled);
  assert.equal(signal.aborted,true);assert.equal(getEventListeners(own.signal,'abort').length,0);
  t.mock.timers.tick(120_000);await flush();assert.ok(result.error instanceof LiveCancelled);
});

test('an already-cancelled request never starts transport',async t=>{
  clock(t);const own=new AbortController();own.abort();let calls=0;
  const client=createLiveClient(async()=>{calls++;return ok();});
  await assert.rejects(client.request({path:'/v1/fixture',scope:'A',signal:own.signal}),LiveCancelled);
  await assert.rejects(client.requestContent({path:'/v1/fixture',scope:'A',signal:own.signal}),LiveCancelled);
  assert.equal(calls,0);
});

test('the original deadline includes stalled authentication recovery and prevents a late replay',async t=>{
  clock(t);const refresh=deferred();let calls=0,invalidations=0;
  const client=createLiveClient(async()=>{calls++;return Response.json({}, {status:401});},'',{
    refresh:()=>refresh.promise,isCurrent:()=>true,onUnauthorized:()=>invalidations++,
  });
  const result=observe(client.request({path:'/v1/fixture',scope:'A',token:'old'}));
  await flush();t.mock.timers.tick(30_000);await flush();timeout(result);
  refresh.resolve('new');await flush();assert.equal(calls,1);assert.equal(invalidations,0);
});

test('a failed token refresh after cancellation cannot invalidate the current session',async t=>{
  clock(t);const own=new AbortController(),refresh=deferred();let calls=0,invalidations=0;
  const client=createLiveClient(async()=>{calls++;return Response.json({}, {status:401});},'',{
    refresh:()=>refresh.promise,isCurrent:()=>true,onUnauthorized:()=>invalidations++,
  });
  const result=observe(client.request({path:'/v1/fixture',scope:'A',token:'old',signal:own.signal}));
  await flush();own.abort();await flush();assert.ok(result.error instanceof LiveCancelled);
  refresh.reject(new Error('late refresh failure'));await flush();
  assert.equal(calls,1);assert.equal(invalidations,0);
});

test('401 refresh and replay share one deadline rather than resetting the clock',async t=>{
  clock(t);const first=deferred(),refresh=deferred(),second=deferred();let calls=0;
  const client=createLiveClient(async()=>++calls===1?first.promise:second.promise,'',{
    refresh:()=>refresh.promise,isCurrent:()=>true,
  });
  const result=observe(client.request({path:'/v1/fixture',scope:'A',token:'old'}));
  t.mock.timers.tick(15_000);first.resolve(Response.json({}, {status:401}));await flush();
  t.mock.timers.tick(10_000);refresh.resolve('new');await flush();assert.equal(calls,2);
  t.mock.timers.tick(5_000);await flush();timeout(result);
  second.resolve(ok());await flush();assert.equal(result.value,undefined);
});

for(const status of [401,403,404])test(`a late ${status} response after cancellation has no auth or access side effects`,async t=>{
  clock(t);const own=new AbortController(),fetching=deferred();let refreshes=0,invalidations=0,denials=0;
  const client=createLiveClient(()=>fetching.promise,'',{
    refresh:async()=>{refreshes++;return 'new';},isCurrent:()=>true,onUnauthorized:()=>invalidations++,
  });
  client.subscribeAccessDenied(()=>denials++);
  // An unsafe write exercises the initial-401 invalidation branch as well.
  const result=observe(client.request({path:'/v1/workspaces/fixture/buyers',scope:'A',token:'old',method:'POST',body:{},signal:own.signal}));
  own.abort();await flush();assert.ok(result.error instanceof LiveCancelled);
  fetching.resolve(Response.json({}, {status}));await flush();
  assert.equal(refreshes,0);assert.equal(invalidations,0);assert.equal(denials,0);
});

test('a late export denial body cannot revoke access after its deadline',async t=>{
  clock(t);const body=deferred();let denials=0;
  const client=createLiveClient(async()=>({ok:false,status:403,headers:new Headers(),json:()=>body.promise}));
  client.subscribeAccessDenied(()=>denials++);
  const result=observe(client.requestContent({path:'/v1/workspaces/fixture/export',scope:'A'}));
  await flush();t.mock.timers.tick(30_000);await flush();timeout(result);
  body.resolve({code:'PERMISSION_DENIED'});await flush();assert.equal(denials,0);
});

test('success and HTTP failure release lifecycle listeners and cancel their timers',async t=>{
  clock(t);
  for(const text of [false,true])for(const success of [false,true]){
    const own=new AbortController();let signal;
    const client=createLiveClient(async(_url,init)=>{
      signal=init.signal;
      return success?(text?new Response('export',{headers:{'Content-Type':'text/plain'}}):ok()):Response.json({code:'DENIED'},{status:403});
    });
    const args={path:'/v1/fixture',scope:'A',signal:own.signal};
    const result=observe(text?client.requestContent(args):client.request(args));await flush();
    if(success)assert.deepEqual(result.value,text?{text:'export',contentType:'text/plain'}:{saved:true});
    else assert.equal(result.error.status,403);
    assert.equal(getEventListeners(own.signal,'abort').length,0);
    t.mock.timers.tick(120_000);await flush();assert.equal(signal.aborted,false);
    own.abort();assert.equal(signal.aborted,false);
  }
});
