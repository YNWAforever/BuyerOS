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
const load=()=>import('../services/live/work-queue.ts');
const rows=[['awaiting_review',{review:'awaiting_review'}],['pending_approval',{approval:'pending'}],['unassigned',{queue:'unassigned'}],['failed_job',{status:'failed'}],['unknown_fit',{queue:'unknown'}],['unknown_acceptance',{acceptance:'unknown'}]];
const summary=()=>({as_of:'2026-10-07T00:01:02+00:00',items:rows.map(([kind,filters],count)=>({kind,count,filters}))});
const scope={workspaceId:'workspace-a',projectId:'project-a'};
async function session(){const {SessionScope}=await import('../services/live/session.ts');const s=new SessionScope({mode:'live',actor:'canonical',workspace:'workspace-a',project:'project-a'});s.setToken('fixture');return s;}

test('C61T-09 every card links to its actual typed scope and filtered list',async()=>{
 const {workQueueLink}=await load();const expected=[['/app/results','review','awaiting_review'],['/app/outreach','approval','pending'],['/app/results','queue','unassigned'],['/app/operations','job_status','failed'],['/app/results','queue','unknown'],['/app/operations','acceptance','unknown']];
 summary().items.forEach((item,i)=>{const url=new URL(workQueueLink(item,scope),'https://fixture.test');assert.equal(url.pathname,expected[i][0]);assert.equal(url.searchParams.get(expected[i][1]),expected[i][2]);assert.equal(url.searchParams.get('workspace'),'workspace-a');assert.equal(url.searchParams.get('project'),'project-a');});
});
test('C61T-09 successful summary retains server as_of and real zero counts',async()=>{
 const {loadWorkQueue}=await load(),s=await session();let request;
 const value=await loadWorkQueue({request:async r=>{request=r;return summary();}},s);
 assert.equal(value.as_of,'2026-10-07T00:01:02+00:00');assert.equal(value.items[0].count,0);
 assert.equal(request.method,'GET');assert.match(request.path,/workspaces\/workspace-a\/projects\/project-a\/work-queue$/);assert.equal(request.token,'fixture');
});
test('C61T-09 held A summary cannot publish after A-B-A scope changes',async()=>{
 const {loadWorkQueue}=await load(),s=await session();let started,release;const begun=new Promise(r=>started=r),held=new Promise(r=>release=r);
 const pending=loadWorkQueue({request:async()=>{started();await held;return summary();}},s);const {LiveCancelled}=await import('../services/live/client.ts');const rejected=assert.rejects(pending,error=>error instanceof LiveCancelled);
 await begun;s.next({project:'project-b'});s.next({project:'project-a'});release();await rejected;
});
test('C61T-09 unavailable, partial or malformed summary never becomes fabricated zero',async()=>{
 const {loadWorkQueue}=await load(),s=await session();
 const unavailable=new Error('fixture 503');await assert.rejects(loadWorkQueue({request:async()=>{throw unavailable;}},s),e=>e===unavailable);
 for(const bad of [{...summary(),items:[]},{...summary(),as_of:'not a date'},{...summary(),items:summary().items.map((x,i)=>i?x:{...x,count:-1})},{...summary(),items:summary().items.map((x,i)=>i?x:{...x,filters:{queue:'unknown'}})}])await assert.rejects(loadWorkQueue({request:async()=>bad},s));
});
test('C61T-09 receipt page uses generated acceptance enum and captured scope',async()=>{
 const {listProviderOperations}=await load(),s=await session();let request;
 const value=await listProviderOperations({request:async r=>{request=r;return {items:[],offset:20,limit:20,total:23};}},s,'unknown',20,20);
 const url=new URL(request.path,'https://fixture.test');assert.equal(url.searchParams.get('acceptance'),'unknown');assert.equal(url.searchParams.get('offset'),'20');assert.equal(value.total,23);
});
