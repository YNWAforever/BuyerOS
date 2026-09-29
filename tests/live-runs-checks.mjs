import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';

const {SessionScope}=await loadModule('services/live/session.ts');
const {subscribeRun}=await loadModule('services/live/runs.ts');
const savedFetch=globalThis.fetch;
let passed=0;
const waitFor=async(predicate)=>{
  for(let i=0;i<40;i++){if(predicate())return;await new Promise(resolve=>setTimeout(resolve,10));}
  assert.fail('run subscription update did not arrive');
};
const setup=(request)=>{
  const session=new SessionScope({mode:'live',actor:'actor',workspace:'ws',project:'p'});
  session.setToken('in-memory-token');
  return {session,client:{request},apiBaseUrl:'https://api.example.test',workspaceId:'ws',projectId:'p'};
};
const frame=(items)=>new Response(items.map(item=>`id: ${item.sequence}\nevent: ${item.type}\ndata: ${JSON.stringify(item)}\n\n`).join(''),
  {status:200,headers:{'content-type':'text/event-stream'}});
const event=(sequence)=>({workspace_id:'ws',run_id:'r',sequence,type:'node.committed'});

try{
  {
    const seen=[],requests=[];
    const ctx=setup(async()=>({id:'r',project_id:'p',last_event_sequence:4}));
    globalThis.fetch=async(url,init)=>{requests.push({url:String(url),headers:init.headers});
      return frame([event(2),event(2),event(1),event(4)]);};
    const stop=subscribeRun({runId:'r',afterSequence:1,ctx,onEvent:update=>seen.push(update)});
    await waitFor(()=>seen.some(item=>item.kind==='snapshot'));stop();
    assert.deepEqual(seen.filter(item=>item.kind==='event').map(item=>item.event.sequence),[2]);
    assert.equal(seen.filter(item=>item.kind==='snapshot').length,1);
    assert.ok(!requests[0].url.includes('in-memory-token'));
    assert.equal(requests[0].headers.Authorization,'Bearer in-memory-token');
    passed++;
  }
  {
    const seen=[],ctx=setup(async()=>({items:[],next_after_sequence:0,latest_sequence:0,has_more:false}));
    globalThis.fetch=async()=>{await new Promise(resolve=>setTimeout(resolve,25));return frame([event(1)]);};
    const stop=subscribeRun({runId:'r',afterSequence:0,ctx,onEvent:update=>seen.push(update)});
    ctx.session.next({workspace:'other',project:null});
    await new Promise(resolve=>setTimeout(resolve,60));stop();
    assert.equal(seen.filter(item=>item.kind==='event').length,0);
    passed++;
  }
  {
    const seen=[];let polls=0;
    const ctx=setup(async()=>{polls++;return {items:polls===1?[event(1)]:[],next_after_sequence:1,
      latest_sequence:1,has_more:false};});
    globalThis.fetch=async()=>new Response('',{status:503});
    const stop=subscribeRun({runId:'r',afterSequence:0,ctx,onEvent:update=>seen.push(update)});
    await waitFor(()=>seen.some(item=>item.kind==='event'));stop();
    assert.deepEqual(seen.filter(item=>item.kind==='event').map(item=>item.event.sequence),[1]);
    assert.ok(seen.some(item=>item.kind==='connection'&&item.transport==='poll'));
    passed++;
  }
  {
    const ctx=setup(async()=>{throw new Error('poll should not run after 401');});
    globalThis.fetch=async()=>new Response('',{status:401});
    const stop=subscribeRun({runId:'r',afterSequence:0,ctx,onEvent:()=>{}});
    await waitFor(()=>!ctx.session.getSnapshot().authenticated);stop();
    passed++;
  }
}finally{globalThis.fetch=savedFetch;}
console.log(`${passed} live run subscription checks passed`);
