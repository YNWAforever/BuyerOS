import {expect,test as base,type Page,type Locator} from '@playwright/test';
import {writeFile} from 'node:fs/promises';
import {apiBase,bearer,leadBuyer,resetLead,signInLead,entry} from './fixtures/lead-workflow';

// Disposable data provisioning has its own bounded fixture budget. The actual
// reload/recovery/save journeys retain the original 30s test and 5s assertions.
const test=base.extend<{leadFixture:void}>({
  leadFixture:[async({request},use)=>{
    await resetLead(request);
    await use(undefined);
  },{auto:true,timeout:30_000}],
});
const timings=new WeakMap<Page,object[]>();
test.beforeEach(async({page})=>{
  const rows:object[]=[];timings.set(page,rows);
  page.on('requestfinished',request=>{
    const url=new URL(request.url());
    if(url.hostname!=='127.0.0.1'&&url.hostname!=='localhost')return;
    rows.push({method:request.method(),path:url.pathname,timing:request.timing()});
  });
});
test.afterEach(async({page},info)=>{
  if(info.status!==info.expectedStatus){
    const path=info.outputPath('local-http-timings.json');
    await writeFile(path,JSON.stringify(timings.get(page)??[],null,2),'utf8');
    await info.attach('local-http-timings',{path,contentType:'application/json'});
  }
});
async function acknowledgedAction(page:Page,panel:Locator,button:string,
  action:'preparation.create'|'preparation.revise'|'preparation.review'){
  const staged=page.waitForResponse(response=>response.status()===201&&
    response.request().method()==='POST'&&response.url()===`${apiBase}/lead-intents`&&
    response.request().postDataJSON()?.action===action);
  const ack=page.waitForResponse(response=>response.status()===200&&
    response.request().method()==='POST'&&response.url().startsWith(`${apiBase}/lead-intents/`)&&
    response.url().endsWith('/acknowledgements'));
  await panel.getByRole('button',{name:button,exact:true}).click();
  const original=(await (await staged).json()).data;
  const confirmed=await ack;
  expect(confirmed.url()).toBe(`${apiBase}/lead-intents/${original.id}/acknowledgements`);
  expect(confirmed.status()).toBe(200);
}
async function create(page:Page){
  await signInLead(page,'/app/outreach');
  const panel=page.getByRole('region',{name:'Lead preparations',exact:true});
  await panel.getByLabel('Preparation company').selectOption(leadBuyer);
  await acknowledgedAction(page,panel,'Create cited preparation','preparation.create');
  await expect(panel.getByLabel('Preparation body')).toHaveValue(/Thai jasmine rice/);
  await expect(panel.getByRole('link',{name:'Fixture product.pptx',exact:true})).toHaveAttribute('href',/document=e3600000/);
  return panel;
}
test('public_channel_preparation_is_reviewable_but_unsendable',async({page,request})=>{
  const before=await (await request.get('http://127.0.0.1:8000/fixture/lead-counts')).json();
  expect(before).toEqual({fixture_only:true,provider_operations:0,model_receipts:0,contact_receipts:0,
    search_receipts:0,async_jobs:0,formal_drafts:0,send_events:0});
  const panel=await create(page);
  await panel.getByLabel('Content review reason').fill('Checked this exact content and its current sources.');
  await panel.getByLabel('I reviewed this exact preparation content.').check();
  await acknowledgedAction(page,panel,'Mark content reviewed','preparation.review');
  await expect(panel.getByText('Preparation state: reviewed',{exact:true})).toBeVisible();
  await expect(panel.getByText('Sending: disabled',{exact:true})).toBeVisible();
  expect(await panel.getByRole('button',{name:/send|export/i}).count()).toBe(0);
  const after=await (await request.get('http://127.0.0.1:8000/fixture/lead-counts')).json();
  expect(after).toEqual(before);
  const stored=(await (await request.get(`${apiBase}/buyers/${leadBuyer}/lead-preparations`,{headers:bearer})).json()).data.items[0];
  expect(stored.state).toBe('reviewed');expect(stored.content.contact_id).toBeTruthy();
});
test('material_change_or_expiry_invalidates_content_review',async({page,request})=>{
  const panel=await create(page);
  await panel.getByLabel('Content review reason').fill('Checked exact current references.');
  await panel.getByLabel('I reviewed this exact preparation content.').check();
  await acknowledgedAction(page,panel,'Mark content reviewed','preparation.review');
  await expect(panel.getByText('Preparation state: reviewed',{exact:true})).toBeVisible();
  await panel.getByLabel('Preparation subject').fill('Changed business proposal');
  await acknowledgedAction(page,panel,'Save preparation revision','preparation.revise');
  await expect(panel.getByText('Preparation state: editing',{exact:true})).toBeVisible();
  const changed=await request.post('http://127.0.0.1:8000/fixture/lead-scenario',{data:{scenario:'expire_channel'}});
  expect(changed.ok(),await changed.text()).toBe(true);
  await panel.getByRole('button',{name:'Refresh preparations',exact:true}).click();
  await expect(panel.getByText('Preparation state: reviewed',{exact:true})).toHaveCount(0);
  await expect(panel.getByText('Source evidence is unavailable or expired.',{exact:true})).toBeVisible();
});
test('preparation_reload_restores_revision_and_original_intent',async({page,request})=>{
  const panel=await create(page);let submissions=0,lostIntentId='';
  await page.route('**/lead-intents/*/apply',async route=>{
    submissions++;if(submissions===1)lostIntentId=route.request().url().split('/').at(-2)!;
    const result=await route.fetch();
    await route.fulfill(submissions===1?{status:503,contentType:'application/json',body:'{"code":"TEMPORARY_UNAVAILABLE","message":"Lost reply","retryable":true,"request_id":"fixture"}'}:{response:result});
  });
  await panel.getByLabel('Preparation subject').fill('Retained exact revision');
  await panel.getByRole('button',{name:'Save preparation revision',exact:true}).click();
  await expect(panel.getByRole('alert')).toBeVisible();
  await page.reload();await signInLead(page,'/app/outreach');
  const restored=page.getByRole('region',{name:'Lead preparations',exact:true});
  await restored.getByLabel('Preparation company').selectOption(leadBuyer);
  const recoveredAck=page.waitForResponse(response=>response.status()===200&&
    response.url()===`${apiBase}/lead-intents/${lostIntentId}/acknowledgements`);
  await restored.getByRole('button',{name:'Read original operation',exact:true}).first().click();
  expect((await recoveredAck).status()).toBe(200);
  await expect(restored.getByLabel('Preparation subject')).toHaveValue('Retained exact revision');
  expect(submissions).toBe(1);
  const stored=(await (await request.get(`${apiBase}/buyers/${leadBuyer}/lead-preparations`,{headers:bearer})).json()).data.items[0];
  expect(stored.revision_number).toBe(2);
  await restored.getByRole('button',{name:'Load revision history',exact:true}).click();
  await expect(restored.getByText('Historical revision 1',{exact:true})).toBeVisible();
  const seeded=await request.post('http://127.0.0.1:8000/fixture/lead-scenario',{data:{scenario:'second_purchaser'}});
  expect(seeded.ok(),await seeded.text()).toBe(true);
  const prerequisite=await seeded.json();expect(prerequisite.fixture_only).toBe(true);
  const other=prerequisite.person_id as string,otherReview=prerequisite.review_id as string;
  await restored.getByRole('button',{name:'Refresh preparations',exact:true}).click();
  await restored.getByLabel('Preparation subject').fill('Original purchaser still intended');
  await acknowledgedAction(page,restored,'Save preparation revision','preparation.revise');
  await expect(restored.getByText('Preparation saved.',{exact:true})).toBeVisible();
  const saved=(await (await request.get(`${apiBase}/buyers/${leadBuyer}/lead-preparations`,{headers:bearer})).json()).data.items[0];
  expect(saved.content.person_id).toBe(stored.content.person_id);
  await restored.getByLabel('Preparation purchasing review').selectOption(otherReview);
  await acknowledgedAction(page,restored,'Save preparation revision','preparation.revise');
  await expect.poll(async()=>((await (await request.get(`${apiBase}/buyers/${leadBuyer}/lead-preparations`,{headers:bearer})).json()).data.items[0].content.person_id)).toBe(other);
});
test('missing_product_fact_or_extraction_caveat_is_visible',async({page,request})=>{
  const changed=await request.post('http://127.0.0.1:8000/fixture/lead-scenario',{data:{scenario:'product_caveat'}});
  expect(changed.ok(),await changed.text()).toBe(true);
  await signInLead(page,'/app/outreach');
  const panel=page.getByRole('region',{name:'Lead preparations',exact:true});
  await panel.getByLabel('Preparation company').selectOption(leadBuyer);
  await expect(panel.getByText('Product extraction is incomplete; verify the original attachment.',{exact:true})).toBeVisible();
  await panel.getByRole('button',{name:'Create cited preparation',exact:true}).click();
  await expect(panel.getByText('No confirmed product fact is available.',{exact:true}).first()).toBeVisible();
  await expect(panel.getByLabel('Preparation body')).toHaveValue('');
  await page.goto(entry('/app/outreach'));await signInLead(page,'/app/outreach');
  await expect(page.getByRole('region',{name:'Lead preparations',exact:true})).toBeVisible();
});


