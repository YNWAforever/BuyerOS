import test from 'node:test';
import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';
const {startJobPoller}=await loadModule('services/live/job-poller.ts');
const {LiveError,createLiveClient}=await loadModule('services/live/client.ts');
const {SessionScope}=await loadModule('services/live/session.ts');
import {fixtureClock,flush} from './fixtures/job-clock.mjs';
const running={id:'job-a',status:'running',requested:1000,processed:1000};
function setup(extra={}){const f=fixtureClock(),controller=new AbortController(),visibility=new EventTarget();return {...f,controller,visibility,options:{signal:controller.signal,isVisible:()=>true,visibilityTarget:visibility,clock:f.clock,...extra}};}

test('B12 2.5s RTT has one in-flight and waits 2s after settlement',async()=>{
 const f=setup(),calls=[],values=[];let inFlight=0,max=0;
 const stop=startJobPoller({...f.options,fetchSummary:async signal=>{calls.push(f.clock.now());max=Math.max(max,++inFlight);try{return await f.latency(2500,running,signal);}finally{inFlight--;}} ,onValue:v=>values.push(v),onError:assert.fail});
 await f.advance(2499);assert.equal(calls.length,1);assert.equal(values.length,0);await f.advance(1);assert.equal(values.length,1);
 await f.advance(1999);assert.equal(calls.length,1);await f.advance(1);assert.equal(calls.length,2);await f.advance(20_000);
 assert.equal(max,1);assert.ok(calls.every((v,i)=>i===0||v-calls[i-1]===4500));stop();await flush();assert.equal(inFlight,0);
});

test('B13 hidden pauses/aborts quietly; repeated visibility signals resume once',async()=>{
 let visible=false;const f=setup({isVisible:()=>visible}),values=[],errors=[];let calls=0;
 const stop=startJobPoller({...f.options,fetchSummary:signal=>{calls++;return f.latency(2500,running,signal);},onValue:v=>values.push(v),onError:e=>errors.push(e)});
 await f.advance(60_000);assert.equal(calls,0);visible=true;f.visibility.dispatchEvent(new Event('visibilitychange'));f.visibility.dispatchEvent(new Event('visibilitychange'));await flush();assert.equal(calls,1);
 visible=false;f.visibility.dispatchEvent(new Event('visibilitychange'));await f.advance(60_000);assert.equal(calls,1);assert.equal(errors.length,0);assert.equal(values.length,0);
 visible=true;f.visibility.dispatchEvent(new Event('visibilitychange'));await f.advance(2500);assert.equal(calls,2);assert.equal(values.length,1);stop();
});

test('B13 transient failures use 2/4/8/16/30/30s and reset after success',async()=>{
 const f=setup(),calls=[],errors=[];
 const stop=startJobPoller({...f.options,fetchSummary:async()=>{calls.push(f.clock.now());if(calls.length<=6)throw new LiveError('outage','UNAVAILABLE',503,'fixture',true);return running;},onValue:()=>{},onError:e=>errors.push(e)});
 await flush();for(const delay of [2000,4000,8000,16000,30000,30000])await f.advance(delay);
 assert.equal(calls.length,7);assert.deepEqual(calls.slice(1).map((v,i)=>v-calls[i]),[2000,4000,8000,16000,30000,30000]);assert.equal(errors.length,6);
 await f.advance(2000);assert.equal(calls.length,8);stop();
});

test('B13 429 honors Retry-After seconds and HTTP dates, invalid header uses backoff',async()=>{
 for(const [header,delay] of [['12',12000],['Sat, 03 Oct 2026 00:00:20 GMT',20000],['invalid',2000]]){
  const f=setup(),calls=[];const stop=startJobPoller({...f.options,fetchSummary:async()=>{calls.push(f.clock.now());if(calls.length===1)throw new LiveError('limit','RATE_LIMITED',429,'fixture',true,header);return running;},onValue:()=>{},onError:()=>{}});
  await flush();await f.advance(delay-1);assert.equal(calls.length,1,header);await f.advance(1);assert.equal(calls.length,2,header);stop();
 }
});

