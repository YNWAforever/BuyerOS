import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';
const require=createRequire(import.meta.url);
let js=ts.transpileModule(readFileSync('features/live/draft-dirty-guard.tsx','utf8'),{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
js=js.replace(/from\s*(['"])(react(?:\/jsx-runtime)?)\1/g,(_,q,spec)=>'from '+JSON.stringify(pathToFileURL(require.resolve(spec)).href));
const {guardDraftTransition}=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));
for(const decision of ['save','discard','cancel'])test(`D02 ${decision} has the required transition order`,async()=>{
  const calls=[];const result=await guardDraftTransition({dirty:true,choose:async()=>{calls.push('choose');return decision;},save:async()=>{calls.push('save');},proceed:async()=>{calls.push('proceed');}});
  assert.equal(result,decision!=='cancel');assert.deepEqual(calls,decision==='cancel'?['choose']:decision==='save'?['choose','save','proceed']:['choose','proceed']);
});
for(const status of [412,503])test(`D02 rejected save ${status} cannot proceed`,async()=>{
  let changed=false;await assert.rejects(guardDraftTransition({dirty:true,choose:async()=> 'save',save:async()=>{throw new Error(String(status));},proceed:async()=>{changed=true;}}),new RegExp(String(status)));assert.equal(changed,false);
});
test('D02 clean transition does not prompt or write',async()=>{let count=0;assert.equal(await guardDraftTransition({dirty:false,choose:async()=>{throw new Error('unexpected prompt');},save:async()=>{throw new Error('unexpected save');},proceed:async()=>{count++;}}),true);assert.equal(count,1);});
test('D02 asynchronous Save completes before proceeding',async()=>{let release;const held=new Promise(r=>release=r);let proceeded=false;const pending=guardDraftTransition({dirty:true,choose:async()=> 'save',save:async()=>held,proceed:async()=>{proceeded=true;}});await new Promise(r=>setImmediate(r));assert.equal(proceeded,false);release();await pending;assert.equal(proceeded,true);});
