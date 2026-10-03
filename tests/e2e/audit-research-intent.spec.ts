import {expect,test} from '@playwright/test';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {resolve} from 'node:path';
import {writeFileSync} from 'node:fs';
import {signInWorkbench,workspace,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';
const project='e9100000-0000-4000-8000-000000000001';
async function counts(){const cwd=resolve('services/worker');return JSON.parse((await promisify(execFile)(resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python'),['tests/fixtures/audit_intents.py'],{cwd,timeout:30_000})).stdout);}
test('B05 B06 committed lost 202 and manual Retry share one durable research intent',async({page})=>{
  await resetWorkbenchFixtureRateWindows();await signInWorkbench(page,true,'access');
  // Another isolated case may have persisted zh-HK in this owned shared fixture.
  await page.getByRole('combobox',{name:/^(Language|語言)$/}).first().selectOption('en');
  await page.getByRole('combobox',{name:'Project',exact:true}).selectOption(project);await page.getByRole('button',{name:'Research runs',exact:true}).click();
  const posted:{key:string|null;body:unknown;id:string}[]=[];
  await page.route(`**/v1/workspaces/${workspace}/projects/${project}/runs`,async route=>{
    if(route.request().method()!=='POST')return route.continue();
    const response=await route.fetch();expect(response.status()).toBe(202);const payload=await response.json();
    posted.push({key:route.request().headers()['idempotency-key'],body:route.request().postDataJSON(),id:payload.data.id});
    if(posted.length===1)return route.abort('failed');return route.fulfill({response});
  });
  await page.getByLabel('Target companies').fill('35');await page.getByLabel('Maximum research cost (USD)').fill('2.0');
  const start=page.getByRole('button',{name:'Start research',exact:true});await expect(start).toBeEnabled();
  // Two synchronous UI clicks exercise the actual busy guard before React re-renders.
  await start.evaluate(button=>{(button as HTMLButtonElement).click();(button as HTMLButtonElement).click();});await expect(page.getByRole('alert').last()).toBeVisible();
  const committed=await counts();expect(committed.runs).toBe(1);expect(committed.admission_outbox).toBe(1);expect(committed.economic_intents).toBe(1);
  await page.waitForTimeout(400);expect(posted).toHaveLength(1);
  await page.getByRole('button',{name:'Operations',exact:true}).click();await expect(page).toHaveURL(/\/app\/operations\?/);await expect(page.getByRole('region',{name:'Job lookup'})).toBeVisible();await page.getByRole('button',{name:'Research runs',exact:true}).click();await expect(page).toHaveURL(/\/app\/runs\?/);
  await expect(page.getByLabel('Target companies')).toHaveValue('35');await expect(page.getByLabel('Maximum research cost (USD)')).toHaveValue('2.000000');
  await page.getByRole('button',{name:/^(Start research|Retry same research)$/}).click();await expect.poll(()=>posted.length).toBe(2);
  const recovered=await counts();writeFileSync('test-results/audit-research-intent.json',JSON.stringify({posted,committed,recovered},null,2));
  expect(posted[1].key).toBe(posted[0].key);expect(posted[1].body).toEqual(posted[0].body);expect(posted[1].id).toBe(posted[0].id);
  expect(recovered.runs).toBe(1);expect(recovered.admission_outbox).toBe(1);expect(recovered.economic_intents).toBe(1);expect(recovered.provider_operations).toBe(0);expect(recovered.reservations).toBe(0);
  await expect(page).toHaveURL(new RegExp(`/app/discover/${posted[0].id}`));await page.screenshot({path:'test-results/audit-research-recovered.png',fullPage:true});
  await page.reload();await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeVisible();expect(posted).toHaveLength(2);
});
