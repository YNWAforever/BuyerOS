# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-template-copy.spec.ts >> A02 fixed-template promise matches two actual outputs; manual edits keep Q15 dirty protection
- Location: tests\e2e\audit-template-copy.spec.ts:24:1

# Error details

```
Error: expect(locator).toHaveCount(expected) failed

Locator:  getByRole('region', { name: 'Prepare grounded draft', exact: true }).getByRole('combobox', { name: 'Tone', exact: true })
Expected: 0
Received: 1
Timeout:  5000ms

Call log:
  - Expect "toHaveCount" getByRole('region', { name: 'Prepare grounded draft', exact: true }).getByRole('combobox', { name: 'Tone', exact: true }) with timeout 5000ms
  - waiting for getByRole('region', { name: 'Prepare grounded draft', exact: true }).getByRole('combobox', { name: 'Tone', exact: true })
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
      - region "Sender identity" [ref=f1e34]:
        - heading "Sender identity" [level=3] [ref=f1e35]
        - paragraph [ref=f1e36]: "Reviewed sender: Fixture Alex · Fictional Seller · alex@example.test · sender:ea000000-0000-4000-8000-000000000001:1"
      - region "Prepare grounded draft" [ref=f1e37]:
        - heading "Prepare grounded draft" [level=3] [ref=f1e38]
        - paragraph [ref=f1e39]: Buyer Fixture 01 · 1 · accepted
        - group "Approved offer facts" [ref=f1e40]:
          - generic [ref=f1e42]:
            - checkbox "Fictional industrial sensors" [checked] [ref=f1e43]
            - text: Fictional industrial sensors
        - group "Supporting buyer evidence" [ref=f1e44]:
          - generic [ref=f1e46]:
            - checkbox "Fixture public catalog lists industrial sensors. · v1" [checked] [ref=f1e47]
            - text: Fixture public catalog lists industrial sensors. · v1
        - paragraph [ref=f1e48]: Initial
        - generic [ref=f1e49]:
          - text: Recipient (optional)
          - combobox "Recipient (optional)" [ref=f1e50]:
            - option "No recipient — unaddressed draft" [selected]
            - option "recipient@fixture.example.test · v1"
        - generic [ref=f1e51]:
          - generic [ref=f1e52]:
            - text: Objective
            - textbox "Objective" [ref=f1e53]: Introduce the approved offer
          - generic [ref=f1e54]:
            - text: Tone
            - combobox "Tone" [ref=f1e55]:
              - option "professional" [selected]
              - option "concise"
              - option "warm"
          - generic [ref=f1e56]:
            - text: Language
            - combobox "Language" [ref=f1e57]:
              - option "English" [selected]
              - option "繁體中文"
        - button "Generate unaddressed draft" [ref=f1e58] [cursor=pointer]
      - region "Draft list" [ref=f1e59]:
        - heading "Draft list" [level=3] [ref=f1e60]
        - paragraph [ref=f1e61]: 1–1 / 1
        - generic [ref=f1e62]:
          - generic [ref=f1e63]: "Introduction: Fictional industrial sensors · draft · v1"
          - button "Open draft" [ref=f1e64] [cursor=pointer]
        - generic [ref=f1e65]:
          - button "Previous page" [disabled] [ref=f1e66]
          - button "Next page" [disabled] [ref=f1e67]
```

# Test source

