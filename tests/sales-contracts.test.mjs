import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import ts from 'typescript';

const scope = '/workspaces/{workspace_id}/projects/{project_id}';
const contract = () => JSON.parse(read('docs/buyeros/contracts/sales.openapi.yaml'));
test('Task8 staged quote routes expose server-built plans and separate receipt contracts', () => {
  const api=contract(),base=scope+'/xverum';
  const create=api.paths[base+'/quotes'].post;
  assert.equal(create.requestBody.content['application/json'].schema.$ref,'#/components/schemas/QuoteRequest');
  assert.equal(api.paths[base+'/quotes/{quote_id}/approve'].post.responses['200'].content['application/json'].schema.$ref,'#/components/schemas/StepReceiptResponse');
  assert.equal(api.paths[base+'/receipts/{receipt_id}'].get.responses['200'].content['application/json'].schema.$ref,'#/components/schemas/XverumReceiptResponse');
  const request=api.components.schemas.QuoteRequest;
  assert.equal(request.properties.tool_plan,undefined);
  assert.deepEqual(request.oneOf[0].required,['stage','buyer_id','connection_id','query','target']);
  assert.deepEqual(request.oneOf[1].required,['stage','search_receipt_id','selected_ids']);
  assert.equal(request.oneOf[1].properties.selected_ids.maxItems,3);
  assert.deepEqual(api.components.schemas.StepReceipt.properties.task_id.anyOf,[{type:'string',format:'uuid'},{type:'null'}]);
});
test('review round1: task routes and after cursor match Task 3', () => {
  const api = contract();
  const routes = [
    ['/sales-tasks','post','createSalesTask'],
    ['/sales-tasks/{task_id}','get','getSalesTask'],
    ['/sales-tasks/{task_id}/events','get','listSalesTaskEvents'],
    ['/sales-tasks/{task_id}/cancel','post','cancelSalesTask'],
  ];
  for (const [path,method,id] of routes) assert.equal(api.paths[scope+path]?.[method]?.operationId,id);
  assert.ok(Object.keys(api.paths).every(path=>!path.includes('/sales/tasks')&&!path.includes('/sales/outputs')));
  const query=api.paths[scope+'/sales-tasks/{task_id}/events'].get.parameters.filter(p=>p.in==='query');
  assert.deepEqual(query.map(p=>p.name).sort(), ['after','limit']);
  assert.equal(query.find(p=>p.name==='after').schema.minimum, 0);
});
test('review round1: task writes require native quoted If-Match and explicit failures', () => {
  const api=contract();
  for(const path of ['/sales-tasks','/sales-tasks/{task_id}/cancel']) {
    const op=api.paths[scope+path]?.post;
    assert.ok(op,path);
    const h=op.parameters.find(p=>p.in==='header'&&p.name==='If-Match');
    assert.equal(h?.required,true);
    const pattern=new RegExp(h.schema.pattern);
    for(const valid of ['"1"','"42"']) assert.ok(pattern.test(valid));
    for(const invalid of ['', '1','W/"1"','"0"','"01"','*']) assert.equal(pattern.test(invalid),false);
    const key=op.parameters.find(p=>p.name==='Idempotency-Key').schema;
    assert.equal(key.minLength,8); assert.equal(key.maxLength,200); assert.equal(key.format,undefined);
    assert.equal(op.responses['400'].content['application/json'].examples.invalidPrecondition.value.code,'INVALID_REQUEST');
    assert.equal(op.responses['409'].content['application/json'].examples.staleRevision.value.code,'STALE_REVISION');
  }
  assert.equal(api.paths[scope+'/sales-tasks/{task_id}/cancel'].post.requestBody,undefined);
});
test('review round1: thread visibility is the save default and private is rejected', () => {
  const schemas=contract().components.schemas;
  for(const name of ['OutputSave','OutputVersion']) assert.deepEqual(schemas[name].properties.visibility.enum,['thread','project']);
  assert.equal(schemas.OutputSave.properties.visibility.default,'thread');
  assert.ok(!schemas.OutputSave.required.includes('visibility'));
});
test('review round1: native-filtered collection and latest detail preserve history', () => {
  const api=contract();
  const list=api.paths[scope+'/sales-outputs']?.get;
  assert.equal(list?.operationId,'listSalesOutputs');
  const query=list.parameters.filter(p=>p.in==='query');
  assert.deepEqual(query.map(p=>p.name).sort(),['limit','native_id','native_surface','offset']);
  assert.equal(query.find(p=>p.name==='native_id').schema.format,'uuid');
  assert.deepEqual(query.find(p=>p.name==='native_surface').schema.enum,['profile','buyer','list','run','draft','document','export']);
  assert.equal(list.responses['200'].content['application/json'].schema.$ref,'#/components/schemas/OutputCollectionResponse');
  const detail=api.paths[scope+'/sales-outputs/{output_id}']?.get;
  assert.equal(detail?.operationId,'getSalesOutput');
  const revision=detail.parameters.find(p=>p.in==='query'&&p.name==='revision');
  assert.equal(revision.required,false); assert.equal(revision.schema.minimum,1);
  assert.match(revision.description,/latest/i);
  assert.equal(api.paths[scope+'/sales-outputs/{output_id}/versions'].get.operationId,'listSalesOutputVersions');
  assert.equal(api.paths[scope+'/sales-outputs/{output_id}/versions/{revision}'].get.operationId,'getSalesOutputRevision');
});
test('review round1: every response declares native envelopes, no-store and correlation', () => {
  const api=contract();
  for(const path of Object.values(api.paths)) for(const op of Object.values(path)) {
    for(const [status,response] of Object.entries(op.responses)) {
      assert.equal(response.headers['Cache-Control'].schema.const,'no-store');
      assert.equal(response.headers['Cache-Control'].required,true);
      assert.equal(response.headers['X-Request-ID'].required,true);
      if(op.operationId==='previewSalesOutput'&&status==='200') {
        assert.equal(response.content['text/html'].schema.type,'string');
        assert.equal(response.headers['Content-Security-Policy'].schema.const,"default-src 'none'; sandbox");
        continue;
      }
      const responseSchema=response.content['application/json'].schema;
      const name=responseSchema.$ref?.split('/').at(-1);
      const schema=name?api.components.schemas[name]:responseSchema;
      if(status.startsWith('2')) {
        assert.deepEqual([...schema.required].sort(),['data','data_mode','request_id']);
        assertLiveOnly(schema.properties.data_mode);
        assert.ok(schema.properties.data.$ref);
      } else {
        assert.equal(name,'ErrorResponse');
        assert.deepEqual([...schema.required].sort(),['code','message','request_id','retryable']);
        assert.equal(schema.properties.retryable.type,'boolean');
      }
    }
    assert.ok(op.responses['400']&&op.responses['500']);
  }
});


