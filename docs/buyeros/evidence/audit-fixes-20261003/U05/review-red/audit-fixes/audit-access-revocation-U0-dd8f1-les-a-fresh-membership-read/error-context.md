# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-access-revocation.spec.ts >> U05 denial during a held access check schedules a fresh membership read
- Location: tests\e2e\audit-access-revocation.spec.ts:83:1

# Error details

```
Error: expect(locator).toHaveCount(expected) failed

Locator:  getByRole('combobox', { name: /^(Project|專案)$/ })
Expected: 0
Received: 1
Timeout:  5000ms

Call log:
  - Expect "toHaveCount" getByRole('combobox', { name: /^(Project|專案)$/ }) with timeout 5000ms
  - waiting for getByRole('combobox', { name: /^(Project|專案)$/ })
    14 × locator resolved to 1 element
       - unexpected value "1"

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
    - generic [ref=f1e19]:
      - region "Workspace selection" [ref=f1e20]:
        - heading "Workspaces" [level=2] [ref=f1e21]
        - generic [ref=f1e22]:
          - text: Workspace
          - combobox "Workspace" [ref=f1e23]:
            - option "Choose workspace"
            - option "E2E fixture workspace" [selected]
            - option "Other U05 fixture"
        - button "Check access again" [ref=f1e24] [cursor=pointer]
        - paragraph [ref=f1e25]: "Role: operator"
      - region "Project selection" [ref=f1e26]:
        - heading "Projects" [level=2] [ref=f1e27]
        - generic [ref=f1e28]:
          - text: Project
          - combobox "Project" [ref=f1e29]:
            - option "Choose project"
            - option "Buyer Fixture Project" [selected]
            - option "Run Fixture Project"
        - generic [ref=f1e30]:
          - button "New project" [ref=f1e31] [cursor=pointer]
          - button "Edit offer" [ref=f1e32] [cursor=pointer]
    - region "Buyer results" [ref=f1e33]:
      - generic [ref=f1e34]:
        - heading "Buyers" [level=2] [ref=f1e35]
        - generic [ref=f1e36]: Loading snapshot...
      - group "Buyer filters" [ref=f1e37]:
        - generic [ref=f1e38]:
          - text: Search buyers
          - textbox "Search buyers" [ref=f1e39]
        - button "Apply filters" [ref=f1e40] [cursor=pointer]
        - generic [ref=f1e41]:
          - text: Fit
          - combobox "Fit filter" [ref=f1e42]:
            - option "Any" [selected]
            - option "Match"
            - option "Needs review"
            - option "Not a match"
        - generic [ref=f1e43]:
          - text: Review
          - combobox "Review filter" [ref=f1e44]:
            - option "Any" [selected]
            - option "Awaiting review"
            - option "Accepted"
            - option "Rejected"
            - option "Needs information"
        - generic [ref=f1e45]:
          - text: Queue
          - combobox "Work queue filter" [ref=f1e46]:
            - option "All" [selected]
            - option "Unassigned"
            - option "Unknown fit"
        - generic [ref=f1e47]:
          - text: Sort
          - combobox "Buyer sort" [ref=f1e48]:
            - option "Name" [selected]
            - option "Best fit"
        - button "Refresh results" [active] [ref=f1e49] [cursor=pointer]
      - alert [ref=f1e50]: "The selected item was not found in this workspace. Request ID: 36ccd812-e886-4b5b-a856-1d189c91d3a8"
      - region "Segmented maintenance" [ref=f1e51]:
        - heading "Segmented maintenance" [level=3] [ref=f1e52]
        - paragraph [ref=f1e53]: This preview freezes all matching IDs and versions, up to 10000. No buyer is changed until you confirm the exact digest.
        - group "Operation" [ref=f1e54]:
          - combobox "Operation" [ref=f1e56]:
            - option "Assign owners" [selected]
            - option "Change list membership"
          - generic [ref=f1e57]:
            - text: Search colleagues
            - textbox "Search colleagues" [ref=f1e58]
          - button "Search" [ref=f1e59] [cursor=pointer]
          - generic [ref=f1e60]:
            - text: Owner
            - combobox "Owner" [ref=f1e61]:
              - option "Clear owner"
              - option "e0000000-0000-4000-8000-000000000002 · e0000000-0000-4000-8000-000000000003" [selected]
              - option "e0000000-0000-4000-8000-000000000004 · e0000000-0000-4000-8000-000000000005"
              - option "e0000000-0000-4000-8000-000000000006 · e0000000-0000-4000-8000-000000000007"
              - option "e0000000-0000-4000-8000-000000000008 · e0000000-0000-4000-8000-000000000009"
          - generic [ref=f1e62]:
            - text: 1–4 / 4
            - button "Previous colleagues" [disabled] [ref=f1e63]
            - button "Next colleagues" [disabled] [ref=f1e64]
        - generic [ref=f1e65]:
          - text: Maintenance reason
          - textbox "Maintenance reason" [ref=f1e66]
        - generic [ref=f1e67]:
          - text: Excluded buyer IDs (one per line)
          - textbox "Excluded buyer IDs (one per line)" [ref=f1e68]
        - button "Preview segmented maintenance" [disabled] [ref=f1e69]
      - region "Buyer lists and saved filters" [ref=f1e70]:
        - heading "Lists and saved filters" [level=3] [ref=f1e71]
        - generic [ref=f1e72]:
          - generic [ref=f1e73]:
            - text: Buyer list
            - combobox "Buyer list" [ref=f1e74]:
              - option "Choose list" [selected]
          - generic [ref=f1e75]:
            - text: List name
            - textbox "List name" [ref=f1e76]
          - button "Create list" [disabled] [ref=f1e77]
          - button "Rename selected list" [disabled] [ref=f1e78]
          - button "Add selected to list" [disabled] [ref=f1e79]
          - button "Remove selected from list" [disabled] [ref=f1e80]
          - button "Show list buyers" [disabled] [ref=f1e81]
        - generic [ref=f1e82]:
          - generic [ref=f1e83]:
            - text: Saved filter
            - combobox "Saved filter" [ref=f1e84]:
              - option "Choose preset" [selected]
          - button "Apply saved filter" [disabled] [ref=f1e85]
          - generic [ref=f1e86]:
            - text: Preset name
            - textbox "Preset name" [ref=f1e87]
          - button "Save current filter" [disabled] [ref=f1e88]
```

