import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
registerHooks({resolve(s,c,next){try{return next(s,c);}catch(e){if(s.startsWith('.'))for(const ext of ['.ts','.tsx'])try{return next(s+ext,c);}catch{}throw e;}},load(u,c,next){if(/\.tsx?$/.test(u))return {format:'module',shortCircuit:true,source:ts.transpileModule(readFileSync(new URL(u),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText};return next(u,c);}});

const {TRANSCRIPT_WINDOW,TRANSCRIPT_BATCH,initialWindow,receiveEntryTotal,revealEarlier,hasEarlier,windowSlice}=
  await import('../features/live/conversation/transcript-window.ts');

test('the transcript window renders a bounded latest subset and reveals exactly one batch at a time',()=>{
  const persisted=Array.from({length:100},(_,index)=>index);
  assert.equal(TRANSCRIPT_WINDOW,25,'the documented render window is small and stable');
  assert.equal(TRANSCRIPT_BATCH,25,'one activation reveals one batch');
  // Initial subset: the latest WINDOW persisted entries.
  let state=initialWindow(persisted.length);
  assert.equal(state.initialized,true);
  assert.equal(state.start,75);
  assert.equal(hasEarlier(state),true);
  assert.deepEqual(windowSlice(persisted,state),persisted.slice(75));
  assert.equal(windowSlice(persisted,state).length,TRANSCRIPT_WINDOW);
  // Exact boundary: a fitting thread has no control; one extra reveals just one.
  const exact=initialWindow(TRANSCRIPT_WINDOW);
  assert.equal(exact.start,0);
  assert.equal(hasEarlier(exact),false);
  assert.deepEqual(windowSlice(persisted.slice(0,TRANSCRIPT_WINDOW),exact),persisted.slice(0,TRANSCRIPT_WINDOW));
  const over=initialWindow(TRANSCRIPT_WINDOW+1);
  assert.equal(over.start,1);
  assert.equal(windowSlice(persisted.slice(0,TRANSCRIPT_WINDOW+1),over).length,TRANSCRIPT_WINDOW);
  // Batch math: 100 -> 75 -> 50 -> 25 -> 0, one batch each time.
  state=revealEarlier(initialWindow(100));
  assert.equal(state.start,50);
  state=revealEarlier(state);
  assert.equal(state.start,25);
  state=revealEarlier(state);
  assert.equal(state.start,0);
  assert.equal(hasEarlier(state),false);
  assert.equal(windowSlice(persisted,state).length,100,'the full reveal loses nothing and duplicates nothing');
  // No-op once everything is shown (or when empty); the reducer keeps identity.
  assert.equal(revealEarlier(state),state);
  const empty=initialWindow(0);
  assert.equal(empty.initialized,false);
  assert.equal(revealEarlier(empty),empty);
  assert.equal(windowSlice([],empty).length,0,'an empty history never exceeds its total');
  // A live/streamed entry grows the total but never moves the revealed start.
  state=revealEarlier(initialWindow(100)); // start 50
  const grown=receiveEntryTotal(state,102);
  assert.equal(grown.start,50,'live growth keeps the revealed older entries');
  assert.equal(grown.total,102);
  assert.deepEqual(windowSlice(persisted,grown),persisted.slice(50),'the same 50 older entries stay mounted');
  assert.equal(receiveEntryTotal(grown,102),grown,'an unchanged total is a no-op');
  // A shrinking persisted total clamps so the start can never exceed the total.
  const clamped=receiveEntryTotal({...state,total:120},80);
  assert.equal(clamped.start,50);
  assert.ok(clamped.start<=clamped.total);
  assert.ok(windowSlice(Array.from({length:80}),(clamped)).length<=80);
});