const root = new URL('../', import.meta.url);
const read = path => readFileSync(new URL(path, root), 'utf8');
test('sales generator checks the complete extension without changing legacy files', () => {
  const legacy = ['docs/buyeros/contracts/openapi.proposed.yaml', 'services/generated/buyeros-api.ts'];
  const before = legacy.map(read);
  const result = spawnSync(process.execPath, ['scripts/generate-sales-api.mjs', '--check'], {cwd: root, encoding:'utf8'});
  assert.equal(result.status, 0, result.stdout + result.stderr);
  assert.deepEqual(legacy.map(read), before);
});
test('extension exposes bounded typed operations and all shared interfaces', () => {
  const api = JSON.parse(read('docs/buyeros/contracts/sales.openapi.yaml'));
  const names = ['Scope','SourceRef','ContextSnapshot','SkillDefinition','TaskInput','TaskRecord',
    'TaskEvent','ActionProposal','OutputCandidate','OutputVersion','NativeRef','XverumQuote',
    'XverumReceipt','EnrichmentProposal','SalesModelRequest','SalesModelResult'];
  for (const name of names) assert.ok(api.components.schemas[name], name);
  const operations = Object.values(api.paths).flatMap(p=>Object.values(p).filter(v=>v.operationId));
  for (const id of ['createSalesTask','getSalesTask','listSalesTaskEvents','cancelSalesTask',
      'getSalesOutput','listSalesOutputVersions','exportSalesReport','createXverumQuote',
      'approveXverumQuote','applyEnrichmentProposal','listSalesSkills']) {
    assert.ok(operations.some(o=>o.operationId===id), id);
  }
  assert.equal(new Set(operations.map(o=>o.operationId)).size, operations.length);
  assert.ok(operations.every(o=>o.responses['404']));
});
test('generated extension compiles as TypeScript', () => {
  const file = new URL('services/generated/sales-api.ts', root);
  const program = ts.createProgram([file.pathname.replace(/^\/([A-Za-z]:)/, '$1')], {
    noEmit:true, strict:true, skipLibCheck:true, types:[], target:ts.ScriptTarget.ES2022,
  });
  assert.deepEqual(ts.getPreEmitDiagnostics(program).map(d=>ts.flattenDiagnosticMessageText(d.messageText,'\n')), []);
});


