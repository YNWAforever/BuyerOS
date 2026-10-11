import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {loadModule} from './ts-loader.mjs';
const {SessionScope}=await loadModule('services/live/session.ts');
async function api(){assert.ok(fs.existsSync('services/live/research-candidates.ts'),'C61-19 native candidate client is missing');return loadModule('services/live/research-candidates.ts');}
function setup(request){const session=new SessionScope({mode:'live',actor:'actor',workspace:'ws',project:'p'});session.setToken('in-memory-token');return {session,client:{request},apiBaseUrl:'https://api.example.test',workspaceId:'ws',projectId:'p'};}
const basis=()=>({run_id:'run',project_id:'p',raw_candidate_id:'raw',company:{id:'company',legal_name:'Independent company',domain:'example.test',hash:'a'.repeat(64)},page:{id:'source',digest:'b'.repeat(64),excerpt:'Independent company page quote',url:'https://example.test/page',retention_until:new Date(Date.now()+60_000).toISOString()},entity_status:'needs_review',fit_status:'needs_review'});
const result={buyer_id:'buyer',evidence_id:'evidence',alias_id:'alias',entity_status:'reviewed',fit_status:'needs_review'};
function fill(d){d.companyId='company';d.context=basis();d.excerpt=d.context.page.excerpt;d.reason='Explicit independent company selection';return d;}

test('candidate reads use scoped generated operations and never submit on load',async()=>{
  const m=await api(),requests=[],ctx=setup(async r=>{requests.push(r);return r.path.includes('review-context')?basis():{items:[],offset:20,limit:20,total:40};});
  const page=await m.loadResearchCandidates(ctx,'run',20,20);assert.equal(page.total,40);
  const value=await m.getCandidateReviewContext(ctx,'run','raw','company');assert.equal(value.company.id,'company');
  assert.match(requests[0].path,/runs\/run\/candidates\?offset=20&limit=20$/);
  assert.match(requests[1].path,/raw\/review-context\?company_id=company$/);
  assert.ok(requests.every(r=>r.method==='GET'&&r.body===undefined&&r.token==='in-memory-token'));
});
test('candidate reads reject old scope before IO and delayed old responses after IO',async()=>{
  const m=await api();let calls=0,resolve;const ctx=setup(async()=>{calls++;return new Promise(r=>resolve=r);});
  const pending=m.loadResearchCandidates(ctx,'run');await new Promise(r=>setTimeout(r,0));ctx.session.next({workspace:'other',project:null});resolve({items:[],offset:0,limit:20,total:0});
  await assert.rejects(pending,/scope changed/);await assert.rejects(m.getCandidateReviewContext(ctx,'run','raw','company'),/scope changed/);assert.equal(calls,1);
});
test('lost review acknowledgement retains one frozen key and pending double-click shares one request',async()=>{
  const m=await api(),requests=[];let reject;const ctx=setup(async r=>{requests.push(r);if(requests.length===1)return new Promise((_,j)=>reject=j);return result;});
  const d=fill(m.candidateReviewDraft(ctx,'run','raw')),a=m.submitCandidateReview(ctx,'run','raw',d),b=m.submitCandidateReview(ctx,'run','raw',d);
  await new Promise(r=>setTimeout(r,0));assert.equal(requests.length,1);reject(new Error('ack lost'));await Promise.all([assert.rejects(a,/ack lost/),assert.rejects(b,/ack lost/)]);
  assert.equal(d.phase,'unknown');d.reason='Changed after unknown';await assert.rejects(m.submitCandidateReview(ctx,'run','raw',d),/frozen/);assert.equal(requests.length,1);
  d.reason='Explicit independent company selection';const retried=await m.submitCandidateReview(ctx,'run','raw',d);assert.deepEqual(retried,result);
  assert.equal(requests[0].idempotencyKey,requests[1].idempotencyKey);assert.deepEqual(requests[0].body,requests[1].body);
  assert.deepEqual(Object.keys(requests[1].body).sort(),['company_id','excerpt','expected_company_hash','expected_page_digest','page_source_id','reason']);
});
test('accepted review never submits again and same session remount retains dirty draft without credentials',async()=>{
  const m=await api();let calls=0;const ctx=setup(async()=>{calls++;return result;}),d=fill(m.candidateReviewDraft(ctx,'run','raw'));
  await m.submitCandidateReview(ctx,'run','raw',d);assert.equal(d.phase,'accepted');await m.submitCandidateReview(ctx,'run','raw',d);assert.equal(calls,1);
  assert.equal(m.candidateReviewDraft({...ctx},'run','raw'),d);assert.ok(!JSON.stringify(d).includes('in-memory-token'));
  const other=setup(async()=>result);assert.notEqual(m.candidateReviewDraft(other,'run','raw'),d);
});
test('foreign context and expired context cannot become a review request; server denial remains failure',async()=>{
  const m=await api();let calls=0;const ctx=setup(async()=>{calls++;throw new Error('403 current membership denied');}),d=fill(m.candidateReviewDraft(ctx,'run','raw'));
  d.context.project_id='foreign';await assert.rejects(m.submitCandidateReview(ctx,'run','raw',d),/context/);assert.equal(calls,0);
  d.context=basis();d.context.page.retention_until=new Date(Date.now()-1000).toISOString();await assert.rejects(m.submitCandidateReview(ctx,'run','raw',d),/expired/);assert.equal(calls,0);
  const fresh=setup(ctx.client.request),denied=fill(m.candidateReviewDraft(fresh,'run','raw'));await assert.rejects(m.submitCandidateReview(fresh,'run','raw',denied),/403/);assert.equal(denied.result,null);assert.notEqual(denied.phase,'accepted');
});

