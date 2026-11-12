import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
registerHooks({resolve(s,c,next){try{return next(s,c);}catch(e){if(s.startsWith('.'))for(const ext of ['.ts','.tsx'])try{return next(s+ext,c);}catch{}throw e;}},load(u,c,next){if(/\.tsx?$/.test(u))return {format:'module',shortCircuit:true,source:ts.transpileModule(readFileSync(new URL(u),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText};return next(u,c);}});

const {SseParser,readTurnStreamEvent,parseTurnStreamChunks,emptyTurnStream,reduceTurnEvent,reduceTurnEvents,
  streamParts,streamStep,reconnectDelay,MAX_STREAM_RECONNECTS,MAX_SSE_FRAME_BYTES,MAX_SSE_BUFFER_BYTES}=await import('../features/live/conversation/stream-events.ts');
const {mergeStreamedEntry,buildTranscript}=await import('../features/live/conversation/parts.ts');
const {readChatThread}=await import('../features/live/conversation/types.ts');
const {ConversationTurns,streamCapabilityFromStatus}=await import('../services/live/conversation-turn.ts');
const {SessionScope}=await import('../services/live/session.ts');

function frame(id,event,payload){return {id:String(id),event,data:JSON.stringify(payload)};}
function session(){const s=new SessionScope({mode:'live',actor:'a',workspace:'w',project:'p'});s.setToken('synthetic');return s;}

test('SSE parser survives chunk boundaries, CRLF, comments and multi-line data',()=>{
  const chunks=[
    'id: 1\r\nevent: turn.sta',
    'rted\r\ndata: {"status":"running"}\r\n\r',
    '\n: heartbeat\r\n\r\nid: 2\r\nevent: part\ndata: {"index":0,\ndata: "part":{"kind":"text","text":"hi"}}',
    '\n\nid: 3\nevent: turn.final\ndata: {"status":"completed"}',
  ];
  const events=parseTurnStreamChunks(chunks);
  assert.deepEqual(events.map(event=>event.kind),['turn.started','part','turn.final']);
  assert.equal(events[1].part.kind,'text');assert.equal(events[1].part.text,'hi');
  assert.equal(events[2].status,'completed');
  const parser=new SseParser();
  assert.deepEqual(parser.push('id: 4\nevent: notice\ndata: {"code":"X","message":"m"}'),[]);
  assert.equal(parser.flush().length,1,'a trailing frame without a blank line still flushes');
});

test('stream event validation allowlists kinds, states, seq and terminal status',()=>{
  assert.equal(readTurnStreamEvent(frame(1,'tool',{call_id:'c',capability:'x.y',state:'running'})).state,'running');
  assert.equal(readTurnStreamEvent(frame(2,'tool',{call_id:'c',capability:'x.y',state:'teleported'})),null);
  assert.equal(readTurnStreamEvent(frame(3,'future.kind',{})),null);
  assert.equal(readTurnStreamEvent(frame(4,'turn.final',{status:'running'})),null);
  assert.equal(readTurnStreamEvent(frame(5,'turn.final',{status:'outcome_unknown'})).status,'outcome_unknown');
  assert.equal(readTurnStreamEvent({id:'',event:'turn.final',data:'{"status":"failed"}'}),null,'seq is required');
  assert.equal(readTurnStreamEvent({id:'6',event:'',data:'{"kind":"turn.final","status":"cancelled","seq":6}'}).status,'cancelled');
  assert.equal(readTurnStreamEvent({id:'7',event:'part',data:'{broken'}),null);
  assert.equal(readTurnStreamEvent(frame(8,'part',{index:0,part:{kind:'text',text:'safe'}})).part.text,'safe');
  // API envelope shape: {seq, turn_id, kind, payload}.
  const nested=readTurnStreamEvent({id:'',event:'part',
    data:JSON.stringify({seq:9,turn_id:'22222222-2222-4222-8222-222222222222',kind:'part',
      payload:{index:0,part:{kind:'text',text:'nested'}}})});
  assert.equal(nested.seq,9);assert.equal(nested.part.text,'nested');
  assert.equal(readTurnStreamEvent({id:'',event:'turn.final',
    data:JSON.stringify({seq:10,kind:'turn.final',payload:{status:'completed'}})}).status,'completed');
});

test('reducer keeps cursor monotonic, ignores replayed events and stops after turn.final',()=>{
  let state=emptyTurnStream('turn-1');
  state=reduceTurnEvents(state,[
    {kind:'turn.started',seq:1,status:'running'},
    {kind:'part',seq:2,index:0,part:{kind:'text',text:'first'}},
    {kind:'part',seq:2,index:0,part:{kind:'text',text:'replayed'}},
    {kind:'tool',seq:3,callId:'call-1',capability:'xverum.enrich_company',state:'running'},
    {kind:'proposal',seq:4,proposalId:'proposal-1',capability:'xverum.enrich_company',requiresApproval:true},
    {kind:'notice',seq:5,code:'XVERUM_NOT_CONFIGURED',message:'Not configured'},
    {kind:'turn.final',seq:6,status:'failed'},
    {kind:'part',seq:7,index:1,part:{kind:'text',text:'after final'}},
  ]);
  assert.equal(state.cursor,6);
  assert.equal(state.final,true);
  assert.equal(state.status,'failed');
  assert.equal(state.parts.length,1);
  assert.equal(state.parts[0].part.text,'first');
  assert.equal(state.tools[0].state,'running');
  assert.equal(state.notices.length,1);
  const replay=reduceTurnEvent(state,{kind:'notice',seq:5,code:'XVERUM_NOT_CONFIGURED',message:'Not configured'});
  assert.equal(replay,state,'a final state is immutable to replay');
});

test('streamed parts keep index order and notices render as honest parts',()=>{
  let state=emptyTurnStream('turn-2');
  state=reduceTurnEvent(state,{kind:'part',seq:1,index:2,part:{kind:'text',text:'second'}});
  state=reduceTurnEvent(state,{kind:'part',seq:2,index:0,part:{kind:'text',text:'first'}});
  state=reduceTurnEvent(state,{kind:'notice',seq:3,code:'X',message:'Configuration notice'});
  const parts=streamParts(state);
  assert.deepEqual(parts.map(part=>part.kind),['text','text','notice']);
  assert.deepEqual(parts.slice(0,2).map(part=>part.text),['first','second']);
  assert.equal(parts[2].message,'Configuration notice');
  assert.equal(streamParts(emptyTurnStream('empty')).length,0);
});

test('progress labels are coarse and never expose capability ids',()=>{
  let state=emptyTurnStream('turn-3');
  assert.equal(streamStep(state),'working');
  state=reduceTurnEvent(state,{kind:'tool',seq:1,callId:'c',capability:'xverum.enrich_company',state:'running'});
  assert.equal(streamStep(state),'step');
  state=reduceTurnEvent(state,{kind:'tool',seq:2,callId:'c',capability:'xverum.enrich_company',state:'completed'});
  state=reduceTurnEvent(state,{kind:'proposal',seq:3,proposalId:'p',capability:'xverum.enrich_company',requiresApproval:true});
  assert.equal(streamStep(state),'approval');
});

test('reconnect backoff is bounded exponential and deterministic',()=>{
  assert.equal(MAX_STREAM_RECONNECTS,5);
  assert.equal(reconnectDelay(1),400);
  assert.equal(reconnectDelay(2),800);
  assert.equal(reconnectDelay(3),1600);
  assert.equal(reconnectDelay(4),3200);
  assert.equal(reconnectDelay(5),6400);
  assert.equal(reconnectDelay(9),8000);
  assert.equal(reconnectDelay(0),400);
  assert.equal(reconnectDelay(-2),400);
});

test('provisional entries never duplicate a persisted turn and are appended at most once',()=>{
  const threadId='11111111-1111-4111-8111-111111111111',turnId='22222222-2222-4222-8222-222222222222';
  const thread=readChatThread({id:threadId,version:1,templateId:'custom',title:'T',createdAt:1,updatedAt:2,
    access:'owner',shareCount:0,buyerId:null,sources:[],runs:[],messages:[
      {id:'33333333-3333-4333-8333-333333333333',seq:1,role:'user',text:'hello',parts:[]},
      {id:'44444444-4444-4444-8444-444444444444',seq:2,role:'assistant',text:'saved',turn_id:turnId,parts:[{kind:'text',text:'saved'}]}]});
  let stream=emptyTurnStream(turnId);
  stream=reduceTurnEvent(stream,{kind:'part',seq:2,index:0,part:{kind:'text',text:'streamed'}});
  const persisted=buildTranscript(thread);
  assert.deepEqual(mergeStreamedEntry(persisted,stream),persisted,'persisted parts win');
  const emptyThread=readChatThread({id:threadId,version:1,templateId:'custom',title:'T',createdAt:1,updatedAt:2,
    access:'owner',shareCount:0,buyerId:null,sources:[],runs:[],messages:[{id:'33333333-3333-4333-8333-333333333333',seq:1,role:'user',text:'hello',turn_id:turnId,parts:[]}]});
  const entries=mergeStreamedEntry(buildTranscript(emptyThread),stream);
  assert.equal(entries.length,2,'the user row of a running turn does not suppress provisional parts');
  assert.equal(entries[1].turnId,turnId);
  assert.equal(entries[1].ephemeral,true);
  assert.equal(entries[1].parts[0].text,'streamed');
  assert.equal(mergeStreamedEntry(buildTranscript(emptyThread),null).length,1);
});

test('SSE parser bounds a single frame and the unparsed buffer',()=>{
  const oversized=`event: part\ndata: ${'x'.repeat(MAX_SSE_FRAME_BYTES+10)}\n\n`;
  const parser=new SseParser();
  const before=parser.push(`event: turn.started\ndata: ${JSON.stringify({seq:1,kind:'turn.started',payload:{status:'running'}})}\n\n`+oversized);
  assert.equal(before.length,1,'frames before the oversized frame are still delivered');
  assert.equal(parser.overflowed,true);
  assert.deepEqual(parser.push('event: turn.final\ndata: {}\n\n'),[],'no more frames after overflow');
  const stuck=new SseParser();
  stuck.push('event: part\ndata: '+'y'.repeat(MAX_SSE_BUFFER_BYTES));
  assert.equal(stuck.overflowed,true,'a frame that never terminates cannot grow the buffer');
  assert.deepEqual(stuck.flush(),[]);
});

test('stream client aborts an oversized SSE body instead of buffering it',async()=>{
  const original=globalThis.fetch;
  const chunk=`event: part\ndata: ${'z'.repeat(MAX_SSE_BUFFER_BYTES+10)}`;
  const errors=[];
  try{
    globalThis.fetch=async()=>new Response(new ReadableStream({start(controller){
      controller.enqueue(new TextEncoder().encode(chunk));controller.close();
    }}),{status:200,headers:{'content-type':'text/event-stream'}});
    const api=new ConversationTurns({async request(){return undefined;}},session(),true);
    const outcome=await api.stream('11111111-1111-4111-8111-111111111111',{signal:new AbortController().signal,
      onEvent(){},onStreamError:error=>errors.push(error)});
    assert.equal(outcome,'overflow');
    assert.deepEqual(errors,[],'an overflow is a bounded outcome, not a transport error');
  }finally{globalThis.fetch=original;}
  const parser=new SseParser();
  parser.push(`event: part\ndata: ${'q'.repeat(MAX_SSE_FRAME_BYTES+1)}\n\n`);
  assert.equal(parser.overflowed,true);
});

test('stream capability probe classifies missing route, existing route and denied access',async()=>{
  assert.equal(streamCapabilityFromStatus(404),'absent');
  assert.equal(streamCapabilityFromStatus(405),'available');
  assert.equal(streamCapabilityFromStatus(204),'available');
  assert.equal(streamCapabilityFromStatus(422),'available');
  assert.equal(streamCapabilityFromStatus(403),'unavailable');
  assert.equal(streamCapabilityFromStatus(500),'unavailable');
  const original=globalThis.fetch;
  try{
    globalThis.fetch=async()=>({status:404});
    assert.equal(await new ConversationTurns({async request(){throw new Error('must not call');}},session(),true).streamCapability(),'absent');
    globalThis.fetch=async()=>{throw new Error('offline');};
    assert.equal(await new ConversationTurns({async request(){throw new Error('must not call');}},session(),true).streamCapability(),'unavailable');
  }finally{globalThis.fetch=original;}
  const disabled=new ConversationTurns({async request(){throw new Error('must not call');}},session(),false);
  assert.equal(await disabled.streamCapability(),'absent');
});

test('cancel and reconcile send no body, keep the thread precondition and one request key',async()=>{
  const threadId='11111111-1111-4111-8111-111111111111',turnId='22222222-2222-4222-8222-222222222222';
  const requests=[],s=session();
  const result=()=>({thread:{id:threadId,version:4,templateId:'custom',title:'T',createdAt:1,updatedAt:2,
    access:'owner',shareCount:0,buyerId:null,messages:[],sources:[],runs:[]},
    turn:{id:turnId,status:'cancelled',parts:[],notices:[]}});
  const api=new ConversationTurns({async request(input){requests.push(input);return result();}},s,true);
  await api.cancel({threadId,turnId,expectedVersion:3});
  assert.equal(requests[0].body,undefined,'cancel takes no request body');
  assert.equal(requests[0].ifMatch,'"3"');assert.ok(requests[0].idempotencyKey);
  assert.match(requests[0].path,new RegExp(`/${turnId}/cancel$`));
  await api.reconcile({threadId,turnId,expectedVersion:3});
  assert.equal(requests[1].body,undefined,'reconcile is a probe, not a payload mutation');
  assert.equal(requests[1].ifMatch,'"3"');assert.ok(requests[1].idempotencyKey);
  assert.match(requests[1].path,new RegExp(`/${turnId}/reconcile$`));
  assert.notEqual(requests[0].idempotencyKey,requests[1].idempotencyKey);
});
