import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {loadModule} from './ts-loader.mjs';

const {SessionScope}=await loadModule('services/live/session.ts');
async function api(){
  assert.ok(fs.existsSync('services/live/lead-intents.ts'),'Durable lead client is missing');
  return loadModule('services/live/lead-intents.ts');
}
const input=()=>({action:'case.update',buyer_id:'buyer',expected_version:7,payload:{
  priority:true,priority_reason:'Official rice wholesale catalog',next_action:'Check purchasing manager',
}});
function setup(request){
  const session=new SessionScope({mode:'live',actor:'actor',workspace:'ws',project:'p'});
  session.setToken('memory-only-token');
  return {session,client:{request}};
}
function server(){
  let row=null,deny=false,losePrepare=false,loseApply=false;
  const requests=[];
  const request=async r=>{
    requests.push(structuredClone({...r,signal:undefined}));
    if(deny)throw new Error('403 current membership denied');
    if(r.method==='POST'&&r.path.endsWith('/lead-intents')){
      row??={id:'intent',workspace_id:'ws',project_id:'p',buyer_id:'buyer',action:r.body.action,
        target_id:null,expected_version:r.body.expected_version,prepare_key:r.idempotencyKey,
        submission_key:'original-submit-key',payload_hash:'sha256:payload',payload:structuredClone(r.body.payload),
        state:'prepared',receipt:null,acknowledged_at:null,redacted:false,created_at:'2026-10-16T00:00:00Z'};
      if(losePrepare){losePrepare=false;throw new Error('prepare acknowledgement lost');}
      return structuredClone(row);
    }
    if(r.method==='POST'&&r.path.endsWith('/apply')){
      row.state='applied';
      row.receipt={intent_id:row.id,resource_type:'lead_case',resource_id:'case',resource_version:8,state:'applied',redacted:false};
      if(loseApply){loseApply=false;throw new Error('apply acknowledgement lost');}
      return structuredClone(row.receipt);
    }
    if(r.method==='POST'&&r.path.endsWith('/acknowledgements')){
      row.acknowledged_at='2026-10-16T00:00:10Z';return structuredClone(row);
    }
    if(r.method==='POST'&&r.path.endsWith('/cancel')){
      row.state='cancelled';return structuredClone(row);
    }
    if(r.path.includes('/lead-intents/'))return structuredClone(row);
    return {items:row&&!row.acknowledged_at&&row.state!=='cancelled'?[structuredClone(row)]:[],offset:0,limit:100,
      total:row&&!row.acknowledged_at&&row.state!=='cancelled'?1:0};
  };
  return {request,requests,get row(){return row;},set deny(v){deny=v;},
    set losePrepare(v){losePrepare=v;},set loseApply(v){loseApply=v;}};
}

test('test_prepare_and_apply_unknown_recover_original_intent',async()=>{
  const m=await api(),s=server(),ctx=setup(s.request),body=input();
  s.losePrepare=true;
  await assert.rejects(m.prepareLeadIntent(ctx.client,ctx.session,body),/acknowledgement lost/);
  const recovered=await m.recoverLeadIntents(ctx.client,ctx.session);
  assert.equal(recovered.length,1);
  const staged=await m.prepareLeadIntent(ctx.client,ctx.session,body);
  assert.equal(staged.id,recovered[0].id);
  assert.equal(s.requests.filter(r=>r.method==='POST'&&r.path.endsWith('/lead-intents')).length,1);
  const edited=structuredClone(body);edited.payload.next_action='Different unpublished edit';
  await assert.rejects(m.prepareLeadIntent(ctx.client,ctx.session,edited),/reconcil|pending|original/i);
  s.loseApply=true;
  await assert.rejects(m.applyLeadIntent(ctx.client,ctx.session,staged),/acknowledgement lost/);
  const receipt=await m.applyLeadIntent(ctx.client,ctx.session,staged);
  assert.equal(receipt.resource_id,'case');
  const mutations=s.requests.filter(r=>r.method==='POST'&&r.path.endsWith('/apply'));
  assert.equal(mutations.length,1);
  assert.equal(mutations[0].idempotencyKey,'original-submit-key');
  assert.equal(mutations[0].ifMatch,'"7"');
  assert.deepEqual(mutations[0].body,{});
  await m.acknowledgeLeadIntent(ctx.client,ctx.session,staged.id);
  assert.deepEqual(await m.recoverLeadIntents(ctx.client,ctx.session),[]);
});

