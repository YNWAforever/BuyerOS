import {writeFileSync} from 'node:fs';
import {expect,test,type Page} from '@playwright/test';
import {signInWorkbench,workspace,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';
const project='e9100000-0000-4000-8000-000000000001',run='e9400000-0000-4000-8000-000000000001';
const raw='c6100000-0000-4000-8000-000000000019',company='c6100000-0000-4000-8000-000000000020',source='c6100000-0000-4000-8000-000000000021';
const entry=`/app/discover/${run}?workspace=${workspace}&project=${project}`;
const saved={buyer_id:'c6100000-0000-4000-8000-000000000022',evidence_id:'c6100000-0000-4000-8000-000000000023',alias_id:'c6100000-0000-4000-8000-000000000024',entity_status:'reviewed',fit_status:'needs_review'};
async function fixture(page:Page,lost=false){
 const posts:{key:string|undefined;body:unknown}[]=[];const context={run_id:run,project_id:project,raw_candidate_id:raw,company:{id:company,legal_name:'Independent Sensors Limited',domain:'sensors.example.test',hash:'a'.repeat(64)},page:{id:source,digest:'b'.repeat(64),excerpt:'Independent Sensors Limited manufactures sensor parts. Buyer role is unverified.',url:'https://sensors.example.test/about',retention_until:new Date(Date.now()+3600_000).toISOString()},entity_status:'needs_review',fit_status:'needs_review'};
 const envelope=(data:unknown)=>({data,request_id:'synthetic-candidate-ui',data_mode:'live'});
 await page.route(`**/v1/workspaces/${workspace}/runs/${run}/candidates**`,async route=>{
   const path=new URL(route.request().url()).pathname;
   if(path.endsWith('/review-context'))return route.fulfill({json:envelope(context)});
   if(path.endsWith('/review')){posts.push({key:route.request().headers()['idempotency-key'],body:route.request().postDataJSON()});if(lost&&posts.length===1)return route.abort('failed');return route.fulfill({json:envelope(saved)});}
   return route.fulfill({json:envelope({items:[{raw_candidate_id:raw,mapping_status:'unmapped',company_id:null,source_status:'page_available',page_source_id:source,title:'Search metadata about sensor catalog',source_url:context.page.url}],offset:0,limit:20,total:1})});
 });
 await page.route(`**/v1/workspaces/${workspace}/projects/${project}/buyer-snapshots`,route=>route.fulfill({json:envelope({id:'c6100000-0000-4000-8000-000000000025',total:1,expires_at:context.page.retention_until,result_limit_reached:false})}));
 await page.route(`**/v1/workspaces/${workspace}/projects/${project}/buyers?**`,route=>route.fulfill({json:envelope({items:[{id:saved.buyer_id,company_id:company,name:context.company.legal_name,normalized_domain:context.company.domain}],offset:0,limit:20,total:1})}));
 return {posts,context};
}
async function open(page:Page,actor:'reviewer'|'viewer'='reviewer'){
 await resetWorkbenchFixtureRateWindows();await signInWorkbench(page,false,actor,entry);
 await expect(page.getByRole('combobox',{name:/^(Project|專案)$/})).toHaveValue(project);
 await page.getByRole('combobox',{name:/^(Language|語言)$/}).selectOption('en');
 await expect(page.getByRole('heading',{name:'Candidate observations',exact:true})).toBeVisible();
}
async function choose(page:Page){
 await page.getByRole('button',{name:'Review candidate',exact:true}).click();
 await page.getByRole('button',{name:'Find existing companies',exact:true}).click();
 await page.getByLabel('Existing company', {exact:true}).selectOption(company);
 await page.getByRole('button',{name:'Load current source',exact:true}).click();
 await expect(page.getByLabel('Exact page quote',{exact:true})).toHaveValue(/Independent Sensors Limited/);
 await page.getByLabel('Entity review reason').fill('Explicit independent company and page review');
}
test('C61 candidate review shows metadata/current source and keeps inference at mobile and zoom',async({page})=>{
 await fixture(page);await open(page);await expect(page.getByText('Search metadata', {exact:true})).toBeVisible();await choose(page);
 await page.getByRole('checkbox',{name:'I selected this existing company and checked the exact page quote.'}).check();
 const submit=page.getByRole('button',{name:'Save entity review',exact:true});await submit.focus();await page.keyboard.press('Enter');
 await expect(page.getByText('Entity review saved. Fit and buyer role still need separate evidence.',{exact:true})).toBeVisible();
 await page.getByRole('combobox',{name:'Language'}).selectOption('zh-HK');await expect(page.getByRole('heading',{name:'候選觀察',exact:true})).toBeVisible();
 await page.setViewportSize({width:390,height:844});await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.locator('body').evaluate(body=>{body.style.zoom='2';});
 const overflow=await page.evaluate(()=>({viewport:innerWidth,scroll:document.documentElement.scrollWidth,items:[...document.querySelectorAll('*')].map(el=>({tag:el.tagName,id:el.id,classes:el.className,text:(el.textContent??'').slice(0,80),right:el.getBoundingClientRect().right,width:el.getBoundingClientRect().width})).filter(el=>el.right>innerWidth+1).slice(-40)}));
 writeFileSync('test-results/c61-candidate-zoom-diagnostic.json',JSON.stringify(overflow,null,2));
 await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:'test-results/c61-candidate-mobile-zhHK-zoom.png',fullPage:true});
});
test('C61 lost entity review ack retains dirty quote/reason and same key across route remount',async({page})=>{
 const f=await fixture(page,true);await open(page);await choose(page);await page.getByLabel('Exact page quote',{exact:true}).fill('Independent Sensors Limited manufactures sensor parts.');
 await page.getByRole('checkbox',{name:'I selected this existing company and checked the exact page quote.'}).check();
 const submit=page.getByRole('button',{name:'Save entity review',exact:true});await submit.evaluate(b=>{(b as HTMLButtonElement).click();(b as HTMLButtonElement).click();});
 await expect(page.getByRole('button',{name:'Retry same entity review',exact:true})).toBeVisible();expect(f.posts).toHaveLength(1);
 await page.getByRole('button',{name:'Operations',exact:true}).click();await page.getByRole('button',{name:'Research runs',exact:true}).click();
 await expect(page.locator('.run-list li')).toHaveCount(10);
 if(await page.locator(`[data-run-id="${run}"]`).count()===0)await page.getByRole('button',{name:'Next',exact:true}).click();
 await page.locator(`[data-run-id="${run}"]`).click();
 await expect(page.getByRole('heading',{name:'Candidate observations',exact:true})).toBeVisible();await page.getByRole('button',{name:'Review candidate',exact:true}).click();
 await expect(page.getByLabel('Exact page quote',{exact:true})).toHaveValue('Independent Sensors Limited manufactures sensor parts.');await expect(page.getByLabel('Entity review reason')).toHaveValue('Explicit independent company and page review');
 expect(f.posts).toHaveLength(1);await page.getByRole('button',{name:'Retry same entity review',exact:true}).click();await expect.poll(()=>f.posts.length).toBe(2);
 expect(f.posts[1]).toEqual(f.posts[0]);await expect(page.getByText('Entity review saved. Fit and buyer role still need separate evidence.',{exact:true})).toBeVisible();
});
test('C61 viewer can browse observations but cannot attest an entity mapping',async({page})=>{
 const f=await fixture(page);await open(page,'viewer');await expect(page.getByRole('button',{name:'Review candidate',exact:true})).toHaveCount(0);expect(f.posts).toHaveLength(0);
 await expect(page.getByText('A reviewer must verify the existing company and source.',{exact:true})).toBeVisible();
});
