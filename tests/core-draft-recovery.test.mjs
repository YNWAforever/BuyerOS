import test from 'node:test';
import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';

const {DraftRecovery}=await loadModule('services/live/draft-recovery.ts');
const buffer=(changes={})=>({actor:'actor',workspace:'ws',project:'project',draftId:'draft',revisionId:'rev',
  version:1,subject:'Synthetic subject',body:'Private unsaved text',language:'en',...changes});
function storage(initial=null){
  let raw=initial;
  return {getItem:()=>raw,setItem:(_key,value)=>{raw=value;},removeItem:()=>{raw=null;},get raw(){return raw;}};
}

test('draft recovery rejects corrupt, oversized and non-array stored payloads',()=>{
  for(const raw of ['{bad json',JSON.stringify(buffer()),'x'.repeat(1_000_001),JSON.stringify(Array(65).fill(buffer()))]){
    assert.equal(new DraftRecovery(storage(raw)).find(buffer()),null);
  }
});

test('draft recovery filters invalid rows and refuses tokens or extra grant fields',()=>{
  const invalid=[buffer({access_token:'must-never-restore'}),buffer({approval:true}),buffer({version:0}),
    buffer({version:1.5}),buffer({language:'invalid'}),buffer({body:7}),buffer({actor:''}),
    buffer({revisionId:'x'.repeat(256)}),buffer({body:'x'.repeat(250_001)}),null,[]];
  const valid=buffer({draftId:'valid'}),recovery=new DraftRecovery(storage(JSON.stringify([...invalid,valid])));
  assert.equal(recovery.find(buffer()),null);
  assert.deepEqual(recovery.find(valid),valid);
  for(const value of invalid)assert.throws(()=>recovery.retain(value),/Invalid draft recovery buffer/);
});

test('draft recovery copies inputs and readbacks so edits require explicit retention',()=>{
  const port=storage(),recovery=new DraftRecovery(port),value=buffer();
  assert.equal(recovery.retain(value),true);
  value.body='Changed by caller';
  const found=recovery.find(buffer());
  assert.equal(found.body,'Private unsaved text');
  found.body='Changed by reader';
  assert.equal(recovery.find(buffer()).body,'Private unsaved text');
  assert.equal(new DraftRecovery(port).find(buffer()).body,'Private unsaved text');
});

test('forget removes only the exact actor/workspace/project/draft and clears storage when empty',()=>{
  const port=storage(),recovery=new DraftRecovery(port),own=buffer();
  const others=[{actor:'other'},{workspace:'other'},{project:'other'},{draftId:'other'}].map(change=>buffer(change));
  for(const value of [own,...others])recovery.retain(value);
  recovery.retain(buffer({version:2,body:'Updated'}));
  assert.equal(JSON.parse(port.raw).length,5);
  recovery.forget(own);
  const reloaded=new DraftRecovery(port);
  assert.equal(reloaded.find(own),null);
  for(const value of others)assert.deepEqual(reloaded.find(value),value);
  for(const value of others)reloaded.forget(value);
  assert.equal(port.raw,null);
});

test('unavailable browser storage leaves recovery usable in memory',()=>{
  const port={getItem(){throw new Error('blocked');},setItem(){throw new Error('quota');},removeItem(){throw new Error('blocked');}};
  const recovery=new DraftRecovery(port);
  assert.equal(recovery.retain(buffer()),false);
  assert.deepEqual(recovery.find(buffer()),buffer());
  recovery.forget(buffer());
  assert.equal(recovery.find(buffer()),null);
});

test('recovery capacity refuses persistence without evicting dirty in-memory drafts',()=>{
  const port=storage(),recovery=new DraftRecovery(port);
  for(let i=0;i<64;i++)assert.equal(recovery.retain(buffer({draftId:`draft-${i}`})),true);
  assert.equal(recovery.retain(buffer({draftId:'overflow'})),false);
  for(let i=0;i<64;i++)assert.deepEqual(recovery.find(buffer({draftId:`draft-${i}`})),buffer({draftId:`draft-${i}`}));
  assert.deepEqual(recovery.find(buffer({draftId:'overflow'})),buffer({draftId:'overflow'}));
  assert.equal(JSON.parse(port.raw).length,64);
  recovery.forget(buffer({draftId:'draft-0'}));
  assert.deepEqual(new DraftRecovery(port).find(buffer({draftId:'overflow'})),buffer({draftId:'overflow'}));
});
