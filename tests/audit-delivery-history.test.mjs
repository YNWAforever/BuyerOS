import test from 'node:test';
import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';
const {SessionScope}=await loadModule('services/live/session.ts');
const {LiveCancelled}=await loadModule('services/live/client.ts');
async function fixture(){
 const {listDraftDeliveryMessages}=await loadModule('services/live/delivery-history.ts');
 const session=new SessionScope({mode:'live',actor:'canonical-user',workspace:'workspace-a',project:'project-a'});session.setToken('memory-only');
 const draft={id:'draft-a',workspace_id:'workspace-a',project_id:'project-a'};
 const row={id:'message-a',workspace_id:'workspace-a',project_id:'project-a',draft_id:'draft-a',draft_revision_id:'revision-a',revision_number:1,approval_id:'approval-a',state:'unknown',created_at:'2026-10-11T00:00:00Z',updated_at:'2026-10-11T00:00:00Z'};
 const page={items:[row],offset:0,limit:20,total:1},calls=[];
 const client={request:async request=>{calls.push(request);return page;}};
 return {read:listDraftDeliveryMessages,session,draft,row,page,calls,client};
}
test('C61-20 history reads exact generated scoped GET without body/key or submission',async()=>{
 const f=await fixture();assert.equal((await f.read(f.client,f.session,f.draft,0)).items[0].id,'message-a');
 assert.equal(f.calls.length,1);const r=f.calls[0],url=new URL(r.path,'http://fixture.test');
 assert.equal(url.pathname,'/v1/workspaces/workspace-a/projects/project-a/drafts/draft-a/delivery-messages');
 assert.equal(url.searchParams.get('limit'),'20');assert.equal(url.searchParams.get('offset'),'0');assert.equal(r.method,'GET');assert.equal(r.token,'memory-only');assert.equal(r.body,undefined);assert.equal(r.idempotencyKey,undefined);
});
for(const field of ['workspace_id','project_id'])test(`C61-20 history rejects foreign draft ${field} before IO`,async()=>{
 const f=await fixture();await assert.rejects(f.read(f.client,f.session,{...f.draft,[field]:'foreign'},0));assert.equal(f.calls.length,0);
});
for(const field of ['workspace_id','project_id','draft_id'])test(`C61-20 history rejects foreign returned ${field}`,async()=>{
 const f=await fixture();f.row[field]='foreign';await assert.rejects(f.read(f.client,f.session,f.draft,0));assert.equal(f.calls.length,1);
});
for(const fault of ['offset','limit','total','too-many','duplicate'])test(`C61-20 history rejects inconsistent page ${fault}`,async()=>{
 const f=await fixture();if(fault==='offset')f.page.offset=20;else if(fault==='limit')f.page.limit=100;else if(fault==='total')f.page.total=0;else if(fault==='too-many')f.page.items=Array.from({length:21},(_,i)=>({...f.row,id:'message-'+i}));else f.page.items=[f.row,f.row];
 await assert.rejects(f.read(f.client,f.session,f.draft,0));
});
test('C61-20 delayed history A-B-A response cannot re-enter the current scope',async()=>{
 const f=await fixture();let release;f.client.request=async r=>{f.calls.push(r);await new Promise(resolve=>release=resolve);return f.page;};
 const pending=f.read(f.client,f.session,f.draft,0);await new Promise(r=>setImmediate(r));f.session.next({workspace:'workspace-b'});f.session.next({workspace:'workspace-a'});release();
 await assert.rejects(pending,LiveCancelled);assert.equal(f.calls.length,1);
});
