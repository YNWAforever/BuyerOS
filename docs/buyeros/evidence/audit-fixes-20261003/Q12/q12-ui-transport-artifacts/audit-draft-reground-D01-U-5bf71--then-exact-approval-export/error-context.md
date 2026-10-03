# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-draft-reground.spec.ts >> D01/U09 reviewer failure retains preparation; lost committed response retries same key then exact approval/export
- Location: tests\e2e\audit-draft-reground.spec.ts:63:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('region', { name: /^(Manual source review|人工來源覆核)$/ })
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('region', { name: /^(Manual source review|人工來源覆核)$/ }) with timeout 5000ms
  - waiting for getByRole('region', { name: /^(Manual source review|人工來源覆核)$/ })

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
  - region "Drafts":
    - heading "Drafts" [level=2]
    - paragraph: Prepare a grounded draft; delivery is disabled.
    - alert: Service temporarily unavailable. Retry after checking the status.
    - status: Loading draft workspace...
- dialog "Build Error":
  - banner:
    - text: Build Error
    - button "Copy Error Info"
    - button "Dismiss": ×
  - text: socket hang up
```

# Test source

```ts
  1   | import {expect,test,type Page} from '@playwright/test';
  2   | import {execFile} from 'node:child_process';
  3   | import {promisify} from 'node:util';
  4   | import {resolve} from 'node:path';
  5   | import {readFile,writeFile} from 'node:fs/promises';
  6   | import {signInWorkbench,workspace,project,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';
  7   | const buyer='e2000000-0000-4000-8000-000000000001';
  8   | const subject='邀請😀了解產品';
  9   | const body='您好👩‍💻\nFictional industrial sensors\nFixture public catalog lists industrial sensors.\n謝謝！';
  10  | async function fixture(...args:string[]){const cwd=resolve('services/worker');return JSON.parse((await promisify(execFile)(resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python'),['tests/fixtures/audit_template.py',...args],{cwd,timeout:60_000})).stdout);}
  11  | async function editedDraft(page:Page){
  12  |  await resetWorkbenchFixtureRateWindows();const seed=await fixture('prepare');
  13  |  await signInWorkbench(page,true,'access',`/app/outreach?workspace=${workspace}&project=${project}&buyer=${buyer}`);
  14  |  await page.getByRole('combobox',{name:/^(Language|語言)$/,exact:true}).first().selectOption('en');await expect(page.locator('html')).toHaveAttribute('lang','en');
  15  |  const prepare=page.getByRole('region',{name:'Prepare grounded draft',exact:true});await prepare.getByRole('combobox',{name:'Recipient (optional)',exact:true}).selectOption(seed.contact);
  16  |  const pending=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith(`/projects/${project}/drafts`));
  17  |  await prepare.getByRole('button',{name:'Generate addressed draft',exact:true}).click();const response=await pending;expect(response.status()).toBe(202);
  18  |  const materialized=await fixture('materialize',(await response.json()).data.id);expect(materialized.duplicate).toBe('duplicate');
  19  |  await page.getByRole('button',{name:'Refresh job',exact:true}).click();const editor=page.getByRole('region',{name:'Open draft',exact:true});await expect(editor).toBeVisible();
  20  |  await editor.getByRole('textbox',{name:'Subject',exact:true}).fill(subject);await editor.getByRole('textbox',{name:'Body',exact:true}).fill(body);await editor.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');
  21  |  await editor.getByRole('button',{name:'Save revision',exact:true}).click();await expect(editor).not.toHaveAttribute('data-live-unsaved','true');
  22  |  return {id:materialized.draft,editor,materialized};
  23  | }
  24  | test('D01/D03 manual Unicode draft exposes a source review and operator cannot attest',async({page})=>{
  25  |  const {editor}=await editedDraft(page);await expect(editor).toContainText('Human edits require a new grounding review before approval.');
  26  |  const grounding=editor.getByRole('region',{name:'Manual source review',exact:true});await expect(grounding).toBeVisible();
  27  |  await expect(grounding).toContainText('A reviewer must submit this source review.');
  28  |  await expect(grounding.getByRole('button',{name:'Submit source review',exact:true})).toHaveCount(0);
  29  |  await expect(editor.getByRole('textbox',{name:'Body',exact:true})).toHaveValue(body);
  30  | });
  31  | 
  32  | async function reviewerPage(page:Page,id:string,locale='en'){
  33  |  await signInWorkbench(page,true,'reviewer',`/app/outreach?workspace=${workspace}&project=${project}&draft=${id}`);
  34  |  await page.getByRole('combobox',{name:/^(Language|語言)$/,exact:true}).first().selectOption(locale);await expect(page.locator('html')).toHaveAttribute('lang',locale);
  35  |  return page.getByRole('region',{name:/^(Open draft|開啟草稿)$/,exact:true});
  36  | }
  37  | async function classify(page:Page,split=false){
> 38  |  const grounding=page.getByRole('region',{name:/^(Manual source review|人工來源覆核)$/,exact:true});await expect(grounding).toBeVisible();await expect(grounding.getByRole('group')).toHaveCount(5);await expect(grounding.getByRole('status')).toHaveCount(0);
      |                                                                                                                       ^ Error: expect(locator).toBeVisible() failed
  39  |  if(split){const first=grounding.getByRole('group').first();await first.getByRole('spinbutton').fill('2');await first.getByRole('button',{name:'分開段落',exact:true}).click();}
  40  |  const groups=grounding.getByRole('group');const count=await groups.count();expect(count).toBe(split?6:5);
  41  |  for(let i=0;i<count;i++){
  42  |   const group=groups.nth(i),text=await group.locator('pre').innerText();const factual=text==='Fictional industrial sensors'||text.startsWith('Fixture public');
  43  |   await group.getByRole('combobox').selectOption(factual?'factual':'non_factual');await group.getByRole('textbox').fill(factual?'Read original retained source':'Greeting, invitation or closing; no factual assertion');
  44  |   if(factual)await group.getByRole('checkbox',{name:text.startsWith('Fixture')?/^(Evidence|證據)/:/^(Offer fact|產品事實)/}).check();
  45  |  }
  46  |  await grounding.getByRole('textbox',{name:/^(Overall review reason|整體覆核理由)$/,exact:true}).fill('Full message and every versioned source read');
  47  |  await grounding.getByRole('checkbox',{name:/^(I read the entire exact message|我已閱讀整篇精確訊息)/}).check();
  48  |  const submit=grounding.getByRole('button',{name:/^(Submit source review|提交來源覆核)$/,exact:true});await expect(submit).toBeEnabled();return {grounding,submit};
  49  | }
  50  | async function approveExport(page:Page,editor:ReturnType<Page['getByRole']>,id:string,label:string){
  51  |  await editor.getByRole('button',{name:/^(Request exact review|要求審核此版本)$/,exact:true}).click();
  52  |  await editor.getByRole('checkbox',{name:/^(I confirm the exact recipient|我確認以上精確收件人)/}).check();await editor.getByRole('button',{name:/^(Approve exact revision|批准此精確版本)$/,exact:true}).click();
  53  |  const exports=editor.getByRole('region',{name:/^(Authorized export|授權匯出)$/,exact:true});await exports.getByRole('button',{name:/^(Prepare approved copy|準備已批准副本)$/,exact:true}).click();
  54  |  const downloading=page.waitForEvent('download');await exports.getByRole('button',{name:/^(Download text|下載文字)$/,exact:true}).click();const text=await readFile((await (await downloading).path())!,'utf8');expect(text).toContain(body);expect(text).toContain(subject);await writeFile(`test-results/q12-${label}-export.txt`,text);
  55  |  const stored=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${id}`,{headers:{Authorization:'Bearer fixture-reviewer'}});expect(stored.status()).toBe(200);const draft=(await stored.json()).data;
  56  |  expect(draft.revision_number).toBe(3);expect(draft.body).toBe(body);expect(draft.grounding_review.reviewed_by).toBe('e0000000-0000-4000-8000-000000000004');
  57  |  const exportId=new URL(page.url()).searchParams.get('export');const viewer=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/exports/${exportId}/content`,{headers:{Authorization:'Bearer fixture-viewer'}});expect(viewer.status()).toBe(403);
  58  |  const deliver=await page.request.post(`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${id}/deliver`,{headers:{Authorization:'Bearer fixture-reviewer','Idempotency-Key':`q12-${label}-delivery`}});expect(deliver.status()).toBe(403);expect((await deliver.json()).code).toBe('DELIVERY_DISABLED');
  59  |  await writeFile(`test-results/q12-${label}-output.json`,JSON.stringify({fixture_only:true,draft,viewer_export:viewer.status(),delivery:deliver.status()},null,2));
  60  | }
  61  | async function resetLocale(page:Page){await page.getByRole('combobox',{name:/^(Language|語言)$/,exact:true}).first().selectOption('en');await expect(page.locator('html')).toHaveAttribute('lang','en');}
  62  | 
  63  | test('D01/U09 reviewer failure retains preparation; lost committed response retries same key then exact approval/export',async({page,browser})=>{
  64  |  const created=await editedDraft(page);const ctx=await browser.newContext();const reviewer=await ctx.newPage();
  65  |  try{
  66  |   const editor=await reviewerPage(reviewer,created.id);const {grounding,submit}=await classify(reviewer);
  67  |   const path=`**/v1/workspaces/${workspace}/drafts/${created.id}/grounding-reviews`;let first=true;
  68  |   await reviewer.route(path,async route=>{if(!first)return route.continue();first=false;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({code:'PROVIDER_UNAVAILABLE',message:'Q12 isolated HTTP failure',request_id:'00000000-0000-4000-8000-000000000012',retryable:true})});});
  69  |   await submit.click();await expect(grounding.getByRole('alert')).toBeVisible();await expect(submit).toBeEnabled();await expect(grounding.getByRole('checkbox',{name:/I read the entire/})).toBeChecked();await expect(editor.getByRole('textbox',{name:'Body',exact:true})).toHaveValue(body);await reviewer.unroute(path);
  70  |   const requests:{key:string;body:unknown}[]=[];first=true;
  71  |   await reviewer.route(path,async route=>{requests.push({key:route.request().headers()['idempotency-key'],body:route.request().postDataJSON()});if(!first)return route.continue();first=false;const committed=await route.fetch();expect(committed.status(),await committed.text()).toBe(200);await route.abort('failed');});
  72  |   await submit.click();await expect(grounding.getByRole('alert')).toBeVisible();await expect(submit).toBeEnabled();await expect(editor.getByRole('textbox',{name:'Body',exact:true})).toHaveValue(body);
  73  |   await submit.click();await expect(reviewer.getByText('Source review recorded; request a new exact review.',{exact:true})).toBeVisible();expect(requests).toHaveLength(2);expect(requests[1]).toEqual(requests[0]);await reviewer.unroute(path);
  74  |   await reviewer.reload();await reviewerPage(reviewer,created.id);await expect(editor).toContainText('Reviewed by');await expect(editor.getByRole('textbox',{name:'Body',exact:true})).toHaveValue(body);await approveExport(reviewer,editor,created.id,'en');
  75  |   await reviewer.screenshot({path:'test-results/q12-en-approved-export.png',fullPage:true});await writeFile('test-results/q12-en-retry.json',JSON.stringify({fixture_only:true,synthetic_503:true,actual_committed_response_dropped:true,requests,materialization:created.materialized},null,2));
  76  |  }finally{await resetLocale(reviewer);await ctx.close();}
  77  | });
  78  | 
  79  | test('D03 zh-HK mobile code-point split reads every source and exports exact Unicode message',async({page,browser})=>{
  80  |  const created=await editedDraft(page);const ctx=await browser.newContext({viewport:{width:390,height:844}});const reviewer=await ctx.newPage();
  81  |  try{
  82  |   const editor=await reviewerPage(reviewer,created.id,'zh-HK');const {submit}=await classify(reviewer,true);
  83  |   await expect.poll(()=>reviewer.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await reviewer.screenshot({path:'test-results/q12-zh-mobile-review.png',fullPage:true});
  84  |   const response=reviewer.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/grounding-reviews'));await submit.click();const reviewed=await response;expect(reviewed.status(),await reviewed.text()).toBe(200);
  85  |   const proof=(await reviewed.json()).data.grounding_review;expect(proof.segments[0]).toMatchObject({start:0,end:2,exact_text:'邀請'});expect(proof.segments[1]).toMatchObject({start:2,end:Array.from(subject).length,exact_text:'😀了解產品'});expect(proof.segments[2].end).toBe(5);
  86  |   await approveExport(reviewer,editor,created.id,'zh');await expect.poll(()=>reviewer.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await reviewer.screenshot({path:'test-results/q12-zh-mobile-approved-export.png',fullPage:true});
  87  |  }finally{await resetLocale(reviewer);await ctx.close();}
  88  | });
  89  | 
  90  | test('U09 real stale revision preserves source form and exact buffers; scope change rejects delayed review result',async({page,browser})=>{
  91  |  const created=await editedDraft(page);const ctx=await browser.newContext();const reviewer=await ctx.newPage();
  92  |  try{
  93  |   const editor=await reviewerPage(reviewer,created.id);let prepared=await classify(reviewer);
  94  |   const base=`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${created.id}`;
  95  |   const before=(await (await reviewer.request.get(base,{headers:{Authorization:'Bearer fixture-reviewer'}})).json()).data;
  96  |   const edit=await reviewer.request.patch(base,{headers:{Authorization:'Bearer fixture-access','Idempotency-Key':'q12-real-stale-edit','If-Match':`"${before.version}"`},data:{subject}});expect(edit.status()).toBe(200);
  97  |   await prepared.submit.click();await expect(prepared.grounding.getByRole('alert')).toBeVisible();await expect(prepared.grounding.getByRole('checkbox',{name:/I read the entire/})).toBeChecked();await expect(editor.getByRole('textbox',{name:'Subject',exact:true})).toHaveValue(subject);await expect(editor.getByRole('textbox',{name:'Body',exact:true})).toHaveValue(body);await expect(editor).not.toHaveAttribute('data-live-unsaved','true');
  98  |   await editor.getByRole('button',{name:'Refresh draft',exact:true}).click();await expect(editor).toHaveAttribute('data-baseline-revision',(await edit.json()).data.revision_id);prepared=await classify(reviewer);
  99  |   let release:()=>void=()=>{},received:()=>void=()=>{};const held=new Promise<void>(r=>release=r),started=new Promise<void>(r=>received=r);
  100 |   const path=`**/v1/workspaces/${workspace}/drafts/${created.id}/grounding-reviews`;
  101 |   await reviewer.route(path,async route=>{const response=await route.fetch();expect(response.status()).toBe(200);received();await held;await route.fulfill({response}).catch(()=>{});});
  102 |   await prepared.submit.click();await started;await reviewer.getByRole('combobox',{name:'Project',exact:true}).selectOption('e9100000-0000-4000-8000-000000000001');release();
  103 |   await expect(reviewer.getByRole('region',{name:'Open draft',exact:true})).toHaveCount(0);await reviewer.waitForTimeout(300);await expect(reviewer.getByRole('region',{name:'Open draft',exact:true})).toHaveCount(0);
  104 |  }finally{await resetLocale(reviewer);await ctx.close();}
  105 | });
  106 | 
```