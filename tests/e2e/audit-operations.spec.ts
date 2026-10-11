import {expect,test} from '@playwright/test';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {signInWorkbench,workspace,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';
async function fixture(count:number,state='completed'):Promise<{job_id:string;ids:string[]}>{
  const cwd=resolve('services/worker');const python=resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
  return JSON.parse((await promisify(execFile)(python,['tests/fixtures/audit_jobs.py',String(count),state],{cwd,timeout:30_000})).stdout);
}
test.beforeEach(async()=>{await resetWorkbenchFixtureRateWindows();});
for(const count of [21,101])test(`B10 B11 all ${count} real producer result IDs are readable in pages of 20`,async({page})=>{
  const seeded=await fixture(count);
  const response=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/jobs/${seeded.job_id}?offset=0&limit=20`,{headers:{Authorization:'Bearer fixture-reviewer'}});expect(response.status()).toBe(200);const payload=await response.json();expect(payload.data.kind).toBe('bulk_mutation');
  for(const [scope,token] of [[workspace,'fixture-access'],['e0000000-0000-4000-8000-000000000101','fixture-reviewer']])expect((await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${scope}/jobs/${seeded.job_id}`,{headers:{Authorization:`Bearer ${token}`}})).status()).toBe(404);expect(payload.data.result_page.items.map((row:{id:string})=>row.id)).toEqual(seeded.ids.slice(0,20));writeFileSync(`test-results/audit-job-payload-${count}.json`,JSON.stringify(payload,null,2));
  await signInWorkbench(page);await page.getByRole('button',{name:'Operations',exact:true}).click();
  const lookup=page.getByRole('region',{name:'Job lookup'});
  await lookup.getByRole('textbox',{name:'Job ID',exact:true}).fill(seeded.job_id);await lookup.getByRole('button',{name:'Load job',exact:true}).click();
  const seen:string[]=[];
  for(let offset=0;offset<count;offset+=20){
    await expect(lookup.locator('code')).toHaveCount(Math.min(20,count-offset));
    await expect(lookup.getByText(`${offset+1}–${Math.min(offset+20,count)} / ${count}`,{exact:true})).toBeVisible();
    seen.push(...await lookup.locator('code').allTextContents());
    if(offset+20<count)await lookup.getByRole('button',{name:'Next results',exact:true}).click();
  }
  expect(seen).toEqual(seeded.ids);expect(new Set(seen).size).toBe(count);
  await expect(lookup.getByRole('button',{name:'Next results',exact:true})).toBeDisabled();
  await lookup.getByRole('button',{name:'Previous results',exact:true}).click();
  await expect(lookup.locator('code').first()).toHaveText(seeded.ids[Math.max(0,Math.floor((count-1)/20)*20-20)]);
  await page.screenshot({path:`test-results/audit-operations-${count}.png`,fullPage:true});
});
test('B11 zero results and late job response cannot replace newer job',async({page})=>{
  const old=await fixture(21),fresh=await fixture(0);await signInWorkbench(page);await page.getByRole('button',{name:'Operations',exact:true}).click();
  let release:()=>void=()=>{};const held=new Promise<void>(r=>release=r);
  await page.route(`**/v1/workspaces/${workspace}/jobs/${old.job_id}?**`,async route=>{const response=await route.fetch();await held;await route.fulfill({response}).catch(()=>{});});
  const lookup=page.getByRole('region',{name:'Job lookup'});
  await lookup.getByRole('textbox',{name:'Job ID'}).fill(old.job_id);await lookup.getByRole('button',{name:'Load job',exact:true}).click();
  await lookup.getByRole('textbox',{name:'Job ID'}).fill(fresh.job_id);await lookup.getByRole('button',{name:'Load job',exact:true}).click();
  await expect(lookup.getByText('0–0 / 0',{exact:true})).toBeVisible();release();
  await expect(lookup.locator('code')).toHaveCount(0);await page.waitForTimeout(300);await expect(lookup.getByText('0–0 / 0',{exact:true})).toBeVisible();
});

