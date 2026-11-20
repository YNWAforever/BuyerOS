import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
registerHooks({resolve(s,c,next){try{return next(s,c);}catch(e){if(s.startsWith('.'))for(const ext of ['.ts','.tsx'])try{return next(s+ext,c);}catch{}throw e;}},load(u,c,next){if(/\.tsx?$/.test(u))return {format:'module',shortCircuit:true,source:ts.transpileModule(readFileSync(new URL(u),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText};return next(u,c);}});

const {retryAttempt,messageHasAttempt,readAttempt}=await import('../features/live/conversation/attempt.ts');
const {attemptStorageKey,readUnresolvedAttempt,writeUnresolvedAttempt,clearUnresolvedAttempt}=await import('../features/live/conversation/attempt-store.ts');
const thread='11111111-1111-4111-8111-111111111111';
const clientMessageId='22222222-2222-4222-8222-222222222222';
const original={threadId:thread,clientMessageId,text:'Keep this exact attempt',skillId:'sales-research',language:'en',expectedVersion:7};

test('an uncertain retry freezes the original language, skill, version and text',()=>{
  const retry=retryAttempt(original,{...original,skillId:null,language:'zh-HK',expectedVersion:9,text:'Edited text'});
  assert.deepEqual(retry,original,'the unresolved attempt is replayed exactly');
  assert.equal(retry.language,'en');
  assert.equal(retry.skillId,'sales-research');
  assert.equal(retry.expectedVersion,7);
  assert.equal(retry.text,'Keep this exact attempt');
});

test('a new message id or thread starts a new attempt instead of replaying the old one',()=>{
  const replacement={...original,clientMessageId:'33333333-3333-4333-8333-333333333333'};
  assert.deepEqual(retryAttempt(original,replacement),replacement);
  const otherThread={...original,threadId:'44444444-4444-4444-8444-444444444444'};
  assert.deepEqual(retryAttempt(original,otherThread),otherThread);
  assert.deepEqual(retryAttempt(null,original),original);
});

test('a saved thread read matches the attempt by client message id',()=>{
  const chat={id:thread,version:2,messages:[{id:'m1',clientMessageId,text:original.text}]};
  assert.equal(messageHasAttempt(chat,clientMessageId),true);
  assert.equal(messageHasAttempt(chat,'55555555-5555-4555-8555-555555555555'),false);
  assert.equal(messageHasAttempt({...chat,messages:[]},clientMessageId),false);
  assert.equal(readAttempt({...original,savedAt:1,routeKey:'new'},'new')?.text,original.text);
  assert.equal(readAttempt({...original,savedAt:1,routeKey:'new'},'home'),null,'a route key mismatch is not recovered');
  assert.equal(readAttempt({...original,text:'x'.repeat(4001),savedAt:1,routeKey:'new'}),null);
});

function storage(){const data=new Map();return {data,getItem:key=>data.get(key)??null,setItem:(key,value)=>data.set(key,value),removeItem:key=>data.delete(key)};}
test('an unresolved attempt survives in one tab without adopting draft edits',()=>{
  const port=storage(),scope=JSON.stringify(['actor','workspace','project']);
  const stored=writeUnresolvedAttempt(scope,'new',{...original,threadId:null},port,1000);
  assert.equal(stored.savedAt,1000);
  assert.equal(port.data.has(attemptStorageKey(scope,'new')),true);
  assert.deepEqual(readUnresolvedAttempt(scope,'new',port),stored);
  assert.equal(readUnresolvedAttempt(scope,'home',port),null,'a different route is not recovered');
  assert.equal(readUnresolvedAttempt(JSON.stringify(['other','workspace','project']),'new',port),null,'another scope is not recovered');
  assert.equal(readUnresolvedAttempt(scope,'new',{getItem(){throw new Error('denied');},setItem(){throw new Error('denied');},removeItem(){throw new Error('denied');}}),null);
  // Editing the editable draft is a different store; the attempt text is unchanged.
  assert.equal(readUnresolvedAttempt(scope,'new',port).text,'Keep this exact attempt');
  clearUnresolvedAttempt(scope,'new',port);
  assert.equal(readUnresolvedAttempt(scope,'new',port),null);
  // Corrupt or oversized values are ignored rather than replayed.
  port.setItem(attemptStorageKey(scope,'new'),'{nope');
  assert.equal(readUnresolvedAttempt(scope,'new',port),null);
  port.setItem(attemptStorageKey(scope,'new'),'x'.repeat(6001));
  assert.equal(readUnresolvedAttempt(scope,'new',port),null);
  assert.equal(writeUnresolvedAttempt(scope,'new',original,{getItem:()=>null,setItem(){throw new Error('denied');},removeItem(){}}),null);
});