test('expired client source copy is erased while original unknown key and reconciliation are retained',async()=>{
  const m=await api();let calls=0;const ctx=setup(async()=>{calls++;throw new Error('ack lost');}),d=fill(m.candidateReviewDraft(ctx,'run','raw'));
  await assert.rejects(m.submitCandidateReview(ctx,'run','raw',d),/ack lost/);const key=d.key;d.context.page.retention_until=new Date(Date.now()-1000).toISOString();
  assert.equal(typeof m.expireCandidateReviewDraft,'function','Current source-memory expiry port missing');m.expireCandidateReviewDraft(d);
  assert.equal(d.phase,'expired');assert.equal(d.key,key);assert.equal(d.excerpt,'');assert.equal(d.context,null);assert.equal(d.frozen,null);
  d.context=basis();d.excerpt=d.context.page.excerpt;await assert.rejects(m.submitCandidateReview(ctx,'run','raw',d),/reconciliation/);assert.equal(calls,1);assert.equal(d.key,key);
});

test('source expiry continues while the review editor is unmounted',async()=>{
  const m=await api(),ctx=setup(async()=>result),d=fill(m.candidateReviewDraft(ctx,'run','raw'));
  d.context.page.retention_until=new Date(Date.now()+80).toISOString();assert.equal(typeof m.watchCandidateReviewSource,'function','Unmounted source-memory expiry missing');
  m.watchCandidateReviewSource(d);await new Promise(r=>setTimeout(r,130));assert.equal(d.phase,'expired');assert.equal(d.context,null);assert.equal(d.excerpt,'');
});
test('remount synchronously masks already expired retained review material before rendering',async()=>{
  const m=await api(),ctx=setup(async()=>result),d=fill(m.candidateReviewDraft(ctx,'run','raw'));d.context.page.retention_until=new Date(Date.now()-1000).toISOString();
  const retained=m.candidateReviewDraft({...ctx},'run','raw');assert.equal(retained,d);assert.equal(retained.phase,'expired');assert.equal(retained.context,null);assert.equal(retained.excerpt,'');
});

test('already reviewed server context cannot start a fresh client intent after losing session memory',async()=>{
 const m=await api();let calls=0;const ctx=setup(async()=>{calls++;return result;}),d=fill(m.candidateReviewDraft(ctx,'run','raw'));d.context.entity_status='reviewed';
 await assert.rejects(m.submitCandidateReview(ctx,'run','raw',d),/reconciliation/);assert.equal(calls,0);assert.equal(d.key,null);
});
test('session-owned dirty review warns on document unload even after its editor closes',async()=>{
 const m=await api(),before=globalThis.window,win=new EventTarget();globalThis.window=win;
 try{const ctx=setup(async()=>result),d=fill(m.candidateReviewDraft(ctx,'run','raw'));const e=new Event('beforeunload',{cancelable:true});Object.defineProperty(e,'returnValue',{value:'',writable:true});win.dispatchEvent(e);assert.equal(e.defaultPrevented,true);
  d.phase='accepted';const done=new Event('beforeunload',{cancelable:true});win.dispatchEvent(done);assert.equal(done.defaultPrevented,false);
 }finally{if(before===undefined)delete globalThis.window;else globalThis.window=before;}
});

test('review source binding and edits preserve dirty preparation and refuse frozen intents',async()=>{
 const m=await api(),ctx=setup(async()=>result),d=m.candidateReviewDraft(ctx,'run','raw');
 assert.equal(typeof m.updateCandidateReviewDraft,'function');assert.equal(typeof m.bindCandidateReviewSource,'function');
 assert.equal(m.updateCandidateReviewDraft(d,{companyId:'company',reason:'Dirty independently prepared reason'}),true);
 assert.equal(m.bindCandidateReviewSource(d,basis()),true);assert.equal(d.excerpt,basis().page.excerpt);
 assert.equal(m.updateCandidateReviewDraft(d,{excerpt:'Independent company page'}),true);
 const wrong=basis();wrong.company.id='other';assert.equal(m.bindCandidateReviewSource(d,wrong),false);assert.equal(d.context.company.id,'company');
 for(const phase of ['pending','unknown','accepted','expired']){
  d.phase=phase;d.key='original-key';const before=JSON.stringify(d);
  assert.equal(m.updateCandidateReviewDraft(d,{companyId:'other',excerpt:'overwritten',reason:'overwritten'}),false);
  assert.equal(m.bindCandidateReviewSource(d,basis()),false);assert.equal(JSON.stringify(d),before);
 }
});
test('changing selected company preserves dirty quote only until its original source deadline',async()=>{
 const m=await api(),ctx=setup(async()=>result),d=m.candidateReviewDraft(ctx,'run','raw'),source=basis();
 assert.equal(typeof m.updateCandidateReviewDraft,'function');assert.equal(typeof m.bindCandidateReviewSource,'function');
 m.updateCandidateReviewDraft(d,{companyId:'company',reason:'Keep independent preparation'});source.page.retention_until=new Date(Date.now()+100).toISOString();
 assert.equal(m.bindCandidateReviewSource(d,source),true);m.updateCandidateReviewDraft(d,{companyId:'other'});
 assert.equal(d.context,null);assert.equal(d.excerpt,source.page.excerpt);assert.equal(d.reason,'Keep independent preparation');
 await new Promise(r=>setTimeout(r,180));assert.equal(d.phase,'expired');assert.equal(d.excerpt,'');assert.equal(d.reason,'Keep independent preparation');
 assert.equal(m.bindCandidateReviewSource(d,basis()),false);
});
