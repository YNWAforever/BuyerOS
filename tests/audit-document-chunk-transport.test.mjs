import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {loadModule} from './ts-loader.mjs';
const proxy=await loadModule('app/v1/[...path]/route.ts');
test('native chunk PUT crosses the actual same-origin proxy with digest and exact bytes',async()=>{
 const originalFetch=globalThis.fetch,binding=process.env.BUYEROS_INTERNAL_API_URL;
 const body=new Uint8Array(2097152).fill(37),digest=createHash('sha256').update(body).digest('hex');
 process.env.BUYEROS_INTERNAL_API_URL='https://owned-api.fixture.invalid/';
 let called=0;
 globalThis.fetch=async(url,init)=>{
  called++;assert.equal(init.method,'PUT');assert.equal(new URL(url).origin,'https://owned-api.fixture.invalid');
  assert.equal(init.headers.get('x-chunk-sha256'),digest);assert.equal(init.headers.get('authorization'),'Bearer private-fixture');
  assert.equal(init.headers.get('cookie'),null);assert.equal(init.headers.get('x-service-secret'),null);
  const received=Buffer.from(await new Response(init.body).arrayBuffer());assert.equal(received.byteLength,2097152);
  assert.equal(createHash('sha256').update(received).digest('hex'),digest);
  return Response.json({data:{received:true},request_id:crypto.randomUUID(),data_mode:'live'});
 };
 try{
  const response=await proxy.PUT(new Request('https://app.fixture.invalid/v1/workspaces/W/offer-document-uploads/U/chunks/0',{
   method:'PUT',body,headers:{authorization:'Bearer private-fixture','content-type':'application/octet-stream','x-chunk-sha256':digest,cookie:'private=not-forwarded','x-service-secret':'not-forwarded'}}));
  assert.equal(response.status,200);assert.equal(called,1);assert.equal(response.headers.get('cache-control'),'private, no-store');
 }finally{globalThis.fetch=originalFetch;if(binding===undefined)delete process.env.BUYEROS_INTERNAL_API_URL;else process.env.BUYEROS_INTERNAL_API_URL=binding;}
});
