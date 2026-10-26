import test from 'node:test';
import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';

const {SessionScope}=await loadModule('services/live/session.ts');
const {startResearch,resetResearchIntent,normalizeResearchBody,hasUncertainResearch,uncertainResearchBody}=
  await loadModule('services/live/runs.ts');
const body=()=>({icp_version_id:'E9200000-0000-4000-8000-000000000001',target_companies:2,
  max_cost:{amount:' 2.5 ',currency:'USD'},limits:{max_results:10,max_pages:5}});
const context=request=>{
  const session=new SessionScope({mode:'live',actor:'actor',workspace:'ws',project:'project'});
  session.setToken('memory-token');
  return {session,client:{request},workspaceId:'ws',projectId:'project',apiBaseUrl:''};
};

test('research admission normalizes exact fixed-point money without mutating the caller',()=>{
  const original=body(),normalized=normalizeResearchBody(original);
  assert.equal(normalized.max_cost.amount,'2.500000');
  assert.equal(normalized.icp_version_id,original.icp_version_id.toLowerCase());
  normalized.limits.max_pages=99;
  normalized.max_cost.amount='3.000000';
  assert.deepEqual(original,body());
  assert.equal(normalizeResearchBody({...body(),max_cost:{amount:'99999999999999.999999',currency:'USD'}}).max_cost.amount,
    '99999999999999.999999');
});

test('invalid research caps are refused before any HTTP admission',()=>{
  let requests=0;
  const ctx=context(async()=>{requests++;});
  for(const amount of ['-1','1e2','NaN','Infinity','01','1.1234567','100000000000000','']){
    assert.throws(()=>startResearch(ctx,{...body(),max_cost:{amount,currency:'USD'}}),/fixed-point cap/);
  }
  assert.equal(requests,0);
});

test('an uncertain research request blocks edited limits until explicit reconciliation reset',async()=>{
  const calls=[],ctx=context(async request=>{calls.push(request);throw new Error('acknowledgement lost');});
  const original=body();
  await assert.rejects(startResearch(ctx,original),/acknowledgement lost/);
  assert.equal(hasUncertainResearch(ctx),true);
  original.limits.max_pages=99;
  const recovered=uncertainResearchBody(ctx);
  assert.equal(recovered.limits.max_pages,5);
  recovered.limits.max_pages=88;
  assert.equal(uncertainResearchBody(ctx).limits.max_pages,5);
  assert.throws(()=>startResearch(ctx,original),/Check existing runs/);
  assert.equal(calls.length,1);
  resetResearchIntent(ctx);
  await assert.rejects(startResearch(ctx,original),/acknowledgement lost/);
  assert.notEqual(calls[1].idempotencyKey,calls[0].idempotencyKey);
});

test('pending admission cannot be reset and successful completion releases the intent',async()=>{
  let release;
  const held=new Promise(resolve=>{release=resolve;}),calls=[];
  const ctx=context(async request=>{calls.push(request);return held;});
  const first=startResearch(ctx,body());
  await new Promise(resolve=>setImmediate(resolve));
  assert.throws(()=>resetResearchIntent(ctx),/still pending/);
  assert.equal(startResearch(ctx,body()),first);
  release({id:'saved-run'});
  assert.deepEqual(await first,{id:'saved-run'});
  assert.equal(hasUncertainResearch(ctx),false);
  assert.equal(uncertainResearchBody(ctx),null);
  await startResearch(ctx,body());
  assert.equal(calls.length,2);
  assert.notEqual(calls[0].idempotencyKey,calls[1].idempotencyKey);
});
