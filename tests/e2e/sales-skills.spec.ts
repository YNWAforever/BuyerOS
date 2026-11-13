import {test,expect,chromium} from '@playwright/test';
import {mkdir,mkdtemp,writeFile,rm} from 'node:fs/promises';
import {resolve,relative} from 'node:path';
import {readFileSync} from 'node:fs';
import {fixture,threadId,otherId,taskId} from '../sales-skills-fixture';
import type {Page} from '@playwright/test';

// The studio makes the conversation primary and keeps the guided skill form behind a
// native disclosure. Every navigation re-opens that disclosure through its visible
// summary control before a test continues with the unchanged guided assertions.
async function openGuided(page:Page){
 // Only discussion/live surfaces have a guided form. Documents and other retained
 // pages have no studio, so return instead of waiting out the test timeout.
 const surface=page.locator('.conversation-home, .conversation-studio').first();
 try{await surface.waitFor({state:'attached',timeout:5000});}catch{return;}
 // On the project dashboard the guided disclosure is absent: open the fixture's
 // saved discussion before looking for the guided form.
 if(await page.locator('.conversation-home').count()){
  const first=page.locator('.conversation-thread-items button').first();
  if(await first.count()){
   if(!(await first.isVisible()))await page.getByRole('button',{name:'Show discussions',exact:true}).click();
   await first.waitFor({state:'visible',timeout:10000});
   await first.click();
   await page.waitForFunction(()=>/^\/app\/discussions\/s\//.test(new URL(location.href).searchParams.get('route')??''),{timeout:10000}).catch(()=>{});
   // Selecting a thread on a narrow viewport leaves the drawer open over the thread.
   if(await page.locator('.conversation-studio[data-mobile-view="threads"]').count())await page.keyboard.press('Escape');
  }
 }
 for(let attempt=0;attempt<5;attempt+=1){
  const disclosure=page.locator('details').filter({has:page.locator('summary',{hasText:/Guided setup|引導設定/})}).first();
  try{await disclosure.waitFor({state:'attached',timeout:5000});}catch{continue;}
  if(await disclosure.evaluate(node=>(node as HTMLDetailsElement).open))return;
  try{await disclosure.locator('summary').first().click();return;}catch{/* A remount closed and replaced it; retry. */}
 }
}
async function gotoPage(page:Page,url:string){await page.goto(url);await openGuided(page);}
async function reloadPage(page:Page){await page.reload();await openGuided(page);}
// Thread selection from the project home: the conversation sidebar owns server
// discussions; the retained Device discussions disclosure still owns legacy/device
// entries. Open whichever surface holds the named thread, without widening the name.
async function openThread(page:Page,name:string){
 const sidebar=page.getByRole('button',{name,exact:true});
 try{await sidebar.first().waitFor({state:'visible',timeout:8000});await sidebar.first().click();return;}catch{/* Retained surface below. */}
 const device=page.locator('details').filter({has:page.locator('summary',{hasText:/Device discussions|此裝置的討論/})}).first();
 if(await device.count()){
  if(!(await device.evaluate(node=>(node as HTMLDetailsElement).open)))await device.locator('summary').first().click();
  const legacy=page.locator('.live-discussion').getByRole('button').filter({hasText:name}).first();
  try{await legacy.waitFor({state:'visible',timeout:5000});await legacy.click();return;}catch{/* Last-resort lookup below. */}
 }
 // Preserve the pre-studio lookup so a surface this helper cannot see is not regressed.
 await page.getByRole('button',{name,exact:true}).first().click();
}


test('task14 purged output cannot return on reload or scope change',async({page})=>{
 const {requests}=await fixture(page,{initial:true});
 await gotoPage(page,`/fixture?route=/app/discussions/s/${threadId}`);
 await page.getByRole('button',{name:'Prepare and save output'}).click();
 await page.getByRole('button',{name:'Open saved output'}).click();
 await expect(page.getByText('Synthetic saved setup',{exact:true})).toBeVisible();
 const writes=requests.filter(r=>r.method==='POST').length;
 await page.route('**/sales-outputs/**',route=>route.fulfill({json:{data:{
  id:'d3000000-0000-4000-8000-000000000001',revision:1,visibility:'thread',kind:'project_setup',
  availability:'unavailable',content:null,citations:[],dependencies:[],native_refs:[]},data_mode:'live',request_id:'task14'}}));
 await reloadPage(page);
 await expect(page.getByText('Synthetic saved setup',{exact:true})).toHaveCount(0);
 await gotoPage(page,`/fixture?route=/app/discussions/s/${threadId}`);
 await page.getByLabel('Fixture project').selectOption('project-b');await openGuided(page);
 await expect(page.getByText('Synthetic saved setup',{exact:true})).toHaveCount(0);
 expect(requests.filter(r=>r.method==='POST')).toHaveLength(writes);
});

test('task14 signout clears saved content and durable client storage',async({page})=>{
 await fixture(page,{initial:true});
 await gotoPage(page,`/fixture?route=/app/discussions/s/${threadId}`);
 await page.getByRole('button',{name:'Prepare and save output'}).click();
 await expect(page.getByText('Synthetic saved setup',{exact:true})).toBeVisible();
 await page.evaluate(()=>{
  (window as unknown as {fixtureSession:{setToken:(token:undefined)=>void}}).fixtureSession.setToken(undefined);
 });
 await expect(page.getByText('Synthetic saved setup',{exact:true})).toHaveCount(0);
 await expect(page.getByLabel('Saved messages')).toHaveCount(0);
 expect(await page.evaluate(()=>Object.values(localStorage).join(' '))).not.toContain('Synthetic saved setup');
});
test.beforeEach(async({page})=>{page.on('dialog',d=>void d.accept());});
// Owner assertions finish before teardown cancels outstanding background reads.
// Playwright otherwise reports disposed-context errors from those route callbacks.
test.afterEach(async({page})=>{await page.unrouteAll({behavior:'ignoreErrors'});});
const catalogue=JSON.parse(readFileSync('services/api/buyeros_api/sales/catalogue.json','utf8')).skills;
for(const skill of catalogue)test(`registered invocation ${skill.id}`,async({page})=>{
 const {requests}=await fixture(page),fresh=skill.id==='first-project';
 const message=fresh?'Synthetic first project: '+ 'Keep the complete initial task. '.repeat(5):'Synthetic requested work';
 await gotoPage(page,fresh?'/fixture?route=/app/discussions/new':`/fixture?route=/app/discussions/s/${threadId}`);
 await page.locator(`[data-skill="${skill.id}"]`).click();await page.getByRole('textbox',{name:'Describe your task'}).fill(message);
 await page.getByRole('button',{name:'Save task',exact:true}).click();await expect(page.getByLabel('Saved messages')).toBeVisible();
 expect(requests.find(r=>r.path.endsWith('/sales-tasks')&&r.method==='POST')?.body).toMatchObject({skill_id:skill.id,skill_version:'1',user_message:message,source_refs:[]});
 if(fresh){
  const creations=requests.filter(r=>r.path.endsWith('/conversation-threads')&&r.method==='POST');expect(creations).toHaveLength(1);
  expect(creations[0].body).toEqual({confirmed:true,template_id:'custom',title:message.slice(0,80),messages:[{text:message}],sources:[],runs:[]});
 }
});
test('catalogue offers every registered skill and typed request review',async({page})=>{
 page.on('pageerror',e=>console.log('PAGE ERROR',e.message));
 await page.route('**/v1/**',route=>{const path=new URL(route.request().url()).pathname;const data=path.endsWith('/sales/skills')?{skills:catalogue.map((s:object)=>({...s,inputs_schema:{properties:{}}}))}:path.endsWith('/conversation-threads')?{items:[],total:0,offset:0,limit:50}:{};return route.fulfill({json:{data,data_mode:'live',request_id:'synthetic'}});});
 await gotoPage(page,'/fixture?route=/app/discussions/new');
 await expect(page.getByRole('button',{name:'Prepare a meeting',exact:true})).toBeVisible();
 await expect(page.locator('[data-skill]')).toHaveCount(17);
 await page.getByLabel('Describe your task').fill('Prepare a meeting');
 await page.getByRole('button',{name:'Review task',exact:true}).click();
 await expect(page.getByLabel('Chosen skill')).toHaveValue('sales-prep');
});
test('saved output survives reload; follow-up is versioned and server messages are explicit',async({page})=>{
 const {requests}=await fixture(page);await gotoPage(page,`/fixture?route=/app/discussions/s/${threadId}`);
 await page.getByRole('textbox',{name:'Describe your task'}).fill('Set up');await page.getByLabel('Chosen skill').selectOption('first-project');await page.getByRole('button',{name:'Save task',exact:true}).click();
 await expect(page.getByText('Needs input',{exact:false}).first()).toBeVisible();
 await page.getByLabel('Offer Description',{exact:true}).fill('Sensors');await page.getByRole('textbox',{name:'Describe your task'}).fill('Use sensors');await page.getByRole('button',{name:'Save follow-up',exact:true}).click();
 await expect(page.getByText('Saved to discussion',{exact:false}).first()).toBeVisible();
 await page.getByRole('button',{name:'Prepare and save output',exact:true}).click();await expect(page.getByText('Synthetic saved setup',{exact:true})).toBeVisible();
 await reloadPage(page);await page.getByRole('button',{name:'Refresh task',exact:true}).click();await expect(page.getByText('Synthetic saved setup',{exact:true})).toBeVisible();
 const follow=requests.find(r=>r.path.endsWith('/followups'));expect(follow?.body?.arguments).toMatchObject({offer_description:'Sensors'});
 await page.getByRole('button',{name:'Open buyer',exact:true}).click();await expect(page.locator('#fixture-path')).toHaveText('/app/discover');
});
test('viewer cannot start, follow up, approve or prepare',async({page})=>{const {requests}=await fixture(page,{viewer:true,initial:true});await gotoPage(page,`/fixture?route=/app/discussions/s/${threadId}`);await expect(page.getByLabel('Saved messages')).toBeVisible();await expect(page.getByRole('button',{name:'Prepare and save output'})).toHaveCount(0);await expect(page.getByLabel('Describe your task')).toHaveCount(0);expect(requests.filter(r=>r.method==='POST')).toHaveLength(0);});
test('exact output route reload and entry-off recovery use reads only',async({page})=>{const {requests}=await fixture(page,{initial:true});await gotoPage(page,`/fixture?route=/app/discussions/s/${threadId}`);await page.getByRole('button',{name:'Prepare and save output'}).click();await page.getByRole('button',{name:'Open saved output'}).click();await expect(page.getByRole('heading',{name:'Documents',exact:true})).toBeVisible();await expect(page.getByText('Synthetic saved setup',{exact:true})).toBeVisible();const url=new URL(page.url());url.searchParams.set('flag','off');const before=requests.filter(r=>r.method==='POST').length;await gotoPage(page,url.href);await expect(page.getByText('Synthetic saved setup',{exact:true})).toBeVisible();expect(requests.filter(r=>r.method==='POST')).toHaveLength(before);await expect(page.getByRole('button',{name:'New discussion',exact:true})).toHaveCount(0);});
test('denied output announces policy error without rendering cached content',async({page})=>{await fixture(page,{denied:true});await gotoPage(page,'/fixture?route=/app/documents/d3000000-0000-4000-8000-000000000001/versions/1');await expect(page.getByRole('alert')).toHaveText('Policy does not allow this source or export.');await expect(page.getByText('Synthetic saved setup')).toHaveCount(0);});
test('native export link requires an explicit currently-authorized download',async({page})=>{await fixture(page);let downloads=0;await page.route('**/v1/**/exports/export-fixture**',route=>{if(route.request().url().endsWith('/content')){downloads++;return route.fulfill({contentType:'application/pdf',body:Buffer.from('%PDF-1.4\nsynthetic fixture\n')});}return route.fulfill({json:{data:{id:'export-fixture',status:'completed'},data_mode:'live',request_id:'synthetic'}});});await gotoPage(page,'/fixture?route=/app/documents&export=export-fixture&flag=off');await expect(page.getByRole('button',{name:'Open authorised export'})).toBeVisible();expect(downloads).toBe(0);const saved=page.waitForEvent('download');await page.getByRole('button',{name:'Open authorised export'}).click();expect((await saved).suggestedFilename()).toBe('report.pdf');expect(downloads).toBe(1);});
test('fresh discussion thread rejection never posts a sales task',async({page})=>{
 const {requests}=await fixture(page),threadPosts:unknown[]=[];
 await page.route('**/conversation-threads',async route=>{
  if(route.request().method()!=='POST')return route.fallback();
  threadPosts.push(route.request().postDataJSON());
  await route.fulfill({status:422,json:{code:'INVALID_REQUEST',message:'Synthetic thread rejection',retryable:false,request_id:'synthetic'}});
 });
 await gotoPage(page,'/fixture?route=/app/discussions/new');
 await page.locator('[data-skill="first-project"]').click();
 const message='Synthetic first project rejected before task creation';
 await page.getByRole('textbox',{name:'Describe your task'}).fill(message);
 const save=page.getByRole('button',{name:'Save task',exact:true});await save.click();
 await expect(page.getByRole('region',{name:'Guided sales',exact:true}).getByRole('alert')).toContainText('Outcome unknown');
 await expect(save).toBeEnabled(); // The request has settled and the action lock is released.
 expect(threadPosts).toEqual([{confirmed:true,template_id:'custom',title:message,messages:[{text:message}],sources:[],runs:[]}]);
 expect(requests.filter(r=>r.path.endsWith('/sales-tasks')&&r.method==='POST')).toHaveLength(0);
 await expect(page.getByLabel('Saved messages')).toHaveCount(0);
 await expect(page.getByRole('textbox',{name:'Describe your task'})).toHaveValue(message);
 await expect(page).toHaveURL(/route=\/app\/discussions\/new/);
});

test('uncertain task send retries the same mutation key',async({page})=>{await fixture(page);const keys:string[]=[];await page.route('**/sales-tasks',async route=>{if(route.request().method()!=='POST')return route.fallback();keys.push(route.request().headers()['idempotency-key']);if(keys.length===1)return route.abort('failed');return route.fallback();});await gotoPage(page,`/fixture?route=/app/discussions/s/${threadId}`);await page.locator('[data-skill="first-project"]').click();await page.getByRole('button',{name:'Save task',exact:true}).click();await expect(page.getByRole('alert').filter({hasText:'Outcome unknown'})).toBeVisible();await page.getByRole('button',{name:'Save task',exact:true}).click();await expect(page.getByLabel('Saved messages')).toBeVisible();expect(keys).toHaveLength(2);expect(keys[0]).toBe(keys[1]);});
test('dirty navigation can be cancelled and accepted without losing the scoped draft',async({page})=>{await fixture(page);page.removeAllListeners('dialog');await gotoPage(page,`/fixture?route=/app/discussions/s/${threadId}`);await page.getByRole('textbox',{name:'Describe your task'}).fill('Keep this draft');page.once('dialog',d=>void d.dismiss());await page.getByRole('button',{name:'Fixture home',exact:true}).click();await expect(page.locator('#fixture-path')).toHaveText(`/app/discussions/s/${threadId}`);page.once('dialog',d=>void d.accept());await page.getByRole('button',{name:'Fixture home',exact:true}).click();await openThread(page,'Synthetic discussion');await openGuided(page);await expect(page.getByRole('textbox',{name:'Describe your task'})).toHaveValue('Keep this draft');});
test('project change discards a delayed old-scope task response',async({page})=>{await fixture(page);let release!:()=>void,received!:()=>void;const held=new Promise<void>(r=>release=r),seen=new Promise<void>(r=>received=r);await page.route('**/sales-tasks',async route=>{if(route.request().method()!=='POST')return route.fallback();received();await held;await route.fulfill({json:{data:{id:'old-task',state:'completed'},data_mode:'live',request_id:'synthetic'}}).catch(()=>{});});await gotoPage(page,`/fixture?route=/app/discussions/s/${threadId}`);await page.locator('[data-skill="first-project"]').click();await page.getByRole('button',{name:'Save task',exact:true}).click();await seen;await page.getByLabel('Fixture project').selectOption('project-b');await openGuided(page);release();await expect(page.getByRole('textbox',{name:'Describe your task'})).toHaveValue('');await expect(page.getByLabel('Saved messages')).toHaveCount(0);});
test('formal recipient is explicitly chosen from current eligible native contacts',async({page})=>{
 const {requests}=await fixture(page);const output={id:'d3000000-0000-4000-8000-000000000001',revision:2,kind:'outreach_preparation',visibility:'thread',availability:'available',content:{summary:'Synthetic authored preparation',messages:[],unknowns:[]},native_refs:[],dependencies:[],citations:[{id:threadId,version:1,kind:'buyer',locator:'buyer:'+threadId,retention_class:'durable'}]};let formal:Record<string,unknown>|null=null;
 await page.route('**/v1/**',async route=>{const p=new URL(route.request().url()).pathname;let data:unknown;
 if(p.includes('/sales-outputs/')){if(p.endsWith('/formal-draft')){formal=route.request().postDataJSON();data={surface:'draft',id:threadId,revision:1};}else if(p.endsWith('/permissions'))data={can_edit:true};else if(p.endsWith('/versions'))data={outputs:[output],next_revision:null};else data=output;}
 else if(p.includes('/buyers/'))data=p.endsWith('/evidence')?{items:[],total:0,offset:0,limit:100}:{contacts:[{id:'eligible',value:'buyer@example.test',access_state:'visible',validity:'provider_marked_valid',checked_at:'2026-11-05T00:00:00Z',retention_until:'2099-01-01T00:00:00Z'},{id:'hidden',value:'hidden@example.test',access_state:'redacted',validity:'provider_marked_valid'}]};
 else if(p.endsWith('/icp-versions'))data={items:[],total:0,offset:0,limit:100};else if(/\/projects\/[^/]+$/.test(p))data={sender_identity:{display_name:'Synthetic sender'}};else return route.fallback();return route.fulfill({json:{data,data_mode:'live',request_id:'synthetic'}});});
 await gotoPage(page,`/fixture?route=/app/documents/${output.id}/versions/2`);await page.getByRole('button',{name:'Review eligible recipients'}).click();await expect(page.getByRole('button',{name:'Create formal draft',exact:true})).toBeDisabled();await expect(page.getByRole('option',{name:'hidden@example.test'})).toHaveCount(0);await page.getByRole('combobox',{name:'Eligible recipient'}).selectOption('eligible');expect(formal).toBeNull();await page.getByRole('button',{name:'Create formal draft',exact:true}).click();await expect(page.locator('#fixture-path')).toHaveText('/app/outreach');expect(formal).toEqual({recipient_id:'eligible',expected_revision:2});expect(requests.some(r=>r.path.includes('/send'))).toBe(false);
});
test('search and detail have separate approvals; only checked fields apply',async({page})=>{
 await fixture(page);const calls:{path:string;body:Record<string,unknown>|null}[]=[];let detail=false;
 await page.route('**/v1/**/xverum/**',async route=>{const p=new URL(route.request().url()).pathname,b=route.request().postData()?route.request().postDataJSON():null;calls.push({path:p,body:b});let data:unknown={};
 if(p.endsWith('/stages'))data={items:detail?[{stage:'detail',search_receipt_id:'search-receipt',receipt:{id:'detail-receipt',version:1,dispatch_state:'settled',credits_used:4,held_credits:0,request_id:'synthetic',projection_digest:'b'.repeat(64)}}]:[]};
 else if(p.endsWith('/connections'))data={connections:[{id:'connection',status:'connected',account_ref:'Synthetic account',version:1,generation:1,project_ids:[],tariff_version:'fixture'}]};
 else if(p.endsWith('/quotes')){detail=b.stage==='detail';data={id:'quote',stage:b.stage,buyer_id:threadId,connection_id:'connection',actor_id:threadId,connection_generation:1,query:b.query,provider_ids:detail?['1']:[],tool_plan:[{tool:detail?'enrich_company_xverum':'search_company_xverum',arguments:detail?{company_id:'1'}:{query:'Synthetic',limit:5}}],max_credits:detail?4:5,tariff_version:'fixture',expires_at:'2099-01-01T00:00:00Z',fingerprint:'a'.repeat(64)};}
 else if(p.endsWith('/approve'))data={id:detail?'detail-receipt':'search-receipt',dispatch_state:'queued',task_id:threadId,native_operation_id:null,reservation_ids:['hold']};
 else if(p.endsWith('/candidates'))data={result_type:'company',results:[{id:'1',company_name:'Synthetic buyer',website:'https://synthetic.example'}],total_count:1,page:1,page_size:5};
 else if(p.endsWith('/enrichment-proposals'))data={id:'proposal',buyer_id:threadId,buyer_version:1,identity_match:'resolved',fields:['industry','location'].map(field=>({field,existing_value:null,proposed_value:field==='industry'?'Manufacturing':'HK',status:'proposed',source_refs:[],retrieved_at:'2026-11-05T00:00:00Z',provider_freshness:null})),source_refs:[]};
 else if(p.endsWith('/apply'))data={surface:'buyer',id:threadId,revision:2};
 else data={id:detail?'detail-receipt':'search-receipt',version:1,dispatch_state:'settled',credits_used:detail?4:5,held_credits:0,request_id:'synthetic',projection_digest:'b'.repeat(64)};
 return route.fulfill({json:{data,data_mode:'live',request_id:'synthetic'}});});
 await gotoPage(page,`/fixture?route=/app/discussions/s/${threadId}`);await page.locator('[data-skill="sales-contacts"]').click();await page.getByLabel('Buyer',{exact:true}).fill(threadId);await page.getByRole('button',{name:'Save task',exact:true}).click();await page.getByRole('combobox',{name:'Connection',exact:true}).selectOption('connection');await page.getByLabel('Search',{exact:true}).fill('Synthetic');await page.getByRole('button',{name:'Review search cost'}).click();expect(calls.filter(c=>c.path.endsWith('/approve'))).toHaveLength(0);await page.getByRole('button',{name:'Approve quoted lookup'}).click();await page.getByRole('button',{name:'Check lookup'}).click();await page.getByRole('checkbox',{name:/Synthetic buyer/}).check();await page.getByRole('button',{name:'Review detail cost'}).click();expect(calls.filter(c=>c.path.endsWith('/approve'))).toHaveLength(1);await page.getByRole('button',{name:'Approve quoted lookup'}).click();await page.getByRole('button',{name:'Check lookup'}).click();await reloadPage(page);await page.getByRole('button',{name:'Resume detail',exact:true}).click();await page.getByRole('button',{name:'Check lookup'}).click();expect(calls.filter(c=>c.path.endsWith('/approve'))).toHaveLength(2);await page.getByRole('button',{name:'Review fields'}).click();await page.getByRole('checkbox',{name:/industry:/}).check();await page.getByRole('button',{name:'Save selected fields'}).click();expect(calls.find(c=>c.path.endsWith('/apply'))?.body?.selected_fields).toEqual(['industry']);
});
test('thread drafts remain separate, project switch clears them, unsafe authored text stays text',async({page})=>{
 await fixture(page);await gotoPage(page,`/fixture?route=/app/discussions/s/${threadId}`);await page.getByRole('textbox',{name:'Describe your task'}).fill('<img src=x onerror=alert(1)>');await page.getByRole('button',{name:'Fixture home',exact:true}).click();await openThread(page,'Second discussion');await openGuided(page);await expect(page.getByRole('textbox',{name:'Describe your task'})).toHaveValue('');await page.getByRole('textbox',{name:'Describe your task'}).fill('B');await page.getByRole('button',{name:'Fixture home',exact:true}).click();await openThread(page,'Synthetic discussion');await openGuided(page);await expect(page.getByRole('textbox',{name:'Describe your task'})).toHaveValue('<img src=x onerror=alert(1)>');expect(await page.locator('img[src=x]').count()).toBe(0);await page.getByLabel('Fixture project').selectOption('project-b');await openGuided(page);await expect(page.getByRole('textbox',{name:'Describe your task'})).toHaveValue('');
});
for(const width of [390,768,1440])test(`keyboard and layout at ${width}, both locales, 200 percent CSS zoom`,async({page})=>{await fixture(page);await page.setViewportSize({width,height:1000});await gotoPage(page,'/fixture');await page.getByRole('textbox',{name:'Describe your task'}).fill('Prepare a meeting');await page.getByRole('button',{name:'Review task',exact:true}).focus();await page.keyboard.press('Enter');await expect(page.getByLabel('Chosen skill')).toHaveValue('sales-prep');for(const zoom of [1,2]){await page.evaluate(z=>{document.body.style.zoom=String(z);},zoom);expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);await page.getByRole('button',{name:'Change language',exact:true}).click();}await page.screenshot({path:`.superpowers/sdd/2026-11-05-guided-sales-skills-xverum/task-13-evidence/width-${width}.png`,fullPage:true});});
test('actual Chromium tab zoom is 200 percent in both locales',async()=>{
 const root=resolve('dist/task13-zoom');await mkdir(root,{recursive:true});const extension=await mkdtemp(resolve(root,'extension-')),profile=await mkdtemp(resolve(root,'profile-'));
 let context:Awaited<ReturnType<typeof chromium.launchPersistentContext>>|undefined;
 try{await writeFile(resolve(extension,'manifest.json'),JSON.stringify({manifest_version:3,name:'Task13 isolated zoom',version:'1.0',permissions:['tabs'],host_permissions:['http://127.0.0.1:4397/*'],background:{service_worker:'background.js'}}));await writeFile(resolve(extension,'background.js'),'chrome.runtime.onInstalled.addListener(()=>{});');context=await chromium.launchPersistentContext(profile,{channel:'chromium',headless:true,viewport:{width:1440,height:1000},args:[`--disable-extensions-except=${extension}`,`--load-extension=${extension}`]});const page=context.pages()[0];await fixture(page);await gotoPage(page,'http://127.0.0.1:4397/fixture');const worker=context.serviceWorkers()[0]??await context.waitForEvent('serviceworker');
 const zoom=await worker.evaluate(async()=>{const api=(globalThis as unknown as {chrome:{tabs:{query:(q:object)=>Promise<{id:number;url:string}[]>;setZoom:(id:number,z:number)=>Promise<void>;getZoom:(id:number)=>Promise<number>}}}).chrome;const tab=(await api.tabs.query({})).find(t=>t.url.includes('/fixture'))!;await api.tabs.setZoom(tab.id,2);return api.tabs.getZoom(tab.id);});expect(zoom).toBe(2);await expect.poll(()=>page.evaluate(()=>innerWidth)).toBe(720);await openGuided(page);for(const locale of ['en','zh-HK']){if(locale==='zh-HK')await page.getByRole('button',{name:'Change language'}).click();await expect(page.getByRole('button',{name:locale==='en'?'Prepare a meeting':'準備會議',exact:true})).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(720);await page.screenshot({path:`.superpowers/sdd/2026-11-05-guided-sales-skills-xverum/task-13-evidence/actual-zoom-${locale}.png`,fullPage:true});}}
 finally{await context?.close();for(const dir of [extension,profile]){const rel=relative(root,dir);if(!rel||rel.startsWith('..'))throw Error('Unowned cleanup');await rm(dir,{recursive:true,force:true});}}
});


