import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
registerHooks({resolve(s,c,next){try{return next(s,c);}catch(e){if(s.startsWith('.'))for(const ext of ['.ts','.tsx'])try{return next(s+ext,c);}catch{}throw e;}},load(u,c,next){if(/\.tsx?$/.test(u))return {format:'module',shortCircuit:true,source:ts.transpileModule(readFileSync(new URL(u),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText};return next(u,c);}});

const {proposalExplain,persistedDecision}=await import('../features/live/conversation/explainer.ts');

const proposal={kind:'proposal',proposal_id:'11111111-1111-4111-8111-111111111111',
  capability:'xverum.enrich_company',title:'Enrich company',rationale:'Verified contact evidence is needed.',
  arguments_preview:{company:'DeltaGrid',profile_version:2,company_id:'internal-id-value',request_hash:'abc123'},
  cost:{kind:'provider_credits',amount:'0',unit:'credits',may_incur_provider_charges:true,known:false},
  requires_approval:true};
const citations={kind:'citations',items:[{id:'document:22222222-2222-4222-8222-222222222222',label:'Offer document',kind:'document',
  href:'/app/discover/edit?document=22222222-2222-4222-8222-222222222222'}]};
const notices={kind:'notice',code:'POLICY_BLOCKED',message:'Current policy approval is required.'};

test('explainer projects persisted rationale, bounded arguments, evidence, cost and policy state',()=>{
  const view=proposalExplain({proposal,turnParts:[citations,notices]});
  assert.equal(view.rationale,'Verified contact evidence is needed.');
  assert.equal(view.argumentsKnown,true);
  assert.deepEqual(view.arguments.map(item=>item.label),['company','profile version']);
  assert.equal(view.evidence.length,1);assert.equal(view.evidence[0].label,'Offer document');
  assert.equal(view.evidence[0].href,'/app/discover/edit?document=22222222-2222-4222-8222-222222222222');
  assert.deepEqual(view.cost,{kind:'review_required'});
  assert.equal(view.requiresApproval,true);
  assert.deepEqual(view.policyNotices,[{code:'POLICY_BLOCKED',message:'Current policy approval is required.'}]);
});

test('missing persisted fields project as unknown instead of inferred values',()=>{
  const minimal={kind:'proposal',proposal_id:'p',capability:'sales.contacts',title:'T',requires_approval:true};
  const view=proposalExplain({proposal:minimal,turnParts:[]});
  assert.equal(view.rationale,null);
  assert.equal(view.argumentsKnown,false);assert.deepEqual(view.arguments,[]);
  assert.deepEqual(view.evidence,[]);
  assert.deepEqual(view.cost,{kind:'unknown'});
  assert.deepEqual(view.policyNotices,[]);
  assert.equal(view.decisionKnown,false);assert.equal(view.decision,null);
});

test('cost keeps the shipped known:false wording and never invents a number',()=>{
  const review=proposalExplain({proposal,turnParts:[]});
  assert.equal(JSON.stringify(review.cost).includes('0'),false,'unknown tariff carries no number');
  const priced=proposalExplain({proposal:{...proposal,cost:{kind:'provider_credits',amount:'4.5',unit:'credits',known:true}},turnParts:[]});
  assert.deepEqual(priced.cost,{kind:'amount',amount:'4.5',unit:'credits',mayIncurProviderCharges:false});
  const nonbillable=proposalExplain({proposal:{...proposal,cost:{kind:'nonbillable',may_incur_provider_charges:false,known:true}},turnParts:[]});
  assert.equal(nonbillable.cost.kind,'nonbillable');
});

test('the ordinary view model carries no internal ids, hashes or capabilities',()=>{
  const view=proposalExplain({proposal,turnParts:[citations]});
  const serialized=JSON.stringify(view);
  assert.equal(serialized.includes('internal-id-value'),false,'internal argument values are filtered');
  assert.equal(serialized.includes('abc123'),false,'hashes are filtered');
  assert.equal(serialized.includes(proposal.proposal_id),false,'proposal ids never cross into the explainer');
  assert.equal(serialized.includes('xverum.enrich_company'),false,'protocol capability names stay out of ordinary copy');
  assert.equal(serialized.includes('document:2222'),false,'citation ids stay out of the explainer');
});

test('argument previews are bounded and structured values are not rendered blindly',()=>{
  const many=Object.fromEntries(Array.from({length:20},(_,index)=>[`field_${index}`,index]));
  const view=proposalExplain({proposal:{...proposal,arguments_preview:{...many,nested:{deep:'value'},long:'x'.repeat(400)}},turnParts:[]});
  assert.equal(view.arguments.length,12);
  assert.equal(view.argumentsTruncated,true);
  assert.ok(view.arguments.every(item=>item.value.length<=200));
  assert.equal(view.arguments.some(item=>item.label==='nested'),false,'nested objects are not guessed into text');
});

test('a persisted decision is surfaced only when it actually exists',()=>{
  assert.equal(persistedDecision(null),null);
  assert.equal(persistedDecision({}),null);
  assert.deepEqual(persistedDecision({decision:'approve',actor:'Reviewer A',decided_at:'2026-11-09T10:00:00Z'}),
    {choice:null,actor:'Reviewer A',decidedAt:'2026-11-09T10:00:00Z'});
  assert.deepEqual(persistedDecision({decision:{choice:'reject',actor:'Reviewer B'}}),
    {choice:'reject',actor:'Reviewer B',decidedAt:null});
  const withDecision=proposalExplain({proposal,turnParts:[],
    decision:persistedDecision({decision:{choice:'approve',actor:'Reviewer C',decided_at:'2026-11-09T10:00:00Z'}})});
  assert.equal(withDecision.decisionKnown,true);
  assert.equal(withDecision.decision.choice,'approve');
  assert.equal(withDecision.decision.actor,'Reviewer C');
  assert.equal(proposalExplain({proposal,turnParts:[]}).decisionKnown,false);
});
