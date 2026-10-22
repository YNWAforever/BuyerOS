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
// Both reviewed runners use this exact fixture path, directly or through the built same-origin proxy.
const apiPath=(url:string)=>new URL(url).pathname;
const pathBase=apiPath(apiBase);
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
    response.request().method()==='POST'&&apiPath(response.url())===`${pathBase}/lead-intents`&&
    response.request().postDataJSON()?.action===action);
  const ack=page.waitForResponse(response=>response.status()===200&&
    response.request().method()==='POST'&&apiPath(response.url()).startsWith(`${pathBase}/lead-intents/`)&&
    response.url().endsWith('/acknowledgements'));
  await panel.getByRole('button',{name:button,exact:true}).click();
  const original=(await (await staged).json()).data;
  const confirmed=await ack;
  expect(['http://localhost:5173','http://127.0.0.1:8000']).toContain(new URL(confirmed.url()).origin);
  expect(apiPath(confirmed.url())).toBe(`${pathBase}/lead-intents/${original.id}/acknowledgements`);
  expect(confirmed.status()).toBe(200);
}
async function create(page:Page){
  await signInLead(page,'/app/outreach');
  const panel=page.getByRole('region',{name:'Lead preparations',exact:true});
  await panel.getByLabel('Preparation company').selectOption(leadBuyer);
  await acknowledgedAction(page,panel,'Create cited preparation','preparation.create');
  await expect(panel.getByText('Preparation saved.',{exact:true})).toBeVisible();
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
    apiPath(response.url())===`${pathBase}/lead-intents/${lostIntentId}/acknowledgements`);
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
    apiPath(response.url())===`${pathBase}/lead-intents/${intentId}/acknowledgements`);
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


