import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {once} from 'node:events';
import {loadModule} from './ts-loader.mjs';

const {createLiveClient,LiveCancelled,LiveError}=await loadModule('services/live/client.ts');
const {SessionScope}=await loadModule('services/live/session.ts');
const {loadSelection}=await loadModule('services/live/selection-read.ts');
const {toProjects}=await loadModule('services/live/mapping.ts');
const project={id:'project-a',name:'Owned project',status:'active'};
const page=(items=[project],offset=0,total=items.length)=>({items,offset,limit:100,total});
const reply=(response,data=page())=>{response.writeHead(200,{'Content-Type':'application/json'});response.end(JSON.stringify({data_mode:'live',request_id:'owned-request',data}));};
const deferred=()=>{let resolve;const promise=new Promise(r=>{resolve=r;});return {promise,resolve};};

async function fixture(t,handle){
  const requests=[];
  const server=http.createServer((request,response)=>{
    requests.push({method:request.method,path:request.url,authorization:request.headers.authorization});
    handle(request,response,requests.length);
  });
  server.listen(0,'127.0.0.1');await once(server,'listening');
  t.after(async()=>{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));});
  const scope=new SessionScope({mode:'live',actor:'owned-actor',workspace:'workspace-a',project:null});scope.setToken('owned-fixture-token');
  const signal=scope.controller().signal;
  const client=createLiveClient(fetch,`http://127.0.0.1:${server.address().port}`);
  return {requests,scope,load:()=>loadSelection(client,scope,'/v1/workspaces/workspace-a/projects',toProjects,signal)};
}

test('selection recovers a real connection reset with one fresh authenticated GET',async t=>{
  const f=await fixture(t,(request,response,count)=>count===1?request.socket.destroy():reply(response));
  assert.deepEqual(await f.load(),[project]);assert.equal(f.requests.length,2);
  assert.ok(f.requests.every(r=>r.method==='GET'&&r.authorization==='Bearer owned-fixture-token'));
});

test('selection stops after two real connection failures',async t=>{
  const f=await fixture(t,request=>request.socket.destroy());
  await assert.rejects(f.load(),error=>error instanceof LiveError&&error.code==='NETWORK_ERROR');
  assert.equal(f.requests.length,2);
});

test('selection deadline cancels a stalled HTTP read and ignores its late 200',async t=>{
  let lateResponse,firstClosed=false;
  const f=await fixture(t,(request,response,count)=>{
    if(count===1){lateResponse=response;request.on('close',()=>{firstClosed=true;});return;}
    reply(response);reply(lateResponse,page([{...project,name:'Stale result'}]));
  });
  assert.deepEqual(await f.load(),[project]);assert.equal(firstClosed,true);assert.equal(f.requests.length,2);
});

for(const status of [401,403,404,429,500])test(`selection does not retry HTTP ${status} even if an error claims to be a network failure`,async t=>{
  const f=await fixture(t,(_request,response)=>{response.writeHead(status,{'Content-Type':'application/json'});response.end(JSON.stringify({code:'NETWORK_ERROR',retryable:true,request_id:'denied'}));});
  await assert.rejects(f.load(),error=>error instanceof LiveError&&error.status===status);
  assert.equal(f.requests.length,1);
});

test('selection retries one explicitly transient gateway failure',async t=>{
  const f=await fixture(t,(_request,response,count)=>{
    if(count===1){response.writeHead(503,{'Content-Type':'application/json'});response.end(JSON.stringify({code:'UNAVAILABLE',retryable:true}));return;}
    reply(response);
  });
  assert.deepEqual(await f.load(),[project]);assert.equal(f.requests.length,2);
});

test('selection honors a server Retry-After response without an early automatic retry',async t=>{
  const f=await fixture(t,(_request,response)=>{response.writeHead(503,{'Content-Type':'application/json','Retry-After':'30'});response.end(JSON.stringify({code:'UNAVAILABLE',retryable:true}));});
  await assert.rejects(f.load(),error=>error instanceof LiveError&&error.status===503&&error.retryAfter==='30');
  assert.equal(f.requests.length,1);
});

test('selection does not retry an invalid live response',async t=>{
  const f=await fixture(t,(_request,response)=>{response.writeHead(200,{'Content-Type':'application/json'});response.end('{}');});
  await assert.rejects(f.load(),error=>error instanceof LiveError&&error.code==='INVALID_ENVELOPE');
  assert.equal(f.requests.length,1);
});

test('selection aborts an in-flight read on A-B-A scope changes without a retry',async t=>{
  const started=deferred();let response;
  const f=await fixture(t,(_request,value)=>{response=value;started.resolve();});
  const result=assert.rejects(f.load(),error=>error instanceof LiveCancelled);
  await started.promise;f.scope.next({workspace:'workspace-b'});f.scope.next({workspace:'workspace-a'});
  reply(response);await result;assert.equal(f.requests.length,1);
});

test('selection cancels during retry backoff without a second request',async t=>{
  let f;
  f=await fixture(t,request=>{request.socket.destroy();setTimeout(()=>f.scope.next({workspace:'workspace-b'}),50);});
  await assert.rejects(f.load(),error=>error instanceof LiveCancelled);assert.equal(f.requests.length,1);
});

test('selection restarts pagination after interruption without retaining a partial list',async t=>{
  const first=Array.from({length:100},(_,i)=>({...project,id:`project-${i}`}));
  const f=await fixture(t,(request,response,count)=>{
    const offset=Number(new URL(request.url,'http://owned.test').searchParams.get('offset'));
    if(count===2){request.socket.destroy();return;}
    reply(response,page(offset===0?first:[{...project,id:'project-100'}],offset,101));
  });
  const result=await f.load();assert.equal(result.length,101);assert.equal(new Set(result.map(p=>p.id)).size,101);
  assert.deepEqual(f.requests.map(r=>Number(new URL(r.path,'http://owned.test').searchParams.get('offset'))),[0,100,0,100]);
});

test('selection rejects malformed pagination without retrying or publishing partial results',async t=>{
  const f=await fixture(t,(_request,response)=>reply(response,page([project],100,101)));
  await assert.rejects(f.load(),/Invalid pagination/);assert.equal(f.requests.length,1);
});
