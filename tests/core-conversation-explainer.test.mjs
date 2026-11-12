import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
registerHooks({resolve(s,c,next){try{return next(s,c);}catch(e){if(s.startsWith('.'))for(const ext of ['.ts','.tsx'])try{return next(s+ext,c);}catch{}throw e;}},load(u,c,next){if(/\.tsx?$/.test(u))return {format:'module',shortCircuit:true,source:ts.transpileModule(readFileSync(new URL(u),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText};return next(u,c);}});

const {proposalExplain,persistedDecision}=await import('../features/live/conversation/explainer.ts');
const {readMessagePart}=await import('../features/live/conversation/types.ts');

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
  // Wider objects: camelCase internal keys and id/hash/PII/protocol-shaped VALUES
  // are dropped too, even when the key itself is benign.
  const uuid='99999999-9999-4999-8999-999999999999',digest='a'.repeat(64);
  const leaky=proposalExplain({proposal:{...proposal,arguments_preview:{
    company:'DeltaGrid',profile_version:2,clientMessageId:'client-1',sourceIds:['source-1'],companyId:'company-1',requestHash:'deadbeef',
    reference:uuid,checksum:digest,contact:'reviewer@example.com',capabilityName:'xverum.enrich_company'}},turnParts:[]});
  assert.deepEqual(leaky.arguments.map(item=>item.label),['company','profile version']);
  const argumentValues=JSON.stringify(leaky.arguments);
  for(const leaked of [uuid,digest,'reviewer@example.com','xverum.enrich_company','client-1','source-1','company-1','deadbeef'])
    assert.equal(argumentValues.includes(leaked),false,`internal-shaped value ${leaked.slice(0,12)} is not projected`);
  assert.equal(leaky.argumentsKnown,true);
});

test('argument previews are bounded and structured values are not rendered blindly',()=>{
  const many=Object.fromEntries(Array.from({length:20},(_,index)=>[`field_${index}`,index]));
  const view=proposalExplain({proposal:{...proposal,arguments_preview:{...many,nested:{deep:'value'},long:'x'.repeat(400)}},turnParts:[]});
  assert.equal(view.arguments.length,12);
  assert.equal(view.argumentsTruncated,true);
  assert.ok(view.arguments.every(item=>item.value.length<=200));
  assert.equal(view.arguments.some(item=>item.label==='nested'),false,'nested objects are not guessed into text');
});

test('a persisted decision is surfaced only when it actually exists and is well formed',()=>{
  assert.equal(persistedDecision(null),null);
  assert.equal(persistedDecision({}),null);
  for(const malformed of [
    {choice:'maybe',decided_at:'2026-11-09T10:00:00Z',decided_by:'you'},
    {choice:'approve',decided_at:'2026-11-09T10:00:00Z',decided_by:'reviewer@example.com'},
    {choice:'approve',decided_at:'2026-11-09T10:00:00Z',decided_by:'11111111-1111-4111-8111-111111111111'},
    {choice:'approve',decided_at:'not-a-date',decided_by:'a workspace member'},
    {choice:'approve',decided_at:'',decided_by:'you'},
    {choice:'approve',decided_by:'you'},
    {decision:{choice:'approve',decided_at:'2026-11-09T10:00:00Z',decided_by:'you'}},
    {choice:'approve',decided_at:'2026-11-09T10:00:00Z',decided_by:'you',actor_id:'11111111-1111-4111-8111-111111111111'},
    {choice:'approve',decided_at:'2026-11-09T10:00:00Z',decided_by:'you',extra:true},
    {choice:'approve',decided_at:'2026-11-09T10:00:00Z',decided_by:'you',decided_by_id:'x'},
  ])assert.equal(persistedDecision(malformed),null,'malformed or wider decisions degrade to absent');
  const mine=persistedDecision({choice:'approve',decided_at:'2026-11-09T10:00:00Z',decided_by:'you'});
  assert.deepEqual(mine,{choice:'approve',actor:'you',decidedAt:'2026-11-09T10:00:00Z'});
  assert.deepEqual(persistedDecision({choice:'reject',decided_at:'2026-11-09T10:00:00+00:00',decided_by:'a workspace member'}),
    {choice:'reject',actor:'a workspace member',decidedAt:'2026-11-09T10:00:00+00:00'});
  const withDecision=proposalExplain({proposal,turnParts:[],decision:mine});
  assert.equal(withDecision.decisionKnown,true);
  assert.equal(withDecision.decision.choice,'approve');
  assert.equal(withDecision.decision.actor,'you');
  assert.equal(JSON.stringify(withDecision).includes('11111111-1111-4111-8111-111111111111'),false);
  assert.equal(proposalExplain({proposal,turnParts:[]}).decisionKnown,false);
  // The part reader is the strict gate: it keeps a well-formed decoration and drops malformed shapes.
  const base={kind:'proposal',proposal_id:'11111111-1111-4111-8111-111111111111',capability:'xverum.enrich_company',
    title:'Enrich company',requires_approval:true};
  const valid=readMessagePart({...base,decision:{choice:'approve',decided_at:'2026-11-09T10:00:00Z',decided_by:'you'}});
  assert.equal(valid.kind,'proposal');
  assert.deepEqual(valid.decision,{choice:'approve',decided_at:'2026-11-09T10:00:00Z',decided_by:'you'});
  const rejected=readMessagePart({...base,decision:{choice:'reject',decided_at:'2026-11-09T10:00:00Z',decided_by:'a workspace member'}});
  assert.equal(rejected.decision.choice,'reject');
  for(const malformed of [null,{},'approve',{choice:'approve'},{choice:'approve',decided_at:'2026-11-09T10:00:00Z'},
    {choice:'approve',decided_at:'2026-11-09T10:00:00Z',decided_by:'someone'},
    {choice:'approve',decided_at:'yesterday',decided_by:'you'},
    {choice:'approve',decided_at:'2026-11-09T10:00:00Z',decided_by:'you',actor_id:'11111111-1111-4111-8111-111111111111'},
    {choice:'approve',decided_at:'2026-11-09T10:00:00Z',decided_by:'you',extra:true}]){
    const part=readMessagePart({...base,decision:malformed});
    assert.equal(part.kind,'proposal');
    assert.equal('decision' in part,false,'the reader drops a malformed or wider decision');
  }
});