test('committed_write_retains_original_handle_when_readback_and_history_are_rate_limited',async({page,request})=>{
  const panel=await create(page);
  const before=await (await request.get('http://127.0.0.1:8000/fixture/lead-counts')).json();
  let committed=false,applies=0,readbackLimited=false,historyLimited=false,intentId='';
  await page.route('**/lead-intents/*/apply',async route=>{
    applies++;intentId=route.request().url().split('/').at(-2)!;
    const response=await route.fetch();expect(response.status()).toBe(200);
    committed=true;await route.fulfill({response});
  });
  const limited={status:429,contentType:'application/json',headers:{'Retry-After':'1'},
    body:'{"code":"RATE_LIMITED","message":"fixture read limit","request_id":"fixture-readback","retryable":true}'};
  await page.route(/\/buyers\/[^/]+\/lead-preparations(?:\?|$)/,async route=>{
    if(committed&&!readbackLimited){readbackLimited=true;await route.fulfill(limited);}else await route.continue();
  });
  await page.route(/\/lead-intents\?/,async route=>{
    if(committed&&!historyLimited){historyLimited=true;await route.fulfill(limited);}else await route.continue();
  });
  await panel.getByLabel('Content review reason').fill('Exact sources reviewed; no consent or sending inferred.');
  await panel.getByLabel('I reviewed this exact preparation content.').check();
  await panel.getByRole('button',{name:'Mark content reviewed',exact:true}).click();
  await expect.poll(()=>committed&&readbackLimited&&historyLimited).toBe(true);
  await expect(panel.getByText('The save result is unconfirmed. Read the original operation before another edit.',{exact:true})).toBeVisible();
  await expect(panel.getByRole('button',{name:'Read original operation',exact:true})).toHaveCount(1);
  await expect(panel.getByRole('button',{name:'Save preparation revision',exact:true})).toBeDisabled();
  await expect(panel.getByText('Content review saved.',{exact:true})).toHaveCount(0);
  const canonical=async()=>((await (await request.get(`${apiBase}/buyers/${leadBuyer}/lead-preparations`,{headers:bearer})).json()).data.items[0]);
  const stored=await canonical();expect(stored.state).toBe('reviewed');expect(stored.version).toBe(2);
  const recoveredAck=page.waitForResponse(response=>response.status()===200&&
    response.url()===`${apiBase}/lead-intents/${intentId}/acknowledgements`);
  await panel.getByRole('button',{name:'Read original operation',exact:true}).click();
  expect((await recoveredAck).status()).toBe(200);
  await expect(panel.getByText('Preparation state: reviewed',{exact:true})).toBeVisible();
  await expect(panel.getByRole('button',{name:'Read original operation',exact:true})).toHaveCount(0);
  expect(applies).toBe(1);expect((await canonical()).version).toBe(stored.version);
  expect(await (await request.get('http://127.0.0.1:8000/fixture/lead-counts')).json()).toEqual(before);
});


