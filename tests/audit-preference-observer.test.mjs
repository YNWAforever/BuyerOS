import test from 'node:test';
import assert from 'node:assert/strict';
import * as observer from './e2e/fixtures/journey-input.ts';
const {createDocumentReads}=observer;

test('keyboard locale observer discards a body lost by actual document replacement and awaits the new real read',async()=>{
 const tracker=createDocumentReads(),oldRequest={};tracker.start(oldRequest);let reject;
 tracker.record(oldRequest,()=>new Promise((_,r)=>{reject=r;}));const stale=tracker.latest();
 tracker.advance();reject(new Error('Network.getResponseBody: navigated away'));
 assert.equal(await stale,undefined);const current={};tracker.start(current);tracker.record(current,async()=>({data:{locale:'zh-HK'}}));
 assert.deepEqual(await tracker.latest(),{data:{locale:'zh-HK'}});
});
test('late response from a previous document never invokes its evicted body reader',async()=>{
 const tracker=createDocumentReads(),request={};tracker.start(request);tracker.advance();let called=0;
 tracker.record(request,async()=>{called++;throw new Error('old document');});assert.equal(await tracker.latest(),undefined);assert.equal(called,0);
});
test('a current document body failure remains an actual error',async()=>{
 const tracker=createDocumentReads(),request={},error=new Error('current response unavailable');tracker.start(request);tracker.record(request,async()=>{throw error;});
 await assert.rejects(tracker.latest(),cause=>cause===error);
});
test('a newer real response supersedes an earlier held response in the same document',async()=>{
 const tracker=createDocumentReads(),old={},current={};let release;tracker.start(old);tracker.record(old,()=>new Promise(r=>{release=r;}));const held=tracker.latest();
 tracker.start(current);tracker.record(current,async()=>({data:{locale:'en'}}));release({data:{locale:'zh-HK'}});assert.equal(await held,undefined);assert.deepEqual(await tracker.latest(),{data:{locale:'en'}});
});

test('navigation admission discards late old preference before frame commit can evict its body',async()=>{
 const {EventEmitter}=await import('node:events'),page=new EventEmitter(),frame={};page.mainFrame=()=>frame;
 const old={method:()=> 'GET',url:()=> 'http://localhost:5173/v1/workspaces/w/preferences',isNavigationRequest:()=>false,frame:()=>frame};
 const nav={method:()=> 'GET',url:()=> 'http://localhost:5173/auth/callback',isNavigationRequest:()=>true,frame:()=>frame};
 let called=0;const stop=observer.observeWorkspaceLocale(page,'w');page.emit('request',old);page.emit('request',nav);
 page.emit('response',{status:()=>200,request:()=>old,json:async()=>{called++;return {data:{locale:'zh-HK'}};}});
 assert.equal(called,0);stop.dispose();
});

test('an explicitly aborted current read is discarded and a later real response remains required',async()=>{
 const tracker=createDocumentReads(),request={};let reject;tracker.start(request);
 tracker.record(request,()=>new Promise((_,r)=>{reject=r;}));const held=tracker.latest();
 tracker.cancel(request);reject(new Error('net::ERR_ABORTED'));
 assert.equal(await held,undefined);assert.equal(await tracker.latest(),undefined);
 const current={};tracker.start(current);tracker.record(current,async()=>({data:{locale:'zh-HK'}}));
 assert.deepEqual(await tracker.latest(),{data:{locale:'zh-HK'}});
});
test('canceling an old request cannot discard a current real response or its error',async()=>{
 const tracker=createDocumentReads(),old={},current={},error=new Error('current failed');
 tracker.start(old);tracker.advance();tracker.start(current);tracker.record(current,async()=>{throw error;});
 tracker.cancel(old);await assert.rejects(tracker.latest(),cause=>cause===error);
});
test('a canceled current body remains discarded if it settled before cancellation',async()=>{
 const tracker=createDocumentReads(),request={};tracker.start(request);
 tracker.record(request,async()=>({data:{locale:'en'}}));tracker.cancel(request);
 assert.equal(await tracker.latest(),undefined);
});

test('preference observer waits for native completion and does not read a canceled body',async()=>{
 const {EventEmitter}=await import('node:events'),page=new EventEmitter(),frame={};page.mainFrame=()=>frame;
 const request=error=>({method:()=> 'GET',url:()=> 'http://localhost:5173/v1/workspaces/w/preferences',isNavigationRequest:()=>false,frame:()=>frame,failure:()=>error?{errorText:error}:null});
 const stop=observer.observeWorkspaceLocale(page,'w'),aborted=request('net::ERR_ABORTED');let finish,bodyCalls=0;
 page.emit('request',aborted);page.emit('response',{status:()=>200,request:()=>aborted,finished:()=>new Promise(r=>{finish=r;}),json:async()=>{bodyCalls++;throw new Error('evicted body must not be read');}});
 assert.equal(bodyCalls,0);finish(new Error('net::ERR_ABORTED'));await new Promise(setImmediate);assert.equal(bodyCalls,0);
 const current=request(null);page.emit('request',current);page.emit('response',{status:()=>200,request:()=>current,finished:async()=>null,json:async()=>{bodyCalls++;return {data:{locale:'zh-HK'}};}});
 await new Promise(setImmediate);assert.equal(bodyCalls,1);stop.dispose();
});
