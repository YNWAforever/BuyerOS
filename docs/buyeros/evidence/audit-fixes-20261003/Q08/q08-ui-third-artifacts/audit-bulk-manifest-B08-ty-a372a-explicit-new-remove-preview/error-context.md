# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-bulk-manifest.spec.ts >> B08 typed list target supports confirmed add and explicit new remove preview
- Location: tests\e2e\audit-bulk-manifest.spec.ts:74:1

# Error details

```
Test timeout of 60000ms exceeded.
```

```
Error: locator.fill: Test timeout of 60000ms exceeded.
Call log:
  - waiting for getByRole('region', { name: 'Segmented maintenance', exact: true }).getByRole('textbox', { name: 'Maintenance reason', exact: true })
    - locator resolved to <input disabled maxlength="2000" aria-label="Maintenance reason" value="Q08 human reviewed maintenance"/>
    - fill("Q08 human reviewed maintenance")
  - attempting fill action
    2 × waiting for element to be visible, enabled and editable
      - element is not enabled
    - retrying fill action
    - waiting 20ms
    2 × waiting for element to be visible, enabled and editable
      - element is not enabled
    - retrying fill action
      - waiting 100ms
    84 × waiting for element to be visible, enabled and editable
       - element is not enabled
     - retrying fill action
       - waiting 500ms

```

# Page snapshot

