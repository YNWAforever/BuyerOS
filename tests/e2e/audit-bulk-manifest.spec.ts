import {expect,test,type Page} from '@playwright/test';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {resolve} from 'node:path';
import {writeFileSync} from 'node:fs';
import {signInWorkbench,workspace,project,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';
const root=`/v1/workspaces/${workspace}/projects/${project}/bulk-manifests`;
const prefix='Q08 Manifest Fixture';
async function fixture(command:string,...args:string[]):Promise<{fixture_only:boolean;count:number;ids:string[];buyers:{id:string;version:number;owner:string|null}[];manifests:{id:string;count:number;status:string;job_id:string|null}[];total:number}>{
 const cwd=resolve('services/worker'),python=resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
 const value=JSON.parse((await promisify(execFile)(python,['tests/fixtures/audit_manifests.py',command,...args],{cwd,timeout:45_000})).stdout);expect(value.fixture_only).toBe(true);return value;
}
async function open(page:Page,actor:'access'|'reviewer'|'viewer'='access',entry?:string){
 await signInWorkbench(page,true,actor,entry);await page.getByRole('combobox',{name:/^(Language|語言)$/}).selectOption('en');await page.getByRole('button',{name:'Buyers',exact:true}).click();
 const buyers=page.getByRole('region',{name:'Buyer results',exact:true});
 await buyers.getByRole('textbox',{name:'Search buyers',exact:true}).fill(prefix);await buyers.getByRole('textbox',{name:'Search buyers',exact:true}).press('Enter');
 await expect(buyers.getByRole('checkbox',{name:/^Select /})).toHaveCount(12);
 return page.getByRole('region',{name:'Segmented maintenance',exact:true});
}
async function preview(page:Page,panel:ReturnType<Page['getByRole']>){
 await panel.getByRole('textbox',{name:'Maintenance reason',exact:true}).fill('Q08 human reviewed maintenance');
 const read=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname===root);
 await panel.getByRole('button',{name:'Preview segmented maintenance',exact:true}).click();const response=await read;expect(response.status()).toBe(201);
 const data=(await response.json()).data;await expect(panel.getByRole('region',{name:'Frozen manifest'})).toContainText(`count: ${data.count}`);return data as {id:string;count:number;digest:string;version:number};
}
async function execute(page:Page,panel:ReturnType<Page['getByRole']>,id:string){
 await panel.getByRole('checkbox',{name:'Confirm exact manifest'}).check();const response=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname===root+`/${id}/execute`);
 await panel.getByRole('button',{name:'Execute confirmed manifest'}).click();return await response;
}
test.beforeEach(async()=>{await resetWorkbenchFixtureRateWindows();});
for(const count of [100,101,1001])test(`B01 B14 ${count} actual rows require frozen preview and explicit execution`,async({page})=>{
 const seed=await fixture('seed',String(count)),panel=await open(page);
 await expect(panel.getByRole('button',{name:'Execute confirmed manifest'})).toHaveCount(0);
 if(count===1001)await expect(page.getByRole('region',{name:'Buyer results',exact:true})).toContainText(/clipped|1000/i);
 const manifest=await preview(page,panel);expect(manifest.count).toBe(count);expect((await fixture('inspect')).buyers.every(b=>b.version===1&&b.owner===null)).toBe(true);
 await expect(panel.getByRole('button',{name:'Execute confirmed manifest'})).toBeDisabled();const response=await execute(page,panel,manifest.id);expect(response.status()).toBe(count===100?200:202);const result=(await response.json()).data;
 if(count>100){const drain=await fixture('drain',result.id);expect(drain.total).toBe(count);const job=page.getByRole('region',{name:'Bulk job progress'});await job.getByRole('button',{name:'Refresh job'}).click();await expect(job).toContainText(`${count} of ${count}`);
  await job.getByRole('button',{name:'Show job results'}).click();await expect(job.locator('code')).toHaveCount(20);const seen:string[]=[];
  for(let offset=0;offset<count;offset+=20){await expect(job.getByText(`${offset+1}–${Math.min(offset+20,count)} / ${count}`,{exact:true})).toBeVisible();seen.push(...await job.locator('code').allTextContents());if(offset+20<count)await job.getByRole('button',{name:'Next job results'}).click();}
  expect(new Set(seen).size).toBe(count);expect(seen.sort()).toEqual(seed.ids.sort());
 }
 const state=await fixture('inspect');expect(state.buyers).toHaveLength(count);expect(state.buyers.every(b=>b.version===2&&b.owner!==null)).toBe(true);
 writeFileSync(`test-results/q08-ui-${count}.json`,JSON.stringify({fixture_only:true,manifest,result,state},null,2));await page.screenshot({path:`test-results/q08-en-${count}.png`,fullPage:true});
});
test('B15 lost preview and committed 202 retry one frozen body/key and restore after re-login',async({page})=>{
 await fixture('seed','101');const panel=await open(page);const previews:{key:string;body:unknown}[]=[],executions:{key:string;body:unknown}[]=[];
 await page.route(`**${root}`,async route=>{if(route.request().method()!=='POST')return route.continue();previews.push({key:route.request().headers()['idempotency-key'],body:route.request().postDataJSON()});const response=await route.fetch();if(previews.length===1)return route.abort('connectionfailed');await route.fulfill({response});});
 await panel.getByRole('textbox',{name:'Maintenance reason'}).fill('Q08 frozen unknown preview');await panel.getByRole('button',{name:'Preview segmented maintenance'}).click();await expect(panel.getByRole('button',{name:'Retry same preview'})).toBeVisible();await expect(panel.getByRole('textbox',{name:'Maintenance reason'})).toBeDisabled();
 await panel.getByRole('button',{name:'Retry same preview'}).click();await expect(panel.getByRole('region',{name:'Frozen manifest'})).toBeVisible();expect(previews).toHaveLength(2);expect(previews[1]).toEqual(previews[0]);
 const id=new URL(page.url()).searchParams.get('bulk_manifest')!;
 await page.route(`**${root}/${id}/execute`,async route=>{executions.push({key:route.request().headers()['idempotency-key'],body:route.request().postDataJSON()});const response=await route.fetch();expect(response.status()).toBe(202);if(executions.length===1)return route.abort('connectionfailed');await route.fulfill({response});});
 await panel.getByRole('checkbox',{name:'Confirm exact manifest'}).check();await panel.getByRole('button',{name:'Execute confirmed manifest'}).click();await expect(panel.getByRole('alert')).toBeVisible();await expect(panel.getByRole('button',{name:'Start a new preview'})).toBeDisabled();await panel.getByRole('button',{name:'Execute confirmed manifest'}).click();await expect(page.getByRole('region',{name:'Bulk job progress'})).toBeVisible();expect(executions).toHaveLength(2);expect(executions[1]).toEqual(executions[0]);
 const proof=await fixture('inspect');expect(proof.manifests.filter(m=>m.id===id)).toHaveLength(1);expect(proof.manifests.find(m=>m.id===id)?.status).toBe('executed');const entry=new URL(page.url()).pathname+new URL(page.url()).search;await signInWorkbench(page,true,'access',entry);await page.getByRole('button',{name:'Buyers',exact:true}).click();await expect(page.getByRole('region',{name:'Frozen manifest'})).toContainText('executed');expect(executions).toHaveLength(2);
 writeFileSync('test-results/q08-ui-unknown-recovery.json',JSON.stringify({fixture_only:true,previews,executions,proof},null,2));
});
test('B08 failed rows get a new exact digest and current versions; successes are retained',async({page})=>{
 const seed=await fixture('seed','101'),panel=await open(page),manifest=await preview(page,panel);await fixture('stale',seed.ids[0]);const response=await execute(page,panel,manifest.id),jobId=(await response.json()).data.id;await fixture('drain',jobId);
 const job=page.getByRole('region',{name:'Bulk job progress'});await job.getByRole('button',{name:'Refresh job'}).click();await expect(job).toContainText('1 conflicts');let directRetry=0;page.on('request',r=>{if(new URL(r.url()).pathname.endsWith('/retry-failed'))directRetry++;});
 await job.getByRole('button',{name:'Preview failed rows with current versions'}).click();const childPanel=page.getByRole('region',{name:'Segmented maintenance'});await expect(childPanel).toContainText('Failed rows only');const child=await preview(page,childPanel);expect(child.count).toBe(1);expect(child.digest).not.toBe(manifest.digest);expect(directRetry).toBe(0);const childResponse=await execute(page,childPanel,child.id);expect(childResponse.status()).toBe(200);const state=await fixture('inspect');expect(state.buyers.filter(b=>b.version===2)).toHaveLength(100);expect(state.buyers.find(b=>b.id===seed.ids[0])?.version).toBe(3);
 writeFileSync('test-results/q08-ui-child.json',JSON.stringify({fixture_only:true,manifest,child,state},null,2));
});
test('B16 late preview cannot cross A-B-A; viewer has no maintenance; zh-HK mobile exact confirmation',async({page,browser})=>{
 await fixture('seed','101');const panel=await open(page);let release:()=>void=()=>{},received:()=>void=()=>{};const held=new Promise<void>(r=>release=r),started=new Promise<void>(r=>received=r);
 await page.route(`**${root}`,async route=>{if(route.request().method()!=='POST')return route.continue();const response=await route.fetch();received();await held;await route.fulfill({response}).catch(()=>{});});
 await panel.getByRole('textbox',{name:'Maintenance reason'}).fill('Q08 old scope request');await panel.getByRole('button',{name:'Preview segmented maintenance'}).click();await started;await page.getByRole('combobox',{name:'Workspace',exact:true}).selectOption('e0000000-0000-4000-8000-000000000101');await page.getByRole('combobox',{name:'Workspace',exact:true}).selectOption(workspace);release();await page.waitForTimeout(300);await expect(page.getByRole('region',{name:'Frozen manifest'})).toHaveCount(0);
 const viewer=await browser.newPage();try{await signInWorkbench(viewer,true,'viewer');await viewer.getByRole('button',{name:'Buyers',exact:true}).click();await expect(viewer.getByRole('region',{name:'Segmented maintenance'})).toHaveCount(0);}finally{await viewer.close();}
 await page.getByRole('combobox',{name:'Project',exact:true}).selectOption(project);await page.getByRole('button',{name:'Buyers',exact:true}).click();await page.unroute(`**${root}`);await page.setViewportSize({width:390,height:844});await page.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');const zh=page.getByRole('region',{name:'分段批量維護'});await expect(zh).toBeVisible();await zh.getByRole('button',{name:'重試同一預覽'}).click();await expect(zh.getByRole('region',{name:'已凍結維護清單'})).toBeVisible();await expect(zh.getByRole('button',{name:'執行已確認維護清單'})).toBeDisabled();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);await page.screenshot({path:'test-results/q08-zh-mobile.png',fullPage:true});
});