test('fix1 empty text preserves intake sources and chosen skill across remount',async({page})=>{
 await fixture(page,{initial:true});
 await page.route('**/sales-outputs?*',r=>r.fulfill({json:{data:{items:[{id:otherId,kind:'project_setup',revision:7,availability:'available'}]},data_mode:'live',request_id:'fixture'}}));
 await gotoPage(page,`/fixture?route=/app/discussions/s/${threadId}`);
 await page.getByLabel('Offer Description',{exact:true}).fill('Unsent field');
 await page.getByText('Selected sources',{exact:false}).first().click();
 await page.getByRole('checkbox',{name:'project setup · 7'}).check();
 await expect(page.getByLabel('Describe your task')).toHaveValue('');
 await page.getByRole('button',{name:'Fixture home',exact:true}).click();
 await openThread(page,'Synthetic discussion');await openGuided(page);
 await expect(page.getByLabel('Offer Description',{exact:true})).toHaveValue('Unsent field');
 await page.getByText('Selected sources',{exact:false}).first().click();
 await expect(page.getByRole('checkbox',{name:'project setup · 7'})).toBeChecked();
 await page.getByLabel('Chosen skill').selectOption('sales-prep');
 await page.getByLabel('Describe your task').fill('');
 await page.getByRole('button',{name:'Fixture home',exact:true}).click();
 await openThread(page,'Synthetic discussion');await openGuided(page);
 await expect(page.getByLabel('Chosen skill')).toHaveValue('sales-prep');
});