test('N21-PREP-02/03 dirty company and version changes require an explicit decision',async({page,request})=>{
 const panel=await create(page);
 await acknowledgedAction(page,panel,'Create cited preparation','preparation.create');
 const saved=panel.getByLabel('Saved preparation'),current=await saved.inputValue();
 const options=await saved.locator('option').evaluateAll(rows=>rows.map(row=>(row as HTMLOptionElement).value));
 const otherId=options.find(value=>value!==current)!;
 await panel.getByLabel('Preparation subject').fill('Exact unsaved subject 中🙂');
 await panel.getByLabel('Preparation body').fill('Exact unsaved body\nSecond line 中🙂');
 await saved.selectOption(otherId!);
 const dialog=page.getByRole('dialog');await expect(dialog).toBeVisible();
 await dialog.getByRole('button',{name:'Cancel',exact:true}).click();
 await expect(panel.getByLabel('Preparation subject')).toHaveValue('Exact unsaved subject 中🙂');
 await expect(panel.getByLabel('Preparation body')).toHaveValue('Exact unsaved body\nSecond line 中🙂');
 await saved.selectOption(otherId!);await dialog.getByRole('button',{name:'Save',exact:true}).click();
 await expect(dialog).not.toBeVisible();
 await expect(saved).toHaveValue(otherId);
 await expect(panel.getByLabel('Preparation subject')).not.toHaveValue('Exact unsaved subject 中🙂');
 const values=(await (await request.get(`${apiBase}/buyers/${leadBuyer}/lead-preparations`,{headers:bearer})).json()).data.items;
 expect(values.filter((row:{content:{subject:string}})=>row.content.subject==='Exact unsaved subject 中🙂')).toHaveLength(1);
});
test('N21-PREP-04 dirty refresh cancels or explicitly discards exact text',async({page})=>{
 const panel=await create(page);
 await panel.getByLabel('Preparation body').fill('Keep my exact refresh buffer 中🙂');
 await panel.getByRole('button',{name:'Refresh preparations',exact:true}).click();
 const dialog=page.getByRole('dialog');await expect(dialog).toBeVisible();
 await dialog.getByRole('button',{name:'Cancel',exact:true}).click();
 await expect(panel.getByLabel('Preparation body')).toHaveValue('Keep my exact refresh buffer 中🙂');
 await panel.getByRole('button',{name:'Refresh preparations',exact:true}).click();
 await dialog.getByRole('button',{name:'Discard',exact:true}).click();
 await expect(panel.getByLabel('Preparation body')).toHaveValue(/Thai jasmine rice/);
});
test('N21-PREP-05 sidebar and logout protect edits while both editors are mounted',async({page})=>{
 const panel=await create(page);await panel.getByLabel('Preparation body').fill('Do not lose this sidebar buffer');
 await page.getByRole('button',{name:'Buyers',exact:true}).click();
 const dialog=page.getByRole('dialog');await expect(dialog).toBeVisible();
 await dialog.getByRole('button',{name:'Cancel',exact:true}).click();
 await expect(panel.getByLabel('Preparation body')).toHaveValue('Do not lose this sidebar buffer');
 await page.getByRole('button',{name:'Sign out',exact:true}).click();await expect(dialog).toBeVisible();
 await dialog.getByRole('button',{name:'Cancel',exact:true}).click();
 await expect(panel.getByLabel('Preparation body')).toHaveValue('Do not lose this sidebar buffer');
});
test('N21-PREP-08 Save then navigate stops on committed readback loss and reconciles one revision',async({page,request})=>{
 const panel=await create(page);let committed=false,applies=0;
 await page.route('**/lead-intents/*/apply',async route=>{applies++;const response=await route.fetch();committed=true;await route.fulfill({response});});
 await page.route(/\/buyers\/[^/]+\/lead-preparations(?:\?|$)/,async route=>{
   if(committed)await route.fulfill({status:503,contentType:'application/json',body:'{"code":"TEMPORARY_UNAVAILABLE","message":"synthetic lost readback","retryable":true}'});
   else await route.continue();
 });
 await panel.getByLabel('Preparation subject').fill('One exact transition revision');
 await page.getByRole('button',{name:'Buyers',exact:true}).click();
 await page.getByRole('dialog').getByRole('button',{name:'Save',exact:true}).click();
 await expect(panel.getByText('The save result is unconfirmed. Read the original operation before another edit.',{exact:true})).toBeVisible();
 await expect(panel.getByLabel('Preparation subject')).toHaveValue('One exact transition revision');
 expect(applies).toBe(1);
 await page.getByRole('button',{name:'Buyers',exact:true}).click();
 const unresolved=page.getByRole('dialog');await expect(unresolved).toBeVisible();
 await expect(unresolved.getByRole('button',{name:'Save',exact:true})).toBeDisabled();
 await expect(unresolved).toContainText('Leaving does not cancel or undo the original operation.');
 await unresolved.getByRole('button',{name:'Cancel',exact:true}).click();
 await page.unroute(/\/buyers\/[^/]+\/lead-preparations(?:\?|$)/);
 await panel.getByRole('button',{name:'Read original operation',exact:true}).click();
 await expect(panel.getByLabel('Preparation subject')).toHaveValue('One exact transition revision');
 expect(applies).toBe(1);
 const stored=(await (await request.get(`${apiBase}/buyers/${leadBuyer}/lead-preparations`,{headers:bearer})).json()).data.items[0];
 expect(stored.revision_number).toBe(2);
});

