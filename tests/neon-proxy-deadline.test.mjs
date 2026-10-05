import assert from 'node:assert/strict';
import {test} from 'node:test';
import {request} from 'node:http';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {executionFixture,listen} from './fixtures/neon-execution/fixture.mjs';
import {createCountedAuthProxy} from '../scripts/neon-counted-proxy.mjs';
import {RealRunJournal} from '../scripts/neon-real-preflight.mjs';

async function wire(t,handler,options={}){
 const f=await executionFixture(handler);t.after(()=>f.cleanup());
 const proxy=createCountedAuthProxy({backend:f.backend,journal:f.journal,...options});f.servers.push(proxy);
 return {...f,proxy,url:await listen(proxy)};
}
function streamed(t,url){
 let req;
 const response=new Promise((ok,bad)=>{
  req=request(url,{method:'POST',headers:{'content-type':'application/json'}},res=>{
   const chunks=[];res.on('data',chunk=>chunks.push(chunk));res.on('error',bad);res.on('end',()=>ok({status:res.statusCode,body:Buffer.concat(chunks).toString('utf8')}));
  });req.on('error',bad);req.setTimeout(4000,()=>req.destroy(new Error('test request stalled')));
 });
 t.after(()=>req.destroy());req.flushHeaders();return {req,response};
}
async function admitted(f){
 const deadline=Date.now()+2000;
 while(f.journal.snapshot().requests.length===0&&Date.now()<deadline)await new Promise(ok=>setTimeout(ok,5));
 assert.equal(f.journal.snapshot().requests.length,1);assert.equal(f.journal.snapshot().requests[0].outcome,'pending');
}

test('N00 streamed body crossing target TTL cannot dispatch a previously reserved auth request',async t=>{
 let clock;const f=await wire(t,()=>false,{now:()=>clock??Date.now()});
 const s=streamed(t,f.url+'/fixture/auth/sign-in/social');s.req.write('{"provider":');await admitted(f);
 clock=Date.parse(f.target.expiresAt)+1;s.req.end('"google"}');
 const reply=await s.response;assert.equal(reply.status,403);assert.match(reply.body,/EXPIRED/);assert.equal(f.model.hits.length,0);
 const recovered=new RealRunJournal(f.root),item=recovered.snapshot().requests[0];assert.equal(item.outcome,'rejected');assert.equal(recovered.snapshot().requests.length,1);
 const receipt=readFileSync(join(f.root,item.evidenceRef),'utf8');assert.doesNotMatch(receipt,/provider|google/);assert.match(receipt,/EXPIRED/);
});

test('N00 continuous body trickle cannot extend the ingress deadline or reach the auth backend',async t=>{
 const f=await wire(t,()=>false,{timeoutMs:100});const s=streamed(t,f.url+'/fixture/auth/sign-in/social');
 s.req.write('[');await admitted(f);let chunks=0;
 const timer=setInterval(()=>{if(++chunks===8){clearInterval(timer);s.req.end('0]');}else s.req.write('0,');},25);
 t.after(()=>clearInterval(timer));
 const reply=await s.response;clearInterval(timer);assert.equal(reply.status,408);assert.match(reply.body,/BODY_TIMEOUT/);assert.equal(f.model.hits.length,0);
 const item=new RealRunJournal(f.root).snapshot().requests[0];assert.equal(item.outcome,'rejected');assert.equal(f.proxy.fixtureReport().metrics.forwarded,0);
});

test('N00 timely streamed body retains exact bytes and one durable native HTTP hop',async t=>{
 let received='';const f=await wire(t,async(req,res)=>{for await(const chunk of req)received+=chunk;assert.equal(req.headers['content-type'],'application/json');res.end('{"ok":true}');return true;});
 const s=streamed(t,f.url+'/fixture/auth/sign-in/social');s.req.write('{"provider":');await admitted(f);s.req.end('"google"}');
 const reply=await s.response;assert.equal(reply.status,200);assert.equal(received,'{"provider":"google"}');assert.deepEqual(JSON.parse(reply.body),{ok:true});
 assert.equal(f.model.hits.length,1);const state=new RealRunJournal(f.root).snapshot();assert.equal(state.requests.length,1);assert.equal(state.requests[0].outcome,'accepted');
});

test('N00 a physical write exceeding remaining TTL stays unknown and cannot replay after restart',async t=>{
 let commits=0;const f=await wire(t,async(req,res)=>{for await(const chunk of req)assert.ok(chunk.length);commits++;setTimeout(()=>res.end('{"committed":true}'),180).unref();return true;},{timeoutMs:1000,now:()=>Date.parse(fixtureExpiry)-100});
 const fixtureExpiry=f.target.expiresAt;
 const first=await fetch(f.url+'/fixture/auth/sign-out',{method:'POST',body:'{"same":"intent"}'});assert.equal(first.status,503);await first.text();assert.equal(commits,1);
 assert.equal(new RealRunJournal(f.root).snapshot().requests[0].outcome,'unknown');
 const again=await fetch(f.url+'/fixture/auth/sign-out',{method:'POST',body:'{"same":"intent"}'});assert.equal(again.status,409);await again.text();assert.equal(commits,1);
 await new Promise(ok=>f.proxy.close(ok));
 const recovered=createCountedAuthProxy({backend:f.backend,journal:new RealRunJournal(f.root)});f.servers.push(recovered);
 const repeat=await fetch((await listen(recovered))+'/fixture/auth/sign-out',{method:'POST',body:'{"same":"intent"}'});assert.equal(repeat.status,409);await repeat.text();assert.equal(commits,1);
});