test('fix1 delayed task A guidance cannot appear under selected task B',async({page})=>{
 await fixture(page);
 const a={id:taskId,thread_id:threadId,skill_id:'sales-research',skill_version:'1',revision:1,state:'needs_input',output_ids:[],intake:[],arguments:{research_question:'A'},source_refs:[],missing_inputs:[],message_sequence:1};
 const b={...a,id:otherId,arguments:{research_question:'B'},message_sequence:2};
 let release!:()=>void;const held=new Promise<void>(r=>release=r);
 await page.route('**/sales-tasks**',async r=>{const p=new URL(r.request().url()).pathname;if(p.endsWith('/core-guidance')){await held;return r.fulfill({json:{data:{action:{operation_id:'startRun',idempotency_key:'A'},work:{},missing_inputs:[]},data_mode:'live',request_id:'fixture'}});}if(p.endsWith('/capability')||p.endsWith('/native-sources'))return r.fallback();return r.fulfill({json:{data:p.endsWith('/sales-tasks')?{items:[b,a]}:p.endsWith('/'+otherId)?b:a,data_mode:'live',request_id:'fixture'}});});
 await gotoPage(page,`/fixture?route=/app/discussions/s/${threadId}`);
 await page.getByRole('button',{name:'Review next action'}).click();
 await page.getByLabel('Saved tasks').selectOption(otherId);release();
 await expect(page.getByLabel('Research Question',{exact:true})).toHaveValue('B');
 await expect(page.getByRole('button',{name:'Review research cost'})).toHaveCount(0);
});