test('N21-PREP-05 browser Back and native reload protect the exact dirty buffer',async({page},info)=>{
 const panel=await create(page);
 await page.getByRole('button',{name:'Overview',exact:true}).click();
 await expect(page).toHaveURL(/\/app\?/);
 await page.getByRole('button',{name:'Drafts',exact:true}).click();
 await expect(page).toHaveURL(/\/app\/outreach/);
 await panel.getByLabel('Preparation company').selectOption(leadBuyer);
 await expect(panel.getByLabel('Preparation body')).toHaveValue(/Thai jasmine rice/);
 await panel.getByLabel('Preparation body').fill('Keep the exact Back buffer 中🙂');
 await page.evaluate(()=>history.back());
 const dialog=page.getByRole('dialog');await expect(dialog).toBeVisible();
 await dialog.getByRole('button',{name:'Cancel',exact:true}).click();
 await expect(page).toHaveURL(/\/app\/outreach/);
 await expect(panel.getByLabel('Preparation body')).toHaveValue('Keep the exact Back buffer 中🙂');
 await page.evaluate(()=>{
   const probe={events:[] as string[]};
   (window as typeof window & {__t21ReloadProbe:typeof probe}).__t21ReloadProbe=probe;
   for(const event of ['beforeunload','pagehide','pageshow'])window.addEventListener(event,()=>probe.events.push(event));
 });
 const nativeDialog=page.waitForEvent('dialog');
 // A canceled navigation never emits the load event that page.reload awaits.
 // Exercise the browser's real reload and observe its native cancellation instead.
 await page.evaluate(()=>{setTimeout(()=>window.location.reload(),0);});
 const warning=await nativeDialog;expect(warning.type()).toBe('beforeunload');await warning.dismiss();
 await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>resolve())));
 const reloadProbe=await page.evaluate(()=>{
   const input=document.querySelector<HTMLTextAreaElement>('[aria-label="Preparation body"]');
   return {events:(window as typeof window & {__t21ReloadProbe?:{events:string[]}}).__t21ReloadProbe?.events??null,
     valueMatches:input?.value==='Keep the exact Back buffer 中🙂',defaultMatches:input?.defaultValue==='Keep the exact Back buffer 中🙂',
     navigation:performance.getEntriesByType('navigation').map(item=>(item as PerformanceNavigationTiming).type)};
 });
 await info.attach('canceled-reload-state',{body:JSON.stringify(reloadProbe),contentType:'application/json'});
 console.log('T21 canceled reload diagnostic',JSON.stringify(reloadProbe));
 await expect(panel.getByLabel('Preparation body')).toHaveValue('Keep the exact Back buffer 中🙂');
 // Chromium can treat Back after a canceled reload as a document navigation.
 // Require actual protection in either browser-controlled or in-app form;
 // an unguarded navigation cannot satisfy the exact buffer/scope assertions.
 let nativeResolve!:(kind:string)=>void;
 const nativeProtection=new Promise<string>(resolve=>{nativeResolve=resolve;});
 const nativeListener=async(warning:import('@playwright/test').Dialog)=>{
   expect(warning.type()).toBe('beforeunload');await warning.dismiss();nativeResolve('native_beforeunload');
 };
 page.on('dialog',nativeListener);
 try{
   await page.evaluate(()=>history.back());
   const kind=await Promise.race([nativeProtection,dialog.waitFor({state:'visible',timeout:5000}).then(()=> 'application_guard')]);
   if(kind==='application_guard')await dialog.getByRole('button',{name:'Cancel',exact:true}).click();
   await info.attach('hard-back-protection',{body:JSON.stringify({kind}),contentType:'application/json'});
   await expect(panel.getByLabel('Preparation body')).toHaveValue('Keep the exact Back buffer 中🙂');
   await expect(page).toHaveURL(/\/app\/outreach/);
 }finally{page.off('dialog',nativeListener);}
 await page.getByRole('button',{name:'Overview',exact:true}).click();await expect(dialog).toBeVisible();
 await dialog.getByRole('button',{name:'Discard',exact:true}).click();
 await expect(page).toHaveURL(/\/app\?/);
});

