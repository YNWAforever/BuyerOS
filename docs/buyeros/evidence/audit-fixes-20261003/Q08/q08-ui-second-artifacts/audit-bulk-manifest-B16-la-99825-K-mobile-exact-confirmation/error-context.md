# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-bulk-manifest.spec.ts >> B16 late preview cannot cross A-B-A; viewer has no maintenance; zh-HK mobile exact confirmation
- Location: tests\e2e\audit-bulk-manifest.spec.ts:62:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('region', { name: '分段維護' })
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('region', { name: '分段維護' }) with timeout 5000ms
  - waiting for getByRole('region', { name: '分段維護' })

```

```yaml
- main:
  - text: FIMMICK BuyerOS 正式工作區 語言
  - combobox "語言":
    - option "English"
    - option "繁體中文" [selected]
  - button "登出"
  - navigation "BuyerOS sections":
    - button "總覽"
    - button "產品資料"
    - button "買家" [disabled]
    - button "結果" [disabled]
    - button "研究進度" [disabled]
    - button "草稿" [disabled]
    - button "設定"
    - button "營運工作台"
  - region "工作區選擇":
    - heading "工作區" [level=2]
    - text: 工作區
    - combobox "工作區":
      - option "選擇工作區"
      - option "E2E fixture workspace" [selected]
      - option "Other audit fixture"
    - paragraph: "角色: 操作員"
  - region "專案選擇":
    - heading "專案" [level=2]
    - text: 專案
    - combobox "專案":
      - option "選擇專案" [selected]
      - option "Buyer Fixture Project"
      - option "Run Fixture Project"
    - button "新增專案"