test('B01 reviewer executes current fit-bound review',async({page})=>{
 await fixture('seed','101');await fixture('assess');const panel=await open(page,'reviewer');await panel.getByRole('combobox',{name:'Operation',exact:true}).selectOption('reviewBuyers');const manifest=await preview(page,panel),response=await execute(page,panel,manifest.id);expect(response.status()).toBe(202);const job=(await response.json()).data;expect((await fixture('drain',job.id)).total).toBe(101);
 const progress=page.getByRole('region',{name:'Bulk job progress'});await progress.getByRole('button',{name:'Refresh job'}).click();await expect(progress).toContainText('101 updated');await page.screenshot({path:'test-results/q08-review-en.png',fullPage:true});
});
test('B01 typed list target supports confirmed add and explicit new remove preview',async({page})=>{
 await fixture('seed','100');const panel=await open(page),management=page.getByRole('region',{name:'Buyer lists and saved filters'});
 await management.getByRole('textbox',{name:'List name'}).fill('Q08 reviewed list');const created=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/lists'));await management.getByRole('button',{name:'Create list',exact:true}).click();const list=(await (await created).json()).data;
 await panel.getByRole('combobox',{name:'Operation',exact:true}).selectOption('changeListMemberships');await panel.getByRole('button',{name:'Reload lists'}).click();await expect(panel.getByRole('combobox',{name:'Target list'}).locator('option',{hasText:'Q08 reviewed list'})).toBeAttached();await panel.getByRole('combobox',{name:'Target list'}).selectOption(list.id);
 const first=await preview(page,panel),added=await execute(page,panel,first.id);expect(added.status()).toBe(200);expect((await added.json()).data.updated).toBe(100);
 await panel.getByRole('button',{name:'Start a new preview'}).click();await panel.getByRole('combobox',{name:'List change'}).selectOption('remove');const second=await preview(page,panel);expect(second.digest).not.toBe(first.digest);const removed=await execute(page,panel,second.id);expect(removed.status()).toBe(200);expect((await removed.json()).data.updated).toBe(100);expect((await fixture('inspect')).buyers.every(b=>b.version===1&&b.owner===null)).toBe(true);
});