test('B11 late result page is discarded after workspace A-B-A',async({page})=>{
  const old=await fixture(21);await signInWorkbench(page);await page.getByRole('button',{name:'Operations',exact:true}).click();
  const lookup=page.getByRole('region',{name:'Job lookup'});
  await lookup.getByRole('textbox',{name:'Job ID'}).fill(old.job_id);await lookup.getByRole('button',{name:'Load job',exact:true}).click();
  await expect(lookup.locator('code').first()).toHaveText(old.ids[0]);
  let release:()=>void=()=>{};let received:()=>void=()=>{};const held=new Promise<void>(r=>release=r),started=new Promise<void>(r=>received=r);
  await page.route(`**/v1/workspaces/${workspace}/jobs/${old.job_id}?offset=20&limit=20`,async route=>{const response=await route.fetch();received();await held;await route.fulfill({response}).catch(()=>{});});
  await lookup.getByRole('button',{name:'Next results'}).click();await started;
  await page.getByRole('combobox',{name:'Workspace',exact:true}).selectOption('e0000000-0000-4000-8000-000000000101');
  await page.getByRole('combobox',{name:'Workspace',exact:true}).selectOption(workspace);release();
  await expect(lookup.locator('code')).toHaveCount(0);await page.waitForTimeout(300);await expect(lookup.locator('code')).toHaveCount(0);
});


test('B12 unopened 1000-result job reads summary only and never walks result pages',async({page})=>{
  const seeded=await fixture(1000,'running');
  const calls:string[]=[];page.on('request',r=>{if(new URL(r.url()).pathname.includes(`/jobs/${seeded.job_id}`))calls.push(new URL(r.url()).pathname);});
  await signInWorkbench(page,true,'reviewer',`/app?workspace=${workspace}&project=e1000000-0000-4000-8000-000000000001&bulk_job=${seeded.job_id}`);
  await page.getByRole('button',{name:'Buyers',exact:true}).click();
  await expect.poll(()=>calls.length).toBeGreaterThan(0);
  expect(calls[0]).toBe(`/v1/workspaces/${workspace}/jobs/${seeded.job_id}/summary`);
  await expect(page.getByRole('region',{name:'Bulk job progress'})).toContainText('1000 of 1000');
  await page.waitForTimeout(4500);expect(calls.every(path=>path.endsWith('/summary'))).toBe(true);
});

async function statusFixture(job:string,state:string){
  const cwd=resolve('services/worker'),python=resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
  const result=await promisify(execFile)(python,['tests/fixtures/audit_jobs.py','status',job,state],{cwd,timeout:30_000});expect(JSON.parse(result.stdout).fixture_only).toBe(true);
}
async function openBulk(page:Parameters<typeof signInWorkbench>[0],job:string){
  await signInWorkbench(page,true,'reviewer',`/app?workspace=${workspace}&project=e1000000-0000-4000-8000-000000000001&bulk_job=${job}`);
  await page.getByRole('combobox',{name:/^(Language|語言)$/}).selectOption('en');
  await page.getByRole('button',{name:'Buyers',exact:true}).click();
  return page.getByRole('region',{name:'Bulk job progress'});
}

