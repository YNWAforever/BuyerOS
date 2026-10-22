import {test,expect} from '@playwright/test';
import {signInLead,resetLead,leadBuyer} from './fixtures/lead-workflow';
test.beforeEach(async({request})=>resetLead(request));
test('N21-PREP-06/07 search is accessible, bounded and preserves the selected company',async({page})=>{
 await signInLead(page,'/app/outreach');
 const panel=page.getByRole('region',{name:'Lead preparations',exact:true});
 await expect(panel.getByRole('searchbox',{name:'Search companies',exact:true})).toBeVisible();
 await panel.getByLabel('Preparation company').selectOption(leadBuyer);
 await panel.getByRole('searchbox',{name:'Search companies',exact:true}).fill('no-such-synthetic-company');
 await expect(panel.getByText('No matching companies.',{exact:true})).toBeVisible();
 await expect(panel.getByLabel('Preparation company')).toHaveValue(leadBuyer);
 await expect(panel.getByLabel('Preparation company').locator('option')).toHaveCount(2);
});
test('N21-BUYER-01 rows identify the actual domain, evidence and unknown market',async({page})=>{
 await signInLead(page,'/app/discover');
 const row=page.locator('.live-buyer-row').filter({hasText:'Fixture Rice Buyer 01'});
 await expect(row).toContainText('buyer1.example.test');
 await expect(row).toContainText('Market: Unknown');
 await expect(row).toContainText(/Sources: \d+/);
 await expect(row).toContainText(/Fit reason:/);
});
test('N21-WORK-05/OPS-01 owner filters use the authorized directory without UUID entry',async({page,request})=>{
 const setup=await request.post('http://127.0.0.1:8000/fixture/lead-scenario',{data:{scenario:'t21_named_members'}});
 expect(setup.ok(),await setup.text()).toBe(true);
 await signInLead(page,'/app/operations');
 const panel=page.getByRole('region',{name:'Lead workflow',exact:true});
 await expect(panel.getByRole('searchbox',{name:'Find owner',exact:true})).toBeVisible();
 await expect(panel.getByRole('combobox',{name:'Owner',exact:true})).toBeVisible();
 await expect(panel.getByLabel('Owner user ID')).toHaveCount(0);
 const owner=panel.getByRole('combobox',{name:'Owner',exact:true});
 await panel.getByRole('searchbox',{name:'Find owner',exact:true}).fill('Fixture Alex Chan');
 await expect(owner.getByRole('option',{name:/Fixture Alex Chan/})).toHaveCount(2);
 await owner.selectOption('e0000000-0000-4000-8000-000000000004');
 await expect(panel.getByText('Matching companies: 1',{exact:true})).toBeVisible();
 await expect(panel.locator('[data-lead-buyer]')).toContainText('Fixture Rice Buyer 02');
 await owner.selectOption('mine');
 await expect(panel.getByText('Matching companies: 1',{exact:true})).toBeVisible();
 await expect(panel.locator('[data-lead-buyer]')).toContainText('Fixture Rice Buyer 01');
 await owner.selectOption('unassigned');
 await expect(page).toHaveURL(/lead_owner=unassigned/);
 await expect(panel.getByText('Matching companies: 22',{exact:true})).toBeVisible();
});

test('N21-WORK-03 browser history reconciles the project through existing membership reads',async({page})=>{
 await signInLead(page,'/app');
 await page.getByRole('button',{name:'Drafts',exact:true}).click();
 await expect(page).toHaveURL(/\/app\/outreach/);
 const picker=page.getByRole('combobox',{name:'Project',exact:true});
 const initial=await picker.inputValue();
 const options=await picker.locator('option').evaluateAll(rows=>rows.map(row=>(row as HTMLOptionElement).value));
 const other=options.find(value=>value&&value!==initial)!;expect(other).toBeTruthy();
 await picker.selectOption(other);await expect(picker).toHaveValue(other);
 await page.evaluate(()=>history.back());
 await expect.poll(()=>new URL(page.url()).searchParams.get('project')).toBe(initial);
 await expect(picker).toHaveValue(initial);
});