test('N21-PREP-02 company Cancel, Discard and confirmed Save retain the original scope and revision',async({page,request})=>{
 const panel=await create(page),company=panel.getByLabel('Preparation company'),other='e3200000-0000-4000-8000-000000000002';
 await panel.getByLabel('Preparation body').fill('Unsaved company A exact text 中🙂');
 await company.selectOption(other);const dialog=page.getByRole('dialog');await expect(dialog).toBeVisible();
 await dialog.getByRole('button',{name:'Cancel',exact:true}).click();
 await expect(company).toHaveValue(leadBuyer);await expect(panel.getByLabel('Preparation body')).toHaveValue('Unsaved company A exact text 中🙂');
 await company.selectOption(other);await dialog.getByRole('button',{name:'Discard',exact:true}).click();
 await expect(company).toHaveValue(other);await expect(panel.getByRole('button',{name:'Create cited preparation',exact:true})).toBeEnabled();
 await company.selectOption(leadBuyer);await expect(panel.getByLabel('Preparation body')).toHaveValue(/Thai jasmine rice/);
 await panel.getByLabel('Preparation body').fill('Saved company A exact text 中🙂');
 await company.selectOption(other);await dialog.getByRole('button',{name:'Save',exact:true}).click();
 await expect(company).toHaveValue(other);
 const rows=(await (await request.get(`${apiBase}/buyers/${leadBuyer}/lead-preparations`,{headers:bearer})).json()).data.items;
 expect(rows).toHaveLength(1);expect(rows[0].content.body).toBe('Saved company A exact text 中🙂');expect(rows[0].revision_number).toBe(2);
});
test('N21-PREP-03 preparation page change guards the real record before showing a synthetic volume page',async({page,request})=>{
 const panel=await create(page);let canonical:Record<string,unknown>|null=null;
 await page.route(new RegExp(`/buyers/${leadBuyer}/lead-preparations\\?`),async route=>{
   const response=await route.fetch(),payload=await response.json(),offset=Number(new URL(route.request().url()).searchParams.get('offset')||0);
   if(payload.data.items.length)canonical=payload.data.items[0];
   payload.data.total=21;
   payload.data.items=offset===0?Array.from({length:20},(_,index)=>({...canonical,
     id:index===0?canonical!.id:`f1000000-0000-4000-8000-${String(index).padStart(12,'0')}`})):
     [{...canonical,id:'f1000000-0000-4000-8000-000000000020'}];
   await route.fulfill({response,json:payload});
 });
 await panel.getByRole('button',{name:'Refresh preparations',exact:true}).click();
 const next=panel.getByRole('button',{name:'Next page',exact:true});await expect(next).toBeEnabled();
 await panel.getByLabel('Preparation body').fill('Real saved page buffer 中🙂');
 await next.click();const dialog=page.getByRole('dialog');await expect(dialog).toBeVisible();
 await dialog.getByRole('button',{name:'Cancel',exact:true}).click();
 await expect(panel.getByLabel('Preparation body')).toHaveValue('Real saved page buffer 中🙂');
 await expect(panel.getByText('1–20 / 21',{exact:true})).toBeVisible();
 await next.click();await dialog.getByRole('button',{name:'Save',exact:true}).click();
 await expect(panel.getByText('21–21 / 21',{exact:true})).toBeVisible();
 const rows=(await (await request.get(`${apiBase}/buyers/${leadBuyer}/lead-preparations`,{headers:bearer})).json()).data.items;
 expect(rows).toHaveLength(1);expect(rows[0].content.body).toBe('Real saved page buffer 中🙂');expect(rows[0].revision_number).toBe(2);
});

