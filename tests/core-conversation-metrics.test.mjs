import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
registerHooks({resolve(s,c,next){try{return next(s,c);}catch(e){if(s.startsWith('.'))for(const ext of ['.ts','.tsx'])try{return next(s+ext,c);}catch{}throw e;}},load(u,c,next){if(/\.tsx?$/.test(u))return {format:'module',shortCircuit:true,source:ts.transpileModule(readFileSync(new URL(u),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText};return next(u,c);}});

const {METRICS_WINDOW_DAYS,MetricsUnverified,metricsPath,readTurnMetrics,formatLatency,formatMetricAmount,
  statusRows,hasTurns}=await import('../features/live/conversation/metrics.ts');

const workspace='11111111-1111-4111-8111-111111111111',project='22222222-2222-4222-8222-222222222222';
function fixture(overrides={}){
  return {
    window_days:7,generated_at:'2026-11-11T12:00:00Z',
    turns:{total:3,by_status:{completed:2,needs_input:1}},
    latency_ms:{samples:3,p50:900,p95:1500,max:2100},
    proposals:{total:2,by_capability:{'research-market':2},by_decision:{approve:1,reject:0},awaiting_decision:1},
    tool_activity:{by_state:{completed:1},outcome_unknown:1},
    model:{unavailable_turns:1},
    budget:{priced_proposals:0,unknown_price_proposals:1,no_cost_proposals:1,
      may_incur_provider_charges:0,estimated:[]},
    ...overrides,
  };
}
function rejects(overrides,label){
  assert.throws(()=>readTurnMetrics(overrides),MetricsUnverified,label);
}

test('metrics URL carries the project scope and a bounded window',()=>{
  assert.equal(metricsPath(workspace,project),
    `/v1/workspaces/${workspace}/projects/${project}/conversation-turns/metrics?window_days=7`);
  assert.equal(METRICS_WINDOW_DAYS,7);
  assert.match(metricsPath(workspace,project,30),/window_days=30$/);
  // An out-of-range window falls back to the bounded default instead of widening.
  assert.match(metricsPath(workspace,project,0),/window_days=7$/);
  assert.match(metricsPath(workspace,project,31),/window_days=7$/);
  assert.equal(metricsPath('','project'),null);
});

test('a verified server payload keeps every aggregate as reported',()=>{
  const metrics=readTurnMetrics(fixture());
  assert.equal(metrics.turns.total,3);
  assert.equal(metrics.turns.by_status.completed,2);
  assert.equal(metrics.latency_ms.p95,1500);
  assert.equal(metrics.proposals.awaiting_decision,1);
  assert.equal(metrics.tool_activity.outcome_unknown,1);
  assert.equal(metrics.model.unavailable_turns,1);
  assert.equal(metrics.budget.unknown_price_proposals,1);
});

test('an unknown status or an inconsistent total fails closed',()=>{
  rejects(fixture({turns:{total:3,by_status:{completed:2,needs_input:1,teleported:0}}}),'unknown status');
  rejects(fixture({turns:{total:4,by_status:{completed:2,needs_input:1}}}),'total mismatch');
  rejects(fixture({turns:{total:2,by_status:{completed:-1,needs_input:3}}}),'negative count');
  rejects(fixture({latency_ms:{samples:3,p50:-1,p95:1500,max:2100}}),'negative latency');
});

test('malformed or unbounded fields are never rendered as zero',()=>{
  rejects(fixture({window_days:365}),'window above contract maximum');
  rejects(fixture({generated_at:42}),'generated_at must be a string');
  rejects(fixture({budget:{...fixture().budget,estimated:[{unit:'EUR',amount:'2'}]}}),'unknown unit');
  rejects(fixture({budget:{...fixture().budget,estimated:[{unit:'USD',amount:'1e3'}]}}),'exponent amount');
  rejects(fixture({proposals:{...fixture().proposals,awaiting_decision:0.5}}),'fractional count');
  assert.throws(()=>readTurnMetrics(null),MetricsUnverified);
});

test('latency formatting is honest about missing samples',()=>{
  assert.equal(formatLatency(null),'—');
  assert.equal(formatLatency(420),'420 ms');
  assert.equal(formatLatency(1500),'1.5 s');
  assert.equal(formatLatency(12_400),'12 s');
  assert.equal(formatLatency(1500,'zh-HK'),'1.5 秒');
});

test('decimal budget strings keep exact precision and trim padding',()=>{
  assert.equal(formatMetricAmount('0'),'0');
  assert.equal(formatMetricAmount('12.5000'),'12.5');
  assert.equal(formatMetricAmount('3.0000'),'3');
  assert.equal(formatMetricAmount('0.75'),'0.75');
  assert.equal(formatMetricAmount('-1'),'—');
  assert.equal(formatMetricAmount('1e3'),'—');
});

test('status rows keep the contract order and zero-fill small windows',()=>{
  const rows=statusRows(readTurnMetrics(fixture({turns:{total:2,by_status:{completed:2}}})));
  assert.deepEqual(rows.map(row=>row.status),
    ['completed','needs_input','needs_approval','failed','outcome_unknown','cancelled']);
  assert.deepEqual(rows.map(row=>row.count),[2,0,0,0,0,0]);
  // Latency samples are never the empty-state signal: turns are.
  assert.equal(hasTurns(readTurnMetrics(fixture())),true);
  assert.equal(hasTurns(readTurnMetrics(fixture({latency_ms:{samples:0,p50:null,p95:null,max:null}}))),true);
  assert.equal(hasTurns(readTurnMetrics(fixture({turns:{total:0,by_status:{}}}))),false);
});
