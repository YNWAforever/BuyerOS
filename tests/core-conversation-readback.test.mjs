import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
registerHooks({resolve(s,c,next){try{return next(s,c);}catch(e){if(s.startsWith('.'))for(const ext of ['.ts','.tsx'])try{return next(s+ext,c);}catch{}throw e;}},load(u,c,next){if(/\.tsx?$/.test(u))return {format:'module',shortCircuit:true,source:ts.transpileModule(readFileSync(new URL(u),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText};return next(u,c);}});

const {mergeReadback,staleReadback,isSavedThreadId}=await import('../features/live/conversation/readback.ts');
const id='11111111-1111-4111-8111-111111111111';
const otherId='22222222-2222-4222-8222-222222222222';
const message=(id,seq,text)=>({id,seq,role:'user',text,clientMessageId:null,turnId:null,createdAt:seq,parts:[]});
function thread(version,messages,extra={}){
  return {id,version,templateId:'blank',title:'Thread',createdAt:1,updatedAt:2,
    access:'owner',shareCount:0,buyerId:null,archived:false,messages,sources:[],runs:[],...extra};
}

test('a late older readback never regresses the loaded snapshot',()=>{
  const newer=thread(5,[message('m1',1,'one'),message('m2',2,'two')],{sources:[{id:'source-1',label:'Source one'}],runs:[{id:'run-1',label:'Run one',status:'completed'}]});
  const stale=thread(4,[message('m1',1,'one')]);
  assert.equal(staleReadback(newer,stale),true);
  assert.equal(mergeReadback(newer,stale),newer,'the strict newer snapshot is retained');
  assert.equal(mergeReadback(null,newer),newer);
});

test('an equal or newer full read is authoritative even when it contains less data',()=>{
  const rich=thread(3,[message('m1',1,'one'),message('m2',2,'two')],{sources:[{id:'source-1',label:'One'}],runs:[{id:'run-1',label:'Run',status:'completed'}]});
  // Equal version: permissions changed independently of the thread version, so a
  // later authorized read may legitimately redact messages/sources/runs.
  const redacted=thread(3,[message('m1',1,'one')]);
  assert.equal(mergeReadback(rich,redacted),redacted);
  // Newer version: authoritative even if it omits a previously observed row.
  const newer=thread(4,[message('m1',1,'one')]);
  assert.equal(mergeReadback(rich,newer),newer);
});

test('a readback for a different thread is never merged into the routed one',()=>{
  const current=thread(2,[message('m1',1,'one')]);
  const different={...thread(9,[message('x',1,'other')]),id:otherId};
  assert.equal(mergeReadback(current,different),different);
  assert.equal(staleReadback(current,different),false);
});

test('only exact saved UUIDs are accepted as routes',()=>{
  assert.equal(isSavedThreadId(id),true);
  assert.equal(isSavedThreadId('s/'+id),false);
  assert.equal(isSavedThreadId('local-'+id),false);
  assert.equal(isSavedThreadId('not-a-thread'),false);
  assert.equal(isSavedThreadId(null),false);
});