test('N21-PREP-08 lost stage receipt plus failed history has a read-only recovery entry',async({page,request})=>{
 const panel=await create(page);let lost=false,blockHistory=true,stages=0,applies=0;
 await page.route('**/lead-intents',async route=>{
   if(route.request().method()!=='POST')return route.continue();
   stages++;const response=await route.fetch();expect(response.status()).toBe(201);lost=true;
   await route.fulfill({status:503,contentType:'application/json',body:'{"code":"TEMPORARY_UNAVAILABLE","message":"Synthetic lost staging receipt","retryable":true}'});
 });
 await page.route(/\/lead-intents\?/,async route=>{
   if(lost&&blockHistory)await route.fulfill({status:429,contentType:'application/json',headers:{'Retry-After':'1'},body:'{"code":"RATE_LIMITED","message":"synthetic history hold","retryable":true}'});
   else await route.continue();
 });
 await page.route('**/lead-intents/*/apply',async route=>{applies++;await route.continue();});
 await panel.getByLabel('Preparation subject').fill('One original staged revision 中🙂');
 await panel.getByRole('button',{name:'Save preparation revision',exact:true}).click();
 await expect(panel.getByText('The save result is unconfirmed. Read the original operation before another edit.',{exact:true})).toBeVisible();
 await expect(panel.getByLabel('Preparation subject')).toHaveValue('One original staged revision 中🙂');
 await expect(panel.getByRole('button',{name:'Save preparation revision',exact:true})).toBeDisabled();
 blockHistory=false;
 await expect(panel.getByRole('button',{name:'Refresh original operations',exact:true})).toBeVisible();
 await panel.getByRole('button',{name:'Refresh original operations',exact:true}).click();
 await expect(panel.getByRole('button',{name:'Continue original operation',exact:true})).toBeVisible();
 await panel.getByRole('button',{name:'Continue original operation',exact:true}).click();
 await expect(panel.getByRole('button',{name:'Continue original operation',exact:true})).toHaveCount(0);
 const rows=(await (await request.get(`${apiBase}/buyers/${leadBuyer}/lead-preparations`,{headers:bearer})).json()).data.items;
 expect(rows).toHaveLength(1);expect(rows[0].revision_number).toBe(2);expect(rows[0].content.subject).toBe('One original staged revision 中🙂');
 expect(stages).toBe(1);expect(applies).toBe(1);
});

test('N21-PREP-08 initial unavailable history blocks new writes until the original applied intent is read',async({page,request})=>{
 const panel=await create(page);let stages=0;
 await page.route('**/lead-intents',async route=>{if(route.request().method()==='POST')stages++;await route.continue();});
 await page.route('**/lead-intents/*/apply',async route=>{
   const response=await route.fetch();await route.fulfill({status:503,contentType:'application/json',body:'{"code":"TEMPORARY_UNAVAILABLE","message":"synthetic committed reply loss","retryable":true}'});
   expect(response.status()).toBe(200);
 });
 await panel.getByLabel('Preparation subject').fill('Committed once before reload 中🙂');
 await panel.getByRole('button',{name:'Save preparation revision',exact:true}).click();
 await expect(panel.getByText('The save result is unconfirmed. Read the original operation before another edit.',{exact:true})).toBeVisible();
 await page.unroute('**/lead-intents/*/apply');
 let unavailable=true;
 await page.route(/\/lead-intents\?/,async route=>{
   if(unavailable)await route.fulfill({status:503,contentType:'application/json',body:'{"code":"TEMPORARY_UNAVAILABLE","message":"synthetic initial history unavailable","retryable":true}'});
   else await route.continue();
 });
 page.once('dialog',warning=>warning.accept());
 await page.reload();await signInLead(page,'/app/outreach');
 const restored=page.getByRole('region',{name:'Lead preparations',exact:true});
 await restored.getByLabel('Preparation company').selectOption(leadBuyer);
 await expect(restored.getByLabel('Preparation subject')).toHaveValue('Committed once before reload 中🙂');
 await expect(restored.getByRole('button',{name:'Save preparation revision',exact:true})).toBeDisabled();
 await expect(restored.getByRole('button',{name:'Create cited preparation',exact:true})).toBeDisabled();
 // Read failures must prevent new writes, not trap a clean reader on this page.
 await page.getByRole('button',{name:'Overview',exact:true}).click();
 await expect(page).toHaveURL(/\/app\?/);
 await page.getByRole('button',{name:'Drafts',exact:true}).click();
 await restored.getByLabel('Preparation company').selectOption(leadBuyer);
 await expect(restored.getByRole('button',{name:'Save preparation revision',exact:true})).toBeDisabled();
 unavailable=false;
 await restored.getByRole('button',{name:'Refresh original operations',exact:true}).click();
 await restored.getByRole('button',{name:'Read original operation',exact:true}).click();
 await expect(restored.getByRole('button',{name:'Read original operation',exact:true})).toHaveCount(0);
 const rows=(await (await request.get(`${apiBase}/buyers/${leadBuyer}/lead-preparations`,{headers:bearer})).json()).data.items;
 expect(rows).toHaveLength(1);expect(rows[0].revision_number).toBe(2);expect(stages).toBe(1);
});