test('Task4 partial intake and reload contracts preserve native transport', () => {
  const api=contract();
  const create=api.paths[scope+'/sales-tasks'].post;
  assert.ok(create.responses['201']);
  const list=api.paths[scope+'/sales-tasks'].get;
  assert.equal(list.operationId,'listSalesTasks');
  assert.equal(list.parameters.find(p=>p.name==='thread_id').required,true);
  const follow=api.paths[scope+'/sales-tasks/{task_id}/followups'].post;
  assert.equal(follow.operationId,'followupSalesTask');
  assert.equal(follow.parameters.find(p=>p.name==='If-Match').required,true);
  assert.equal(follow.requestBody.content['application/json'].schema.$ref,'#/components/schemas/TaskFollowup');
  assert.equal(api.components.schemas.IntakeProjectArguments.required,undefined);
  assert.ok(api.components.schemas.ProjectArguments.required.includes('offer_description'));
  assert.equal(api.components.schemas.TaskDetail.properties.intake.maxItems,33);
});

test('R3 generated request consumers preserve omission and reject invalid supplied values', () => {
  const filename=new URL('tests/__sales_request_consumer.ts',root).pathname.replace(/^\/([A-Za-z]:)/,'$1');
  const source=`import type {components,operations} from '../services/generated/sales-api';
    type NativeHeaders=operations['applySalesNativeAction']['parameters']['header'];
    const nativeHeaders:NativeHeaders={'Idempotency-Key':'native-action','If-Match':'"2"'};
    type RotationHeaders=operations['rotateXverumConnection']['parameters']['header'];
    const rotationHeaders:RotationHeaders={'Idempotency-Key':'rotate-action','If-Match':'"3"'};
    // @ts-expect-error generation in the separate body cannot replace the native version header
    const missingRotationMatch:RotationHeaders={'Idempotency-Key':'rotate-action'};
    type RotationBody=operations['rotateXverumConnection']['requestBody']['content']['application/json'];
    const rotationBody:RotationBody={expected_generation:7};
    // @ts-expect-error the If-Match header cannot replace the separate generation precondition
    const missingRotationGeneration:RotationBody={};
    // @ts-expect-error native mutations require a strong If-Match header
    const missingNativeMatch:NativeHeaders={'Idempotency-Key':'native-action'};
    type C=components['schemas'];
    const base={thread_id:'id',skill_version:'1' as const,user_message:'Synthetic',source_refs:[]};
    const project:C['TaskInput']={...base,skill_id:'first-project',arguments:{}};
    const quick:C['TaskInput']={...base,skill_id:'sales-quick',arguments:{}};
    const follow:C['TaskFollowup']={user_message:'Synthetic',arguments:{}};
    const bounded:C['TaskInput']={...base,skill_id:'sales-prospect',arguments:{bounds:{}}};
    // @ts-expect-error supplied nested limits remain numeric
    const badBounds:C['TaskInput']={...base,skill_id:'sales-prospect',arguments:{bounds:{max_model_calls:'many'}}};
    // @ts-expect-error supplied offer must be text
    const bad:C['TaskInput']={...base,skill_id:'first-project',arguments:{offer_description:42}};
    // @ts-expect-error unknown authority key
    const authority:C['TaskInput']={...base,skill_id:'first-project',arguments:{actor_id:'id'}};
    // @ts-expect-error supplied source selection must be references or null
    const sources:C['TaskFollowup']={user_message:'Synthetic',arguments:{},source_refs:'private'};
    // @ts-expect-error full execution offer is still required
    const full:C['ProjectArguments']={language:'en'};
    // @ts-expect-error response fields remain required
    const response:C['TaskDetail']={id:'id'};
    const child:C['SalesSectionCandidate']={kind:'sales_proposal',section:'solution',content:{solution:'Synthetic'},citations:[],complete:false};
    // @ts-expect-error child fields cannot carry authority keys
    const childAuthority:C['SalesSectionCandidate']={kind:'sales_proposal',section:'solution',content:{solution:'Synthetic',approved:true},citations:[],complete:false};
    // @ts-expect-error child cannot impersonate a complete output
    const saved:C['OutputCandidate']=child;
    void [project,quick,follow,bounded,badBounds,bad,authority,sources,full,response,child,childAuthority,saved];`;
  const options={noEmit:true,strict:true,skipLibCheck:true,types:[],target:ts.ScriptTarget.ES2022};
  const host=ts.createCompilerHost(options),original=host.getSourceFile.bind(host);
  host.getSourceFile=(file,version,...rest)=>file===filename ? ts.createSourceFile(file,source,version,true) : original(file,version,...rest);
  const program=ts.createProgram([filename],options,host);
  assert.deepEqual(ts.getPreEmitDiagnostics(program).map(d=>(d.file && d.start !== undefined ? 'line '+(d.file.getLineAndCharacterOfPosition(d.start).line+1)+': ' : '')+ts.flattenDiagnosticMessageText(d.messageText,'\n')),[]);
});

