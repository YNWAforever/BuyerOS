# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-job-scope.spec.ts >> U15 project A0 B5; card and failed list share scope; explicit workspace5
- Location: tests\e2e\audit-job-scope.spec.ts:15:1

# Error details

```
Error: expect(page).toHaveURL(expected) failed

Expected pattern: /job_status=failed/
Received string:  "http://localhost:5173/app/operations?workspace=e0000000-0000-4000-8000-000000000001&job_scope=project&project=e1000000-0000-4000-8000-000000000001"
Timeout: 5000ms

Call log:
  - Expect "toHaveURL" with timeout 5000ms
    14 × locator resolved to <html lang="en">…</html>
       - unexpected value "http://localhost:5173/app/operations?workspace=e0000000-0000-4000-8000-000000000001&job_scope=project&project=e1000000-0000-4000-8000-000000000001"

```

```yaml
- main:
  - text: FIMMICK BuyerOS Live workspace Language
  - combobox "Language":
    - option "English" [selected]
    - option "繁體中文"
  - button "Sign out"
  - navigation "BuyerOS sections":
    - button "Overview"
    - button "Offer" [disabled]
    - button "Buyers"
    - button "Results"
    - button "Research runs"
    - button "Drafts"
    - button "Settings"
    - button "Operations"
  - region "Workspace selection":
    - heading "Workspaces" [level=2]
    - text: Workspace
    - combobox "Workspace":
      - option "Choose workspace"
      - option "E2E fixture workspace" [selected]
    - paragraph: "Role: reviewer"
  - region "Project selection":
    - heading "Projects" [level=2]
    - text: Project
    - combobox "Project":
      - option "Choose project"
      - option "Buyer Fixture Project" [selected]
      - option "Run Fixture Project"
      - option "Q14 project B"
  - region "Operations":
    - heading "Operations" [level=2]
    - paragraph: Live domain state only. Provider readiness remains blocked until verified.
    - region "Work queue":
      - heading "Work queue" [level=3]
      - paragraph: "Profile approval: 0"
      - paragraph: "Failed jobs: 0"
      - paragraph: "Buyer review: Open the live buyer list for current review status."
      - button "Open buyer list"
    - region "Integrations":
      - heading "Integrations" [level=3]
      - paragraph: "research: unconfigured · live_providers_not_activated"
      - paragraph: "contact_enrichment: unconfigured · live_providers_not_activated"
      - paragraph: "draft_generation: unconfigured · live_providers_not_activated"
      - paragraph: "mailbox: disabled · live_providers_not_activated"
      - paragraph: "crm: disabled · live_providers_not_activated"
    - region "Bulk jobs":
      - heading "Bulk jobs" [level=3]
      - text: Job scope
      - combobox "Job scope":
        - option "Project jobs" [selected]
        - option "Workspace jobs"
      - paragraph:
        - text: "Project jobs:"
        - code: e1000000-0000-4000-8000-000000000001
      - paragraph: Only jobs created by your account are included.
      - text: Filter status
      - combobox "Filter status":
        - option "All statuses" [selected]
        - option "queued"
        - option "running"
        - option "cancel_requested"
        - option "cancelled"
        - option "completed"
        - option "failed"
      - paragraph: 0 jobs in scope
      - paragraph: No jobs in this scope.
      - button "Previous" [disabled]
      - text: 0–0 / 0
      - button "Next" [disabled]
    - region "Job lookup":
      - heading "Job lookup" [level=3]
      - text: Job ID
      - textbox "Job ID"
      - button "Load job"
```

# Test source