test('N21-PREP-05 in-document Back Discard is explicit and Forward restores the same project',async({page})=>{
 const panel=await create(page);
 await page.getByRole('button',{name:'Overview',exact:true}).click();
 await expect(page).toHaveURL(/\/app\?/);
 await page.getByRole('button',{name:'Drafts',exact:true}).click();
 await expect(page).toHaveURL(/\/app\/outreach/);
 await panel.getByLabel('Preparation company').selectOption(leadBuyer);
 await expect(panel.getByLabel('Preparation body')).toHaveValue(/Thai jasmine rice/);
 await panel.getByLabel('Preparation body').fill('Only an explicit Discard may leave this text');
 await page.evaluate(()=>history.back());const dialog=page.getByRole('dialog');await expect(dialog).toBeVisible();
 await dialog.getByRole('button',{name:'Discard',exact:true}).click();
 await expect(page).toHaveURL(/\/app\?/);
 await page.evaluate(()=>history.forward());
 await expect(page).toHaveURL(/\/app\/outreach/);
 await expect(page.getByRole('combobox',{name:'Project',exact:true})).toHaveValue('e3100000-0000-4000-8000-000000000001');
});

test('N21-PREP-05 confirmed clean save may navigate while auxiliary history is held',async({page})=>{
 await signInLead(page,'/app/outreach');
 const panel=page.getByRole('region',{name:'Lead preparations',exact:true});
 await panel.getByLabel('Preparation company').selectOption(leadBuyer);
 let acknowledged=false,release!:()=>void,held=false;
 const hold=new Promise<void>(resolve=>{release=resolve;});
 page.on('response',response=>{if(response.status()===200&&response.url().endsWith('/acknowledgements'))acknowledged=true;});
 await page.route(/\/lead-intents\?/,async route=>{
   if(acknowledged){held=true;await hold;}
   await route.continue();
 });
 try{
   await acknowledgedAction(page,panel,'Create cited preparation','preparation.create');
   await expect(panel.getByText('Preparation saved.',{exact:true})).toBeVisible();
   await expect.poll(()=>held).toBe(true);
   await page.getByRole('button',{name:'Overview',exact:true}).click();
   await expect(page).toHaveURL(/\/app\?/);
 }finally{release();}
});

test('N21-PREP-05 approved slow route removes the old editor before it can accept late edits',async({page})=>{
 const panel=await create(page);let held=false,release!:()=>void;
 const hold=new Promise<void>(resolve=>{release=resolve;});
 await page.route('http://localhost:5173/app?**',async route=>{
   const request=route.request();
   if(request.method()==='GET'&&['fetch','xhr'].includes(request.resourceType())){held=true;await hold;}
   await route.continue();
 });
 try{
   await page.getByRole('button',{name:'Overview',exact:true}).click();
   await expect.poll(()=>held).toBe(true);
   await expect(panel.getByLabel('Preparation body')).toHaveCount(0);
   await expect(page.getByRole('status')).toContainText('Opening page');
 }finally{release();}
 await expect(page.getByRole('heading',{name:'Overview',exact:true})).toBeVisible();
});

