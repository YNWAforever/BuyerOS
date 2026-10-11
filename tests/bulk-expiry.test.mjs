import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const root=resolve('.'),rootUrl=pathToFileURL(root+'/').href;
registerHooks({resolve(specifier,context,next){
 if(specifier.startsWith('@/'))specifier=pathToFileURL(resolve(root,specifier.slice(2))).href;
 try{return next(specifier,context);}catch(error){
  if(error.code!=='ERR_MODULE_NOT_FOUND'||!context.parentURL?.startsWith(rootUrl))throw error;
  for(const ext of ['.ts','.tsx']){try{return next(specifier+ext,context);}catch{}}
  throw error;
 }
},load(url,context,next){
 if(url.startsWith(rootUrl)&&/\.tsx?$/.test(url))return {format:'module',shortCircuit:true,source:ts.transpileModule(readFileSync(new URL(url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText};
 return next(url,context);
}});

const manifest=()=>({id:'manifest-a',workspace_id:'workspace-a',project_id:'project-a',actor_user_id:'canonical',operation:'assignBuyerOwners',target:{owner_membership_id:null},filters:{},excluded_ids:[],reason:'Reviewed fixture maintenance',count:1,digest:'a'.repeat(64),expires_at:'2026-10-07T00:15:00+00:00',created_at:'2026-10-07T00:00:00+00:00',status:'ready',version:1});
test('C61T-11 exact fifteen minute deadline invalidates a new confirmation',async()=>{
 const {manifestConfirmationAvailable}=await import('../services/live/bulk-manifests.ts');
 const item=manifest(),deadline=Date.parse(item.expires_at);
 assert.equal(manifestConfirmationAvailable(item,deadline-1),true);
 assert.equal(manifestConfirmationAvailable(item,deadline),false);
 assert.equal(manifestConfirmationAvailable(item,deadline+1),false);
});
test('C61T-11 invalid expiry, clock or terminal state cannot permit confirmation',async()=>{
 const {manifestConfirmationAvailable}=await import('../services/live/bulk-manifests.ts');
 const now=Date.parse('2026-10-07T00:01:00Z');
 for(const item of [{...manifest(),expires_at:'invalid'},{...manifest(),expires_at:'2026-10-07T00:15:00'},{...manifest(),status:'executed'}])assert.equal(manifestConfirmationAvailable(item,now),false);
 assert.equal(manifestConfirmationAvailable(manifest(),NaN),false);
 assert.equal(manifestConfirmationAvailable(null,now),false);
});
test('C61T-11 lost execution after expiry retains exact intent key body and version',async()=>{
 const {executeManifest}=await import('../services/live/bulk-manifests.ts'),{SessionScope}=await import('../services/live/session.ts');
 const s=new SessionScope({mode:'live',actor:'canonical',workspace:'workspace-a',project:'project-a'});s.setToken('fixture');
 const sent=[],item=manifest(),value={updated:1,unchanged:0,blocked:0,conflicts:0,items:[]};
 const client={request:async request=>{sent.push(request);if(sent.length===1)throw new Error('Fixture committed response lost');return value;}};
 await assert.rejects(executeManifest(client,s,item));item.expires_at='2020-01-01T00:00:00Z';
 assert.deepEqual(await executeManifest(client,s,item),value);
 assert.equal(sent.length,2);assert.equal(sent[1].idempotencyKey,sent[0].idempotencyKey);
 assert.deepEqual(sent[1].body,sent[0].body);assert.equal(sent[1].ifMatch,sent[0].ifMatch);
});