test('Task5 reviewed execution contracts bind preview approval admission and recovery', () => {
  const api=contract(),base=scope+'/sales-tasks/{task_id}';
  for(const [suffix,method,id] of [
    ['/execution-preview','post','previewSalesExecution'],['/reviews','post','approveSalesStep'],
    ['/steps','post','admitSalesStep'],['/steps','get','listSalesSteps']]) {
    assert.equal(api.paths[base+suffix][method].operationId,id);
  }
  for(const suffix of ['/reviews','/steps']) {
    for(const name of ['If-Match','Idempotency-Key']) {
      assert.equal(api.paths[base+suffix].post.parameters.find(p=>p.name===name)?.required,true);
    }
  }
  assert.deepEqual(api.components.schemas.StepReviewInput.required,['proposal','fingerprint']);
  assert.deepEqual(api.components.schemas.StepAdmission.required,['proposal','review_id']);
  assert.ok(!api.components.schemas.StepReceipt.properties.dispatch_state.enum.includes('completed'));
  assert.equal(api.components.schemas.StepReceipt.properties.reservation_ids.maxItems,1);
});

test('Task6 native actions require strong native CAS and document stale 412', () => {
  const op=contract().paths[scope+'/sales-outputs/native-actions'].post;
  const header=op.parameters.find(p=>p.name==='If-Match'&&p.in==='header');
  assert.equal(header?.required,true);
  const pattern=new RegExp(header.schema.pattern);
  for(const value of ['"1"','"23"']) assert.ok(pattern.test(value));
  for(const value of ['1','W/"1"','*','"0"','"01"']) assert.equal(pattern.test(value),false);
  assert.equal(op.responses['412'].content['application/json'].examples.staleRevision.value.code,'STALE_REVISION');
});

