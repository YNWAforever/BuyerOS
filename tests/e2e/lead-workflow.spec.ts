import {expect,test} from '@playwright/test';
import {entry,leadProject,resetLead,signInLead,apiBase,bearer,leadBuyer,mutateCase} from './fixtures/lead-workflow';
test.beforeEach(async({request})=>resetLead(request));
test('six_pages_preserve_project_and_progress_after_reload',async({page})=>{
  await signInLead(page,'/app');
  for(const path of ['/app','/app/discover/edit','/app/discover','/app/operations','/app/outreach','/app/settings']){
    await page.goto(entry(path));await page.reload();
    await expect(page.getByRole('combobox',{name:/^(Project|專案)$/})).toHaveValue(leadProject,{timeout:30_000});
    await expect(page.getByRole('combobox',{name:'Project',exact:true})).toHaveValue(leadProject);
    if(path==='/app'||path==='/app/operations')await expect(page.getByRole('region',{name:'Lead workflow',exact:true})).toBeVisible();
    if(path==='/app/outreach')await expect(page.getByRole('region',{name:'Lead preparations',exact:true})).toBeVisible();
    if(path==='/app/settings')await expect(page.getByRole('region',{name:'Pilot monthly budget',exact:true})).toBeVisible();
  }
});
test('metrics_and_filtered_results_count_distinct_companies',async({page})=>{
  await signInLead(page,'/app');
  const panel=page.getByRole('region',{name:'Lead workflow',exact:true});
  for(const text of ['Company evidence: 24 / 24','Priority companies: 8 / 8','Purchasing people: 6 / 6','Direct channels: 4 / 4','Reviewed preparations: 0 / 4'])
    await expect(panel.getByRole('link',{name:text,exact:true})).toBeVisible();
  await panel.getByRole('link',{name:'Direct channels: 4 / 4',exact:true}).click();
  const results=page.getByRole('region',{name:'Lead workflow',exact:true});
  await expect(results.getByText('Matching companies: 4',{exact:true})).toBeVisible();
  await expect(results.locator('[data-lead-buyer]')).toHaveCount(4);
  await page.reload();await signInLead(page,'/app/operations?lead_qualifies=direct_channel');
  await expect(results.getByText('Matching companies: 4',{exact:true})).toBeVisible();
  await results.getByRole('link',{name:'Clear lead filters',exact:true}).click();
  await expect(results.getByText('Matching companies: 24',{exact:true})).toBeVisible();
  await results.getByRole('button',{name:'Next page',exact:true}).click();
  await expect(results.getByText('Fixture Rice Buyer 21',{exact:true})).toBeVisible();
  await results.getByRole('link',{name:'Direct channels: 4 / 4',exact:true}).click();
  await expect(results.getByText('Matching companies: 4',{exact:true})).toBeVisible();
  await expect(results.locator('[data-lead-buyer]')).toHaveCount(4);
});
test('read_failure_is_unavailable_not_zero',async({page})=>{
  await page.route('**/lead-workflow?*',route=>route.fulfill({status:503,contentType:'application/json',body:'{"code":"TEMPORARY_UNAVAILABLE","message":"Unavailable","retryable":true,"request_id":"fixture"}'}));
  await signInLead(page,'/app');
  const panel=page.getByRole('region',{name:'Lead workflow',exact:true});
  await expect(panel.getByRole('alert')).toContainText('Lead progress unavailable.');
  await expect(panel.getByRole('link',{name:/Company evidence:/})).toHaveCount(0);
  await page.unroute('**/lead-workflow?*');
  await panel.getByRole('button',{name:'Refresh lead progress',exact:true}).click();
  await expect(panel.getByRole('link',{name:'Company evidence: 24 / 24',exact:true})).toBeVisible();
  await panel.getByRole('link',{name:'Company evidence: 24 / 24',exact:true}).click();
  await expect(panel.getByText('Matching companies: 24',{exact:true})).toBeVisible();
  let release!:()=>void,delivered!:()=>void,oldFetched=false,heldOnce=false;
  const hold=new Promise<void>(resolve=>{release=resolve;});
  const oldDelivered=new Promise<void>(resolve=>{delivered=resolve;});
  await page.route('**/lead-workflow?*',async route=>{
    if(new URL(route.request().url()).searchParams.get('qualifies_for')==='company_card'&&!heldOnce){
      heldOnce=true;const response=await route.fetch();oldFetched=true;
      await hold;try{await route.fulfill({response});}finally{delivered();}
    }else await route.continue();
  });
  try{
    await panel.getByRole('button',{name:'Refresh lead progress',exact:true}).click();
    await expect.poll(()=>oldFetched).toBe(true);
    await panel.getByRole('link',{name:'Direct channels: 4 / 4',exact:true}).click();
    await expect(panel.getByText('Matching companies: 4',{exact:true})).toBeVisible();
    release();await oldDelivered;
    await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
    await expect(panel.getByText('Matching companies: 4',{exact:true})).toBeVisible();
    await expect(panel.locator('[data-lead-buyer]')).toHaveCount(4);
  }finally{release();}
});
test('followup_due_date_never_starts_a_job',async({page,request})=>{
  const before=await (await request.get('http://127.0.0.1:8000/fixture/lead-counts')).json();
  const current=(await (await request.get(`${apiBase}/buyers/${leadBuyer}/lead-workflow`,{headers:bearer})).json()).data;
  await mutateCase(request,leadBuyer,current.version,'Read the official supplier page manually','2026-10-15');
  await signInLead(page,'/app/operations');
  const panel=page.getByRole('region',{name:'Lead workflow',exact:true});
  await expect(panel.getByText('Read the official supplier page manually',{exact:true})).toBeVisible();
  await expect(panel.getByText('Follow-up dates are reminders; no automatic jobs are started.',{exact:true})).toBeVisible();
  const company=panel.locator('[data-lead-buyer]').filter({hasText:'Fixture Rice Buyer 01'});
  await expect(company.getByText(/Follow-up date: 2026-10-15/)).toBeVisible();
  await company.getByRole('button',{name:'Review company evidence',exact:true}).click();
  const evidence=company.getByRole('region',{name:'Manual lead evidence',exact:true});
  await evidence.getByLabel('Evidence claim').selectOption('procurement_scope');
  await evidence.getByLabel('Evidence person').selectOption(current.selected_person_id);
  await evidence.getByLabel('Source stance').selectOption('refutes');
  await evidence.getByLabel('Evidence source title').fill('Official changed purchasing scope');
  await evidence.getByLabel('Evidence source URL').fill('https://buyer1.example.test/team-update');
  await evidence.getByLabel('Evidence excerpt').fill('The named person no longer manages rice procurement.');
  await evidence.getByLabel('Evidence rationale').fill('An official current source contradicts the earlier purchasing role.');
  await evidence.getByRole('button',{name:'Save lead evidence',exact:true}).click();
  await expect(company.getByRole('region',{name:'Lead contact preparation'}).getByText('Purchasing role: pending',{exact:true})).toBeVisible();
  await page.reload();await signInLead(page,'/app/operations');
  expect(await (await request.get('http://127.0.0.1:8000/fixture/lead-counts')).json()).toEqual(before);
});