test('N21-WORK-05 Mine directory 503 keeps local recovery and filters visible',async({page})=>{
 let unavailable=true;
 await page.route('**/eligible-assignees?**',async route=>{
   if(unavailable)await route.fulfill({status:503,contentType:'application/json',body:'{"code":"TEMPORARY_UNAVAILABLE","message":"synthetic member lookup unavailable","retryable":true}'});
   else await route.continue();
 });
 await signInLead(page,'/app/operations?lead_owner=mine');
 const panel=page.getByRole('region',{name:'Lead workflow',exact:true});
 await expect(panel.getByRole('button',{name:'Retry members',exact:true})).toBeVisible();
 await expect(panel.getByRole('link',{name:'Clear lead filters',exact:true})).toBeVisible();
 unavailable=false;await panel.getByRole('button',{name:'Retry members',exact:true}).click();
 await expect(panel.getByText('Matching companies: 0',{exact:true})).toBeVisible();
});
for(const actor of ['reviewer','viewer'] as const){
 test(`N21-WORK-05 denied directory ${actor} can leave Mine without a privilege bypass`,async({page})=>{
   await signInLead(page,'/app/operations?lead_owner=mine',actor);
   const panel=page.getByRole('region',{name:'Lead workflow',exact:true});
   await expect(panel.getByRole('link',{name:'Clear lead filters',exact:true})).toBeVisible();
   await panel.getByRole('combobox',{name:'Owner',exact:true}).selectOption('unassigned');
   await expect(panel.getByText('Matching companies: 24',{exact:true})).toBeVisible();
 });
}

test('N21-PREP-06/07 company retry preserves its query and directly resolves the selected deep link',async({page})=>{
 let unavailable=true,listReads=0;
 await page.route('**/buyer-snapshots',async route=>{
   if(unavailable)return route.fulfill({status:503,contentType:'application/json',body:'{"code":"TEMPORARY_UNAVAILABLE","message":"synthetic directory outage","retryable":true}'});
   await route.continue();
 });
 page.on('request',request=>{if(/\/buyers\?/.test(request.url()))listReads++;});
 await signInLead(page,`/app/outreach?buyer=${leadBuyer}`);
 const panel=page.getByRole('region',{name:'Lead preparations',exact:true}),picker=panel.getByLabel('Preparation company');
 await expect(picker).toHaveValue(leadBuyer);
 await expect(picker.getByRole('option',{name:'Fixture Rice Buyer 01',exact:true})).toHaveCount(1);
 expect(listReads).toBe(0);
 const search=panel.getByRole('searchbox',{name:'Search companies',exact:true});
 const failedQuery=page.waitForResponse(response=>response.request().method()==='POST'&&response.url().endsWith('/buyer-snapshots')&&response.request().postDataJSON()?.filters?.q==='Fixture Rice Buyer 01');
 await search.fill('Fixture Rice Buyer 01');
 expect((await failedQuery).status()).toBe(503);
 await expect(panel.getByRole('button',{name:'Retry companies',exact:true})).toBeVisible();
 unavailable=false;
 const retriedQuery=page.waitForRequest(request=>request.method()==='POST'&&request.url().endsWith('/buyer-snapshots')&&request.postDataJSON()?.filters?.q==='Fixture Rice Buyer 01');
 await panel.getByRole('button',{name:'Retry companies',exact:true}).click();
 expect((await retriedQuery).postDataJSON().filters.q).toBe('Fixture Rice Buyer 01');
 await expect(picker.locator('option')).toHaveCount(2);
 await expect(picker.getByRole('option',{name:'Fixture Rice Buyer 01 · buyer1.example.test',exact:true})).toHaveCount(1);
 await expect(search).toHaveValue('Fixture Rice Buyer 01');
 await expect(picker).toHaveValue(leadBuyer);
});
test('N21-PREP-07 superseded company-search responses cannot replace the current query',async({page})=>{
 await signInLead(page,'/app/outreach');
 const panel=page.getByRole('region',{name:'Lead preparations',exact:true}),picker=panel.getByLabel('Preparation company');
 await expect(picker.locator('option')).toHaveCount(25);
 let held=false,release!:()=>void,settled!:()=>void;
 const hold=new Promise<void>(resolve=>{release=resolve;}),done=new Promise<void>(resolve=>{settled=resolve;});
 await page.route('**/buyer-snapshots',async route=>{
   if(route.request().postDataJSON()?.filters?.q!=='Fixture Rice Buyer 01')return route.continue();
   const response=await route.fetch();held=true;await hold;
   try{await route.fulfill({response});}catch{expect(route.request().failure()).toBeTruthy();}finally{settled();}
 });
 try{
   const search=panel.getByRole('searchbox',{name:'Search companies',exact:true});
   await search.fill('Fixture Rice Buyer 01');await expect.poll(()=>held).toBe(true);
   await search.fill('Fixture Rice Buyer 02');
   await expect(picker.getByRole('option',{name:'Fixture Rice Buyer 02 · buyer2.example.test',exact:true})).toHaveCount(1);
   release();await done;
   await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
   await expect(search).toHaveValue('Fixture Rice Buyer 02');
   await expect(picker.getByRole('option',{name:'Fixture Rice Buyer 02 · buyer2.example.test',exact:true})).toHaveCount(1);
   await expect(picker.getByRole('option',{name:/Fixture Rice Buyer 01/})).toHaveCount(0);
 }finally{release();}
});