test('B09 UI cancel preserves the committed first50 and cancels only pending51',async({page})=>{
 await fixture('seed','101');const panel=await open(page),manifest=await preview(page,panel),response=await execute(page,panel,manifest.id),jobId=(await response.json()).data.id;
 expect((await fixture('chunk',jobId)).total).toBe(50);const progress=page.getByRole('region',{name:'Bulk job progress'});await progress.getByRole('button',{name:'Refresh job'}).click();await expect(progress).toContainText('50 of 101');
 const cancelled=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith(`/jobs/${jobId}/cancel`));await progress.getByRole('button',{name:'Cancel pending rows'}).click();expect((await cancelled).status()).toBe(200);expect((await fixture('drain',jobId)).total).toBe(51);await progress.getByRole('button',{name:'Refresh job'}).click();await expect(progress).toContainText('cancelled:');await expect(progress).toContainText('51 cancelled');const proof=await fixture('inspect');expect(proof.buyers.filter(b=>b.version===2&&b.owner!==null)).toHaveLength(50);expect(proof.buyers.filter(b=>b.version===1&&b.owner===null)).toHaveLength(51);
 writeFileSync('test-results/q08-ui-cancel.json',JSON.stringify({fixture_only:true,manifest,jobId,proof},null,2));await page.screenshot({path:'test-results/q08-cancel-en.png',fullPage:true});
});
