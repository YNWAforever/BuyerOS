# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-draft-reground.spec.ts >> U09 real stale revision preserves source form and exact buffers; scope change rejects delayed review result
- Location: tests\e2e\audit-draft-reground.spec.ts:90:1

# Error details

```
Error: expect(received).toBe(expected) // Object.is equality

Expected: 5
Received: 0
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
    - region "Drafts" [ref=f1e31]:
      - heading "Drafts" [level=2] [ref=f1e32]
      - paragraph [ref=f1e33]: Prepare a grounded draft; delivery is disabled.
      - status [ref=f1e34]: Human edits require a new grounding review before approval.
      - region "Sender identity" [ref=f1e35]:
        - heading "Sender identity" [level=3] [ref=f1e36]
        - paragraph [ref=f1e37]: "Reviewed sender: Fixture Alex · Fictional Seller · alex@example.test · sender:ea000000-0000-4000-8000-000000000001:1"
      - region "Prepare grounded draft" [ref=f1e38]:
        - heading "Prepare grounded draft" [level=3] [ref=f1e39]
        - paragraph [ref=f1e40]:
          - strong [ref=f1e41]: Free fixed template
        - paragraph [ref=f1e42]: Template language changes only fixed headings, opening and closing; offer facts and source citations stay in their original language and are not automatically translated.
        - paragraph [ref=f1e43]: Edit the draft manually after generation; changes need a new grounding review before approval.
        - paragraph [ref=f1e44]: Buyer Fixture 01 · 1 · accepted
        - group "Approved offer facts" [ref=f1e45]:
          - generic [ref=f1e47]:
            - checkbox "Fictional industrial sensors" [checked] [ref=f1e48]
            - text: Fictional industrial sensors
        - group "Supporting buyer evidence" [ref=f1e49]:
          - generic [ref=f1e51]:
            - checkbox "Fixture public catalog lists industrial sensors. · v1" [checked] [ref=f1e52]
            - text: Fixture public catalog lists industrial sensors. · v1
        - paragraph [ref=f1e53]: Initial
        - generic [ref=f1e54]:
          - text: Recipient (optional)
          - combobox "Recipient (optional)" [ref=f1e55]:
            - option "No recipient — unaddressed draft"
            - option "recipient@fixture.example.test · v1" [selected]
        - generic [ref=f1e56]:
          - generic [ref=f1e57]:
            - text: Internal work objective — does not change the template body
            - textbox "Internal work objective — does not change the template body" [ref=f1e58]: Introduce the approved offer
          - generic [ref=f1e59]:
            - text: Template language
            - combobox "Template language" [ref=f1e60]:
              - option "English"
              - option "繁體中文" [selected]
        - button "Generate addressed draft" [ref=f1e61] [cursor=pointer]
      - status [ref=f1e62]:
        - heading "Job status" [level=3] [ref=f1e63]
        - paragraph [ref=f1e64]: 5db74ddb-b979-49af-99f0-dc322f8df6aa · completed
        - button "Refresh job" [ref=f1e65] [cursor=pointer]
      - region "Draft list" [ref=f1e66]:
        - heading "Draft list" [level=3] [ref=f1e67]
        - paragraph [ref=f1e68]: 1–5 / 5
        - generic [ref=f1e69]:
          - generic [ref=f1e70]: "Introduction: Fictional industrial sensors · draft · v1"
          - button "Open draft" [ref=f1e71] [cursor=pointer]
        - generic [ref=f1e72]:
          - generic [ref=f1e73]: 邀請😀了解產品 · draft · v2
          - button "Open draft" [ref=f1e74] [cursor=pointer]
        - generic [ref=f1e75]:
          - generic [ref=f1e76]: 邀請😀了解產品 · draft · v3
          - button "Open draft" [ref=f1e77] [cursor=pointer]
        - generic [ref=f1e78]:
          - generic [ref=f1e79]: 邀請😀了解產品 · approved · v5
          - button "Open draft" [ref=f1e80] [cursor=pointer]
        - generic [ref=f1e81]:
          - generic [ref=f1e82]: 邀請😀了解產品 · draft · v2
          - button "Open draft" [ref=f1e83] [cursor=pointer]
        - generic [ref=f1e84]:
          - button "Previous page" [disabled] [ref=f1e85]
          - button "Next page" [disabled] [ref=f1e86]
      - region "Open draft" [ref=f1e87]:
        - heading "邀請😀了解產品" [level=3] [ref=f1e88]
        - paragraph [ref=f1e89]: "Revision: 2 · draft · zh-HK"
        - paragraph [ref=f1e90]: Delivery is disabled.
        - generic [ref=f1e91]:
          - generic [ref=f1e92]:
            - text: Subject
            - textbox "Subject" [ref=f1e93]: 邀請😀了解產品
          - generic [ref=f1e94]:
            - text: Body
            - textbox "Body" [ref=f1e95]: 您好👩‍💻 Fictional industrial sensors Fixture public catalog lists industrial sensors. 謝謝！
          - generic [ref=f1e96]:
            - text: Language
            - combobox "Language" [ref=f1e97]:
              - option "English"
              - option "繁體中文" [selected]
        - generic [ref=f1e98]:
          - button "Save revision" [disabled] [ref=f1e99]
          - button "Prepare follow-up" [ref=f1e100] [cursor=pointer]
        - heading "Claims and sources" [level=4] [ref=f1e101]
        - paragraph [ref=f1e102]: Human edits require a new grounding review before approval.
        - region "Manual source review" [ref=f1e103]:
          - heading "Manual source review" [level=4] [ref=f1e104]
          - paragraph [ref=f1e105]: Classify every segment, read each cited source and the whole message. This records your source review; it does not verify semantic truth.
          - paragraph [ref=f1e106]: "Revision: 2 · 378b9d6d0730ec3fc0e34b351d1fa1dbb74ca06d3aeae5492d33b754c49cf048"
          - paragraph [ref=f1e107]: A reviewer must submit this source review.
          - group "Segment 1" [ref=f1e108]:
            - generic [ref=f1e109]: Segment 1 · Subject · [0, 7)
            - generic [ref=f1e110]: 邀請😀了解產品
            - generic [ref=f1e111]:
              - text: Classification
              - combobox "Classification" [ref=f1e112]:
                - option "Choose classification" [selected]
                - option "Factual — cite a source"
                - option "Non-factual — explain why"
            - generic [ref=f1e113]:
              - text: Segment reason
              - textbox "Segment reason" [ref=f1e114]
            - generic [ref=f1e115]:
              - text: Split position (code points)
              - spinbutton "Split position (code points)" [ref=f1e116]
            - button "Split segment" [disabled] [ref=f1e117]
          - group "Segment 2" [ref=f1e118]:
            - generic [ref=f1e119]: Segment 2 · Body · [0, 5)
            - generic [ref=f1e120]: 您好👩‍💻
            - generic [ref=f1e121]:
              - text: Classification
              - combobox "Classification" [ref=f1e122]:
                - option "Choose classification" [selected]
                - option "Factual — cite a source"
                - option "Non-factual — explain why"
            - generic [ref=f1e123]:
              - text: Segment reason
              - textbox "Segment reason" [ref=f1e124]
            - generic [ref=f1e125]:
              - text: Split position (code points)
              - spinbutton "Split position (code points)" [ref=f1e126]
            - button "Split segment" [disabled] [ref=f1e127]
          - group "Segment 3" [ref=f1e128]:
            - generic [ref=f1e129]: Segment 3 · Body · [6, 34)
            - generic [ref=f1e130]: Fictional industrial sensors
            - generic [ref=f1e131]:
              - text: Classification
              - combobox "Classification" [ref=f1e132]:
                - option "Choose classification" [selected]
                - option "Factual — cite a source"
                - option "Non-factual — explain why"
            - generic [ref=f1e133]:
              - text: Segment reason
              - textbox "Segment reason" [ref=f1e134]
            - generic [ref=f1e135]:
              - text: Split position (code points)
              - spinbutton "Split position (code points)" [ref=f1e136]
            - button "Split segment" [disabled] [ref=f1e137]
          - group "Segment 4" [ref=f1e138]:
            - generic [ref=f1e139]: Segment 4 · Body · [35, 83)
            - generic [ref=f1e140]: Fixture public catalog lists industrial sensors.
            - generic [ref=f1e141]:
              - text: Classification
              - combobox "Classification" [ref=f1e142]:
                - option "Choose classification" [selected]
                - option "Factual — cite a source"
                - option "Non-factual — explain why"
            - generic [ref=f1e143]:
              - text: Segment reason
              - textbox "Segment reason" [ref=f1e144]
            - generic [ref=f1e145]:
              - text: Split position (code points)
              - spinbutton "Split position (code points)" [ref=f1e146]
            - button "Split segment" [disabled] [ref=f1e147]
          - group "Segment 5" [ref=f1e148]:
            - generic [ref=f1e149]: Segment 5 · Body · [84, 87)
            - generic [ref=f1e150]: 謝謝！
            - generic [ref=f1e151]:
              - text: Classification
              - combobox "Classification" [ref=f1e152]:
                - option "Choose classification" [selected]
                - option "Factual — cite a source"
                - option "Non-factual — explain why"
            - generic [ref=f1e153]:
              - text: Segment reason
              - textbox "Segment reason" [ref=f1e154]
            - generic [ref=f1e155]:
              - text: Split position (code points)
              - spinbutton "Split position (code points)" [ref=f1e156]
            - button "Split segment" [disabled] [ref=f1e157]
          - generic [ref=f1e158]:
            - text: Overall review reason
            - textbox "Overall review reason" [ref=f1e159]
          - generic [ref=f1e160]:
            - checkbox "I read the entire exact message and every cited source, including all non-factual classifications." [disabled] [ref=f1e161]
            - text: I read the entire exact message and every cited source, including all non-factual classifications.
        - region "Exact revision review" [ref=f1e162]:
          - heading "Exact revision review" [level=4] [ref=f1e163]
          - paragraph [ref=f1e164]: "Revision: 2 · 378b9d6d0730ec3fc0e34b351d1fa1dbb74ca06d3aeae5492d33b754c49cf048"
          - paragraph [ref=f1e165]: An eligible addressed draft and current policy are required before review.
          - button "Refresh draft" [ref=f1e167] [cursor=pointer]
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
  38  |  const grounding=page.getByRole('region',{name:/^(Manual source review|人工來源覆核)$/,exact:true});await expect(grounding.getByRole('status')).toHaveCount(0);
  39  |  if(split){const first=grounding.getByRole('group').first();await first.getByRole('spinbutton').fill('2');await first.getByRole('button',{name:'分開段落',exact:true}).click();}
> 40  |  const groups=grounding.getByRole('group');const count=await groups.count();expect(count).toBe(split?6:5);
      |                                                                                           ^ Error: expect(received).toBe(expected) // Object.is equality
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
  73  |   await submit.click();await expect(editor).toContainText('Source review recorded; request a new exact review.');expect(requests).toHaveLength(2);expect(requests[1]).toEqual(requests[0]);await reviewer.unroute(path);
  74  |   await reviewer.reload();await expect(editor).toContainText('Reviewed by');await expect(editor.getByRole('textbox',{name:'Body',exact:true})).toHaveValue(body);await approveExport(reviewer,editor,created.id,'en');
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
  98  |   await editor.getByRole('button',{name:'Refresh draft',exact:true}).click();prepared=await classify(reviewer);
  99  |   let release:()=>void=()=>{},received:()=>void=()=>{};const held=new Promise<void>(r=>release=r),started=new Promise<void>(r=>received=r);
  100 |   const path=`**/v1/workspaces/${workspace}/drafts/${created.id}/grounding-reviews`;
  101 |   await reviewer.route(path,async route=>{const response=await route.fetch();expect(response.status()).toBe(200);received();await held;await route.fulfill({response}).catch(()=>{});});
  102 |   await prepared.submit.click();await started;await reviewer.getByRole('combobox',{name:'Project',exact:true}).selectOption('e9100000-0000-4000-8000-000000000001');release();
  103 |   await expect(reviewer.getByRole('region',{name:'Open draft',exact:true})).toHaveCount(0);await reviewer.waitForTimeout(300);await expect(reviewer.getByRole('region',{name:'Open draft',exact:true})).toHaveCount(0);
  104 |  }finally{await resetLocale(reviewer);await ctx.close();}
  105 | });
  106 | 
```