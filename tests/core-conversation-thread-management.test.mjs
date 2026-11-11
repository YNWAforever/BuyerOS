import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
registerHooks({resolve(s,c,next){try{return next(s,c);}catch(e){if(s.startsWith('.'))for(const ext of ['.ts','.tsx'])try{return next(s+ext,c);}catch{}throw e;}},load(u,c,next){if(/\.tsx?$/.test(u))return {format:'module',shortCircuit:true,source:ts.transpileModule(readFileSync(new URL(u),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText};return next(u,c);}});

const {nextThreadPreferences,preferenceAllowed,shareControlVisible,sortThreadRows,visibleThreadRows,
  persistThreadPreference,applyStoredPreference,applyStoredListPreference}=await import('../features/live/conversation/thread-management.ts');
const {liveZh}=await import('../features/live/locale.ts');

test('pin and archive payloads preserve the other preference flag',async()=>{
  const pinned={pinned:true,archived:false},archived={pinned:true,archived:true};
  const input={pinned:false,archived:true},snapshot={...input};
  assert.deepEqual(nextThreadPreferences(archived,'pin'),{pinned:false,archived:true},'unpin keeps archived');
  assert.deepEqual(nextThreadPreferences(pinned,'archive'),{pinned:true,archived:true},'archive keeps pinned');
  assert.deepEqual(nextThreadPreferences({pinned:false,archived:true},'pin'),{pinned:true,archived:true});
  nextThreadPreferences(input,'pin');
  assert.deepEqual(input,snapshot,'the input preference is never mutated');
  const sent=[];
  const api={preferences:async(id,pinnedFlag,archivedFlag)=>{sent.push([id,pinnedFlag,archivedFlag]);
    return {pinned:pinnedFlag,archived:archivedFlag};}};
  const {stored}=await persistThreadPreference(api,'thread-1',{pinned:true,archived:true},'pin');
  assert.deepEqual(sent,[['thread-1',false,true]],'the request carries both flags, never one alone');
  assert.deepEqual(stored,{pinned:false,archived:true});
});

test('pin/archive stay available to every access role while sharing is owner-only',()=>{
  for(const access of ['owner','editor','viewer'])assert.equal(preferenceAllowed(access),true,access);
  assert.equal(shareControlVisible('owner'),true);
  assert.equal(shareControlVisible('editor'),false,'an editor gets the badge, not the owner dialog');
  assert.equal(shareControlVisible('viewer'),false,'a viewer never opens a dialog whose reads 404');
});

test('pinned-first ordering and archive visibility follow the persisted row',()=>{
  const rows=[{id:'older',updatedAt:10,pinned:false},{id:'newer',updatedAt:20,pinned:false},
    {id:'pinned',updatedAt:5,pinned:true}];
  assert.deepEqual(sortThreadRows(rows).map(row=>row.id),['pinned','newer','older'],'pinned rows sort first, then recency');
  rows.find(row=>row.id==='older').pinned=true;
  assert.deepEqual(sortThreadRows(rows).map(row=>row.id),['older','pinned','newer'],'a newly pinned row moves to the front');
  const items=[{id:'normal',archived:false},{id:'gone',archived:true}];
  assert.deepEqual(visibleThreadRows(items,false).map(row=>row.id),['normal'],'archived rows leave the normal list');
  assert.deepEqual(visibleThreadRows(items,true).map(row=>row.id),['normal','gone'],'the archive view keeps them');
});

test('only a stored preference updates a row; a failure keeps prior state and draft-safe inputs',async()=>{
  const baseline={id:'thread-1',pinned:false,archived:false};
  const failed={preferences:async()=>{throw new Error('preferences failed');}};
  const draft='unsent text stays';
  await assert.rejects(persistThreadPreference(failed,'thread-1',{pinned:false,archived:false},'pin'));
  assert.deepEqual(baseline,{id:'thread-1',pinned:false,archived:false},'no optimistic state is applied');
  assert.equal(draft,'unsent text stays','composer text is untouched by a preference failure');
  const stored={pinned:true,archived:false};
  assert.deepEqual(applyStoredPreference(baseline,stored),{id:'thread-1',pinned:true,archived:false});
  const list=[baseline,{id:'thread-2',pinned:false,archived:false}];
  assert.deepEqual(applyStoredListPreference(list,'thread-1',stored),
    [{id:'thread-1',pinned:true,archived:false},{id:'thread-2',pinned:false,archived:false}]);
  assert.equal(list[0].pinned,false,'the previous list is not mutated');
  assert.deepEqual(applyStoredListPreference(list,'thread-1',null),list,'a missing payload leaves rows untouched');
});

test('new pin/archive strings have EN and zh-HK copy',()=>{
  for(const key of ['Pin discussion','Unpin discussion','Archive discussion','Restore discussion'])
    assert.equal(typeof liveZh[key],'string',key);
});
