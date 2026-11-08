import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
registerHooks({resolve(s,c,next){try{return next(s,c);}catch(e){if(s.startsWith('.'))for(const ext of ['.ts','.tsx'])try{return next(s+ext,c);}catch{}throw e;}},load(u,c,next){if(/\.tsx?$/.test(u))return {format:'module',shortCircuit:true,source:ts.transpileModule(readFileSync(new URL(u),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText};return next(u,c);}});

const {proposalUiState,decisionGate,approvalNoticeKey,decisionIntentKey,followUpNoticeKey,toolStateAfterDecision}=await import('../features/live/conversation/approval.ts');
const proposal={kind:'proposal',proposal_id:'p-1',capability:'sales-contacts',title:'Enrich buyer',requires_approval:true};
const optional={...proposal,proposal_id:'p-2',requires_approval:false};

test('a fresh proposal waits for an explicit editor decision; viewers cannot decide',()=>{
  assert.equal(proposalUiState(proposal,'needs_approval',undefined,'owner'),'awaiting');
  assert.equal(proposalUiState(proposal,undefined,undefined,'editor'),'awaiting');
  assert.equal(proposalUiState(proposal,'needs_approval',undefined,'viewer'),'unavailable');
  assert.deepEqual(decisionGate('awaiting'),{canDecide:true,canReject:true,noticeKey:''});
  assert.equal(decisionGate('unavailable').canDecide,false);
  assert.equal(decisionGate('approved').canReject,false);
  assert.equal(proposalUiState(optional,'completed',undefined,'viewer'),'not_required');
});

test('submitting, approved, rejected and failed decisions are distinct stable states',()=>{
  assert.equal(proposalUiState(proposal,'needs_approval',{choice:'approve',state:'submitting'},'owner'),'submitting');
  assert.equal(proposalUiState(proposal,'needs_approval',{choice:'approve',state:'accepted'},'owner'),'approved');
  assert.equal(proposalUiState(proposal,'needs_approval',{choice:'reject',state:'accepted'},'owner'),'rejected');
  assert.equal(proposalUiState(proposal,'needs_approval',{choice:'reject',state:'failed'},'owner'),'failed');
  assert.equal(decisionGate('failed').canDecide,true);
  assert.match(approvalNoticeKey('approved'),/Approved/);
  assert.match(approvalNoticeKey('rejected'),/Rejected/);
  assert.match(approvalNoticeKey('unknown_outcome'),/unknown/);
});

test('finished or uncertain turns suspend approval; a rejection never executes',()=>{
  assert.equal(proposalUiState(proposal,'outcome_unknown',undefined,'owner'),'unknown_outcome');
  assert.equal(proposalUiState(proposal,'cancelled',undefined,'owner'),'unavailable');
  assert.equal(proposalUiState(proposal,'failed',undefined,'owner'),'unavailable');
  assert.equal(decisionGate('unknown_outcome').canDecide,false);
  assert.equal(decisionGate(proposalUiState(proposal,'needs_approval',{choice:'reject',state:'accepted'},'owner')).canDecide,false);
});

test('decision identity is retry-stable per proposal and choice',()=>{
  const a=decisionIntentKey('t','turn','p','approve');
  assert.equal(a,decisionIntentKey('t','turn','p','approve'));
  assert.notEqual(a,decisionIntentKey('t','turn','p','reject'));
  assert.notEqual(a,decisionIntentKey('t','other','p','approve'));
  assert.ok(a.includes('conversation-decision'));
});

test('tool activity supersedes a stale approval card message',()=>{
  assert.equal(toolStateAfterDecision({kind:'tool_activity',call_id:'c',capability:'sales-contacts',title:'Enrich',state:'running'}),'running');
  assert.equal(toolStateAfterDecision(null),null);
  assert.match(followUpNoticeKey('completed'),/completed/);
  assert.match(followUpNoticeKey('outcome_unknown'),/confirmed/);
  assert.equal(followUpNoticeKey('proposed'),'');
});
