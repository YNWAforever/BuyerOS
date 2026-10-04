# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-access-revocation.spec.ts >> U05 revoked open-page read clears private scope en
- Location: tests\e2e\audit-access-revocation.spec.ts:33:45

# Error details

```
Test timeout of 60000ms exceeded.
```

```
Error: page.waitForResponse: Test timeout of 60000ms exceeded.
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
        - paragraph [ref=f1e24]: "Role: operator"
      - region "Project selection" [ref=f1e25]:
        - heading "Projects" [level=2] [ref=f1e26]
        - generic [ref=f1e27]:
          - text: Project
          - combobox "Project" [ref=f1e28]:
            - option "Choose project"
            - option "Buyer Fixture Project" [selected]
            - option "Run Fixture Project"
        - generic [ref=f1e29]:
          - button "New project" [ref=f1e30] [cursor=pointer]
          - button "Edit offer" [ref=f1e31] [cursor=pointer]
    - region "Buyer results" [ref=f1e32]:
      - generic [ref=f1e33]:
        - heading "Buyers" [level=2] [ref=f1e34]
        - generic [ref=f1e35]: Loading snapshot...
      - group "Buyer filters" [ref=f1e36]:
        - generic [ref=f1e37]:
          - text: Search buyers
          - textbox "Search buyers" [ref=f1e38]
        - button "Apply filters" [ref=f1e39] [cursor=pointer]
        - generic [ref=f1e40]:
          - text: Fit
          - combobox "Fit filter" [ref=f1e41]:
            - option "Any" [selected]
            - option "Match"
            - option "Needs review"
            - option "Not a match"
        - generic [ref=f1e42]:
          - text: Review
          - combobox "Review filter" [ref=f1e43]:
            - option "Any" [selected]
            - option "Awaiting review"
            - option "Accepted"
            - option "Rejected"
            - option "Needs information"
        - generic [ref=f1e44]:
          - text: Queue
          - combobox "Work queue filter" [ref=f1e45]:
            - option "All" [selected]
            - option "Unassigned"
            - option "Unknown fit"
        - generic [ref=f1e46]:
          - text: Sort
          - combobox "Buyer sort" [ref=f1e47]:
            - option "Name" [selected]
            - option "Best fit"
        - button "Refresh results" [active] [ref=f1e48] [cursor=pointer]
      - alert [ref=f1e49]: "The selected item was not found in this workspace. Request ID: 44430ba4-4532-4cd8-b79f-25b615409e9a"
      - region "Segmented maintenance" [ref=f1e50]:
        - heading "Segmented maintenance" [level=3] [ref=f1e51]
        - paragraph [ref=f1e52]: This preview freezes all matching IDs and versions, up to 10000. No buyer is changed until you confirm the exact digest.
        - group "Operation" [ref=f1e53]:
          - combobox "Operation" [ref=f1e55]:
            - option "Assign owners" [selected]
            - option "Change list membership"
          - generic [ref=f1e56]:
            - text: Search colleagues
            - textbox "Search colleagues" [ref=f1e57]
          - button "Search" [ref=f1e58] [cursor=pointer]
          - generic [ref=f1e59]:
            - text: Owner
            - combobox "Owner" [ref=f1e60]:
              - option "Clear owner"
              - option "e0000000-0000-4000-8000-000000000002 · e0000000-0000-4000-8000-000000000003" [selected]
              - option "e0000000-0000-4000-8000-000000000004 · e0000000-0000-4000-8000-000000000005"
              - option "e0000000-0000-4000-8000-000000000006 · e0000000-0000-4000-8000-000000000007"
              - option "e0000000-0000-4000-8000-000000000008 · e0000000-0000-4000-8000-000000000009"
          - generic [ref=f1e61]:
            - text: 1–4 / 4
            - button "Previous colleagues" [disabled] [ref=f1e62]
            - button "Next colleagues" [disabled] [ref=f1e63]
        - generic [ref=f1e64]:
          - text: Maintenance reason
          - textbox "Maintenance reason" [ref=f1e65]
        - generic [ref=f1e66]:
          - text: Excluded buyer IDs (one per line)
          - textbox "Excluded buyer IDs (one per line)" [ref=f1e67]
        - button "Preview segmented maintenance" [disabled] [ref=f1e68]
      - region "Buyer lists and saved filters" [ref=f1e69]:
        - heading "Lists and saved filters" [level=3] [ref=f1e70]
        - generic [ref=f1e71]:
          - generic [ref=f1e72]:
            - text: Buyer list
            - combobox "Buyer list" [ref=f1e73]:
              - option "Choose list" [selected]
          - generic [ref=f1e74]:
            - text: List name
            - textbox "List name" [ref=f1e75]
          - button "Create list" [disabled] [ref=f1e76]
          - button "Rename selected list" [disabled] [ref=f1e77]
          - button "Add selected to list" [disabled] [ref=f1e78]
          - button "Remove selected from list" [disabled] [ref=f1e79]
          - button "Show list buyers" [disabled] [ref=f1e80]
        - generic [ref=f1e81]:
          - generic [ref=f1e82]:
            - text: Saved filter
            - combobox "Saved filter" [ref=f1e83]:
              - option "Choose preset" [selected]
          - button "Apply saved filter" [disabled] [ref=f1e84]
          - generic [ref=f1e85]:
            - text: Preset name
            - textbox "Preset name" [ref=f1e86]
          - button "Save current filter" [disabled] [ref=f1e87]
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
  23  |  await expect(page.getByRole('combobox',{name:/^(Project|專案)$/})).toHaveCount(0);
  24  |  await expect(page.getByRole('combobox',{name:/^(Workspace|工作空間)$/})).toHaveValue('');
  25  |  await expect(page.getByRole('region',{name:/^(Buyer results|買家結果)$/})).toHaveCount(0);
  26  |  const url=new URL(page.url());for(const key of ['workspace','project','profile'])expect(url.searchParams.has(key)).toBe(false);
  27  |  await expect(page.getByRole('button',{name:/^(Sign out|登出)$/})).toBeVisible();
  28  | }
  29  | async function proof(name:string,value:unknown){await test.info().attach(name,{body:JSON.stringify(value,null,2),contentType:'application/json'});}
  30  | test.beforeEach(async()=>{await resetWorkbenchFixtureRateWindows();await fixture('reset');});
  31  | test.afterEach(async()=>{await fixture('reset');});
  32  | 
  33  | for(const locale of ['en','zh-HK'] as const)test(`U05 revoked open-page read clears private scope ${locale}`,async({page})=>{
  34  |  if(locale==='zh-HK')await page.setViewportSize({width:390,height:844});
  35  |  await signInWorkbench(page,true,'access',`/app/discover?workspace=${workspace}&project=${project}`);
  36  |  await page.getByRole('combobox',{name:/^(Language|語言)$/}).first().selectOption(locale);
  37  |  const buyers=page.getByRole('region',{name:/^(Buyer results|買家結果)$/});await expect(buyers.getByRole('checkbox',{name:/^(Select |選取 )/}).first()).toBeVisible();
  38  |  const before=await fixture();const changed=await changeAccess(page);const statuses=await denied(page);
> 39  |  const failed=page.waitForResponse(r=>r.request().method()==='GET'&&r.url().includes(`/workspaces/${workspace}/`)&&r.status()===404);
      |                    ^ Error: page.waitForResponse: Test timeout of 60000ms exceeded.
  40  |  await buyers.getByRole('button',{name:/^(Refresh results|更新結果)$/}).click();await failed;await cleared(page);
  41  |  await page.getByRole('combobox',{name:/^(Language|語言)$/}).first().selectOption(locale==='en'?'zh-HK':'en');
  42  |  await page.getByRole('button',{name:/^(Check access again|重新檢查存取)$/}).click();await cleared(page);
  43  |  const after=await fixture();expect(after.active).toBe(false);expect(after.version).toBe(2);expect(after.users).toBe(before.users);expect(after.memberships).toBe(before.memberships);
  44  |  await proof(`U05 revoked read ${locale}`,{before,changed,statuses,after});await page.screenshot({path:`test-results/u05-revoked-${locale}.png`,fullPage:true});
  45  | });
  46  | 
  47  | test('U05 explicit recheck cancels held pre-withdrawal buyer rows',async({page})=>{
  48  |  await signInWorkbench(page,true,'access',`/app/discover?workspace=${workspace}&project=${project}`);
  49  |  const buyers=page.getByRole('region',{name:'Buyer results',exact:true});await expect(buyers.getByRole('checkbox',{name:/^Select /}).first()).toBeVisible();
  50  |  let release=()=>{},started=()=>{};const held=new Promise<void>(r=>release=r),received=new Promise<void>(r=>started=r);
  51  |  await page.route(`**/v1/workspaces/${workspace}/projects/${project}/buyers?**`,async route=>{const response=await route.fetch();expect(response.status()).toBe(200);started();await held;await route.fulfill({response}).catch(()=>{});});
  52  |  try{await buyers.getByRole('button',{name:'Refresh results',exact:true}).click();await received;await changeAccess(page);
  53  |  await page.getByRole('button',{name:'Check access again',exact:true}).click();await cleared(page);release();await cleared(page);
  54  |  await expect(page.getByText('Fixture company',{exact:false})).toHaveCount(0);
  55  |  await proof('U05 held rows',{active:(await fixture()).active,old_response_status:200,scope_cleared:true});
  56  |  }finally{release();}
  57  | });
  58  | 
  59  | test('U05 older access check cannot restore withdrawn A after another recheck',async({page})=>{
  60  |  await signInWorkbench(page,true,'access');let release=()=>{},started=()=>{},hold=true;
  61  |  const held=new Promise<void>(r=>release=r),received=new Promise<void>(r=>started=r);
  62  |  await page.route('**/v1/workspaces?**',async route=>{if(!hold)return route.continue();hold=false;const response=await route.fetch();expect(response.status()).toBe(200);started();await held;await route.fulfill({response}).catch(()=>{});});
  63  |  try{await page.getByRole('button',{name:'Check access again',exact:true}).click();await received;await changeAccess(page);
  64  |  await page.getByRole('button',{name:'Check access again',exact:true}).click();await cleared(page);release();await cleared(page);
  65  |  await expect(page.getByRole('combobox',{name:'Workspace',exact:true}).getByRole('option',{name:'E2E fixture workspace',exact:true})).toHaveCount(0);
  66  |  }finally{release();}
  67  | });
  68  | 
  69  | test('U05 delayed A access result cannot clear current B',async({page})=>{
  70  |  await signInWorkbench(page,true,'access');let release=()=>{},started=()=>{},hold=true;
  71  |  const held=new Promise<void>(r=>release=r),received=new Promise<void>(r=>started=r);
  72  |  await changeAccess(page);
  73  |  await page.route('**/v1/workspaces?**',async route=>{if(!hold)return route.continue();hold=false;const response=await route.fetch();started();await held;await route.fulfill({response}).catch(()=>{});});
  74  |  try{await page.getByRole('button',{name:'Check access again',exact:true}).click();await received;
  75  |  await page.getByRole('combobox',{name:'Workspace',exact:true}).selectOption(other);
  76  |  await expect(page.getByRole('combobox',{name:'Workspace',exact:true})).toHaveValue(other);release();
  77  |  await expect(page.getByRole('combobox',{name:'Workspace',exact:true})).toHaveValue(other);
  78  |  expect(new URL(page.url()).searchParams.get('workspace')).toBe(other);
  79  |  }finally{release();}
  80  | });
  81  | 
  82  | test('U05 forbidden save rechecks downgraded role while retaining dirty Unicode draft',async({page})=>{
  83  |  const seeded=await fixture('create','audit_drafts.py');await signInWorkbench(page,true,'access',`/app/outreach?workspace=${workspace}&project=${project}&draft=${seeded.draft}&draft_job=${seeded.job}`);
  84  |  const editor=page.getByRole('region',{name:'Open draft',exact:true});await expect(editor.getByRole('textbox',{name:'Subject',exact:true})).toHaveValue(seeded.subject);
  85  |  await editor.getByRole('textbox',{name:'Subject',exact:true}).fill('未保存主旨🙂');await editor.getByRole('textbox',{name:'Body',exact:true}).fill('保留本地內容🙂');await editor.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');
  86  |  await changeAccess(page,true,['viewer']);const fail=page.waitForResponse(r=>r.request().method()==='PATCH'&&r.url().includes('/drafts/')&&r.status()===403);
  87  |  await editor.getByRole('button',{name:'Save revision',exact:true}).click();await fail;
  88  |  await expect(page.getByText('Role: viewer',{exact:true})).toBeVisible();await expect(page.getByRole('combobox',{name:'Workspace',exact:true})).toHaveValue(workspace);
  89  |  await expect(editor.getByRole('textbox',{name:'Subject',exact:true})).toHaveValue('未保存主旨🙂');await expect(editor.getByRole('textbox',{name:'Body',exact:true})).toHaveValue('保留本地內容🙂');await expect(editor.getByRole('combobox',{name:'Language',exact:true})).toHaveValue('zh-HK');await expect(editor).toHaveAttribute('data-live-unsaved','true');
  90  |  const stored=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${seeded.draft}`,{headers:{Authorization:'Bearer fixture-admin'}});expect(stored.status()).toBe(200);expect((await stored.json()).data.subject).toBe(seeded.subject);
  91  |  await proof('U05 denied write unchanged',{membership:await fixture(),stored:(await stored.json()).data});
  92  | });
  93  | 
  94  | test('U05 missing job does not revoke an active membership',async({page})=>{
  95  |  let checks=0;page.on('request',r=>{if(new URL(r.url()).pathname==='/v1/workspaces')checks++;});
  96  |  await signInWorkbench(page,true,'access');const before=checks;
  97  |  await page.getByRole('button',{name:'Operations',exact:true}).click();
  98  |  const input=page.getByRole('textbox',{name:'Job ID',exact:true});await input.fill('f9999999-0000-4000-8000-000000000000');
  99  |  await page.getByRole('button',{name:'Load job',exact:true}).click();await expect.poll(()=>checks).toBeGreaterThan(before);
  100 |  await expect(page.getByRole('combobox',{name:'Workspace',exact:true})).toHaveValue(workspace);expect((await fixture()).active).toBe(true);
  101 | });
  102 | 
  103 | test('U05 failed access recheck preserves scope and supports explicit recovery',async({page})=>{
  104 |  await signInWorkbench(page,true,'access');let fail=true;
  105 |  await page.route('**/v1/workspaces?**',async route=>{if(!fail)return route.continue();await route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({code:'INTERNAL_ERROR',message:'fixture failure',request_id:'12345678-1234-4123-8123-123456789012',retryable:true})});});
  106 |  await page.getByRole('button',{name:'Check access again',exact:true}).click();await expect(page.getByRole('alert').filter({hasText:'Service temporarily unavailable.'})).toBeVisible();
  107 |  await expect(page.getByRole('combobox',{name:'Workspace',exact:true})).toHaveValue(workspace);fail=false;
  108 |  await page.getByRole('button',{name:'Check access again',exact:true}).click();await expect(page.getByRole('alert').filter({hasText:'Service temporarily unavailable.'})).toHaveCount(0);
  109 |  expect((await fixture()).active).toBe(true);
  110 | });
  111 | 
```