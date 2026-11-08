import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
registerHooks({resolve(s,c,next){try{return next(s,c);}catch(e){if(s.startsWith('.'))for(const ext of ['.ts','.tsx'])try{return next(s+ext,c);}catch{}throw e;}},load(u,c,next){if(/\.tsx?$/.test(u))return {format:'module',shortCircuit:true,source:ts.transpileModule(readFileSync(new URL(u),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText};return next(u,c);}});

const {ConversationTurns,turnNotice,turnNotices}=await import('../services/live/conversation-turn.ts');
const {SessionScope}=await import('../services/live/session.ts');
const {LiveError}=await import('../services/live/client.ts');
const threadId='11111111-1111-4111-8111-111111111111';
const turnId='22222222-2222-4222-8222-222222222222';
const clientId='33333333-3333-4333-8333-333333333333';
function thread(){return {id:threadId,version:1,templateId:'custom',title:'Research buyer',createdAt:1,updatedAt:2,access:'owner',shareCount:0,messages:[],sources:[],runs:[]};}
function result(){return {thread:thread(),turn:{id:turnId,status:'completed',parts:[],notices:[]}};}
function session(){const s=new SessionScope({mode:'live',actor:'a',workspace:'w',project:'p'});s.setToken('synthetic');return s;}

test('capability probe: live route, missing route and failing route are distinct states',async()=>{
  const calls=[];
  const live=new ConversationTurns({async request(input){calls.push(input);return {};}},session(),true);
  assert.equal(await live.capability(),'available');
  assert.equal(calls[0].method,'OPTIONS');assert.match(calls[0].path,/conversation-turns$/);assert.equal(calls[0].idempotencyKey,undefined);
  const missing=new ConversationTurns({async request(){throw new LiveError('request failed','NOT_FOUND',404,'',false);}},session(),true);
  assert.equal(await missing.capability(),'absent');
  const broken=new ConversationTurns({async request(){throw new LiveError('unavailable','UNKNOWN_ERROR',503,'',true);}},session(),true);
  assert.equal(await broken.capability(),'unavailable');
  const forbidden=new ConversationTurns({async request(){throw new LiveError('forbidden','UNKNOWN_ERROR',403,'',false);}},session(),true);
  assert.equal(await forbidden.capability(),'available');
  const disabled=new ConversationTurns({async request(){throw new Error('must not call');}},session(),false);
  assert.equal(await disabled.capability(),'absent');
});

test('a first turn omits thread id and If-Match, a later turn sends both and one key per payload',async()=>{
  const requests=[],sessionScope=session();
  const api=new ConversationTurns({async request(input){requests.push(input);return result();}},sessionScope,true);
  const first=await api.submit({threadId:null,clientMessageId:clientId,expectedVersion:null,text:'Research this buyer',language:'en'});
  assert.equal(first.turn.status,'completed');
  // Amendment A1: the first turn omits thread_id/expected_thread_version entirely.
  assert.equal('thread_id' in requests[0].body,false);assert.equal('expected_thread_version' in requests[0].body,false);
  assert.deepEqual(requests[0].body,{client_message_id:clientId,language:'en',text:'Research this buyer',skill_id:null});
  assert.equal(requests[0].ifMatch,undefined);
  await api.submit({threadId,turnId,clientMessageId:clientId,expectedVersion:3,text:'Research this buyer',skillId:'sales-research',language:'zh-HK'});
  assert.equal(requests[1].ifMatch,'"3"');assert.equal(requests[1].body.thread_id,threadId);
  assert.equal(requests[1].body.expected_thread_version,3);assert.equal(requests[1].body.language,'zh-HK');
  assert.equal(requests[1].body.skill_id,'sales-research');
  let failed=false;
  const retrying=new ConversationTurns({async request(input){requests.push(input);if(!failed){failed=true;throw new Error('lost response');}return result();}},sessionScope,true);
  await assert.rejects(retrying.submit({threadId,clientMessageId:clientId,expectedVersion:3,text:'Research this buyer',skillId:'sales-research',language:'zh-HK'}));
  await retrying.submit({threadId,clientMessageId:clientId,expectedVersion:3,text:'Research this buyer',skillId:'sales-research',language:'zh-HK'});
  assert.equal(requests.at(-2).idempotencyKey,requests.at(-1).idempotencyKey);
  assert.equal(turnNotice(new LiveError('changed','STALE_REVISION',412,'',false)),turnNotices.stale);
  assert.equal(turnNotice(new LiveError('over budget','BUDGET_LIMIT',409,'',false)),turnNotices.budget);
  assert.equal(turnNotice(new Error(turnNotices.invalid)),turnNotices.invalid);
});

test('decisions post to the owning turn with the chosen proposal and version',async()=>{
  const requests=[],sessionScope=session();
  const api=new ConversationTurns({async request(input){requests.push(input);return result();}},sessionScope,true);
  const decision=await api.decide({threadId,turnId,proposalId:'proposal-1',decision:'approve',expectedVersion:4});
  assert.equal(decision.thread.id,threadId);
  assert.match(requests[0].path,new RegExp(`/conversation-turns/${turnId}/decisions$`));
  assert.deepEqual(requests[0].body,{proposal_id:'proposal-1',decision:'approve',expected_thread_version:4});
  assert.equal(requests[0].ifMatch,'"4"');assert.ok(requests[0].idempotencyKey);
  await assert.rejects(api.decide({threadId,turnId,proposalId:'',decision:'approve',expectedVersion:4}));
});

test('invalid input is rejected locally and a scope change cancels in-flight turns',async()=>{
  const {LiveCancelled}=await import('../services/live/client.ts');
  const requests=[];
  const sessionScope=session();
  const api=new ConversationTurns({async request(input){requests.push(input);return result();}},sessionScope,true);
  await assert.rejects(api.submit({threadId:null,clientMessageId:'not-a-uuid',expectedVersion:null,text:'x',language:'en'}),/rejected/);
  await assert.rejects(api.submit({threadId:null,clientMessageId:clientId,expectedVersion:null,text:'   ',language:'en'}),/rejected/);
  await assert.rejects(api.submit({threadId:null,clientMessageId:clientId,expectedVersion:null,text:'x',language:'en',skillId:'../bad'}),/rejected/);
  assert.equal(requests.length,0);
  const hanging=new ConversationTurns({request(input){requests.push(input);return new Promise((_resolve,reject)=>{
    input.signal.addEventListener('abort',()=>reject(new LiveCancelled('cancelled')),{once:true});
  });}},sessionScope,true);
  const inflight=hanging.submit({threadId:null,clientMessageId:clientId,expectedVersion:null,text:'Keep me',language:'en'});
  void inflight.catch(()=>{});
  await new Promise(resolve=>setImmediate(resolve));
  sessionScope.next({project:'other'});
  assert.equal(requests[0].signal.aborted,true);
  await assert.rejects(inflight);
});