# Test source

```ts
  1   | import {expect,test,type Page} from '@playwright/test';
  2   | import {execFile} from 'node:child_process';
  3   | import {promisify} from 'node:util';
  4   | import {resolve} from 'node:path';
  5   | import {signInWorkbench,workspace,project,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';
  6   | const other='e0000000-0000-4000-8000-000000000101';
  7   | const member='e0000000-0000-4000-8000-000000000003';
  8   | async function fixture(action='inspect',script='audit_access_revocation.py'){
  9   |  const cwd=resolve('services/worker');return JSON.parse((await promisify(execFile)(resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python'),[`tests/fixtures/${script}`,action],{cwd,timeout:30_000})).stdout);
  10  | }
  11  | async function changeAccess(page:Page,active=false,roles=['operator']){
  12  |  const response=await page.request.patch(`http://127.0.0.1:8000/v1/workspaces/${workspace}/memberships/${member}`,{headers:{Authorization:'Bearer fixture-admin','If-Match':'"1"','Idempotency-Key':crypto.randomUUID()},data:{active,roles,reason:'U05 fictional access change'}});
  13  |  expect(response.status()).toBe(200);return (await response.json()).data;
  14  | }
  15  | async function denied(page:Page){
  16  |  const headers={Authorization:'Bearer fixture-access'};
  17  |  const read=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/projects`,{headers});
  18  |  expect(read.status()).toBe(404);expect((await read.json()).code).toBe('NOT_FOUND');
  19  |  const write=await page.request.patch(`http://127.0.0.1:8000/v1/workspaces/${workspace}/preferences`,{headers:{...headers,'If-Match':'"1"','Idempotency-Key':crypto.randomUUID()},data:{locale:'zh-HK'}});
  20  |  expect(write.status()).toBe(404);return {read:read.status(),write:write.status()};
  21  | }
  22  | async function cleared(page:Page){
> 23  |  await expect(page.getByRole('combobox',{name:/^(Project|專案)$/})).toHaveCount(0);
      |                                                                   ^ Error: expect(locator).toHaveCount(expected) failed
  24  |  await expect(page.getByRole('combobox',{name:/^(Workspace|工作區)$/})).toHaveValue('');
  25  |  await expect(page.getByRole('region',{name:/^(Buyer results|買家結果)$/})).toHaveCount(0);
  26  |  const url=new URL(page.url());for(const key of ['workspace','project','profile','bulk_job','bulk_manifest','draft','draft_job'])expect(url.searchParams.has(key)).toBe(false);
  27  |  await expect(page.getByRole('button',{name:/^(Sign out|登出)$/})).toBeVisible();
  28  | }
  29  | async function proof(name:string,value:unknown){await test.info().attach(name,{body:JSON.stringify(value,null,2),contentType:'application/json'});}
  30  | test.beforeEach(async({page})=>{await page.addInitScript(()=>localStorage.setItem('buyeros.locale','en'));await resetWorkbenchFixtureRateWindows();await fixture('reset');});
  31  | test.afterEach(async()=>{await fixture('cleanup');});
  32  | 
  33  | for(const locale of ['en','zh-HK'] as const)test(`U05 revoked open-page read clears private scope ${locale}`,async({page})=>{
  34  |  if(locale==='zh-HK')await page.setViewportSize({width:390,height:844});
  35  |  await signInWorkbench(page,true,'access',`/app/discover?workspace=${workspace}&project=${project}`);
  36  |  await page.getByRole('combobox',{name:/^(Language|語言)$/}).first().selectOption(locale);
  37  |  const buyers=page.getByRole('region',{name:/^(Buyer results|買家結果)$/});await expect(buyers.getByRole('checkbox',{name:/^(Select |選取 )/}).first()).toBeVisible();
  38  |  const before=await fixture();const changed=await changeAccess(page);const statuses=await denied(page);
  39  |  const failed=page.waitForResponse(r=>r.url().includes(`/workspaces/${workspace}/`)&&r.status()===404);
  40  |  await buyers.getByRole('button',{name:/^(Refresh results|更新結果)$/}).click();await failed;await cleared(page);
  41  |  await page.getByRole('combobox',{name:/^(Language|語言)$/}).first().selectOption(locale==='en'?'zh-HK':'en');
  42  |  await page.getByRole('button',{name:/^(Check access again|重新檢查存取)$/}).click();await cleared(page);
  43  |  const after=await fixture();expect(after.active).toBe(false);expect(after.version).toBe(2);expect(after.users).toBe(before.users);expect(after.memberships).toBe(before.memberships);
  44  |  await page.getByRole('combobox',{name:/^(Language|語言)$/}).first().selectOption(locale);await expect(page.locator('html')).toHaveAttribute('lang',locale);
  45  |  await proof(`U05 revoked read ${locale}`,{before,changed,statuses,after});await page.screenshot({path:`test-results/u05-revoked-${locale}.png`,fullPage:true});
  46  | });
  47  | 
  48  | test('U05 explicit recheck cancels held pre-withdrawal buyer rows',async({page})=>{
  49  |  await signInWorkbench(page,true,'access',`/app/discover?workspace=${workspace}&project=${project}`);
  50  |  const buyers=page.getByRole('region',{name:'Buyer results',exact:true});await expect(buyers.getByRole('checkbox',{name:/^Select /}).first()).toBeVisible();
  51  |  let release=()=>{},started=()=>{},completed=()=>{};const finished=new Promise<void>(r=>completed=r),held=new Promise<void>(r=>release=r),received=new Promise<void>(r=>started=r);
  52  |  await page.route(`**/v1/workspaces/${workspace}/projects/${project}/buyers?**`,async route=>{const response=await route.fetch();expect(response.status()).toBe(200);started();await held;await route.fulfill({response}).catch(()=>{});completed();});
  53  |  try{await buyers.getByRole('button',{name:'Refresh results',exact:true}).click();await received;await changeAccess(page);
  54  |  await page.getByRole('button',{name:'Check access again',exact:true}).click();await cleared(page);release();await finished;await cleared(page);
  55  |  await expect(page.getByText('Fixture company',{exact:false})).toHaveCount(0);
  56  |  await proof('U05 held rows',{active:(await fixture()).active,old_response_status:200,scope_cleared:true});
  57  |  }finally{release();}
  58  | });
  59  | 
  60  | test('U05 older access check cannot restore withdrawn A after another recheck',async({page})=>{
  61  |  await signInWorkbench(page,true,'access');let release=()=>{},started=()=>{},completed=()=>{},hold=true;
  62  |  const finished=new Promise<void>(r=>completed=r),held=new Promise<void>(r=>release=r),received=new Promise<void>(r=>started=r);
  63  |  await page.route('**/v1/workspaces?**',async route=>{if(!hold)return route.continue();hold=false;const response=await route.fetch();expect(response.status()).toBe(200);started();await held;await route.fulfill({response}).catch(()=>{});completed();});
  64  |  try{await page.getByRole('button',{name:'Check access again',exact:true}).click();await received;await changeAccess(page);
  65  |  await page.getByRole('button',{name:'Check access again',exact:true}).click();await cleared(page);release();await finished;await cleared(page);
  66  |  await expect(page.getByRole('combobox',{name:'Workspace',exact:true}).getByRole('option',{name:'E2E fixture workspace',exact:true})).toHaveCount(0);
  67  |  }finally{release();}
  68  | });
  69  | 
  70  | test('U05 delayed A access result cannot clear current B',async({page})=>{
  71  |  await signInWorkbench(page,true,'access');let release=()=>{},started=()=>{},completed=()=>{},hold=true;
  72  |  const finished=new Promise<void>(r=>completed=r),held=new Promise<void>(r=>release=r),received=new Promise<void>(r=>started=r);
  73  |  await changeAccess(page);
  74  |  await page.route('**/v1/workspaces?**',async route=>{if(!hold)return route.continue();hold=false;const response=await route.fetch();started();await held;await route.fulfill({response}).catch(()=>{});completed();});
  75  |  try{await page.getByRole('button',{name:'Check access again',exact:true}).click();await received;
  76  |  await page.getByRole('combobox',{name:'Workspace',exact:true}).selectOption(other);
  77  |  await expect(page.getByRole('combobox',{name:'Workspace',exact:true})).toHaveValue(other);release();await finished;
  78  |  await expect(page.getByRole('combobox',{name:'Workspace',exact:true})).toHaveValue(other);
  79  |  expect(new URL(page.url()).searchParams.get('workspace')).toBe(other);
  80  |  }finally{release();}
  81  | });
  82  | 
  83  | test('U05 denial during a held access check schedules a fresh membership read',async({page})=>{
  84  |  await signInWorkbench(page,true,'access',`/app/discover?workspace=${workspace}&project=${project}`);
  85  |  const buyers=page.getByRole('region',{name:'Buyer results',exact:true});await expect(buyers.getByRole('checkbox',{name:/^Select /}).first()).toBeVisible();
  86  |  let release=()=>{},started=()=>{},completed=()=>{},hold=true;
  87  |  const held=new Promise<void>(r=>release=r),received=new Promise<void>(r=>started=r),finished=new Promise<void>(r=>completed=r);
  88  |  await page.route('**/v1/workspaces?**',async route=>{if(!hold)return route.continue();hold=false;const response=await route.fetch();expect(response.status()).toBe(200);started();await held;await route.fulfill({response}).catch(()=>{});completed();});
  89  |  try{await page.getByRole('button',{name:'Check access again',exact:true}).click();await received;await changeAccess(page);
  90  |  const denied=page.waitForResponse(r=>r.url().includes(`/workspaces/${workspace}/`)&&r.status()===404);
  91  |  await buyers.getByRole('button',{name:'Refresh results',exact:true}).click();await denied;
  92  |  release();await finished;await cleared(page);
  93  |  await proof('U05 denial while checking',{active:(await fixture()).active,pre_withdrawal_directory:200,scope_cleared:true});
  94  |  }finally{release();}
  95  | });
  96  | 
  97  | test('U05 forbidden save rechecks downgraded role while retaining dirty Unicode draft',async({page})=>{
  98  |  const seeded=await fixture('create','audit_drafts.py');await signInWorkbench(page,true,'access',`/app/outreach?workspace=${workspace}&project=${project}&draft=${seeded.draft}&draft_job=${seeded.job}`);
  99  |  const editor=page.getByRole('region',{name:'Open draft',exact:true});await expect(editor.getByRole('textbox',{name:'Subject',exact:true})).toHaveValue(seeded.subject);
  100 |  await editor.getByRole('textbox',{name:'Subject',exact:true}).fill('未保存主旨🙂');await editor.getByRole('textbox',{name:'Body',exact:true}).fill('保留本地內容🙂');await editor.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');
  101 |  await changeAccess(page,true,['viewer']);const fail=page.waitForResponse(r=>r.request().method()==='PATCH'&&r.url().includes('/drafts/')&&r.status()===403);
  102 |  await editor.getByRole('button',{name:'Save revision',exact:true}).click();await fail;
  103 |  await expect(page.getByText('Role: viewer',{exact:true})).toBeVisible();await expect(page.getByRole('combobox',{name:'Workspace',exact:true})).toHaveValue(workspace);
  104 |  await expect(editor.getByRole('textbox',{name:'Subject',exact:true})).toHaveValue('未保存主旨🙂');await expect(editor.getByRole('textbox',{name:'Body',exact:true})).toHaveValue('保留本地內容🙂');await expect(editor.getByRole('combobox',{name:'Language',exact:true})).toHaveValue('zh-HK');await expect(editor).toHaveAttribute('data-live-unsaved','true');
  105 |  const stored=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${seeded.draft}`,{headers:{Authorization:'Bearer fixture-admin'}});expect(stored.status()).toBe(200);expect((await stored.json()).data.subject).toBe(seeded.subject);
  106 |  await proof('U05 denied write unchanged',{membership:await fixture(),stored:(await stored.json()).data});
  107 | });
  108 | 
  109 | test('U05 revoked save is denied without creating a revision or replaying',async({page})=>{
  110 |  const seeded=await fixture('create','audit_drafts.py');await signInWorkbench(page,true,'access',`/app/outreach?workspace=${workspace}&project=${project}&draft=${seeded.draft}&draft_job=${seeded.job}`);
  111 |  const editor=page.getByRole('region',{name:'Open draft',exact:true});await expect(editor.getByRole('textbox',{name:'Subject',exact:true})).toHaveValue(seeded.subject);
  112 |  await editor.getByRole('textbox',{name:'Subject',exact:true}).fill('未保存主旨🙂');await editor.getByRole('textbox',{name:'Body',exact:true}).fill('保留本地內容🙂');await editor.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');
  113 |  let writes=0;page.on('request',r=>{if(r.method()==='PATCH'&&r.url().includes('/drafts/'))writes++;});
  114 |  await changeAccess(page);const fail=page.waitForResponse(r=>r.request().method()==='PATCH'&&r.url().includes('/drafts/')&&r.status()===404);
  115 |  await editor.getByRole('button',{name:'Save revision',exact:true}).click();await fail;
  116 |  await cleared(page);expect(writes).toBe(1);
  117 |  const stored=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${seeded.draft}`,{headers:{Authorization:'Bearer fixture-admin'}});expect(stored.status()).toBe(200);expect((await stored.json()).data.subject).toBe(seeded.subject);expect((await stored.json()).data.revision_number).toBe(1);
  118 |  await proof('U05 revoked write unchanged',{membership:await fixture(),stored:(await stored.json()).data});
  119 | });
  120 | 
  121 | test('U05 missing job does not revoke an active membership',async({page})=>{
  122 |  let checks=0;page.on('request',r=>{if(new URL(r.url()).pathname==='/v1/workspaces')checks++;});
  123 |  await signInWorkbench(page,true,'access');const before=checks;
```