for(const language of ['en','zh-HK'])test(`fix1 full shell history ${language}`,async({page})=>{
 test.skip(process.env.TASK13_FULL_SHELL!=='1','Dedicated full-shell run');
 page.on('pageerror',e=>console.log('SHELL ERROR',e.stack));
 await fixture(page,{initial:true});
 await page.addInitScript(lang=>localStorage.setItem('buyeros.locale',lang),language);
 const ws='a1000000-0000-4000-8000-000000000001',pr='a2000000-0000-4000-8000-000000000001';
 await page.route('**/v1/**',async r=>{const u=new URL(r.request().url()),p=u.pathname;let data;
 if(p==='/v1/workspaces')data={items:[{id:ws,name:'Owned fixture workspace',roles:['workspace_admin']}],offset:0,limit:100,total:1};
 else if(p.endsWith('/projects'))data={items:[{id:pr,name:'Owned fixture project',status:'active'}],offset:0,limit:100,total:1};
 else if(p.endsWith('/preferences'))data={locale:language,version:1};
 else return r.fallback();return r.fulfill({json:{data,data_mode:'live',request_id:'shell-fixture'}});});
 const label=(en:string,zh:string)=>language==='en'?en:zh;
 await gotoPage(page,`/app/discussions/s/${threadId}?workspace=${ws}&project=${pr}`);
 await page.getByRole('button',{name:label('Prepare and save output','準備並儲存成果'),exact:true}).click();
 await page.getByRole('button',{name:label('Open saved output','開啟已儲存成果'),exact:true}).click();
 await expect(page).toHaveURL(/app\/documents\//);
 expect(new URL(page.url()).searchParams.get('project')).toBe(pr);
 await page.goBack();await openGuided(page);
 await page.getByLabel(label('Offer Description','產品或服務描述'),{exact:true}).fill('Dirty intake only');
 page.removeAllListeners('dialog');let dialogs=0;
 page.on('dialog',async d=>{await d.dismiss();dialogs++;});
 await page.goForward({timeout:2000}).catch(()=>null);await openGuided(page);
 await expect.poll(()=>dialogs).toBe(1);
 await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
 await expect(page).toHaveURL(new RegExp('/app/discussions/s/'+threadId));
 await expect(page.getByLabel(label('Offer Description','產品或服務描述'),{exact:true})).toHaveValue('Dirty intake only');
 page.removeAllListeners('dialog');page.on('dialog',async d=>{await d.accept();});
 await page.goForward({timeout:2000}).catch(()=>null);await openGuided(page);await expect(page).toHaveURL(/app\/documents\//);
 await page.goBack();await openGuided(page);
 await expect(page.getByLabel(label('Offer Description','產品或服務描述'),{exact:true})).toHaveValue('Dirty intake only');
 // Native route -> actual shell discussion navigation creates a second history entry.
 await page.getByRole('button',{name:label('Open saved output','開啟已儲存成果'),exact:true}).click();
 await page.getByRole('button',{name:label('New discussion','新增討論'),exact:true}).click();
 await openThread(page,'Synthetic discussion');await openGuided(page);
 await expect(page.getByLabel(label('Offer Description','產品或服務描述'),{exact:true})).toHaveValue('Dirty intake only');
 page.removeAllListeners('dialog');page.on('dialog',d=>void d.dismiss());
 await page.goBack({timeout:2000}).catch(()=>null);await openGuided(page);
 await expect(page.getByLabel(label('Offer Description','產品或服務描述'),{exact:true})).toHaveValue('Dirty intake only');
 page.removeAllListeners('dialog');page.on('dialog',d=>void d.accept());
 await page.goBack({timeout:2000}).catch(()=>null);await openGuided(page);await expect(page).toHaveURL(/app\/documents\//);
 expect(new URL(page.url()).searchParams.get('workspace')).toBe(ws);expect(new URL(page.url()).searchParams.get('project')).toBe(pr);
});


test('fix1 owned qualification existing run and uncertain native admission',async({page,request})=>{
 test.skip(!process.env.TASK13_OWNED_CONFIG,'Strict owned API bridge only');test.setTimeout(90000);
 const cfg=JSON.parse(readFileSync(process.env.TASK13_OWNED_CONFIG!,'utf8'));
 const posted:{body:unknown;key:string}[]=[];let lose=true;
 await page.route('**/v1/**',async route=>{
  const req=route.request(),u=new URL(req.url());
  const response=await request.fetch(cfg.url+u.pathname+u.search,{method:req.method(),headers:req.headers(),data:req.postData()??undefined});
  if(req.method()==='POST'&&u.pathname.endsWith('/projects/'+cfg.project+'/runs')){posted.push({body:req.postDataJSON(),key:req.headers()['idempotency-key']});if(lose&&response.status()===202){lose=false;return route.abort('failed');}}
  await route.fulfill({response});
 });
 const open=async()=>{await page.goto(`/fixture?route=/app/discussions/s/${cfg.thread}&workspace=${cfg.workspace}&project=${cfg.project}`);await openGuided(page);};
 if(process.env.TASK13_OWNED_PHASE!=='retry'){
 await open();
 await page.locator('[data-skill="sales-qualify"]').click();
 await page.getByText('Selected sources',{exact:false}).first().click();
 await page.getByRole('checkbox',{name:'buyer '+cfg.buyer.slice(0,8),exact:true}).check();
 await page.getByRole('checkbox',{name:'profile '+cfg.profile.slice(0,8),exact:true}).check();
 await expect(page.getByLabel('Buyer',{exact:true})).toHaveValue(cfg.buyer);await expect(page.getByLabel('Profile',{exact:true})).toHaveValue(cfg.profile);await expect(page.getByLabel('Profile Version',{exact:true})).toHaveValue('1');
 await page.getByRole('button',{name:'Save task',exact:true}).click();
 await page.getByRole('button',{name:'Prepare and save output'}).click();
 await expect(page.getByRole('button',{name:'Open saved output'})).toBeVisible();
 await page.locator('[data-skill="sales-research"]').click();
 await page.getByLabel('Research Question',{exact:true}).fill('Current reviewed evidence');
 await page.getByRole('checkbox',{name:'run '+cfg.run.slice(0,8),exact:true}).check();
 await page.getByRole('button',{name:'Save task',exact:true}).click();
 await page.getByRole('button',{name:'Prepare and save output'}).click();
 await expect(page.getByRole('button',{name:'Open saved output'})).toBeVisible();
 // Stale selected source and permission denial reach real native authority.
 await request.post(cfg.url+'/fixture-control',{data:{stale:true}});
 await page.locator('[data-skill="sales-qualify"]').click();
 await page.getByLabel('Buyer',{exact:true}).fill(cfg.buyer);await page.getByLabel('Profile',{exact:true}).fill(cfg.profile);await page.getByLabel('Profile Version',{exact:true}).fill('1');
 await page.getByRole('button',{name:'Save task',exact:true}).click();
 await expect(page.getByRole('alert').filter({hasText:/changed|unknown|unavailable/i}).first()).toBeVisible();
 await request.post(cfg.url+'/fixture-control',{data:{deny:true}});
 const denied=await request.get(cfg.url+`/v1/workspaces/${cfg.workspace}/projects/${cfg.project}/sales-tasks/native-sources`);expect([403,404]).toContain(denied.status());
 await reloadPage(page);
 await expect(page.getByRole('checkbox',{name:'buyer '+cfg.buyer.slice(0,8),exact:true})).toHaveCount(0);
 return;
 }
 // A new explicit research task has no selected completed run.
 await open();await page.locator('[data-skill="sales-research"]').click();await page.getByLabel('Research Question',{exact:true}).fill('Explicit new native research');
 await page.getByText('Selected sources',{exact:false}).first().click();
 const checked=page.locator('input[type=checkbox]:checked');while(await checked.count()){const count=await checked.count();await checked.first().click();await expect(checked).toHaveCount(count-1);}
 await page.getByRole('button',{name:'Save task',exact:true}).click();
 await page.getByRole('button',{name:'Review next action'}).click();await page.getByRole('button',{name:'Review research cost'}).click();
 await page.getByRole('button',{name:'Confirm and start research',exact:true}).click();
 await expect(page.getByRole('alert').filter({hasText:'Outcome unknown'})).toBeVisible();
 await page.getByRole('button',{name:'Fixture home',exact:true}).click();await openThread(page,'Synthetic note');await openGuided(page);
 await page.getByRole('button',{name:'Review next action'}).click();
 await page.getByRole('button',{name:'Retry same research request',exact:true}).click();
 await expect(page.getByRole('alert').filter({hasText:'Research run saved to discussion'})).toBeVisible();
 expect(lose).toBe(false);expect(posted).toHaveLength(2);expect(posted[0]).toEqual(posted[1]);
 const thread=await request.get(cfg.url+`/v1/workspaces/${cfg.workspace}/projects/${cfg.project}/conversation-threads/${cfg.thread}`);
 expect((await thread.json()).data.runs).toHaveLength(1);
 await request.post(cfg.url+'/fixture-control',{data:{deny:true}});
 const denied=await request.get(cfg.url+`/v1/workspaces/${cfg.workspace}/projects/${cfg.project}/sales-tasks/native-sources`);expect([403,404]).toContain(denied.status());
 await reloadPage(page);
 await expect(page.getByRole('checkbox',{name:'buyer '+cfg.buyer.slice(0,8),exact:true})).toHaveCount(0);
});


test('fix1 contact quote from A cannot be approved after choosing B',async({page})=>{
 await fixture(page);let approvals=0;
 const a={id:taskId,thread_id:threadId,skill_id:'sales-contacts',skill_version:'1',revision:1,state:'ready_for_review',output_ids:[],intake:[],arguments:{buyer_id:threadId},source_refs:[],missing_inputs:[],message_sequence:1},b={...a,id:otherId,arguments:{buyer_id:otherId},message_sequence:2};
 let release!:()=>void;const held=new Promise<void>(r=>release=r);
 await page.route('**/v1/**',async r=>{const p=new URL(r.request().url()).pathname;let data;
 if(p.endsWith('/sales-tasks'))data={items:[b,a]};
 else if(p.endsWith('/sales-tasks/'+otherId))data=b;
 else if(p.endsWith('/sales-tasks/'+taskId))data=a;
 else if(p.endsWith('/xverum/connections'))data={connections:[{id:'connection',version:1,status:'connected',assigned:true,account_ref:'Synthetic',generation:1}]};
 else if(p.endsWith('/stages'))data={items:[]};
 else if(p.endsWith('/quotes')){await held;data={id:'quote-A',stage:'search',max_credits:5,expires_at:'2027-01-01',tool_plan:{},fingerprint:'a'.repeat(64)};}
 else if(p.endsWith('/approve')){approvals++;data={id:'receipt-A'};}
 else return r.fallback();return r.fulfill({json:{data,data_mode:'live',request_id:'fixture'}});
 });
 await gotoPage(page,`/fixture?route=/app/discussions/s/${threadId}`);
 await page.getByRole('combobox',{name:'Connection',exact:true}).selectOption('connection');await page.getByLabel('Search',{exact:true}).fill('A');
 await page.getByRole('button',{name:'Review search cost'}).click();
 await page.getByLabel('Saved tasks').selectOption(otherId);release();
 await expect(page.getByLabel('Buyer',{exact:true})).toHaveValue(otherId);
 await expect(page.getByRole('button',{name:'Approve quoted lookup'})).toHaveCount(0);
 await expect(page.getByRole('button',{name:'Save selected fields'})).toHaveCount(0);expect(approvals).toBe(0);
});

for(const language of ['en','zh-HK'])test(`fix1 owned capability recovery ${language}`,async({page,request})=>{
 test.skip(!process.env.TASK13_OWNED_CONFIG||process.env.TASK13_FULL_SHELL!=='1','Owned full shell only');
 const cfg=JSON.parse(readFileSync(process.env.TASK13_OWNED_CONFIG!,'utf8'));
 await page.addInitScript(lang=>localStorage.setItem('buyeros.locale',lang),language);
 await page.route('**/v1/**',async route=>{const req=route.request(),u=new URL(req.url());const response=await request.fetch(cfg.url+u.pathname+u.search,{method:req.method(),headers:req.headers(),data:req.postData()??undefined});await route.fulfill({response});});
 const base=`workspace=${cfg.workspace}&project=${cfg.project}`;
 const newDiscussion=language==='en'?'New discussion':'新增討論';
 for(const mode of ['server','workspace']){
  await request.post(cfg.url+'/fixture-control',{data:{deny:false,enabled:mode==='workspace',opted:mode==='server'}});
  await gotoPage(page,`/app/documents/${cfg.output}/versions/1?${base}`);
  await expect(page.getByRole('button',{name:newDiscussion,exact:true})).toHaveCount(0);
  await expect(page.getByLabel(language==='en'?'Workspace':'工作區',{exact:true})).toBeVisible();
  await expect(page.locator('.sales-output')).toBeVisible();
  await gotoPage(page,`/app/discover/${cfg.run}?${base}`);
  await page.locator('summary').filter({hasText:language==='en'?'Linked outputs':'相關成果'}).click();
  await page.getByRole('button',{name:cfg.outputKind.replaceAll('_',' ')+' · 1',exact:true}).click();
  await expect(page.locator('.sales-output')).toBeVisible();
  await expect(page).toHaveURL(new RegExp('/app/documents/'+cfg.output+'/versions/1'));
  await expect(page.getByRole('button',{name:language==='en'?'New discussion with this output':'以此成果開始新討論',exact:true})).toHaveCount(0);
  expect(new URL(page.url()).searchParams.get('project')).toBe(cfg.project);
 }
 await request.post(cfg.url+'/fixture-control',{data:{enabled:true,opted:true}});
});


test('fix1 delayed A field proposal cannot apply from B',async({page})=>{
 await fixture(page);let applies=0;
 const a={id:taskId,thread_id:threadId,skill_id:'sales-contacts',skill_version:'1',revision:1,state:'ready_for_review',output_ids:[],intake:[],arguments:{buyer_id:threadId},source_refs:[],missing_inputs:[],message_sequence:1},b={...a,id:otherId,arguments:{buyer_id:otherId},message_sequence:2};
 let release!:()=>void;const held=new Promise<void>(r=>release=r);
 await page.route('**/v1/**',async r=>{const p=new URL(r.request().url()).pathname;let data;
 if(p.endsWith('/sales-tasks'))data={items:[b,a]};
 else if(p.endsWith('/sales-tasks/'+otherId))data=b;
 else if(p.endsWith('/sales-tasks/'+taskId))data=a;
 else if(p.endsWith('/xverum/connections'))data={connections:[]};
 else if(p.endsWith('/stages'))data={items:p.includes(taskId)?[{stage:'detail',search_receipt_id:'search-A',receipt:{id:'detail-A',version:1,dispatch_state:'settled',held_credits:0,credits_used:4}}]:[]};
 else if(p.endsWith('/enrichment-proposals')){await held;data={id:'proposal-A',buyer_version:1,identity_match:'resolved',fields:[{field:'industry',existing_value:null,proposed_value:'Sensors',status:'proposed'}]};}
 else if(p.endsWith('/apply')){applies++;data={};}
 else return r.fallback();return r.fulfill({json:{data,data_mode:'live',request_id:'fixture'}});
 });
 await gotoPage(page,`/fixture?route=/app/discussions/s/${threadId}`);await page.getByRole('button',{name:'Resume detail'}).click();await page.getByRole('button',{name:'Review fields'}).click();
 await page.getByLabel('Saved tasks').selectOption(otherId);release();
 await expect(page.getByLabel('Buyer',{exact:true})).toHaveValue(otherId);await expect(page.getByRole('button',{name:'Save selected fields'})).toHaveCount(0);expect(applies).toBe(0);
});


for(const phase of ['native','people'])test('final owned '+phase,async({page,request})=>{
 test.skip(!process.env.FINAL_OWNED_CONFIG,'Strict owned API bridge only');test.setTimeout(180000);
 const cfg=JSON.parse(readFileSync(process.env.FINAL_OWNED_CONFIG!,'utf8'));
 test.skip(cfg.phase!==phase,'Other owned phase');
 const applies:{url:string;headers:Record<string,string>;body:unknown;result:unknown}[]=[];
 await page.route('**/v1/**',async route=>{
  const req=route.request(),u=new URL(req.url());
  const response=await request.fetch(cfg.url+u.pathname+u.search,{method:req.method(),headers:req.headers(),data:req.postData()??undefined});
  if(req.method()==='POST'&&(u.pathname.endsWith('/apply')||u.pathname.endsWith('/native-actions'))&&response.status()===200)
   applies.push({url:cfg.url+u.pathname,headers:req.headers(),body:req.postDataJSON(),result:(await response.json()).data});
  await route.fulfill({response});
 });
 const base=`workspace=${cfg.workspace}&project=${cfg.project}`;
 if(phase==='native'){
  await gotoPage(page,`/fixture?route=/app/documents/${cfg.output}/versions/1&${base}`);
  await page.locator('summary').filter({hasText:'Save to buyer'}).click();
  await page.getByRole('combobox',{name:/^Buyer/}).selectOption(cfg.buyer);
  await page.getByLabel('Buyer note',{exact:true}).fill('Browser reviewed buyer note');
  await page.getByRole('checkbox',{name:'Selected changes will be visible to the project.'}).check();
  await page.getByRole('button',{name:'Save to buyer',exact:true}).click();
  await expect.poll(()=>applies.length,{timeout:45000}).toBe(1);
  const payload=applies[0].body as {source_versions:{kind:string;id:string;version:number}[]};
  expect(payload.source_versions).toContainEqual({id:cfg.output,version:1,kind:'output',locator:'output:'+cfg.output,retention_class:'durable'});
 }else{
  await gotoPage(page,`/fixture?route=/app/discussions/s/${cfg.thread}&${base}`);
  await page.getByRole('button',{name:'Resume detail',exact:true}).click();
  for(let i=1;i<=cfg.count;i++){
   if(i<cfg.count)await page.getByRole('combobox',{name:/^Person/}).selectOption(String(i));
   await page.getByRole('button',{name:'Review fields',exact:true}).click();
   await page.getByRole('checkbox',{name:/^person name:/i}).check();
   await page.getByRole('checkbox',{name:/^job title:/i}).check();
   await page.getByRole('checkbox',{name:/^business email:/i}).check();
   await page.getByRole('button',{name:'Save selected fields',exact:true}).click();
   await expect.poll(()=>applies.length,{timeout:45000}).toBe(i);
  }
 }
 for(const saved of applies){
  const replay=await request.post(saved.url,{headers:saved.headers,data:saved.body});
  expect(replay.status(),await replay.text()).toBe(200);expect((await replay.json()).data).toEqual(saved.result);
 }
});
