import test from 'node:test';
import assert from 'node:assert/strict';
import {loadModule} from '../tests/ts-loader.mjs';
import {fixtureClock,flush} from '../tests/fixtures/job-clock.mjs';
const {startJobPoller}=await loadModule('test-results/q06-manual-poller.ts');
const {LiveError}=await loadModule('services/live/client.ts');
test('manual rollback reads once, remains idle60s, explicit refresh reads once again',async()=>{
 const f=fixtureClock(),visibility=new EventTarget(),controller=new AbortController();let calls=0;
 const options={clock:f.clock,visibilityTarget:visibility,signal:controller.signal,isVisible:()=>true,fetchSummary:async()=>{calls++;return {status:'running'};},onValue:()=>{},onError:assert.fail};
 let stop=startJobPoller(options);await flush();await f.advance(60_000);assert.equal(calls,1);visibility.dispatchEvent(new Event('visibilitychange'));await f.advance(60_000);assert.equal(calls,1);
 stop();stop=startJobPoller(options);await flush();assert.equal(calls,2);stop();
});
test('manual rollback reports error once without automatic retry',async()=>{
 const f=fixtureClock();let calls=0,errors=0;
 const stop=startJobPoller({clock:f.clock,signal:new AbortController().signal,isVisible:()=>true,fetchSummary:async()=>{calls++;throw new LiveError('fixture','UNAVAILABLE',503,'fixture',true);},onValue:assert.fail,onError:()=>errors++});
 await f.advance(60_000);assert.equal(calls,1);assert.equal(errors,1);stop();
});
test('manual rollback aborts obsolete response without materializing it',async()=>{
 const f=fixtureClock(),controller=new AbortController();let values=0;
 startJobPoller({clock:f.clock,signal:controller.signal,isVisible:()=>true,fetchSummary:signal=>f.latency(2500,{status:'running'},signal),onValue:()=>values++,onError:assert.fail});
 controller.abort();await f.advance(60_000);assert.equal(values,0);
});