```

# Test source

```ts
  1  | import {expect,test,type Page} from '@playwright/test';
  2  | import {execFile} from 'node:child_process';
  3  | import {promisify} from 'node:util';
  4  | import {resolve} from 'node:path';
  5  | import {writeFileSync} from 'node:fs';
  6  | import {signInWorkbench,workspace,project,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';
  7  | const root=`/v1/workspaces/${workspace}/projects/${project}/bulk-manifests`;
  8  | const prefix='Q08 Manifest Fixture';
  9  | async function fixture(command:string,...args:string[]):Promise<{fixture_only:boolean;count:number;ids:string[];buyers:{id:string;version:number;owner:string|null}[];manifests:{id:string;count:number;status:string;job_id:string|null}[];total:number}>{
  10 |  const cwd=resolve('services/worker'),python=resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
  11 |  const value=JSON.parse((await promisify(execFile)(python,['tests/fixtures/audit_manifests.py',command,...args],{cwd,timeout:45_000})).stdout);expect(value.fixture_only).toBe(true);return value;
  12 | }
  13 | async function open(page:Page,actor:'access'|'reviewer'|'viewer'='access',entry?:string){
  14 |  await signInWorkbench(page,true,actor,entry);await page.getByRole('combobox',{name:/^(Language|語言)$/}).selectOption('en');await page.getByRole('button',{name:'Buyers',exact:true}).click();
  15 |  const buyers=page.getByRole('region',{name:'Buyer results',exact:true});
  16 |  await buyers.getByRole('textbox',{name:'Search buyers',exact:true}).fill(prefix);await buyers.getByRole('textbox',{name:'Search buyers',exact:true}).press('Enter');
  17 |  await expect(buyers.getByRole('checkbox',{name:/^Select /})).toHaveCount(12);
  18 |  return page.getByRole('region',{name:'Segmented maintenance',exact:true});
  19 | }
  20 | async function preview(page:Page,panel:ReturnType<Page['getByRole']>){
  21 |  await panel.getByRole('textbox',{name:'Maintenance reason',exact:true}).fill('Q08 human reviewed maintenance');
  22 |  const read=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname===root);
  23 |  await panel.getByRole('button',{name:'Preview segmented maintenance',exact:true}).click();const response=await read;expect(response.status()).toBe(201);
  24 |  const data=(await response.json()).data;await expect(panel.getByRole('region',{name:'Frozen manifest'})).toContainText(`count: ${data.count}`);return data as {id:string;count:number;digest:string;version:number};
  25 | }
  26 | async function execute(page:Page,panel:ReturnType<Page['getByRole']>,id:string){
  27 |  await panel.getByRole('checkbox',{name:'Confirm exact manifest'}).check();const response=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname===root+`/${id}/execute`);
  28 |  await panel.getByRole('button',{name:'Execute confirmed manifest'}).click();return await response;
  29 | }
  30 | test.beforeEach(async()=>{await resetWorkbenchFixtureRateWindows();});
  31 | for(const count of [100,101,1001])test(`B01 B08 B14 ${count} actual rows require frozen preview and explicit execution`,async({page})=>{
  32 |  const seed=await fixture('seed',String(count)),panel=await open(page);
  33 |  await expect(panel.getByRole('button',{name:'Execute confirmed manifest'})).toHaveCount(0);
  34 |  if(count===1001)await expect(page.getByRole('region',{name:'Buyer results',exact:true})).toContainText(/clipped|1000/i);
  35 |  const manifest=await preview(page,panel);expect(manifest.count).toBe(count);expect((await fixture('inspect')).buyers.every(b=>b.version===1&&b.owner===null)).toBe(true);
  36 |  await expect(panel.getByRole('button',{name:'Execute confirmed manifest'})).toBeDisabled();const response=await execute(page,panel,manifest.id);expect(response.status()).toBe(count===100?200:202);const result=(await response.json()).data;
  37 |  if(count>100){const drain=await fixture('drain',result.id);expect(drain.total).toBe(count);const job=page.getByRole('region',{name:'Bulk job progress'});await job.getByRole('button',{name:'Refresh job'}).click();await expect(job).toContainText(`${count} of ${count}`);
  38 |   await job.getByRole('button',{name:'Show job results'}).click();await expect(job.locator('code')).toHaveCount(20);const seen:string[]=[];
  39 |   for(let offset=0;offset<count;offset+=20){await expect(job.getByText(`${offset+1}–${Math.min(offset+20,count)} / ${count}`,{exact:true})).toBeVisible();seen.push(...await job.locator('code').allTextContents());if(offset+20<count)await job.getByRole('button',{name:'Next job results'}).click();}
  40 |   expect(new Set(seen).size).toBe(count);expect(seen.sort()).toEqual(seed.ids.sort());
  41 |  }
  42 |  const state=await fixture('inspect');expect(state.buyers).toHaveLength(count);expect(state.buyers.every(b=>b.version===2&&b.owner!==null)).toBe(true);
  43 |  writeFileSync(`test-results/q08-ui-${count}.json`,JSON.stringify({fixture_only:true,manifest,result,state},null,2));await page.screenshot({path:`test-results/q08-en-${count}.png`,fullPage:true});
  44 | });
  45 | test('B15 lost preview and committed 202 retry one frozen body/key and restore after re-login',async({page})=>{
  46 |  await fixture('seed','101');const panel=await open(page);const previews:{key:string;body:unknown}[]=[],executions:{key:string;body:unknown}[]=[];
  47 |  await page.route(`**${root}`,async route=>{if(route.request().method()!=='POST')return route.continue();previews.push({key:route.request().headers()['idempotency-key'],body:route.request().postDataJSON()});const response=await route.fetch();if(previews.length===1)return route.abort('connectionfailed');await route.fulfill({response});});
  48 |  await panel.getByRole('textbox',{name:'Maintenance reason'}).fill('Q08 frozen unknown preview');await panel.getByRole('button',{name:'Preview segmented maintenance'}).click();await expect(panel.getByRole('button',{name:'Retry same preview'})).toBeVisible();await expect(panel.getByRole('textbox',{name:'Maintenance reason'})).toBeDisabled();
  49 |  await panel.getByRole('button',{name:'Retry same preview'}).click();await expect(panel.getByRole('region',{name:'Frozen manifest'})).toBeVisible();expect(previews).toHaveLength(2);expect(previews[1]).toEqual(previews[0]);
  50 |  const id=new URL(page.url()).searchParams.get('bulk_manifest')!;
  51 |  await page.route(`**${root}/${id}/execute`,async route=>{executions.push({key:route.request().headers()['idempotency-key'],body:route.request().postDataJSON()});const response=await route.fetch();expect(response.status()).toBe(202);if(executions.length===1)return route.abort('connectionfailed');await route.fulfill({response});});
  52 |  await panel.getByRole('checkbox',{name:'Confirm exact manifest'}).check();await panel.getByRole('button',{name:'Execute confirmed manifest'}).click();await expect(panel.getByRole('alert')).toBeVisible();await panel.getByRole('button',{name:'Execute confirmed manifest'}).click();await expect(page.getByRole('region',{name:'Bulk job progress'})).toBeVisible();expect(executions).toHaveLength(2);expect(executions[1]).toEqual(executions[0]);
  53 |  const proof=await fixture('inspect');expect(proof.manifests.filter(m=>m.id===id)).toHaveLength(1);expect(proof.manifests.find(m=>m.id===id)?.status).toBe('executed');const entry=new URL(page.url()).pathname+new URL(page.url()).search;await signInWorkbench(page,true,'access',entry);await page.getByRole('button',{name:'Buyers',exact:true}).click();await expect(page.getByRole('region',{name:'Frozen manifest'})).toContainText('executed');expect(executions).toHaveLength(2);
  54 |  writeFileSync('test-results/q08-ui-unknown-recovery.json',JSON.stringify({fixture_only:true,previews,executions,proof},null,2));
  55 | });
  56 | test('B09 failed rows get a new exact digest and current versions; successes are retained',async({page})=>{
  57 |  const seed=await fixture('seed','101'),panel=await open(page),manifest=await preview(page,panel);await fixture('stale',seed.ids[0]);const response=await execute(page,panel,manifest.id),jobId=(await response.json()).data.id;await fixture('drain',jobId);
  58 |  const job=page.getByRole('region',{name:'Bulk job progress'});await job.getByRole('button',{name:'Refresh job'}).click();await expect(job).toContainText('1 conflicts');let directRetry=0;page.on('request',r=>{if(new URL(r.url()).pathname.endsWith('/retry-failed'))directRetry++;});
  59 |  await job.getByRole('button',{name:'Preview failed rows with current versions'}).click();const childPanel=page.getByRole('region',{name:'Segmented maintenance'});await expect(childPanel).toContainText('Failed rows only');const child=await preview(page,childPanel);expect(child.count).toBe(1);expect(child.digest).not.toBe(manifest.digest);expect(directRetry).toBe(0);const childResponse=await execute(page,childPanel,child.id);expect(childResponse.status()).toBe(200);const state=await fixture('inspect');expect(state.buyers.filter(b=>b.version===2)).toHaveLength(100);expect(state.buyers.find(b=>b.id===seed.ids[0])?.version).toBe(3);
  60 |  writeFileSync('test-results/q08-ui-child.json',JSON.stringify({fixture_only:true,manifest,child,state},null,2));
  61 | });
  62 | test('B16 late preview cannot cross A-B-A; viewer has no maintenance; zh-HK mobile exact confirmation',async({page,browser})=>{
  63 |  await fixture('seed','101');const panel=await open(page);let release:()=>void=()=>{},received:()=>void=()=>{};const held=new Promise<void>(r=>release=r),started=new Promise<void>(r=>received=r);
  64 |  await page.route(`**${root}`,async route=>{if(route.request().method()!=='POST')return route.continue();const response=await route.fetch();received();await held;await route.fulfill({response}).catch(()=>{});});
  65 |  await panel.getByRole('textbox',{name:'Maintenance reason'}).fill('Q08 old scope request');await panel.getByRole('button',{name:'Preview segmented maintenance'}).click();await started;await page.getByRole('combobox',{name:'Workspace',exact:true}).selectOption('e0000000-0000-4000-8000-000000000101');await page.getByRole('combobox',{name:'Workspace',exact:true}).selectOption(workspace);release();await page.waitForTimeout(300);await expect(page.getByRole('region',{name:'Frozen manifest'})).toHaveCount(0);
  66 |  const viewer=await browser.newPage();try{await signInWorkbench(viewer,true,'viewer');await viewer.getByRole('button',{name:'Buyers',exact:true}).click();await expect(viewer.getByRole('region',{name:'Segmented maintenance'})).toHaveCount(0);}finally{await viewer.close();}
> 67 |  await page.unroute(`**${root}`);await page.setViewportSize({width:390,height:844});await page.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');const zh=page.getByRole('region',{name:'分段維護'});await expect(zh).toBeVisible();await zh.getByRole('button',{name:'重試同一預覽'}).click();await expect(zh.getByRole('region',{name:'已凍結維護清單'})).toBeVisible();await expect(zh.getByRole('button',{name:'執行已確認維護清單'})).toBeDisabled();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);await page.screenshot({path:'test-results/q08-zh-mobile.png',fullPage:true});
     |                                                                                                                                                                                                                                          ^ Error: expect(locator).toBeVisible() failed
  68 | });
  69 | 
```