import test from 'node:test';
import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';

const {SessionScope}=await loadModule('services/live/session.ts');
const {subscribeRun}=await loadModule('services/live/runs.ts');
const {LiveError}=await loadModule('services/live/client.ts');
const event=sequence=>({workspace_id:'ws',run_id:'run',sequence,type:'node.committed',message:'買家'});
const context=request=>{
  const session=new SessionScope({mode:'live',actor:'actor',workspace:'ws',project:'project'});
  session.setToken('memory-token');
  return {session,client:{request},apiBaseUrl:'https://api.example.test',workspaceId:'ws',projectId:'project'};
};
const frame=(item,newline='\n')=>`id: ${item.sequence}${newline}data: ${JSON.stringify(item)}${newline}${newline}`;
const response=chunks=>new Response(new ReadableStream({start(controller){
  for(const chunk of chunks)controller.enqueue(chunk);
  controller.close();
}}),{headers:{'content-type':'text/event-stream'}});
const bytes=text=>new TextEncoder().encode(text);
const settle=()=>new Promise(resolve=>setImmediate(resolve));
function subscribe(t,ctx,onEvent,afterSequence=0){
  const stop=subscribeRun({runId:'run',afterSequence,ctx,onEvent});
  t.after(stop);
  return stop;
}

test('run progress parses CRLF frames when every network chunk ends between CR and LF',async t=>{
  const seen=[];
  const ctx=context(async()=>{assert.fail('valid stream must not poll');});
  const chunks=frame(event(1),'\r\n').split(/(?<=\r)/).map(bytes);
  t.mock.method(globalThis,'fetch',async()=>response(chunks));
  subscribe(t,ctx,update=>seen.push(update));
  await settle();
  assert.deepEqual(seen.filter(update=>update.kind==='event').map(update=>update.event),[event(1)]);
});

test('run progress preserves UTF-8 across byte-sized chunks and ignores other scopes and replayed events',async t=>{
  const seen=[];
  const text=frame({...event(1),workspace_id:'foreign'})+frame({...event(1),run_id:'foreign'})+
    frame(event(1))+frame(event(1))+frame(event(2));
  t.mock.method(globalThis,'fetch',async()=>response([...bytes(text)].map(value=>Uint8Array.of(value))));
  subscribe(t,context(async()=>assert.fail('unexpected snapshot')),update=>seen.push(update));
  await settle();
  assert.deepEqual(seen.filter(update=>update.kind==='event').map(update=>update.event),[event(1),event(2)]);
});

test('a sequence gap reloads the committed snapshot before accepting the next event',async t=>{
  const requests=[],seen=[];
  const snapshot={id:'run',workspace_id:'ws',project_id:'project',last_event_sequence:4};
  const ctx=context(async request=>{requests.push(request);return snapshot;});
  t.mock.method(globalThis,'fetch',async()=>response([bytes(frame(event(2))+frame(event(4))+frame(event(5)))]));
  subscribe(t,ctx,update=>seen.push(update),1);
  await settle();
  assert.deepEqual(seen.filter(update=>['event','snapshot'].includes(update.kind)),[
    {kind:'event',event:event(2)},{kind:'snapshot',run:snapshot},{kind:'event',event:event(5)},
  ]);
  assert.equal(requests.length,1);
  assert.equal(requests[0].path,'/v1/workspaces/ws/runs/run');
});

test('SSE fallback drains paginated events using the committed cursor and bearer headers',async t=>{
  const requests=[],seen=[];
  const ctx=context(async request=>{
    requests.push(request);
    return {items:[event(requests.length)],has_more:requests.length===1};
  });
  t.mock.method(globalThis,'fetch',async(url,init)=>{
    assert.equal(init.headers.Authorization,'Bearer memory-token');
    assert.equal(init.headers['Last-Event-ID'],'0');
    assert.doesNotMatch(String(url),/memory-token/);
    return new Response('',{status:503});
  });
  subscribe(t,ctx,update=>seen.push(update));
  await settle();
  assert.deepEqual(requests.map(request=>request.path),[
    '/v1/workspaces/ws/runs/run/events?after_sequence=0&limit=200',
    '/v1/workspaces/ws/runs/run/events?after_sequence=1&limit=200',
  ]);
  assert.ok(requests.every(request=>request.token==='memory-token'));
  assert.deepEqual(seen.filter(update=>update.kind==='event').map(update=>update.event.sequence),[1,2]);
});

for(const transport of ['sse','poll'])test(`${transport} 401 clears identity and stops progress`,async t=>{
  const ctx=context(async()=>{throw new LiveError('expired','UNAUTHORIZED',401,'fixture',false);});
  t.mock.method(globalThis,'fetch',async()=>new Response('',{status:transport==='sse'?401:503}));
  const seen=[];
  subscribe(t,ctx,update=>seen.push(update));
  await settle();
  assert.equal(ctx.session.token(),undefined);
  assert.equal(ctx.session.current().actor,'');
  assert.equal(seen.some(update=>update.kind==='event'),false);
});

test('A-B-A scope changes discard a delayed stream and abort its request',async t=>{
  let release,signal;
  const held=new Promise(resolve=>{release=resolve;});
  t.mock.method(globalThis,'fetch',async(_url,init)=>{signal=init.signal;return held;});
  const seen=[],ctx=context(async()=>assert.fail('stale stream must not poll'));
  subscribe(t,ctx,update=>seen.push(update));
  await settle();
  ctx.session.next({workspace:'other'});
  ctx.session.next({workspace:'ws'});
  assert.equal(signal.aborted,true);
  release(response([bytes(frame(event(1)))]));
  await settle();
  assert.equal(seen.some(update=>update.kind==='event'),false);
});

test('unsubscribing discards an already requested polling response',async t=>{
  let release,signal;
  const held=new Promise(resolve=>{release=resolve;});
  const ctx=context(async request=>{signal=request.signal;return held;});
  t.mock.method(globalThis,'fetch',async()=>new Response('',{status:503}));
  const seen=[],stop=subscribe(t,ctx,update=>seen.push(update));
  await settle();
  stop();
  assert.equal(signal.aborted,true);
  release({items:[event(1)],has_more:false});
  await settle();
  assert.equal(seen.some(update=>update.kind==='event'),false);
});
