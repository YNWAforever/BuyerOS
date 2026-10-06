import {expect,test,type Page} from '@playwright/test';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {resolve} from 'node:path';
import {writeFile} from 'node:fs/promises';
import {signInWorkbench,workspace,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';
type QueueFixture={id:string;counts:Record<string,number>};
async function prepare(){await resetWorkbenchFixtureRateWindows();const cwd=resolve('services/worker');return JSON.parse((await promisify(execFile)(resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python'),['tests/fixtures/c61_work_queue.py'],{cwd,timeout:30_000})).stdout).projects as QueueFixture[];}
const panel=(page:Page)=>page.getByRole('region',{name:/^(Daily work queue|每日工作佇列)$/,exact:true});
async function counts(page:Page,fixture:QueueFixture){for(const [kind,count] of Object.entries(fixture.counts))await expect(panel(page).locator(`[data-work-queue-kind="${kind}"] output`)).toHaveText(String(count));await expect(panel(page).locator('time')).toHaveAttribute('datetime',/T/);}

for(const index of [0,1])test(`U15/C61T-09 project ${index?'B zh-HK mobile':'A en desktop'} cards equal each real filtered list`,async({page})=>{
 test.setTimeout(120_000);if(index)await page.setViewportSize({width:390,height:844});
 const fixtures=await prepare(),selected=fixtures[index];await signInWorkbench(page);
 if(index){await page.getByRole('combobox',{name:/^(Language|語言)$/}).first().selectOption('zh-HK');await expect(page.locator('html')).toHaveAttribute('lang','zh-HK');}
 await page.getByRole('combobox',{name:/^(Project|專案)$/}).selectOption(selected.id);await counts(page,selected);
 const as_of=await panel(page).locator('time').getAttribute('datetime');await page.screenshot({path:`test-results/c61-queue-${index}-overview.png`,fullPage:true});
 const observations=[];
 for(const [kind,total] of Object.entries(selected.counts)){
  const target=kind==='pending_approval'?'drafts':kind==='failed_job'?'jobs':kind==='unknown_acceptance'?'provider-operations':'buyers';
  const response=page.waitForResponse(r=>r.request().method()==='GET'&&new URL(r.url()).pathname.endsWith('/'+target)&&(target==='jobs'?new URL(r.url()).searchParams.get('project_id')===selected.id:new URL(r.url()).pathname.includes(`/projects/${selected.id}/`)));
  await panel(page).locator(`[data-work-queue-kind="${kind}"]`).getByRole('button',{name:/^(Open|開啟)$/,exact:true}).click();
  const actual=await response;expect(actual.status(),await actual.text()).toBe(200);const data=(await actual.json()).data;expect(data.total).toBe(total);
  const url=new URL(page.url());expect(url.searchParams.get('workspace')).toBe(workspace);expect(url.searchParams.get('project')).toBe(selected.id);
  if(kind==='pending_approval'){expect(url.searchParams.get('approval')).toBe('pending');expect(data.items.every((row:{status:string})=>row.status==='review_requested')).toBe(true);}
  if(kind==='unknown_acceptance'){expect(url.searchParams.get('acceptance')).toBe('unknown');expect(data.items.every((row:{status:string})=>row.status==='unknown')).toBe(true);await expect(page.getByRole('region',{name:/^(Bulk jobs|批量工作)$/,exact:true})).toHaveCount(0);}
  observations.push({kind,total,response_total:data.total,query:url.search});
  await page.getByRole('button',{name:/^(Overview|總覽)$/,exact:true}).click();await counts(page,selected);
 }
 await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await writeFile(`test-results/c61-queue-${index}-counts.json`,JSON.stringify({fixture_only:true,selected,as_of,observations},null,2));
});

test('C61T-09 held project summary cannot overwrite newer scope; failed refresh stays unavailable',async({page})=>{
 const [a,b]=await prepare();await signInWorkbench(page);let started:()=>void=()=>{},release:()=>void=()=>{},complete:()=>void=()=>{};let old_response_disposition='pending';const completed=new Promise<void>(r=>complete=r);const begun=new Promise<void>(r=>started=r),held=new Promise<void>(r=>release=r);
 const aPath=`**/v1/workspaces/${workspace}/projects/${a.id}/work-queue`;
 await page.route(aPath,async route=>{const result=await route.fetch();expect(result.status()).toBe(200);started();await held;try{await route.fulfill({response:result});old_response_disposition='fulfilled';}catch{old_response_disposition='request_cancelled_after_scope_switch';}finally{complete();}});
 await page.getByRole('combobox',{name:/^(Project|專案)$/}).selectOption(a.id);await begun;
 await page.getByRole('combobox',{name:/^(Project|專案)$/}).selectOption(b.id);await counts(page,b);const asOf=await panel(page).locator('time').getAttribute('datetime');release();await completed;await counts(page,b);expect(await panel(page).locator('time').getAttribute('datetime')).toBe(asOf);await page.unroute(aPath);
 const path=`**/v1/workspaces/${workspace}/projects/${b.id}/work-queue`;
 await page.route(path,route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({code:'PROVIDER_UNAVAILABLE',message:'Isolated C61 summary read failure',request_id:'00000000-0000-4000-8000-000000000021',retryable:true})}));
 await panel(page).getByRole('button',{name:/^(Refresh work queue|重新整理今日待辦)$/,exact:true}).click();await expect(panel(page).getByRole('alert')).toBeVisible();
 for(const kind of Object.keys(b.counts))await expect(panel(page).locator(`[data-work-queue-kind="${kind}"] output`)).toHaveText('—');await expect(panel(page).locator('time')).toHaveCount(0);
 await page.unroute(path);await panel(page).getByRole('button',{name:/^(Refresh work queue|重新整理今日待辦)$/,exact:true}).click();await counts(page,b);
 await writeFile('test-results/c61-queue-scope-race.json',JSON.stringify({fixture_only:true,held_scope:a.id,new_scope:b.id,as_of_before_old_response:asOf,old_response_disposition,counts_and_as_of_unchanged_after_old_response:true,synthetic_503_unavailable:true,restored_counts:b.counts},null,2));
});