test('B12 2.5s summary RTT never overlaps or preloads results; terminal refreshes visible page once',async({page})=>{
  const seeded=await fixture(1000,'running');let active=0,max=0,calls=0;const results:string[]=[];
  page.on('request',r=>{const u=new URL(r.url());if(u.pathname===`/v1/workspaces/${workspace}/jobs/${seeded.job_id}`)results.push(u.search);});
  await page.route(`**/jobs/${seeded.job_id}/summary`,async route=>{calls++;max=Math.max(max,++active);try{const response=await route.fetch();await new Promise(r=>setTimeout(r,2500));await route.fulfill({response}).catch(()=>{});}finally{active--;}});
  const panel=await openBulk(page,seeded.job_id);await expect(panel).toContainText('1000 of 1000');await page.waitForTimeout(6500);expect(calls).toBeGreaterThanOrEqual(2);expect(max).toBe(1);expect(results).toEqual([]);
  await panel.getByRole('button',{name:'Show job results',exact:true}).click();await expect(panel.locator('code')).toHaveCount(20);expect(results).toHaveLength(1);
  await panel.getByRole('button',{name:'Next job results',exact:true}).click();await expect(panel.getByText('21–40 / 1000',{exact:true})).toBeVisible();expect(results).toHaveLength(2);
  const terminalResponse=page.waitForResponse(async r=>new URL(r.url()).pathname.endsWith(`/jobs/${seeded.job_id}/summary`)&&r.status()===200&&(await r.json()).data.status==='completed',{timeout:12_000});
  await statusFixture(seeded.job_id,'completed');await terminalResponse;await expect(panel).toContainText('completed:');await expect.poll(()=>results.length).toBe(3);expect(results.at(-1)).toBe('?offset=20&limit=20');
  const final=calls;await page.waitForTimeout(4500);expect(calls).toBe(final);expect(results).toHaveLength(3);expect(max).toBe(1);
  writeFileSync('test-results/q06-slow-terminal.json',JSON.stringify({fixture_only:true,calls,max_in_flight:max,result_requests:results},null,2));await page.screenshot({path:'test-results/q06-bulk-en.png',fullPage:true});
});

test('B13 hidden summary pause and double visibility resume produce exactly one refresh',async({page})=>{
  await page.addInitScript(()=>{let hidden=false;Object.defineProperty(document,'hidden',{configurable:true,get:()=>hidden});window.addEventListener('audit-hidden',()=>{hidden=true;document.dispatchEvent(new Event('visibilitychange'));});window.addEventListener('audit-visible',()=>{hidden=false;document.dispatchEvent(new Event('visibilitychange'));});});
  const seeded=await fixture(21,'running');let calls=0;page.on('request',r=>{if(new URL(r.url()).pathname.endsWith(`/jobs/${seeded.job_id}/summary`))calls++;});
  const panel=await openBulk(page,seeded.job_id);await expect(panel).toContainText('21 of 21');
  await page.evaluate(()=>window.dispatchEvent(new Event('audit-hidden')));const before=calls;await page.waitForTimeout(4500);expect(calls).toBe(before);
  await page.evaluate(()=>{window.dispatchEvent(new Event('audit-visible'));window.dispatchEvent(new Event('audit-visible'));});await expect.poll(()=>calls).toBe(before+1);
  await page.evaluate(()=>window.dispatchEvent(new Event('audit-hidden')));await page.waitForTimeout(2500);expect(calls).toBe(before+1);await expect(panel.getByRole('alert')).toHaveCount(0);
});

test('B13 actual 429 Retry-After and 503 recover without result-page traffic',async({page})=>{
  const seeded=await fixture(21,'running'),times:number[]=[];let details=0;
  page.on('request',r=>{if(new URL(r.url()).pathname===`/v1/workspaces/${workspace}/jobs/${seeded.job_id}`)details++;});
  await page.route(`**/jobs/${seeded.job_id}/summary`,async route=>{
    times.push(Date.now());if(times.length<3)await route.fulfill({status:times.length===1?429:503,contentType:'application/json',headers:times.length===1?{'Retry-After':'3'}:{},body:JSON.stringify({code:times.length===1?'RATE_LIMITED':'INTERNAL_ERROR',message:'fixture failure',request_id:'e0000000-0000-4000-8000-000000000010',retryable:true})});else await route.continue();
  });
  const panel=await openBulk(page,seeded.job_id);await expect(panel.getByRole('alert')).toContainText('Service temporarily unavailable');await expect(panel).toContainText('21 of 21',{timeout:20_000});
  expect(times[1]-times[0]).toBeGreaterThanOrEqual(3000);expect(times[2]-times[1]).toBeGreaterThanOrEqual(4000);expect(details).toBe(0);await expect(panel.getByRole('alert')).toHaveCount(0);
  writeFileSync('test-results/q06-backoff.json',JSON.stringify({fixture_only:true,attempt_times:times,detail_requests:details},null,2));
});

