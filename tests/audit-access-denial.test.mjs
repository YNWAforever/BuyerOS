import {test} from 'node:test';
import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';
const {createLiveClient,LiveError}=await loadModule('services/live/client.ts');
const error=status=>new Response(JSON.stringify({code:status===404?'NOT_FOUND':'FORBIDDEN',message:'denied',request_id:'fixture-id',retryable:false}),{status,headers:{'Content-Type':'application/json'}});
for(const method of ['request','requestContent'])test(`U05 ${method} emits a scoped denial without changing its error or replaying`,async()=>{
 let calls=0;const client=createLiveClient(async()=>{calls++;return error(404);});const events=[];
 const stop=client.subscribeAccessDenied(event=>events.push(event));
 await assert.rejects(client[method]({path:'/v1/workspaces/A/jobs/missing',scope:'current-generation',token:'private-token'}),e=>e instanceof LiveError&&e.status===404&&e.requestId==='fixture-id');
 assert.equal(calls,1);assert.deepEqual(events,[{workspace:'A',scope:'current-generation'}]);assert.equal(JSON.stringify(events).includes('private-token'),false);
 stop();await assert.rejects(client[method]({path:'/v1/workspaces/A/jobs/missing',scope:'later-generation'}));assert.equal(events.length,1);
});
test('U05 observer only requests membership checks for workspace-scoped 403/404',async()=>{
 let status=403;const client=createLiveClient(async()=>error(status)),events=[];client.subscribeAccessDenied(e=>events.push(e));
 for(const path of ['/v1/workspaces','/v1/workspaces?offset=0','/v1/unknown'])await assert.rejects(client.request({path,scope:'current'}));
 assert.deepEqual(events,[]);
 for(status of [401,409,412,429,500])await assert.rejects(client.request({path:'/v1/workspaces/A/buyers',scope:'current'}));
 assert.deepEqual(events,[]);status=403;await assert.rejects(client.request({path:'/v1/workspaces/A/buyers',scope:'current'}));assert.equal(events.length,1);
});
test('U05 an already aborted response cannot trigger a current access check',async()=>{
 const controller=new AbortController(),client=createLiveClient(async()=>{controller.abort();return error(404);}),events=[];client.subscribeAccessDenied(e=>events.push(e));
 await assert.rejects(client.request({path:'/v1/workspaces/A/buyers',scope:'old',signal:controller.signal}));assert.deepEqual(events,[]);
});
