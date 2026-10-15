import {expect,test,type APIRequestContext} from '@playwright/test';
import {apiBase,bearer,resetLead,signInLead} from './fixtures/lead-workflow';
const proof=[{title:'Fictional provider statement',url:'https://billing.example.test/statement'}];
async function budget(request:APIRequestContext){return (await (await request.get(`${apiBase}/pilot-budget`,{headers:bearer})).json()).data;}
async function write(request:APIRequestContext,action:string,payload:object){
  const current=await budget(request);
  const prepared=await request.post(`${apiBase}/lead-intents`,{headers:{...bearer,'Idempotency-Key':crypto.randomUUID()},
    data:{action,expected_version:current.version,payload}});
  expect(prepared.status(),await prepared.text()).toBe(201);const intent=(await prepared.json()).data;
  const result=await request.post(`${apiBase}/lead-intents/${intent.id}/apply`,{
    headers:{...bearer,'Idempotency-Key':intent.submission_key,'If-Match':`"${current.version}"`},data:{}});
  expect(result.ok(),await result.text()).toBe(true);const receipt=(await result.json()).data;
  expect((await budget(request)).version).toBeGreaterThan(current.version);
  const ack=await request.post(`${apiBase}/lead-intents/${intent.id}/acknowledgements`,{
    headers:{...bearer,'Idempotency-Key':`ack-${intent.id}`},data:{}});
  expect(ack.ok(),await ack.text()).toBe(true);return receipt;
}
test.beforeEach(async({request})=>resetLead(request));
test('monthly_policy_and_disabled_activation_are_separate',async({page,request})=>{
  const before=await (await request.get('http://127.0.0.1:8000/fixture/lead-counts')).json();
  await signInLead(page,'/app/settings');
  const panel=page.getByRole('region',{name:'Pilot monthly budget',exact:true});
  await expect(panel.getByText('Policy not saved',{exact:true})).toBeVisible();
  await panel.getByLabel('Monthly USD limit').fill('10');
  await panel.getByLabel('Budget change reason').fill('Approved combined pilot ceiling');
  await panel.getByRole('button',{name:'Save pilot policy',exact:true}).click();
  await expect(panel.getByText('Paid execution: disabled',{exact:true})).toBeVisible();
  const current=await budget(request);expect(current.limit).toBe('10.000000');expect(current.activation).toBe('disabled');
  expect(current.remaining).toBeNull();
  expect(await (await request.get('http://127.0.0.1:8000/fixture/lead-counts')).json()).toEqual(before);
});
test('unknown_spend_and_shared_provider_usage_require_reconciliation',async({page,request})=>{
  await write(request,'pilot.policy',{monthly_limit:'10',reason:'Approved pilot'});
  await signInLead(page,'/app/settings');const panel=page.getByRole('region',{name:'Pilot monthly budget',exact:true});
  await expect(panel.getByText('Remaining USD: unknown',{exact:true})).toBeVisible();
  await panel.getByLabel('Budget evidence title').fill('Fictional statement');
  await panel.getByLabel('Budget evidence URL').fill('https://billing.example.test/statement');
  await panel.getByLabel('Budget evidence reason').fill('All project and shared provider usage checked.');
  await expect(panel.getByRole('button',{name:'Reconcile this period',exact:true})).toBeDisabled();
  await panel.getByLabel('Shared provider usage is fully accounted for.').check();
  await panel.getByRole('button',{name:'Reconcile this period',exact:true}).click();
  await expect(panel.getByText('Remaining USD: 10.000000',{exact:true})).toBeVisible();
  expect((await budget(request)).reconciliation_status).toBe('reconciled');
});
test('prepaid_settlement_and_correction_are_not_double_counted',async({page,request})=>{
  await write(request,'pilot.policy',{monthly_limit:'10',reason:'Approved pilot'});
  const current=await budget(request);
  const charge={economic_charge_key:'fixture-prepaid-001',period_start:current.period_start,state:'settled',
    usd_amount:'6',fees_included:true,minimum_purchase_included:true,source_refs:proof,reason:'Full credit purchase'};
  const receipt=await write(request,'cost.record',charge);
  await write(request,'credits.record',{provider:'Fictional provider',unit:'page credits',
    period_start:current.period_start,period_end:current.period_end,used:'2',remaining:'98',as_of:new Date().toISOString(),source_refs:proof});
  await write(request,'cost.record',{...charge,state:'corrected',usd_amount:'5',previous_event_id:receipt.resource_id,reason:'Correct invoice total'});
  await signInLead(page,'/app/settings');const panel=page.getByRole('region',{name:'Pilot monthly budget',exact:true});
  await expect(panel.getByText('Recorded settled USD: 5.000000',{exact:true})).toBeVisible();
  await expect(panel.getByText(/Fictional provider.*page credits/)).toBeVisible();
  await expect(panel.getByText('Remaining USD: unknown',{exact:true})).toBeVisible();
});
test('utc_rollover_keeps_unknown_holds_and_local_display',async({page,request})=>{
  await write(request,'pilot.policy',{monthly_limit:'10',reason:'Approved pilot'});
  const current=await budget(request),previous=new Date(current.period_start);previous.setUTCMonth(previous.getUTCMonth()-1);
  await write(request,'cost.record',{economic_charge_key:'fixture-old-unknown',period_start:previous.toISOString(),state:'unknown',
    usd_upper_bound:'3',fees_included:true,minimum_purchase_included:true,source_refs:proof,reason:'Prior period unresolved charge'});
  await signInLead(page,'/app/settings');const panel=page.getByRole('region',{name:'Pilot monthly budget',exact:true});
  await expect(panel.getByText('External unsettled USD: 3.000000',{exact:true})).toBeVisible();
  await expect(panel.getByText(/UTC billing period/)).toBeVisible();
  await expect(panel.getByText(/Hong Kong display/)).toBeVisible();
  expect((await budget(request)).remaining).toBeNull();
});