test('B16 old summary cannot overwrite another scope after A-B-A',async({page})=>{
  const seeded=await fixture(21,'running');let release:()=>void=()=>{};let received:()=>void=()=>{};const held=new Promise<void>(r=>release=r),started=new Promise<void>(r=>received=r);let calls=0;
  await page.route(`**/jobs/${seeded.job_id}/summary`,async route=>{calls++;const response=await route.fetch();if(calls===1){received();await held;}await route.fulfill({response}).catch(()=>{});});
  await signInWorkbench(page);await page.getByRole('button',{name:'Operations',exact:true}).click();
  const lookup=page.getByRole('region',{name:'Job lookup'});
  await lookup.getByRole('textbox',{name:'Job ID'}).fill(seeded.job_id);await lookup.getByRole('button',{name:'Load job',exact:true}).click();
  await started;await statusFixture(seeded.job_id,'completed');
  await page.getByRole('combobox',{name:'Workspace',exact:true}).selectOption('e0000000-0000-4000-8000-000000000101');
  await expect(lookup.locator('code')).toHaveCount(0);
  await page.getByRole('combobox',{name:'Workspace',exact:true}).selectOption(workspace);
  await lookup.getByRole('textbox',{name:'Job ID'}).fill(seeded.job_id);await lookup.getByRole('button',{name:'Load job',exact:true}).click();
  await expect(lookup).toContainText('completed');await expect(lookup.locator('code').first()).toHaveText(seeded.ids[0]);release();
  await page.waitForTimeout(2500);await expect(lookup).not.toContainText('running');await expect(lookup.locator('code').first()).toHaveText(seeded.ids[0]);
});

test('B13 zh-HK 390px summary/results controls remain usable without overflow',async({page})=>{
  const seeded=await fixture(21);await page.setViewportSize({width:390,height:844});const panel=await openBulk(page,seeded.job_id);
  await page.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');const zh=page.getByRole('region',{name:'批量工作進度'});await expect(zh).toContainText('已處理 21／21');
  await zh.getByRole('button',{name:'顯示工作結果',exact:true}).click();await expect(zh.locator('code')).toHaveCount(20);await zh.getByRole('button',{name:'下一頁工作結果',exact:true}).click();await expect(zh.getByText('21–21 / 21',{exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);await page.screenshot({path:'test-results/q06-bulk-zh-mobile.png',fullPage:true});
  const saved=page.waitForResponse(r=>r.request().method()==='PATCH'&&new URL(r.url()).pathname.endsWith('/preferences'));await page.getByRole('combobox',{name:'語言',exact:true}).selectOption('en');expect((await saved).status()).toBe(200);
  await expect(panel).toBeVisible();
});

test('B13 Operations clears a transient summary error after a valid recovery',async({page})=>{
  const seeded=await fixture(21,'running');let calls=0;
  await page.route(`**/jobs/${seeded.job_id}/summary`,async route=>{calls++;if(calls===1)await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({code:'INTERNAL_ERROR',message:'fixture failure',request_id:'e0000000-0000-4000-8000-000000000010',retryable:true})});else await route.continue();});
  await signInWorkbench(page);await page.getByRole('button',{name:'Operations',exact:true}).click();
  const operations=page.getByRole('region',{name:'Operations',exact:true}),lookup=page.getByRole('region',{name:'Job lookup'});
  await lookup.getByRole('textbox',{name:'Job ID'}).fill(seeded.job_id);await lookup.getByRole('button',{name:'Load job',exact:true}).click();
  await expect(operations.getByRole('alert')).toContainText('Service temporarily unavailable');await expect.poll(()=>calls).toBeGreaterThanOrEqual(2);
  await expect(operations.getByRole('alert')).toHaveCount(0);await expect(lookup).toContainText('running');
});