test('Task7 rotation declares native strong If-Match independently of generation', () => {
  const api=contract(),op=api.paths[scope+'/xverum/connections/{connection_id}/rotate'].post;
  const header=op.parameters.find(p=>p.name==='If-Match'&&p.in==='header');
  assert.equal(header?.required,true);
  assert.deepEqual(header.schema,api.components.schemas.TaskMutationHeaders.properties['If-Match']);
  const pattern=new RegExp(header.schema.pattern);
  for(const value of ['"1"','"23"']) assert.ok(pattern.test(value));
  for(const value of ['1','W/"1"','*','"0"','"01"']) assert.equal(pattern.test(value),false);
  assert.equal(op.requestBody.content['application/json'].schema.$ref,'#/components/schemas/ConnectionRotation');
  assert.deepEqual(api.components.schemas.ConnectionRotation.required,['expected_generation']);
  assert.equal(api.components.schemas.XverumEducation,undefined);
  assert.equal(api.components.schemas.XverumPersonDetail.properties.education,undefined);
  assert.equal(api.components.schemas.XverumPersonDetail.properties.about_me,undefined);
  assert.deepEqual(Object.keys(api.components.schemas.XverumExperience.properties).sort(),
    ['company_name','end_time','position','start_time']);
});


test('Task9 repair and linked approval expose exact authority and CAS without retry', () => {
  const api=contract(),base=scope+'/xverum';
  for(const suffix of ['/receipts/{receipt_id}/reconcile','/receipts/{receipt_id}/cancel','/tasks/{task_id}/quotes/{quote_id}/approve']) {
    const op=api.paths[base+suffix].post;
    for(const name of ['If-Match','Idempotency-Key']) assert.equal(op.parameters.find(p=>p.name===name)?.required,true);
  }
  assert.deepEqual(api.paths[base+'/receipts/{receipt_id}/reconcile'].post['x-permitted-roles'],['workspace_admin']);
  assert.deepEqual(api.paths[base+'/receipts/{receipt_id}/liability'].get['x-permitted-roles'],['workspace_admin']);
  const proof=api.components.schemas.ReconciliationEvidence;
  assert.equal(proof.properties.evidence_ref.format,'uuid');
  assert.ok(proof.required.includes('expected_version'));
  assert.ok(!Object.keys(api.paths).some(p=>p.includes('xverum')&&p.includes('retry')));
  const liability=api.components.schemas.XverumToolLiability.properties;
  assert.equal(liability.projection,undefined);assert.equal(liability.arguments,undefined);
});
test('Task10 enrichment uses reviewed producer routes and native buyer CAS', () => {
  const api=contract();
  const root='/workspaces/{workspace_id}/projects/{project_id}/xverum/enrichment-proposals';
  assert.equal(api.paths[root].post.operationId,'createEnrichmentProposal');
  assert.equal(api.paths[root+'/{proposal_id}'].get.operationId,'getEnrichmentProposal');
  const apply=api.paths[root+'/{proposal_id}/apply'].post;
  assert.equal(apply.operationId,'applyEnrichmentProposal');
  assert.equal(apply.parameters.find(p=>p.name==='If-Match').required,true);
  assert.ok(!Object.keys(api.paths).some(p=>p.includes('/xverum/proposals')));
  assert.ok(api.components.schemas.EnrichmentCreate.properties.receipt_ids);
});


function assertLiveOnly(mode) {
  if (Object.hasOwn(mode,'const')) assert.equal(mode.const,'live');
  else assert.deepEqual(mode.enum,['live']);
}
test('final M1 live-only rejects mixed enums and retains inline schemas', () => {
  assertLiveOnly({const:'live'});
  assertLiveOnly({enum:['live']});
  assert.throws(()=>assertLiveOnly({enum:['live','fixture']}));
});
