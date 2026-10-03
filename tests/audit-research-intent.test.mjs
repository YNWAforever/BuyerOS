import test from 'node:test';
import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';
const {SessionScope}=await loadModule('services/live/session.ts');
const {startResearch,researchFingerprint,resetResearchIntent}=await loadModule('services/live/runs.ts');
const {LiveCancelled}=await loadModule('services/live/client.ts');
const body={icp_version_id:'e9200000-0000-4000-8000-000000000001',target_companies:24,max_cost:{amount:'2.0',currency:'USD'},limits:{query_rounds:3,max_queries_per_run:12,max_results:300,max_pages:200,max_page_bytes:2097152,max_duration_seconds:1800,max_model_tokens:100000,provider_concurrency:4}};
function context(request){const session=new SessionScope({mode:'live',actor:'stable-subject',workspace:'workspace-a',project:'project-a'});session.setToken('token-one');return {session,client:{request},workspaceId:'workspace-a',projectId:'project-a',apiBaseUrl:''};}
test('B05 token renewal and route remount retain lost-response key; double start shares work',async()=>{
  const calls=[];let fail=true;const ctx=context(async r=>{calls.push(r);if(fail)throw new Error('lost response');return {id:'committed-run'};});
  await Promise.all([assert.rejects(startResearch(ctx,body)),assert.rejects(startResearch(ctx,body))]);assert.equal(calls.length,1);
  ctx.session.setToken('token-two');fail=false;await startResearch({...ctx}, {...body,max_cost:{amount:'2.000000',currency:'USD'}});
  assert.equal(calls.length,2);assert.equal(calls[0].idempotencyKey,calls[1].idempotencyKey);assert.equal(calls[1].token,'token-two');assert.deepEqual(calls[0].body,calls[1].body);
});
test('B06 full normalized payload and actor/scope define intent; generation and key order do not',()=>{
  const ctx=context(async()=>({}));const fingerprint=researchFingerprint(ctx,body);
  ctx.session.next({project:'project-b'});ctx.session.next({project:'project-a'});assert.equal(researchFingerprint(ctx,body),fingerprint);
  assert.equal(researchFingerprint(ctx,{limits:{...body.limits},max_cost:{currency:'USD',amount:'2.000000'},target_companies:24,icp_version_id:body.icp_version_id}),fingerprint);
  for(const changed of [{...body,target_companies:25},{...body,max_cost:{amount:'3',currency:'USD'}},{...body,icp_version_id:'other-icp'},{...body,limits:{...body.limits,max_results:301}}])assert.notEqual(researchFingerprint(ctx,changed),fingerprint);
  for(const changed of [{workspaceId:'workspace-b'},{projectId:'project-b'}])assert.notEqual(researchFingerprint({...ctx,...changed},body),fingerprint);
  ctx.session.next({actor:'other-subject'});assert.notEqual(researchFingerprint(ctx,body),fingerprint);
});
test('B05 A-B-A rejects late result but reuses durable key; explicit reset creates new intent',async()=>{
  let release;const held=new Promise(r=>release=r),calls=[];
  const ctx=context(async r=>{calls.push(r);if(calls.length===1)await held;else if(calls.length===2)throw new Error('still unknown');return {id:'run'};});
  const first=startResearch(ctx,body);await new Promise(r=>setImmediate(r));ctx.session.next({project:'project-b'});ctx.session.next({project:'project-a'});release();await assert.rejects(first,LiveCancelled);
  await assert.rejects(startResearch(ctx,body));assert.equal(calls[1].idempotencyKey,calls[0].idempotencyKey);
  resetResearchIntent(ctx);await startResearch(ctx,body);assert.notEqual(calls[2].idempotencyKey,calls[0].idempotencyKey);
});
