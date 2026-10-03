# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-bulk-manifest.spec.ts >> B01 B08 B14 100 actual rows require frozen preview and explicit execution
- Location: tests\e2e\audit-bulk-manifest.spec.ts:31:35

# Error details

```
Error: expect(locator).toContainText(expected) failed

Locator: getByRole('region', { name: 'Segmented maintenance', exact: true }).getByRole('region', { name: 'Frozen manifest' })
Expected substring: "count: 100"
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toContainText" getByRole('region', { name: 'Segmented maintenance', exact: true }).getByRole('region', { name: 'Frozen manifest' }) with timeout 5000ms
  - waiting for getByRole('region', { name: 'Segmented maintenance', exact: true }).getByRole('region', { name: 'Frozen manifest' })

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
    - button "Offer"
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
    - paragraph: "Role: operator"
  - region "Project selection":
    - heading "Projects" [level=2]
    - text: Project
    - combobox "Project":
      - option "Choose project"
      - option "Buyer Fixture Project" [selected]
      - option "Run Fixture Project"
    - button "New project"
    - button "Edit offer"
  - region "Buyer results":
    - heading "Buyers" [level=2]
    - text: 100 in snapshot
    - group "Buyer filters":
      - text: Search buyers
      - textbox "Search buyers": Q08 Manifest Fixture
      - button "Apply filters"
      - text: Fit
      - combobox "Fit filter":
        - option "Any" [selected]
        - option "Match"
        - option "Needs review"
        - option "Not a match"
      - text: Review
      - combobox "Review filter":
        - option "Any" [selected]
        - option "Awaiting review"
        - option "Accepted"
        - option "Rejected"
        - option "Needs information"
      - text: Queue
      - combobox "Work queue filter":
        - option "All" [selected]
        - option "Unassigned"
        - option "Unknown fit"
      - text: Sort
      - combobox "Buyer sort":
        - option "Name" [selected]
        - option "Best fit"
      - button "Refresh results"
    - button "Select this page"
    - button "Select all filtered"
    - button "Clear selection"
    - text: 0 selected explicitly
    - checkbox "Select Q08 Manifest Fixture 00000"
    - text: Q08 Manifest Fixture 00000
    - paragraph: Fit not assessed · Not reviewed · No note
    - button "Details"
    - checkbox "Select Q08 Manifest Fixture 00001"
    - text: Q08 Manifest Fixture 00001
    - paragraph: Fit not assessed · Not reviewed · No note
    - button "Details"
    - checkbox "Select Q08 Manifest Fixture 00002"
    - text: Q08 Manifest Fixture 00002
    - paragraph: Fit not assessed · Not reviewed · No note
    - button "Details"
    - checkbox "Select Q08 Manifest Fixture 00003"
    - text: Q08 Manifest Fixture 00003
    - paragraph: Fit not assessed · Not reviewed · No note
    - button "Details"
    - checkbox "Select Q08 Manifest Fixture 00004"
    - text: Q08 Manifest Fixture 00004
    - paragraph: Fit not assessed · Not reviewed · No note
    - button "Details"
    - checkbox "Select Q08 Manifest Fixture 00005"
    - text: Q08 Manifest Fixture 00005
    - paragraph: Fit not assessed · Not reviewed · No note
    - button "Details"
    - checkbox "Select Q08 Manifest Fixture 00006"
    - text: Q08 Manifest Fixture 00006
    - paragraph: Fit not assessed · Not reviewed · No note
    - button "Details"
    - checkbox "Select Q08 Manifest Fixture 00007"
    - text: Q08 Manifest Fixture 00007
    - paragraph: Fit not assessed · Not reviewed · No note
    - button "Details"
    - checkbox "Select Q08 Manifest Fixture 00008"
    - text: Q08 Manifest Fixture 00008
    - paragraph: Fit not assessed · Not reviewed · No note
    - button "Details"
    - checkbox "Select Q08 Manifest Fixture 00009"
    - text: Q08 Manifest Fixture 00009
    - paragraph: Fit not assessed · Not reviewed · No note
    - button "Details"
    - checkbox "Select Q08 Manifest Fixture 00010"
    - text: Q08 Manifest Fixture 00010
    - paragraph: Fit not assessed · Not reviewed · No note
    - button "Details"
    - checkbox "Select Q08 Manifest Fixture 00011"
    - text: Q08 Manifest Fixture 00011
    - paragraph: Fit not assessed · Not reviewed · No note
    - button "Details"
    - button "Previous page" [disabled]
    - text: Rows 1–12 of 100
    - button "Next page"
    - text: Rows per page
    - combobox "Rows per page":
      - option "8"
      - option "12" [selected]
      - option "24"
    - region "Authorized export":
      - heading "Authorized export" [level=3]
      - paragraph: Only current policy and, for addressed drafts, current exact approval allow content.
      - paragraph: Copy and download never send a message.
      - paragraph: "Selected scope: No selection"
      - checkbox "Include eligible contact data"
      - text: Include eligible contact data
      - paragraph: Company-only CSV
      - button "Prepare export" [disabled]
    - region "Assign buyer owners":
      - heading "Assign buyer owners" [level=3]
      - paragraph: "Preview: 0 selected buyers; each current version and owner membership is checked again before commit."
      - paragraph: "Scope: e0000000-0000-4000-8000-000000000001 / e1000000-0000-4000-8000-000000000001"
      - paragraph: "Owner: Me"
      - text: Owner
      - combobox "Owner":
        - option "No owner"
        - option "Me" [selected]
        - option "e0000000-0000-4000-8000-000000000004 · e0000000-0000-4000-8000-000000000004"
        - option "e0000000-0000-4000-8000-000000000006 · e0000000-0000-4000-8000-000000000006"
        - option "e0000000-0000-4000-8000-000000000008 · e0000000-0000-4000-8000-000000000008"
      - text: Search colleagues
      - textbox "Search colleagues"
      - button "Search"
      - text: 1–4 / 4
      - button "Previous colleagues" [disabled]
      - button "Next colleagues" [disabled]
      - text: Assignment reason
      - textbox "Assignment reason"
      - paragraph: "Reason:"
      - checkbox "Confirm owner assignment" [disabled]
      - text: Confirm this preview
      - button "Assign selected buyers" [disabled]
    - region "Segmented maintenance":
      - heading "Segmented maintenance" [level=3]
      - paragraph: This preview freezes all matching IDs and versions, up to 10000. No buyer is changed until you confirm the exact digest.
      - group "Operation":
        - text: Operation
        - combobox "Operation" [disabled]:
          - option "Assign owners" [disabled] [selected]
          - option "Change list membership" [disabled]
        - text: Search colleagues
        - textbox "Search colleagues" [disabled]
        - button "Search" [disabled]
        - text: Owner
        - combobox "Owner" [disabled]:
          - option "Clear owner" [disabled]
          - option "e0000000-0000-4000-8000-000000000002 · e0000000-0000-4000-8000-000000000003" [disabled] [selected]
          - option "e0000000-0000-4000-8000-000000000004 · e0000000-0000-4000-8000-000000000005" [disabled]
          - option "e0000000-0000-4000-8000-000000000006 · e0000000-0000-4000-8000-000000000007" [disabled]
          - option "e0000000-0000-4000-8000-000000000008 · e0000000-0000-4000-8000-000000000009" [disabled]
        - text: 1–4 / 4
        - button "Previous colleagues" [disabled]
        - button "Next colleagues" [disabled]
      - text: Maintenance reason
      - textbox "Maintenance reason" [disabled]: Q08 human reviewed maintenance
      - text: Excluded buyer IDs (one per line)
      - textbox "Excluded buyer IDs (one per line)" [disabled]
      - heading "Frozen manifest" [level=4]
      - paragraph: "511e8e3d-3a1b-4706-b68c-eb2132a43479 · ready · count: 100"
      - paragraph: "digest: 7534fe4ba78d4518c41c9dfa1857509317ca50be4e6863417d8c9ac15eabf94c"
      - paragraph: "expires_at: 2026-10-03T14:07:49.682205+00:00"
      - paragraph: Assign owners
      - text: "{ \"target\": { \"owner_membership_id\": \"e0000000-0000-4000-8000-000000000003\" }, \"filters\": { \"q\": \"Q08 Manifest Fixture\" }, \"reason\": \"Q08 human reviewed maintenance\", \"excluded_ids\": [] }"
      - paragraph: Read the count, operation, target, reason and filters before confirming.
      - checkbox "Confirm exact manifest"
      - text: Confirm exact manifest
      - button "Execute confirmed manifest" [disabled]
      - button "Recheck manifest"
      - button "Start a new preview"
    - region "Buyer lists and saved filters":
      - heading "Lists and saved filters" [level=3]
      - text: Buyer list
      - combobox "Buyer list":
        - option "Choose list" [selected]
      - text: List name
      - textbox "List name"
      - button "Create list" [disabled]
      - button "Rename selected list" [disabled]
      - button "Add selected to list" [disabled]
      - button "Remove selected from list" [disabled]
      - button "Show list buyers" [disabled]
      - text: Saved filter
      - combobox "Saved filter":
        - option "Choose preset" [selected]
      - button "Apply saved filter" [disabled]
      - text: Preset name
      - textbox "Preset name"
      - button "Save current filter" [disabled]
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
> 24 |  const data=(await response.json()).data;await expect(panel.getByRole('region',{name:'Frozen manifest'})).toContainText(`count: ${data.count}`);return data as {id:string;count:number;digest:string;version:number};
     |                                                                                                           ^ Error: expect(locator).toContainText(expected) failed
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
  67 |  await page.unroute(`**${root}`);await page.setViewportSize({width:390,height:844});await page.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');const zh=page.getByRole('region',{name:'分段維護'});await expect(zh).toBeVisible();await zh.getByRole('button',{name:'重試同一預覽'}).click();await expect(zh.getByRole('region',{name:'已凍結維護清單'})).toBeVisible();await expect(zh.getByRole('button',{name:'執行已確認維護清單'})).toBeDisabled();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);await page.screenshot({path:'test-results/q08-zh-mobile.png',fullPage:true});
  68 | });
  69 | 
```