import {expect,test} from '@playwright/test';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {signInWorkbench,workspace,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';
async function fixture(count:number):Promise<{job_id:string;ids:string[]}>{
  const cwd=resolve('services/worker');const python=resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
  return JSON.parse((await promisify(execFile)(python,['tests/fixtures/audit_jobs.py',String(count)],{cwd,timeout:30_000})).stdout);
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
