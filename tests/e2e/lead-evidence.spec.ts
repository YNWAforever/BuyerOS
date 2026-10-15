import {expect,test} from '@playwright/test';
import {apiBase,bearer,leadBuyer,workspace,resetLead,signInLead,openLeadBuyer,fillLeadEvidence,mutateCase} from './fixtures/lead-workflow';

test.beforeEach(async({request})=>resetLead(request));

test('company_person_channel_have_separate_statuses',async({page})=>{
  await signInLead(page);
  await openLeadBuyer(page,1,'Contacts');
  const panel=page.getByRole('region',{name:'Lead contact preparation'});
  await expect(panel.getByText('Purchasing role: confirmed',{exact:true})).toBeVisible();
  await expect(panel.getByText('Channel ownership: confirmed',{exact:true})).toBeVisible();
  await expect(panel.getByText('Technical check: not tested',{exact:true})).toBeVisible();
  await expect(panel.getByText('Sending: disabled',{exact:true})).toBeVisible();
  await panel.getByRole('button',{name:'Load purchasing review history',exact:true}).click();
  await expect(panel.getByRole('region',{name:'Purchasing review history',exact:true})
    .getByText('Fictional purchasing identity and source ownership checked.',{exact:true})).toBeVisible();
  await page.getByRole('combobox',{name:/^(Language|語言)$/}).selectOption('zh-HK');
  const zh=page.getByRole('region',{name:'採購聯絡準備'});
  await expect(zh.getByText('採購職責：已核實',{exact:true})).toBeVisible();
  await expect(zh.getByText('技術驗證：未測',{exact:true})).toBeVisible();
  await expect(zh.getByText('寄信：停用',{exact:true})).toBeVisible();
});

test('unknown_save_survives_reload_and_company_switch',async({page,request})=>{
  await signInLead(page);await openLeadBuyer(page);
  let applies=0;
  await page.route('**/lead-intents/*/apply',async route=>{
    applies++;const result=await route.fetch();
    if(applies===1){await route.fulfill({status:503,contentType:'application/json',
      body:JSON.stringify({code:'TEMPORARY_UNAVAILABLE',message:'Unconfirmed fixture reply',retryable:true,request_id:'fixture'})});}
    else await route.fulfill({response:result});
  });
  await fillLeadEvidence(page,'Uncertain Fixture Person');
  await page.getByRole('region',{name:'Manual lead evidence'}).getByRole('button',{name:'Save lead evidence',exact:true}).click();
  await expect(page.getByText('The save result is unconfirmed. Read the original operation before another edit.',{exact:true})).toBeVisible();
  await page.reload();await signInLead(page);await openLeadBuyer(page);
  const panel=page.getByRole('region',{name:'Manual lead evidence'});
  await panel.getByRole('button',{name:'Read original operation',exact:true}).first().click();
  await expect(panel.locator('article').getByText('Uncertain Fixture Person',{exact:true})).toBeVisible();
  expect(applies).toBe(1);
  const rows=(await (await request.get(`${apiBase}/buyers/${leadBuyer}/lead-evidence`,{headers:bearer})).json()).data.items;
  expect(rows.filter((row:{person:{full_name:string}|null})=>row.person?.full_name==='Uncertain Fixture Person')).toHaveLength(1);
  await page.getByRole('button',{name:/^(Close details|關閉詳情)$/}).click();await openLeadBuyer(page,2);
  await expect(page.getByRole('region',{name:'Manual lead evidence'}).getByText('Uncertain Fixture Person')).toHaveCount(0);
});

