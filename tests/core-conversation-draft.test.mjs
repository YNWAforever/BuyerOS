import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
registerHooks({resolve(s,c,next){try{return next(s,c);}catch(e){if(s.startsWith('.'))for(const ext of ['.ts','.tsx'])try{return next(s+ext,c);}catch{}throw e;}},load(u,c,next){if(/\.tsx?$/.test(u))return {format:'module',shortCircuit:true,source:ts.transpileModule(readFileSync(new URL(u),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText};return next(u,c);}});

const {ConversationDrafts,draftKey,nextDraft,readDraftValue,draftMaxText}=await import('../features/live/conversation/draft.ts');
const scope={actor:'actor-a',workspace:'workspace-a',project:'project-a'};
const other={actor:'actor-b',workspace:'workspace-a',project:'project-a'};
const threadId='11111111-1111-4111-8111-111111111111';
function storage(){const data=new Map();return {data,getItem:key=>data.get(key)??null,setItem:(key,value)=>data.set(key,value),removeItem:key=>data.delete(key)};}

test('drafts persist per actor, workspace, project and thread only',()=>{
  const port=storage(),drafts=new ConversationDrafts(scope,port);
  const written=drafts.write(threadId,'Draft one',1000);
  assert.equal(written.text,'Draft one');assert.ok(port.data.has(draftKey(scope,threadId)));
  assert.deepEqual(drafts.read(threadId),{...written});
  assert.equal(drafts.read('new'),null);
  assert.equal(new ConversationDrafts({...scope,project:'project-b'},port).read(threadId),null);
  assert.equal(new ConversationDrafts(other,port).read(threadId),null);
  assert.equal(drafts.available,true);
});

test('an identical retry keeps its client message id; edited text mints a new one',()=>{
  const port=storage(),drafts=new ConversationDrafts(scope,port);
  const first=drafts.write(threadId,'Research this buyer',10);
  const retry=drafts.write(threadId,'Research this buyer',20);
  assert.equal(retry.clientMessageId,first.clientMessageId);
  assert.equal(retry.updatedAt,20);
  const edited=drafts.write(threadId,'Research this buyer and prepare follow-up',30);
  assert.notEqual(edited.clientMessageId,first.clientMessageId);
  drafts.clear(threadId);
  assert.equal(drafts.read(threadId),null);
  assert.equal(port.data.has(draftKey(scope,threadId)),false);
});

test('failed-send text survives navigation and reload for the same scope',()=>{
  const port=storage();
  const before=new ConversationDrafts(scope,port);
  const failed=before.write(threadId,'Unsent question',5000);
  const reloaded=new ConversationDrafts(scope,port);
  assert.deepEqual(reloaded.read(threadId),{...failed});
  assert.equal(nextDraft(null,'',6000),null);
  assert.equal(new ConversationDrafts(scope,storage()).available,true);
});

test('corrupt, unsupported, empty and oversized drafts are ignored; blank text clears',()=>{
  const port=storage(),key=draftKey(scope,threadId);
  port.setItem(key,'{corrupt');assert.equal(new ConversationDrafts(scope,port).read(threadId),null);
  port.setItem(key,JSON.stringify({version:99,text:'x',clientMessageId:'11111111-1111-4111-8111-111111111111',boundText:'x',updatedAt:1}));
  assert.equal(new ConversationDrafts(scope,port).read(threadId),null);
  port.setItem(key,JSON.stringify({version:1,text:'x'.repeat(draftMaxText+1),clientMessageId:'11111111-1111-4111-8111-111111111111',boundText:'x'.repeat(draftMaxText+1),updatedAt:1}));
  assert.equal(new ConversationDrafts(scope,port).read(threadId),null);
  assert.equal(readDraftValue(null),null);assert.equal(readDraftValue(42),null);
  const drafts=new ConversationDrafts(scope,port);
  drafts.write(threadId,'Keep me',1);drafts.write(threadId,'   ',2);
  assert.equal(drafts.read(threadId),null);assert.equal(port.data.has(key),false);
});

test('unavailable storage keeps the draft in this tab and never throws',()=>{
  const broken={getItem(){throw new Error('denied');},setItem(){throw new Error('denied');},removeItem(){throw new Error('denied');}};
  const drafts=new ConversationDrafts(scope,broken);
  const draft=drafts.write('new','Compose now',100);
  assert.equal(draft.text,'Compose now');
  assert.deepEqual(drafts.read('new'),{...draft});
  assert.equal(drafts.available,false);
});