test('test_revoked_actor_cannot_read_apply_or_replay_intent',async()=>{
  const m=await api(),s=server(),ctx=setup(s.request);
  const staged=await m.prepareLeadIntent(ctx.client,ctx.session,input());
  await m.applyLeadIntent(ctx.client,ctx.session,staged);
  s.deny=true;
  await assert.rejects(m.applyLeadIntent(ctx.client,ctx.session,staged),/403/);
  await assert.rejects(m.recoverLeadIntents(ctx.client,ctx.session),/403/);
  assert.equal(s.requests.filter(r=>r.method==='POST'&&r.path.endsWith('/apply')).length,1);
});

test('test_scope_transition_discards_old_result_without_changing_intent',async()=>{
  const m=await api();
  let release,started;
  const began=new Promise(resolve=>{started=resolve;});
  const gate=new Promise(resolve=>{release=resolve;});
  const requests=[];
  const ctx=setup(async r=>{
    requests.push(r);
    if(r.method==='POST'){started();await gate;return {id:'old',workspace_id:'ws',project_id:'p',buyer_id:'buyer',state:'prepared'};}
    return {items:[],offset:0,limit:100,total:0};
  });
  const pending=m.prepareLeadIntent(ctx.client,ctx.session,input());
  await began;
  ctx.session.next({project:'other'});
  release();
  await assert.rejects(pending,/scope|project|cancel/i);
  assert.equal(requests.find(r=>r.method==='POST').path,'/v1/workspaces/ws/projects/p/lead-intents');
  assert.equal(requests.find(r=>r.method==='POST').body.expected_version,7);
});

test('test_retention_redacts_recoverable_payload_and_replay',async()=>{
  const beforeLocal=globalThis.localStorage,beforeSession=globalThis.sessionStorage;
  const writes=[];
  const storage={getItem(){throw new Error('Storage must not be read');},setItem(...args){writes.push(args);},removeItem(){}};
  globalThis.localStorage=storage;globalThis.sessionStorage=storage;
  try{
    const m=await api(),s=server(),ctx=setup(s.request),body=input();
    body.payload.next_action='Contact Alex Fixture';
    const staged=await m.prepareLeadIntent(ctx.client,ctx.session,body);
    s.row.payload=null;s.row.redacted=true;
    const recovered=await m.recoverLeadIntents(ctx.client,ctx.session);
    assert.equal(recovered[0].payload,null);
    assert.ok(!JSON.stringify(recovered).includes('Alex Fixture'));
    await assert.rejects(m.applyLeadIntent(ctx.client,ctx.session,staged),/unavailable|retained|redact/i);
    assert.equal(s.requests.filter(r=>r.method==='POST'&&r.path.endsWith('/apply')).length,0);
    assert.deepEqual(writes,[]);
  }finally{
    if(beforeLocal===undefined)delete globalThis.localStorage;else globalThis.localStorage=beforeLocal;
    if(beforeSession===undefined)delete globalThis.sessionStorage;else globalThis.sessionStorage=beforeSession;
  }
});

test('foreign intent scope is rejected before any HTTP write',async()=>{
  const m=await api(),s=server(),ctx=setup(s.request);
  const staged=await m.prepareLeadIntent(ctx.client,ctx.session,input());
  const before=s.requests.length;
  await assert.rejects(m.applyLeadIntent(ctx.client,ctx.session,{...staged,project_id:'foreign'}),/scope|project/i);
  assert.equal(s.requests.length,before);
});

test('definitive prepare validation failure permits a corrected edit without inventing an unknown retry',async()=>{
  const m=await api(),s=server();
  const {LiveError}=await loadModule('services/live/client.ts');
  let first=true;
  const ctx=setup(async request=>{
    if(first&&request.method==='POST'&&request.path.endsWith('/lead-intents')){
      first=false;throw new LiveError('Invalid values','INVALID_REQUEST',422,'fixture',false);
    }
    return s.request(request);
  });
  await assert.rejects(m.prepareLeadIntent(ctx.client,ctx.session,input()),/Invalid values/);
  const corrected=input();corrected.payload.next_action='Corrected action';
  const result=await m.prepareLeadIntent(ctx.client,ctx.session,corrected);
  assert.equal(result.payload.next_action,'Corrected action');
});