```ts
  1  | import {expect,test,type Page} from '@playwright/test';
  2  | import {execFile} from 'node:child_process';
  3  | import {promisify} from 'node:util';
  4  | import {resolve} from 'node:path';
  5  | import {writeFileSync} from 'node:fs';
  6  | import {signInWorkbench,workspace,project,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';
  7  | const projectB='e1140000-0000-4000-8000-000000000002';
  8  | async function seed(count=5):Promise<{own_ids:string[];other_ids:string[]}>{
  9  |  const cwd=resolve('services/worker'),python=resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
  10 |  const result=JSON.parse((await promisify(execFile)(python,['tests/fixtures/audit_job_scopes.py',String(count)],{cwd,timeout:30_000})).stdout);expect(result.fixture_only).toBe(true);return result;
  11 | }
  12 | async function login(page:Page,entry?:string){await signInWorkbench(page,true,'reviewer',entry);await page.getByRole('combobox',{name:/^(Language|語言)$/}).selectOption('en');}
  13 | function failedCard(page:Page){return page.getByRole('region',{name:'Daily work queue'}).locator('.activity').filter({has:page.getByText('Failed jobs',{exact:true})});}
  14 | test.beforeEach(async()=>{await resetWorkbenchFixtureRateWindows();});
  15 | test('U15 project A0 B5; card and failed list share scope; explicit workspace5',async({page})=>{
  16 |  const seeded=await seed();await login(page);const card=failedCard(page);await expect(card.locator('p')).toHaveText('0');
  17 |  await card.getByRole('button',{name:'Open',exact:true}).click();
> 18 |  const jobs=page.getByRole('region',{name:'Bulk jobs'});await expect(jobs).toContainText('0 jobs in scope');await expect(page).toHaveURL(/job_scope=project/);await expect(page).toHaveURL(/job_status=failed/);
     |                                                                                                                                                                                  ^ Error: expect(page).toHaveURL(expected) failed
  19 |  await page.getByRole('combobox',{name:'Project',exact:true}).selectOption(projectB);await expect(jobs).toContainText('5 jobs in scope');
  20 |  const queue=page.getByRole('region',{name:'Work queue',exact:true});await expect(queue).toContainText('Failed jobs: 5');
  21 |  await page.getByRole('button',{name:'Overview',exact:true}).click();await expect(failedCard(page).locator('p')).toHaveText('5');await failedCard(page).getByRole('button',{name:'Open',exact:true}).click();
  22 |  await page.getByRole('combobox',{name:'Job scope',exact:true}).selectOption('workspace');await expect(jobs).toContainText('Workspace jobs');await expect(jobs).toContainText('5 jobs in scope');
  23 |  await expect(page).toHaveURL(/job_scope=workspace/);expect(new Set(await jobs.getByRole('button').filter({hasText:/^[0-9a-f-]{36}$/}).allTextContents())).toEqual(new Set(seeded.own_ids));
  24 |  await page.screenshot({path:'test-results/q14-en-scope.png',fullPage:true});writeFileSync('test-results/q14-en-scope.json',JSON.stringify({fixture_only:true,...seeded,url:page.url()},null,2));
  25 | });
  26 | test('U15 workspace view remains actor-bound, other actor detail denied; admin read sees all',async({page})=>{
  27 |  const seeded=await seed();await login(page,`/app/operations?workspace=${workspace}&project=${project}&job_scope=workspace&job_status=failed`);
  28 |  const jobs=page.getByRole('region',{name:'Bulk jobs'});await expect(jobs).toContainText('5 jobs in scope');for(const id of seeded.other_ids)await expect(jobs.getByRole('button',{name:id,exact:true})).toHaveCount(0);
  29 |  for(const [token,total] of [['fixture-reviewer',5],['fixture-access',3],['fixture-admin',8],['fixture-viewer',0]] as const){const r=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/jobs?status=failed&offset=0&limit=20`,{headers:{Authorization:`Bearer ${token}`}});expect(r.status()).toBe(200);expect((await r.json()).data.total).toBe(total);}
  30 |  expect((await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/jobs/${seeded.other_ids[0]}`,{headers:{Authorization:'Bearer fixture-reviewer'}})).status()).toBe(404);
  31 | });
  32 | for(const count of [21,101])test(`U15 actual ${count} job list fully pages20; scope resets offset and old rows`,async({page})=>{
  33 |  const seeded=await seed(count);await login(page,`/app/operations?workspace=${workspace}&project=${project}&job_status=failed`);await page.getByRole('combobox',{name:'Project',exact:true}).selectOption(projectB);
  34 |  const jobs=page.getByRole('region',{name:'Bulk jobs'}),seen:string[]=[];
  35 |  for(let offset=0;offset<count;offset+=20){await expect(jobs.getByText(`${offset+1}–${Math.min(offset+20,count)} / ${count}`,{exact:true})).toBeVisible();seen.push(...await jobs.getByRole('button').filter({hasText:/^[0-9a-f-]{36}$/}).allTextContents());if(offset+20<count)await jobs.getByRole('button',{name:'Next',exact:true}).click();}
  36 |  expect(new Set(seen)).toEqual(new Set(seeded.own_ids));expect(seen.length).toBe(count);
  37 |  await page.getByRole('combobox',{name:'Project',exact:true}).selectOption(project);await expect(jobs).toContainText('0 jobs in scope');await expect(jobs.getByText('0–0 / 0',{exact:true})).toBeVisible();expect(new URL(page.url()).searchParams.get('job_offset')??'0').toBe('0');
  38 | });
  39 | test('U15 held B list and count cannot overwrite newer A-B-A generation',async({page})=>{
  40 |  await seed();await login(page,`/app/operations?workspace=${workspace}&project=${project}&job_status=failed`);
  41 |  let release=()=>{},received=()=>{};const hold=new Promise<void>(r=>release=r),started=new Promise<void>(r=>received=r);let held=0;
  42 |  await page.route('**/v1/workspaces/*/jobs?**',async route=>{const u=new URL(route.request().url());if(u.searchParams.get('project_id')===projectB){const response=await route.fetch();held++;received();await hold;await route.fulfill({response}).catch(()=>{});}else await route.continue();});
  43 |  await page.getByRole('combobox',{name:'Project',exact:true}).selectOption(projectB);await started;await expect.poll(()=>held).toBeGreaterThanOrEqual(2);
  44 |  await page.getByRole('combobox',{name:'Project',exact:true}).selectOption(project);const jobs=page.getByRole('region',{name:'Bulk jobs'});await expect(jobs).toContainText('0 jobs in scope');release();await page.waitForTimeout(300);await expect(jobs).toContainText('0 jobs in scope');await expect(page.getByRole('region',{name:'Work queue',exact:true})).toContainText('Failed jobs: 0');
  45 | });
  46 | test('U15 zh-HK390 workspace label, filter URL/reload reauth and read failure recovery',async({page})=>{
  47 |  await seed();await page.setViewportSize({width:390,height:844});await login(page,`/app/operations?workspace=${workspace}&project=${project}&job_scope=workspace&job_status=failed`);
  48 |  await page.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');const jobs=page.getByRole('region',{name:'批量工作'});await expect(jobs).toContainText('工作區工作');await expect(jobs).toContainText('5 項範圍內工作');expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  49 |  await page.screenshot({path:'test-results/q14-zh-mobile.png',fullPage:true});const saved=page.waitForResponse(r=>r.request().method()==='PATCH'&&r.url().endsWith('/preferences'));await page.getByRole('combobox',{name:'語言',exact:true}).selectOption('en');expect((await saved).status()).toBe(200);
  50 |  const url=page.url();await login(page,url);await expect(page.getByRole('combobox',{name:'Job scope',exact:true})).toHaveValue('workspace');await expect(page.getByRole('combobox',{name:'Filter status',exact:true})).toHaveValue('failed');await expect(page.getByRole('region',{name:'Bulk jobs'})).toContainText('5 jobs in scope');
  51 |  let failed=false;await page.route('**/jobs?**',async route=>{if(!failed&&new URL(route.request().url()).searchParams.get('limit')==='20'){failed=true;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({code:'INTERNAL_ERROR',message:'Fixture read failure',request_id:'e0000000-0000-4000-8000-000000000014',retryable:true})});}else await route.continue();});
  52 |  await page.getByRole('combobox',{name:'Filter status',exact:true}).selectOption('completed');await expect(page.getByRole('region',{name:'Bulk jobs'}).getByRole('alert')).toContainText('Service temporarily unavailable');await page.getByRole('button',{name:'Retry loading jobs',exact:true}).click();await expect(page.getByRole('region',{name:'Bulk jobs'})).toContainText('0 jobs in scope');
  53 | });
  54 | 
```