test('N21-PREP-03 dirty Save then Archive uses the newly confirmed version without orphan intents',async({page,request})=>{
 const panel=await create(page);let applies=0;
 await page.route('**/lead-intents/*/apply',async route=>{applies++;await route.continue();});
 await panel.getByLabel('Preparation body').fill('Exact body saved before archive 中🙂');
 await panel.getByLabel('Content review reason').fill('Archive only after preserving this exact edited body.');
 await panel.getByRole('button',{name:'Archive preparation',exact:true}).click();
 const dialog=page.getByRole('dialog');await expect(dialog).toBeVisible();
 await dialog.getByRole('button',{name:'Save',exact:true}).click();
 await expect(panel.getByText('Preparation state: archived',{exact:true})).toBeVisible();
 const rows=(await (await request.get(`${apiBase}/buyers/${leadBuyer}/lead-preparations`,{headers:bearer})).json()).data.items;
 expect(rows).toHaveLength(1);expect(rows[0].revision_number).toBe(2);expect(rows[0].content.body).toBe('Exact body saved before archive 中🙂');expect(applies).toBe(2);
 const pending=(await (await request.get(`${apiBase}/lead-intents`,{headers:bearer})).json()).data.items;
 expect(pending).toHaveLength(0);
});

test('N21-PREP-03 paged readback cannot substitute another preparation during Save then Archive',async({page,request})=>{
 const panel=await create(page),saved=panel.getByLabel('Saved preparation');
 const original=await saved.inputValue();
 await acknowledgedAction(page,panel,'Create cited preparation','preparation.create');
 await expect(saved.locator('option')).toHaveCount(2);
 const other=(await saved.locator('option').evaluateAll(rows=>rows.map(row=>(row as HTMLOptionElement).value))).find(id=>id!==original)!;expect(other).toBeTruthy();
 const before=(await (await request.get(`${apiBase}/buyers/${leadBuyer}/lead-preparations`,{headers:bearer})).json()).data.items;
 const untouched=before.find((row:{id:string})=>row.id===other);expect(untouched).toBeTruthy();
 await saved.selectOption(original);
 await expect(saved).toHaveValue(original);
 // Two persisted records; model a page shifting after a concurrent insert by
 // omitting the selected record from this list window. Direct reads remain real.
 let shifted=false;
 await page.route('**/lead-intents/*/apply',async route=>{
   const response=await route.fetch();shifted=true;await route.fulfill({response});
 });
 await page.route(/\/buyers\/[^/]+\/lead-preparations\?/,async route=>{
   const response=await route.fetch();
   if(!shifted)return route.fulfill({response});
   const body=await response.json();
   body.data.items=body.data.items.filter((row:{id:string})=>row.id!==original);
   await route.fulfill({response,json:body});
 });
 await panel.getByLabel('Preparation body').fill('Preserve original identity across a shifted list window 中🙂');
 await panel.getByLabel('Content review reason').fill('Archive only this originally selected preparation.');
 await panel.getByRole('button',{name:'Archive preparation',exact:true}).click();
 await page.getByRole('dialog').getByRole('button',{name:'Save',exact:true}).click();
 await expect(panel.getByText('Preparation state: archived',{exact:true})).toBeVisible();
 const rows=(await (await request.get(`${apiBase}/buyers/${leadBuyer}/lead-preparations`,{headers:bearer})).json()).data.items;
 expect(rows.find((row:{id:string})=>row.id===original)?.state).toBe('archived');
 expect(rows.find((row:{id:string})=>row.id===original)?.content.body).toBe('Preserve original identity across a shifted list window 中🙂');
 expect(rows.find((row:{id:string})=>row.id===other)).toEqual(untouched);
 expect(rows.filter((row:{state:string})=>row.state==='archived')).toHaveLength(1);
});

test('N21-PREP-05 forced session expiry clears protected content and explains unsaved preparation loss',async({page})=>{
 await page.clock.install({time:new Date()});
 const panel=await create(page),canary='Unsubmitted preparation-only expiry canary 中🙂';
 await panel.getByLabel('Preparation body').fill(canary);
 await page.clock.fastForward(900_000);
 await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeVisible();
 await expect(panel.getByLabel('Preparation body')).toHaveCount(0);
 await expect(page.getByRole('alert')).toContainText('Your session ended. Preparation edits on this page were cleared. A submitted save may have completed. Sign in and read the original operation before retrying.');
 expect(await page.evaluate(()=>JSON.stringify(Object.fromEntries(Object.entries(sessionStorage))))).not.toContain(canary);
});
