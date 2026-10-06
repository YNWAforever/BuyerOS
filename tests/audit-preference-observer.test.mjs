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