```yaml
- main [ref=f1e2]:
  - generic [ref=f1e3]:
    - generic [ref=f1e4]:
      - generic [ref=f1e5]: FIMMICK BuyerOS
      - generic [ref=f1e6]: Live workspace
      - generic [ref=f1e7]:
        - text: Language
        - combobox "Language" [ref=f1e8]:
          - option "English" [selected]
          - option "繁體中文"
      - button "Sign out" [ref=f1e9] [cursor=pointer]
    - navigation "BuyerOS sections" [ref=f1e10]:
      - button "Overview" [ref=f1e11] [cursor=pointer]
      - button "Offer" [ref=f1e12] [cursor=pointer]
      - button "Buyers" [ref=f1e13] [cursor=pointer]
      - button "Results" [ref=f1e14] [cursor=pointer]
      - button "Research runs" [ref=f1e15] [cursor=pointer]
      - button "Drafts" [ref=f1e16] [cursor=pointer]
      - button "Settings" [ref=f1e17] [cursor=pointer]
      - button "Operations" [ref=f1e18] [cursor=pointer]
    - region "Workspace selection" [ref=f1e19]:
      - heading "Workspaces" [level=2] [ref=f1e20]
      - generic [ref=f1e21]:
        - text: Workspace
        - combobox "Workspace" [ref=f1e22]:
          - option "Choose workspace"
          - option "E2E fixture workspace" [selected]
          - option "Other audit fixture"
      - paragraph [ref=f1e23]: "Role: operator"
    - region "Project selection" [ref=f1e24]:
      - heading "Projects" [level=2] [ref=f1e25]
      - generic [ref=f1e26]:
        - text: Project
        - combobox "Project" [ref=f1e27]:
          - option "Choose project"
          - option "Buyer Fixture Project" [selected]
          - option "Run Fixture Project"
      - generic [ref=f1e28]:
        - button "New project" [ref=f1e29] [cursor=pointer]
        - button "Edit offer" [ref=f1e30] [cursor=pointer]
    - region "Buyer results" [ref=f1e31]:
      - generic [ref=f1e32]:
        - heading "Buyers" [level=2] [ref=f1e33]
        - generic [ref=f1e34]: 100 in snapshot
      - group "Buyer filters" [ref=f1e35]:
        - generic [ref=f1e36]:
          - text: Search buyers
          - textbox "Search buyers" [ref=f1e37]: Q08 Manifest Fixture
        - button "Apply filters" [ref=f1e38] [cursor=pointer]
        - generic [ref=f1e39]:
          - text: Fit
          - combobox "Fit filter" [ref=f1e40]:
            - option "Any" [selected]
            - option "Match"
            - option "Needs review"
            - option "Not a match"
        - generic [ref=f1e41]:
          - text: Review
          - combobox "Review filter" [ref=f1e42]:
            - option "Any" [selected]
            - option "Awaiting review"
            - option "Accepted"
            - option "Rejected"
            - option "Needs information"
        - generic [ref=f1e43]:
          - text: Queue
          - combobox "Work queue filter" [ref=f1e44]:
            - option "All" [selected]
            - option "Unassigned"
            - option "Unknown fit"
        - generic [ref=f1e45]:
          - text: Sort
          - combobox "Buyer sort" [ref=f1e46]:
            - option "Name" [selected]
            - option "Best fit"
        - button "Refresh results" [ref=f1e47] [cursor=pointer]
      - generic [ref=f1e48]:
        - button "Select this page" [ref=f1e49] [cursor=pointer]
        - button "Select all filtered" [ref=f1e50] [cursor=pointer]
        - button "Clear selection" [ref=f1e51] [cursor=pointer]
        - generic [ref=f1e52]: 0 selected explicitly
      - generic [ref=f1e53]:
        - checkbox "Select Q08 Manifest Fixture 00000" [ref=f1e54]
        - generic [ref=f1e55]:
          - text: Q08 Manifest Fixture 00000
          - paragraph [ref=f1e56]: Fit not assessed · Not reviewed · No note
        - button "Details" [ref=f1e57] [cursor=pointer]
      - generic [ref=f1e58]:
        - checkbox "Select Q08 Manifest Fixture 00001" [ref=f1e59]
        - generic [ref=f1e60]:
          - text: Q08 Manifest Fixture 00001
          - paragraph [ref=f1e61]: Fit not assessed · Not reviewed · No note
        - button "Details" [ref=f1e62] [cursor=pointer]
      - generic [ref=f1e63]:
        - checkbox "Select Q08 Manifest Fixture 00002" [ref=f1e64]
        - generic [ref=f1e65]:
          - text: Q08 Manifest Fixture 00002
          - paragraph [ref=f1e66]: Fit not assessed · Not reviewed · No note
        - button "Details" [ref=f1e67] [cursor=pointer]
      - generic [ref=f1e68]:
        - checkbox "Select Q08 Manifest Fixture 00003" [ref=f1e69]
        - generic [ref=f1e70]:
          - text: Q08 Manifest Fixture 00003
          - paragraph [ref=f1e71]: Fit not assessed · Not reviewed · No note
        - button "Details" [ref=f1e72] [cursor=pointer]
      - generic [ref=f1e73]:
        - checkbox "Select Q08 Manifest Fixture 00004" [ref=f1e74]
        - generic [ref=f1e75]:
          - text: Q08 Manifest Fixture 00004
          - paragraph [ref=f1e76]: Fit not assessed · Not reviewed · No note
        - button "Details" [ref=f1e77] [cursor=pointer]
      - generic [ref=f1e78]:
        - checkbox "Select Q08 Manifest Fixture 00005" [ref=f1e79]
        - generic [ref=f1e80]:
          - text: Q08 Manifest Fixture 00005
          - paragraph [ref=f1e81]: Fit not assessed · Not reviewed · No note
        - button "Details" [ref=f1e82] [cursor=pointer]
      - generic [ref=f1e83]:
        - checkbox "Select Q08 Manifest Fixture 00006" [ref=f1e84]
        - generic [ref=f1e85]:
          - text: Q08 Manifest Fixture 00006
          - paragraph [ref=f1e86]: Fit not assessed · Not reviewed · No note
        - button "Details" [ref=f1e87] [cursor=pointer]
      - generic [ref=f1e88]:
        - checkbox "Select Q08 Manifest Fixture 00007" [ref=f1e89]
        - generic [ref=f1e90]:
          - text: Q08 Manifest Fixture 00007
          - paragraph [ref=f1e91]: Fit not assessed · Not reviewed · No note
        - button "Details" [ref=f1e92] [cursor=pointer]
      - generic [ref=f1e93]:
        - checkbox "Select Q08 Manifest Fixture 00008" [ref=f1e94]
        - generic [ref=f1e95]:
          - text: Q08 Manifest Fixture 00008
          - paragraph [ref=f1e96]: Fit not assessed · Not reviewed · No note
        - button "Details" [ref=f1e97] [cursor=pointer]
      - generic [ref=f1e98]:
        - checkbox "Select Q08 Manifest Fixture 00009" [ref=f1e99]
        - generic [ref=f1e100]:
          - text: Q08 Manifest Fixture 00009
          - paragraph [ref=f1e101]: Fit not assessed · Not reviewed · No note
        - button "Details" [ref=f1e102] [cursor=pointer]
      - generic [ref=f1e103]:
        - checkbox "Select Q08 Manifest Fixture 00010" [ref=f1e104]
        - generic [ref=f1e105]:
          - text: Q08 Manifest Fixture 00010
          - paragraph [ref=f1e106]: Fit not assessed · Not reviewed · No note
        - button "Details" [ref=f1e107] [cursor=pointer]
      - generic [ref=f1e108]:
        - checkbox "Select Q08 Manifest Fixture 00011" [ref=f1e109]
        - generic [ref=f1e110]:
          - text: Q08 Manifest Fixture 00011
          - paragraph [ref=f1e111]: Fit not assessed · Not reviewed · No note
        - button "Details" [ref=f1e112] [cursor=pointer]
      - generic [ref=f1e113]:
        - generic [ref=f1e114]:
          - button "Previous page" [disabled] [ref=f1e115]
          - generic [ref=f1e116]: Rows 1–12 of 100
          - button "Next page" [ref=f1e117] [cursor=pointer]
        - generic [ref=f1e118]:
          - text: Rows per page
          - combobox "Rows per page" [ref=f1e119]:
            - option "8"
            - option "12" [selected]
            - option "24"
      - region "Authorized export" [ref=f1e120]:
        - heading "Authorized export" [level=3] [ref=f1e121]
        - paragraph [ref=f1e122]: Only current policy and, for addressed drafts, current exact approval allow content.
        - paragraph [ref=f1e123]: Copy and download never send a message.
        - paragraph [ref=f1e124]: "Selected scope: No selection"
        - generic [ref=f1e125]:
          - checkbox "Include eligible contact data" [ref=f1e126]
          - text: Include eligible contact data
        - paragraph [ref=f1e127]: Company-only CSV
        - button "Prepare export" [disabled] [ref=f1e129]
      - region "Assign buyer owners" [ref=f1e130]:
        - heading "Assign buyer owners" [level=3] [ref=f1e131]
        - paragraph [ref=f1e132]: "Preview: 0 selected buyers; each current version and owner membership is checked again before commit."
        - paragraph [ref=f1e133]: "Scope: e0000000-0000-4000-8000-000000000001 / e1000000-0000-4000-8000-000000000001"
        - paragraph [ref=f1e134]: "Owner: Me"
        - generic [ref=f1e135]:
          - text: Owner
          - combobox "Owner" [ref=f1e136]:
            - option "No owner"
            - option "Me" [selected]
            - option "e0000000-0000-4000-8000-000000000004 · e0000000-0000-4000-8000-000000000004"
            - option "e0000000-0000-4000-8000-000000000006 · e0000000-0000-4000-8000-000000000006"
            - option "e0000000-0000-4000-8000-000000000008 · e0000000-0000-4000-8000-000000000008"
        - generic [ref=f1e137]:
          - generic [ref=f1e138]:
            - text: Search colleagues
            - textbox "Search colleagues" [ref=f1e139]
          - button "Search" [ref=f1e140] [cursor=pointer]
        - generic [ref=f1e141]:
          - generic [ref=f1e142]: 1–4 / 4
          - button "Previous colleagues" [disabled] [ref=f1e143]
          - button "Next colleagues" [disabled] [ref=f1e144]
        - generic [ref=f1e145]:
          - text: Assignment reason
          - textbox "Assignment reason" [ref=f1e146]
        - paragraph [ref=f1e147]: "Reason:"
        - generic [ref=f1e148]:
          - generic [ref=f1e149]:
            - checkbox "Confirm owner assignment" [disabled] [ref=f1e150]
            - text: Confirm this preview
          - button "Assign selected buyers" [disabled] [ref=f1e151]
      - region "Segmented maintenance" [ref=f1e152]:
        - heading "Segmented maintenance" [level=3] [ref=f1e153]
        - paragraph [ref=f1e154]: This preview freezes all matching IDs and versions, up to 10000. No buyer is changed until you confirm the exact digest.
        - group "Operation" [ref=f1e155]:
          - combobox "Operation" [disabled] [ref=f1e157]:
            - option "Assign owners" [disabled]
            - option "Change list membership" [disabled] [selected]
          - generic [ref=f1e158]:
            - text: Target list
            - combobox "Target list" [disabled] [ref=f1e159]:
              - option "Choose list" [disabled]
              - option "Q08 reviewed list · 57907720-34ac-40ca-9f0f-1de0071fef6c" [disabled] [selected]
          - generic [ref=f1e160]:
            - text: List change
            - combobox "List change" [disabled] [ref=f1e161]:
              - option "add" [disabled]
              - option "remove" [disabled] [selected]
          - button "Reload lists" [disabled] [ref=f1e162]
          - generic [ref=f1e163]:
            - text: 1–1 / 1
            - button "Previous lists" [disabled] [ref=f1e164]
            - button "Next lists" [disabled] [ref=f1e165]
        - generic [ref=f1e166]:
          - text: Maintenance reason
          - textbox "Maintenance reason" [disabled] [ref=f1e167]: Q08 human reviewed maintenance
        - generic [ref=f1e168]:
          - text: Excluded buyer IDs (one per line)
          - textbox "Excluded buyer IDs (one per line)" [disabled] [ref=f1e169]
        - region "Frozen manifest" [ref=f1e170]:
          - heading "Frozen manifest" [level=4] [ref=f1e171]
          - paragraph [ref=f1e172]: "52450049-c5c6-4c06-b5af-a01c064da9e4 · executed · count: 100"
          - paragraph [ref=f1e173]: "digest: 7745d5a45e88858229515a5b4bbf23046f2142e33319f06f86987b475f7f69a7"
          - paragraph [ref=f1e174]: "expires_at: 2026-10-03T14:26:37.052767+00:00"
          - paragraph [ref=f1e175]: Change list membership
          - generic [ref=f1e176]: "{ \"target\": { \"list_id\": \"57907720-34ac-40ca-9f0f-1de0071fef6c\", \"operation\": \"add\" }, \"filters\": { \"q\": \"Q08 Manifest Fixture\" }, \"reason\": \"Q08 human reviewed maintenance\", \"excluded_ids\": [] }"
          - paragraph [ref=f1e177]: Read the count, operation, target, reason and filters before confirming.
          - generic [ref=f1e178]:
            - checkbox "Confirm exact manifest" [disabled] [ref=f1e179]
            - text: Confirm exact manifest
          - button "Execute confirmed manifest" [disabled] [ref=f1e180]
          - button "Recheck manifest" [ref=f1e181] [cursor=pointer]
        - button "Start a new preview" [ref=f1e182] [cursor=pointer]
      - region "Buyer lists and saved filters" [ref=f1e183]:
        - heading "Lists and saved filters" [level=3] [ref=f1e184]
        - status [ref=f1e185]: Created list Q08 reviewed list
        - generic [ref=f1e186]:
          - generic [ref=f1e187]:
            - text: Buyer list
            - combobox "Buyer list" [ref=f1e188]:
              - option "Choose list"
              - option "Q08 reviewed list (0)" [selected]
          - generic [ref=f1e189]:
            - text: List name
            - textbox "List name" [ref=f1e190]
          - button "Create list" [disabled] [ref=f1e191]
          - button "Rename selected list" [disabled] [ref=f1e192]
          - button "Add selected to list" [disabled] [ref=f1e193]
          - button "Remove selected from list" [disabled] [ref=f1e194]
          - button "Show list buyers" [ref=f1e195] [cursor=pointer]
        - generic [ref=f1e196]:
          - generic [ref=f1e197]:
            - text: Saved filter
            - combobox "Saved filter" [ref=f1e198]:
              - option "Choose preset" [selected]
          - button "Apply saved filter" [disabled] [ref=f1e199]
          - generic [ref=f1e200]:
            - text: Preset name
            - textbox "Preset name" [ref=f1e201]
          - button "Save current filter" [disabled] [ref=f1e202]
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
> 21 |  await panel.getByRole('textbox',{name:'Maintenance reason',exact:true}).fill('Q08 human reviewed maintenance');
     |                                                                          ^ Error: locator.fill: Test timeout of 60000ms exceeded.
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
  52 |  await panel.getByRole('checkbox',{name:'Confirm exact manifest'}).check();await panel.getByRole('button',{name:'Execute confirmed manifest'}).click();await expect(panel.getByRole('alert')).toBeVisible();await expect(panel.getByRole('button',{name:'Start a new preview'})).toBeDisabled();await panel.getByRole('button',{name:'Execute confirmed manifest'}).click();await expect(page.getByRole('region',{name:'Bulk job progress'})).toBeVisible();expect(executions).toHaveLength(2);expect(executions[1]).toEqual(executions[0]);
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
  67 |  await page.getByRole('combobox',{name:'Project',exact:true}).selectOption(project);await page.getByRole('button',{name:'Buyers',exact:true}).click();await page.unroute(`**${root}`);await page.setViewportSize({width:390,height:844});await page.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');const zh=page.getByRole('region',{name:'分段批量維護'});await expect(zh).toBeVisible();await zh.getByRole('button',{name:'重試同一預覽'}).click();await expect(zh.getByRole('region',{name:'已凍結維護清單'})).toBeVisible();await expect(zh.getByRole('button',{name:'執行已確認維護清單'})).toBeDisabled();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);await page.screenshot({path:'test-results/q08-zh-mobile.png',fullPage:true});
  68 | });
  69 | 
  70 | test('B01 reviewer executes current fit-bound review while operator cannot select review',async({page})=>{
  71 |  await fixture('seed','101');await fixture('assess');const panel=await open(page,'reviewer');await panel.getByRole('combobox',{name:'Operation',exact:true}).selectOption('reviewBuyers');const manifest=await preview(page,panel),response=await execute(page,panel,manifest.id);expect(response.status()).toBe(202);const job=(await response.json()).data;expect((await fixture('drain',job.id)).total).toBe(101);
  72 |  const progress=page.getByRole('region',{name:'Bulk job progress'});await progress.getByRole('button',{name:'Refresh job'}).click();await expect(progress).toContainText('101 updated');await page.screenshot({path:'test-results/q08-review-en.png',fullPage:true});
  73 | });
  74 | test('B08 typed list target supports confirmed add and explicit new remove preview',async({page})=>{
  75 |  await fixture('seed','100');const panel=await open(page),management=page.getByRole('region',{name:'Buyer lists and saved filters'});
  76 |  await management.getByRole('textbox',{name:'List name'}).fill('Q08 reviewed list');const created=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/lists'));await management.getByRole('button',{name:'Create list',exact:true}).click();const list=(await (await created).json()).data;
  77 |  await panel.getByRole('combobox',{name:'Operation',exact:true}).selectOption('changeListMemberships');await panel.getByRole('button',{name:'Reload lists'}).click();await expect(panel.getByRole('combobox',{name:'Target list'}).locator('option',{hasText:'Q08 reviewed list'})).toBeAttached();await panel.getByRole('combobox',{name:'Target list'}).selectOption(list.id);
  78 |  const first=await preview(page,panel),added=await execute(page,panel,first.id);expect(added.status()).toBe(200);expect((await added.json()).data.updated).toBe(100);
  79 |  await panel.getByRole('button',{name:'Start a new preview'}).click();await panel.getByRole('combobox',{name:'List change'}).selectOption('remove');const second=await preview(page,panel);expect(second.digest).not.toBe(first.digest);const removed=await execute(page,panel,second.id);expect(removed.status()).toBe(200);expect((await removed.json()).data.updated).toBe(100);expect((await fixture('inspect')).buyers.every(b=>b.version===1&&b.owner===null)).toBe(true);
  80 | });
  81 | 
```