test('acknowledged_write_is_not_recovered_after_history_refresh_failure',async({page,request})=>{
  const panel=await create(page);
  const before=await (await request.get('http://127.0.0.1:8000/fixture/lead-counts')).json();
  let applies=0,acknowledged=false,limited=false,intentId='';
  await page.route('**/lead-intents/*/apply',async route=>{
    applies++;intentId=route.request().url().split('/').at(-2)!;
    const response=await route.fetch();expect(response.status()).toBe(200);await route.fulfill({response});
  });
  const ackReply=page.waitForResponse(response=>response.status()===200&&
    Boolean(intentId)&&response.url().includes(`/lead-intents/${intentId}/acknowledgements`));
  page.on('response',response=>{
    if(response.status()===200&&intentId&&response.url().includes(`/lead-intents/${intentId}/acknowledgements`))acknowledged=true;
  });
  const limitedReply=page.waitForResponse(response=>response.status()===429&&/\/lead-intents\?/.test(response.url()));
  await page.route(/\/lead-intents\?/,async route=>{
    if(acknowledged&&!limited){limited=true;await route.fulfill({status:429,contentType:'application/json',
      headers:{'Retry-After':'1'},body:'{"code":"RATE_LIMITED","message":"fixture history read limit","request_id":"fixture-post-ack","retryable":true}'});
    }else await route.continue();
  });
  await panel.getByLabel('Content review reason').fill('Exact sources reviewed; acknowledged save must remain complete.');
  await panel.getByLabel('I reviewed this exact preparation content.').check();
  await panel.getByRole('button',{name:'Mark content reviewed',exact:true}).click();
  await ackReply;await limitedReply;
  expect(acknowledged&&limited).toBe(true);
  const saved=(await (await request.get(`${apiBase}/buyers/${leadBuyer}/lead-preparations`,{headers:bearer})).json()).data.items[0];
  expect(saved.state).toBe('reviewed');expect(saved.version).toBe(2);
  const pending=(await (await request.get(`${apiBase}/lead-intents`,{headers:bearer})).json()).data.items;
  expect(pending.some((row:{id:string})=>row.id===intentId)).toBe(false);
  await expect(panel.getByText('Content review saved.',{exact:true})).toBeVisible();
  await expect(panel.getByText('The save result is unconfirmed. Read the original operation before another edit.',{exact:true})).toHaveCount(0);
  await expect(panel.getByRole('button',{name:'Read original operation',exact:true})).toHaveCount(0);
  await expect(panel.getByRole('button',{name:'Save preparation revision',exact:true})).toBeEnabled();
  expect(applies).toBe(1);
  expect(await (await request.get('http://127.0.0.1:8000/fixture/lead-counts')).json()).toEqual(before);
});
