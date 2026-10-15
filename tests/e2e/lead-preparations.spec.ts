import {expect,test,type Page} from '@playwright/test';
import {apiBase,bearer,leadBuyer,resetLead,signInLead,entry} from './fixtures/lead-workflow';

test.beforeEach(async({request})=>resetLead(request));
async function create(page:Page){
  await signInLead(page,'/app/outreach');
  const panel=page.getByRole('region',{name:'Lead preparations',exact:true});
  await panel.getByLabel('Preparation company').selectOption(leadBuyer);
  await panel.getByRole('button',{name:'Create cited preparation',exact:true}).click();
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
  await panel.getByRole('button',{name:'Mark content reviewed',exact:true}).click();
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
  await panel.getByRole('button',{name:'Mark content reviewed',exact:true}).click();
  await expect(panel.getByText('Preparation state: reviewed',{exact:true})).toBeVisible();
  await panel.getByLabel('Preparation subject').fill('Changed business proposal');
  await panel.getByRole('button',{name:'Save preparation revision',exact:true}).click();
  await expect(panel.getByText('Preparation state: editing',{exact:true})).toBeVisible();
  const changed=await request.post('http://127.0.0.1:8000/fixture/lead-scenario',{data:{scenario:'expire_channel'}});
  expect(changed.ok(),await changed.text()).toBe(true);
  await panel.getByRole('button',{name:'Refresh preparations',exact:true}).click();
  await expect(panel.getByText('Preparation state: reviewed',{exact:true})).toHaveCount(0);
  await expect(panel.getByText('Source evidence is unavailable or expired.',{exact:true})).toBeVisible();
});
test('preparation_reload_restores_revision_and_original_intent',async({page,request})=>{
  const panel=await create(page);let submissions=0;
  await page.route('**/lead-intents/*/apply',async route=>{
    submissions++;const result=await route.fetch();
    await route.fulfill(submissions===1?{status:503,contentType:'application/json',body:'{"code":"TEMPORARY_UNAVAILABLE","message":"Lost reply","retryable":true,"request_id":"fixture"}'}:{response:result});
  });
  await panel.getByLabel('Preparation subject').fill('Retained exact revision');
  await panel.getByRole('button',{name:'Save preparation revision',exact:true}).click();
  await expect(panel.getByRole('alert')).toBeVisible();
  await page.reload();await signInLead(page,'/app/outreach');
  const restored=page.getByRole('region',{name:'Lead preparations',exact:true});
  await restored.getByLabel('Preparation company').selectOption(leadBuyer);
  await restored.getByRole('button',{name:'Read original operation',exact:true}).first().click();
  await expect(restored.getByLabel('Preparation subject')).toHaveValue('Retained exact revision');
  expect(submissions).toBe(1);
  const stored=(await (await request.get(`${apiBase}/buyers/${leadBuyer}/lead-preparations`,{headers:bearer})).json()).data.items[0];
  expect(stored.revision_number).toBe(2);
  await restored.getByRole('button',{name:'Load revision history',exact:true}).click();
  await expect(restored.getByText('Historical revision 1',{exact:true})).toBeVisible();
  async function append(action:string,payload:object,version?:number){
    const staged=await request.post(`${apiBase}/lead-intents`,{headers:{...bearer,'Idempotency-Key':crypto.randomUUID()},
      data:{action,buyer_id:leadBuyer,payload,...(version?{expected_version:version}:{})}});
    expect(staged.status(),await staged.text()).toBe(201);const intent=(await staged.json()).data;
    const applied=await request.post(`${apiBase}/lead-intents/${intent.id}/apply`,{
      headers:{...bearer,'Idempotency-Key':intent.submission_key,...(version?{'If-Match':`"${version}"`}:{})},data:{}});
    expect(applied.ok(),await applied.text()).toBe(true);return (await applied.json()).data.resource_id as string;
  }
  const observation={stance:'supports',checked_at:new Date().toISOString(),rationale:'Official fixture identifies the rice buyer.',
    sources:[{title:'Official second purchaser',url:'https://buyer1.example.test/blair',excerpt:'Blair Fixture buys rice and uses blair@buyer1.example.test.',source_kind:'official'}]};
  const employment=await append('observation.append',{...observation,claim:'employment',person:{full_name:'Blair Fixture',role:'Rice Buyer'}});
  const evidence=async()=>((await (await request.get(`${apiBase}/buyers/${leadBuyer}/lead-evidence`,{headers:bearer})).json()).data.items);
  const other=(await evidence()).find((row:{id:string})=>row.id===employment).person_id as string;
  const procurement=await append('observation.append',{...observation,claim:'procurement_scope',person:{person_id:other}});
  const channel=await append('observation.append',{...observation,claim:'channel_ownership',person:{person_id:other},
    channel:{type:'business_email',value:'blair@buyer1.example.test',person_id:other}});
  const contact=(await evidence()).find((row:{id:string})=>row.id===channel).contact_id as string;
  const current=(await (await request.get(`${apiBase}/buyers/${leadBuyer}/lead-workflow`,{headers:bearer})).json()).data;
  const otherReview=await append('lead.review',{person_id:other,contact_id:contact,employment:'accepted',
    procurement_scope:'accepted',channel_ownership:'accepted',observation_ids:[employment,procurement,channel],
    rationale:'Independent official purchasing role and business channel.'},current.version);
  await restored.getByRole('button',{name:'Refresh preparations',exact:true}).click();
  await restored.getByLabel('Preparation subject').fill('Original purchaser still intended');
  await restored.getByRole('button',{name:'Save preparation revision',exact:true}).click();
  await expect(restored.getByText('Preparation saved.',{exact:true})).toBeVisible();
  const saved=(await (await request.get(`${apiBase}/buyers/${leadBuyer}/lead-preparations`,{headers:bearer})).json()).data.items[0];
  expect(saved.content.person_id).toBe(stored.content.person_id);
  await restored.getByLabel('Preparation purchasing review').selectOption(otherReview);
  await restored.getByRole('button',{name:'Save preparation revision',exact:true}).click();
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