test('duplicate_apply_and_stale_edit_do_not_duplicate_or_overwrite',async({page,request})=>{
  await signInLead(page);await openLeadBuyer(page,1,'Contacts');
  let original:{id:string;submission_key:string;expected_version:number}|null=null;
  page.on('response',async response=>{
    if(response.request().method()==='POST'&&response.url().endsWith('/lead-intents')&&response.ok()){
      const value=await response.json();if(value.data.action==='case.update')original=value.data;
    }
  });
  const panel=page.getByRole('region',{name:'Lead contact preparation'});
  await panel.getByLabel('Next lead action').fill('First saved action');
  await panel.getByRole('button',{name:'Save lead work state',exact:true}).click();
  await expect(panel.getByText('Lead work state saved.',{exact:true})).toBeVisible();
  const before=(await (await request.get(`${apiBase}/buyers/${leadBuyer}/lead-workflow`,{headers:bearer})).json()).data;
  await expect.poll(()=>original!==null).toBe(true);
  const fixed=original as unknown as {id:string;submission_key:string;expected_version:number};
  const replay=await request.post(`${apiBase}/lead-intents/${fixed.id}/apply`,{
    headers:{...bearer,'Idempotency-Key':fixed.submission_key,'If-Match':`"${fixed.expected_version}"`},data:{}});
  expect(replay.status()).toBe(200);
  expect((await (await request.get(`${apiBase}/buyers/${leadBuyer}/lead-workflow`,{headers:bearer})).json()).data.version).toBe(before.version);
  await panel.getByLabel('Next lead action').fill('Stale local edit');
  await mutateCase(request,leadBuyer,before.version,'Concurrent latest action');
  await panel.getByRole('button',{name:'Save lead work state',exact:true}).click();
  await expect(panel.getByRole('alert')).toBeVisible();
  const after=(await (await request.get(`${apiBase}/buyers/${leadBuyer}/lead-workflow`,{headers:bearer})).json()).data;
  expect(after.next_action).toBe('Concurrent latest action');
  await expect(panel.getByLabel('Next lead action')).toHaveValue('Stale local edit');
});

test('viewer_and_revoked_actor_cannot_edit_or_replay',async({page,browser,request})=>{
  await signInLead(page,'/app/discover','viewer');await openLeadBuyer(page);
  const panel=page.getByRole('region',{name:'Manual lead evidence'});
  await expect(panel).toBeVisible();
  await expect(panel.getByRole('button',{name:'Save lead evidence',exact:true})).toHaveCount(0);
  await page.getByRole('tab',{name:/^(Contacts|聯絡資料)$/}).click();
  await expect(page.getByRole('region',{name:'Lead contact preparation'}).getByRole('button',{name:'Save lead work state'})).toHaveCount(0);
  const editorContext=await browser.newContext();
  try{
    const editor=await editorContext.newPage();
    await signInLead(editor);await openLeadBuyer(editor);await fillLeadEvidence(editor,'Revoked Fixture Person');
    const revoked=await request.post('http://127.0.0.1:8000/fixture/lead-revoke-admin');
    expect(revoked.ok()).toBe(true);
    await editor.getByRole('region',{name:'Manual lead evidence'}).getByRole('button',{name:'Save lead evidence',exact:true}).click();
    await expect(editor.getByRole('alert').first()).toBeVisible();
    const raw=await request.get(`${apiBase}/buyers/${leadBuyer}/lead-evidence`,{headers:{Authorization:'Bearer fixture-reviewer'}});
    expect((await raw.json()).data.items.some((item:{person:{full_name:string}|null})=>item.person?.full_name==='Revoked Fixture Person')).toBe(false);
  }finally{await editorContext.close();}
});

test('source_checks_and_research_fit_remain_unchanged',async({page,request})=>{
  const sources=`http://127.0.0.1:8000/v1/workspaces/${workspace}/buyers/${leadBuyer}/source-checks`;
  const oldBuyer=`http://127.0.0.1:8000/v1/workspaces/${workspace}/buyers/${leadBuyer}`;
  const beforeChecks=(await (await request.get(sources,{headers:bearer})).json()).data;
  const before=(await (await request.get(oldBuyer,{headers:bearer})).json()).data;
  await signInLead(page);await openLeadBuyer(page);await fillLeadEvidence(page,'Independent Fixture Person');
  const panel=page.getByRole('region',{name:'Manual lead evidence'});
  await panel.getByRole('button',{name:'Save lead evidence',exact:true}).click();
  await expect(panel.getByText('Lead evidence saved.',{exact:true})).toBeVisible();
  const afterChecks=(await (await request.get(sources,{headers:bearer})).json()).data;
  const after=(await (await request.get(oldBuyer,{headers:bearer})).json()).data;
  expect(afterChecks).toEqual(beforeChecks);
  expect(after.fit).toEqual(before.fit);expect(after.review_status).toEqual(before.review_status);
});