test('B13 actual live client preserves Retry-After metadata without response secrets',async()=>{
 for(const header of ['12','Sat, 03 Oct 2026 00:00:20 GMT']){
  const client=createLiveClient(async()=>new Response(JSON.stringify({code:'RATE_LIMITED',message:'limit',request_id:'fixture',retryable:true}),{status:429,headers:{'Retry-After':header}}));
  await assert.rejects(client.request({path:'/jobs/a/summary',scope:'fixture'}),e=>e instanceof LiveError&&e.retryAfter===header&&e.status===429);
 }
});

test('B12 request timeout aborts before a retry and late value is ignored',async()=>{
 const f=setup(),errors=[];let calls=0,inFlight=0,max=0;
 const stop=startJobPoller({...f.options,fetchSummary:async signal=>{calls++;max=Math.max(max,++inFlight);try{return await f.latency(20_000,running,signal);}finally{inFlight--;}} ,onValue:assert.fail,onError:e=>errors.push(e)});
 await f.advance(10_000);assert.equal(errors.length,1);assert.equal(inFlight,0);await f.advance(1999);assert.equal(calls,1);await f.advance(1);assert.equal(calls,2);assert.equal(max,1);stop();await flush();assert.equal(errors.length,1);
});

test('B12 cancel/unmount suppresses late values/errors and all later requests',async()=>{
 const f=setup(),values=[],errors=[];let calls=0;
 startJobPoller({...f.options,fetchSummary:()=>{calls++;return f.latency(2500,running);},onValue:v=>values.push(v),onError:e=>errors.push(e)});
 await flush();f.controller.abort();await f.advance(60_000);assert.equal(calls,1);assert.deepEqual(values,[]);assert.deepEqual(errors,[]);
});

test('B16 A-B-A lifetimes reject the obsolete result even with same scope IDs',async()=>{
 const f=setup(),session=new SessionScope({mode:'live',actor:'actor',workspace:'A',project:'p'});session.setToken('memory');const values=[];
 const begin=(delay,value)=>{const ctx=session.captureWriteContext();return startJobPoller({...f.options,signal:ctx.signal,fetchSummary:()=>f.latency(delay,value),onValue:v=>{if(session.isCurrent(ctx.identity))values.push(v.id);},onError:assert.fail});};
 begin(8000,{...running,id:'old-A'});await flush();session.next({workspace:'B'});begin(5000,{...running,id:'B'});await flush();session.next({workspace:'A'});const stop=begin(100,{...running,id:'new-A',status:'completed'});
 await f.advance(10_000);assert.deepEqual(values,['new-A']);stop();
});

test('B12 terminal summary is delivered once and stops through refresh/visibility changes',async()=>{
 for(const status of ['completed','failed','cancelled']){
  const f=setup(),values=[];let calls=0;const stop=startJobPoller({...f.options,fetchSummary:async()=>{calls++;return {...running,status};},onValue:v=>values.push(v),onError:assert.fail});
  await flush();f.visibility.dispatchEvent(new Event('visibilitychange'));await f.advance(60_000);assert.equal(calls,1);assert.equal(values.length,1);stop();
 }
});

test('B13 access denied stops rather than polling a revoked account',async()=>{
 for(const status of [401,403,404]){
  const f=setup();let calls=0,errors=0;const stop=startJobPoller({...f.options,fetchSummary:async()=>{calls++;throw new LiveError('access','NOT_FOUND',status,'fixture',false);},onValue:assert.fail,onError:()=>errors++});
  await f.advance(60_000);assert.equal(calls,1);assert.equal(errors,1);stop();
 }
});


test('B13 rapid hidden-visible during abort settlement resumes once immediately',async()=>{
 let visible=true;const f=setup({isVisible:()=>visible});let calls=0;
 const stop=startJobPoller({...f.options,fetchSummary:signal=>{calls++;return f.latency(2500,running,signal);},onValue:()=>{},onError:assert.fail});
 await flush();assert.equal(calls,1);visible=false;f.visibility.dispatchEvent(new Event('visibilitychange'));visible=true;f.visibility.dispatchEvent(new Event('visibilitychange'));f.visibility.dispatchEvent(new Event('visibilitychange'));await flush();
 assert.equal(calls,2);stop();await flush();
});