```ts
  1  | import {expect,test,type Page} from '@playwright/test';
  2  | import {execFile} from 'node:child_process';
  3  | import {promisify} from 'node:util';
  4  | import {resolve} from 'node:path';
  5  | import {readFile,writeFile} from 'node:fs/promises';
  6  | import {signInWorkbench,workspace,project,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';
  7  | const buyer='e2000000-0000-4000-8000-000000000001';
  8  | const source='Fixture public catalog lists industrial sensors.';
  9  | async function fixture(...args:string[]){const cwd=resolve('services/worker');return JSON.parse((await promisify(execFile)(resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python'),['tests/fixtures/audit_template.py',...args],{cwd,timeout:60_000})).stdout);}
  10 | async function enter(page:Page){await resetWorkbenchFixtureRateWindows();const seeded=await fixture('prepare');await signInWorkbench(page,true,'access',`/app/outreach?workspace=${workspace}&project=${project}&buyer=${buyer}`);return {seeded,prepare:page.getByRole('region',{name:'Prepare grounded draft',exact:true})};}
  11 | async function generate(page:Page,prepare:ReturnType<Page['getByRole']>,objective:string,addressed=false){
  12 |   await prepare.getByRole('textbox',{name:/^(Internal work objective|內部工作目的)/}).fill(objective);
  13 |   const pending=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith(`/projects/${project}/drafts`));
  14 |   await prepare.getByRole('button',{name:addressed?/^(Generate addressed draft|產生已指定收件人的草稿)$/:/^(Generate unaddressed draft|產生未指定收件人的草稿)$/}).click();
  15 |   const response=await pending;expect(response.status(),await response.text()).toBe(202);
  16 |   const command=response.request().postDataJSON();expect(command.tone).toBe('professional');expect(command.objective).toBe(objective);expect(command.max_cost).toEqual({amount:'0.000000',currency:'USD'});
  17 |   const job=(await response.json()).data;const materialized=await fixture('materialize',job.id);expect(materialized.duplicate).toBe('duplicate');expect(materialized.paid_after).toEqual(materialized.paid_before);
  18 |   await page.getByRole('button',{name:/^(Refresh job|重新整理工作)$/,exact:true}).click();
  19 |   const editor=page.getByRole('region',{name:/^(Open draft|開啟草稿)$/,exact:true});await expect(editor).toBeVisible();
  20 |   const read=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${materialized.draft}`,{headers:{Authorization:'Bearer fixture-access'}});expect(read.status()).toBe(200);
  21 |   const draft=(await read.json()).data;expect(await editor.getByRole('textbox',{name:/^(Body|內容)$/,exact:true}).inputValue()).toBe(draft.body);
  22 |   return {draft,editor,command,materialized};
  23 | }
  24 | test('A02 fixed-template promise matches two actual outputs; manual edits keep Q15 dirty protection',async({page})=>{
  25 |   const {prepare}=await enter(page);
> 26 |   await expect(prepare.getByRole('combobox',{name:'Tone',exact:true})).toHaveCount(0);
     |                                                                        ^ Error: expect(locator).toHaveCount(expected) failed
  27 |   await expect(prepare).toContainText('Free fixed template');
  28 |   await expect(prepare).toContainText('Internal work objective — does not change the template body');
  29 |   await expect(prepare).toContainText('Edit the draft manually after generation; changes need a new grounding review before approval.');
  30 |   const first=await generate(page,prepare,'Request a demonstration');const second=await generate(page,prepare,'Discuss procurement');
  31 |   expect(second.draft.subject).toBe(first.draft.subject);expect(second.draft.body).toBe(first.draft.body);expect(second.draft.objective).not.toBe(first.draft.objective);expect(second.draft.body).toContain(source);
  32 |   await second.editor.getByRole('textbox',{name:'Subject',exact:true}).fill('Q07 manual subject');await second.editor.getByRole('textbox',{name:'Body',exact:true}).fill('Q07 manual content pending grounding review');
  33 |   await page.getByRole('button',{name:'Refresh draft',exact:true}).click();await page.getByRole('dialog').getByRole('button',{name:'Cancel',exact:true}).click();await expect(second.editor).toHaveAttribute('data-live-unsaved','true');await expect(second.editor.getByRole('textbox',{name:'Body',exact:true})).toHaveValue('Q07 manual content pending grounding review');
  34 |   await page.getByRole('button',{name:'Save revision',exact:true}).click();await expect(second.editor).not.toHaveAttribute('data-live-unsaved','true');await expect(second.editor).toContainText('Human edits require a new grounding review before approval.');await expect(second.editor.getByRole('button',{name:'Request exact review',exact:true})).toHaveCount(0);
  35 |   await page.screenshot({path:'test-results/q07-template-en-edited.png',fullPage:true});await writeFile('test-results/q07-A02-output.json',JSON.stringify({fixture_only:true,first:first.draft,second:second.draft,materialization:[first.materialized,second.materialized]},null,2));
  36 | });
  37 | test('A07 zh-HK mobile template keeps original English citations through exact approval and authorized export',async({page,browser})=>{
  38 |   await page.setViewportSize({width:390,height:844});const {seeded,prepare:englishPrepare}=await enter(page);
  39 |   await page.getByRole('combobox',{name:'Language',exact:true}).first().selectOption('zh-HK');const prepare=page.getByRole('region',{name:'準備有證據草稿',exact:true});
  40 |   await expect(englishPrepare).toHaveCount(0);await expect(prepare).toContainText('免費固定模板');await expect(prepare).toContainText('內部工作目的，不會改變模板正文');await expect(prepare).toContainText('模板語言只改變固定標題、開場及結尾；產品事實與來源引用保留原語言，不會自動翻譯。');await expect(prepare.getByRole('combobox',{name:'語氣',exact:true})).toHaveCount(0);
  41 |   await prepare.getByRole('combobox',{name:'收件人（可選）',exact:true}).selectOption(seeded.contact);await prepare.getByRole('combobox',{name:'模板語言',exact:true}).selectOption('zh-HK');
  42 |   const generated=await generate(page,prepare,'內部跟進工作',true);expect(generated.draft.body).toContain('你好，');expect(generated.draft.body).toContain(source);expect(generated.draft.body).toContain('Fictional industrial sensors');expect(generated.draft.body).toContain('[evidence:');
  43 |   await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.screenshot({path:'test-results/q07-template-zh-mobile.png',fullPage:true});
  44 |   await page.getByRole('button',{name:'要求審核此版本',exact:true}).click();
  45 |   const context=await browser.newContext({viewport:{width:390,height:844}});const reviewer=await context.newPage();
  46 |   try{
  47 |     await signInWorkbench(reviewer,true,'reviewer',`/app/outreach?workspace=${workspace}&project=${project}&draft=${generated.draft.id}`);
  48 |     await reviewer.getByRole('checkbox',{name:/我確認以上精確收件人/}).check();await reviewer.getByRole('button',{name:'批准此精確版本',exact:true}).click();
  49 |     const exports=reviewer.getByRole('region',{name:'授權匯出',exact:true});await exports.getByRole('button',{name:'準備已批准副本',exact:true}).click();await expect(exports).toContainText('允許: 1');
  50 |     const downloaded=reviewer.waitForEvent('download');await exports.getByRole('button',{name:'下載文字',exact:true}).click();const copy=await readFile((await (await downloaded).path())!,'utf8');expect(copy).toContain(source);expect(copy).toContain('你好，');expect(copy).toContain('recipient@fixture.example.test');
  51 |     await writeFile('test-results/q07-A07-export.txt',copy);await reviewer.screenshot({path:'test-results/q07-template-zh-approved-export.png',fullPage:true});
  52 |     const exportId=new URL(reviewer.url()).searchParams.get('export');const denied=await reviewer.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/exports/${exportId}/content`,{headers:{Authorization:'Bearer fixture-viewer'}});expect(denied.status()).toBe(403);
  53 |     const deliver=await reviewer.request.post(`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${generated.draft.id}/deliver`,{headers:{Authorization:'Bearer fixture-reviewer','Idempotency-Key':'q07-disabled-delivery'}});expect(deliver.status()).toBe(403);expect((await deliver.json()).code).toBe('DELIVERY_DISABLED');
  54 |     await writeFile('test-results/q07-A07-output.json',JSON.stringify({fixture_only:true,draft:generated.draft,materialization:generated.materialized,viewer_export:denied.status(),delivery:deliver.status()},null,2));
  55 |   }finally{await context.close();await page.getByRole('combobox',{name:'語言',exact:true}).first().selectOption('en');await expect(page.locator('html')).toHaveAttribute('lang','en');}
  56 | });
  57 | 
```