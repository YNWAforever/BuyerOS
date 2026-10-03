# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-draft-reground.spec.ts >> D01/D03 manual Unicode draft exposes a source review and operator cannot attest
- Location: tests\e2e\audit-draft-reground.spec.ts:23:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('region', { name: 'Open draft', exact: true }).getByRole('region', { name: 'Manual source review', exact: true })
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('region', { name: 'Open draft', exact: true }).getByRole('region', { name: 'Manual source review', exact: true }) with timeout 5000ms
  - waiting for getByRole('region', { name: 'Open draft', exact: true }).getByRole('region', { name: 'Manual source review', exact: true })

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
  - region "Drafts":
    - heading "Drafts" [level=2]
    - paragraph: Prepare a grounded draft; delivery is disabled.
    - status: Human edits require a new grounding review before approval.
    - region "Sender identity":
      - heading "Sender identity" [level=3]
      - paragraph: "Reviewed sender: Fixture Alex · Fictional Seller · alex@example.test · sender:ea000000-0000-4000-8000-000000000001:1"
    - region "Prepare grounded draft":
      - heading "Prepare grounded draft" [level=3]
      - paragraph:
        - strong: Free fixed template
      - paragraph: Template language changes only fixed headings, opening and closing; offer facts and source citations stay in their original language and are not automatically translated.
      - paragraph: Edit the draft manually after generation; changes need a new grounding review before approval.
      - paragraph: Buyer Fixture 01 · 1 · accepted
      - group "Approved offer facts":
        - text: Approved offer facts
        - checkbox "Fictional industrial sensors" [checked]
        - text: Fictional industrial sensors
      - group "Supporting buyer evidence":
        - text: Supporting buyer evidence
        - checkbox "Fixture public catalog lists industrial sensors. · v1" [checked]
        - text: Fixture public catalog lists industrial sensors. · v1
      - paragraph: Initial
      - text: Recipient (optional)
      - combobox "Recipient (optional)":
        - option "No recipient — unaddressed draft"
        - option "recipient@fixture.example.test · v1" [selected]
      - text: Internal work objective — does not change the template body
      - textbox "Internal work objective — does not change the template body": Introduce the approved offer
      - text: Template language
      - combobox "Template language":
        - option "English"
        - option "繁體中文" [selected]
      - button "Generate addressed draft"
    - status:
      - heading "Job status" [level=3]
      - paragraph: ec04795d-34f7-408f-a9aa-1c2bc30095b6 · completed
      - button "Refresh job"
    - region "Draft list":
      - heading "Draft list" [level=3]
      - paragraph: 1–2 / 2
      - text: "Introduction: Fictional industrial sensors · draft · v1"
      - button "Open draft"
      - text: 邀請😀了解產品 · draft · v2
      - button "Open draft"
      - button "Previous page" [disabled]
      - button "Next page" [disabled]
    - region "Open draft":
      - heading "邀請😀了解產品" [level=3]
      - paragraph: "Revision: 2 · draft · zh-HK"
      - paragraph: Delivery is disabled.
      - text: Subject
      - textbox "Subject": 邀請😀了解產品
      - text: Body
      - textbox "Body": 您好👩‍💻 Fictional industrial sensors Fixture public catalog lists industrial sensors. 謝謝！
      - text: Language
      - combobox "Language":
        - option "English"
        - option "繁體中文" [selected]
      - button "Save revision" [disabled]
      - button "Prepare follow-up"
      - heading "Claims and sources" [level=4]
      - paragraph: Human edits require a new grounding review before approval.
      - region "Exact revision review":
        - heading "Exact revision review" [level=4]
        - paragraph: "Revision: 2 · 378b9d6d0730ec3fc0e34b351d1fa1dbb74ca06d3aeae5492d33b754c49cf048"
        - paragraph: An eligible addressed draft and current policy are required before review.
        - button "Refresh draft"
```

# Test source

```ts
  1  | import {expect,test,type Page} from '@playwright/test';
  2  | import {execFile} from 'node:child_process';
  3  | import {promisify} from 'node:util';
  4  | import {resolve} from 'node:path';
  5  | import {signInWorkbench,workspace,project,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';
  6  | const buyer='e2000000-0000-4000-8000-000000000001';
  7  | const subject='邀請😀了解產品';
  8  | const body='您好👩‍💻\nFictional industrial sensors\nFixture public catalog lists industrial sensors.\n謝謝！';
  9  | async function fixture(...args:string[]){const cwd=resolve('services/worker');return JSON.parse((await promisify(execFile)(resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python'),['tests/fixtures/audit_template.py',...args],{cwd,timeout:60_000})).stdout);}
  10 | async function editedDraft(page:Page){
  11 |  await resetWorkbenchFixtureRateWindows();const seed=await fixture('prepare');
  12 |  await signInWorkbench(page,true,'access',`/app/outreach?workspace=${workspace}&project=${project}&buyer=${buyer}`);
  13 |  await page.getByRole('combobox',{name:/^(Language|語言)$/,exact:true}).first().selectOption('en');await expect(page.locator('html')).toHaveAttribute('lang','en');
  14 |  const prepare=page.getByRole('region',{name:'Prepare grounded draft',exact:true});await prepare.getByRole('combobox',{name:'Recipient (optional)',exact:true}).selectOption(seed.contact);
  15 |  const pending=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith(`/projects/${project}/drafts`));
  16 |  await prepare.getByRole('button',{name:'Generate addressed draft',exact:true}).click();const response=await pending;expect(response.status()).toBe(202);
  17 |  const materialized=await fixture('materialize',(await response.json()).data.id);expect(materialized.duplicate).toBe('duplicate');
  18 |  await page.getByRole('button',{name:'Refresh job',exact:true}).click();const editor=page.getByRole('region',{name:'Open draft',exact:true});await expect(editor).toBeVisible();
  19 |  await editor.getByRole('textbox',{name:'Subject',exact:true}).fill(subject);await editor.getByRole('textbox',{name:'Body',exact:true}).fill(body);await editor.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');
  20 |  await editor.getByRole('button',{name:'Save revision',exact:true}).click();await expect(editor).not.toHaveAttribute('data-live-unsaved','true');
  21 |  return {id:materialized.draft,editor,materialized};
  22 | }
  23 | test('D01/D03 manual Unicode draft exposes a source review and operator cannot attest',async({page})=>{
  24 |  const {editor}=await editedDraft(page);await expect(editor).toContainText('Human edits require a new grounding review before approval.');
> 25 |  const grounding=editor.getByRole('region',{name:'Manual source review',exact:true});await expect(grounding).toBeVisible();
     |                                                                                                              ^ Error: expect(locator).toBeVisible() failed
  26 |  await expect(grounding).toContainText('A reviewer must submit this source review.');
  27 |  await expect(grounding.getByRole('button',{name:'Submit source review',exact:true})).toHaveCount(0);
  28 |  await expect(editor.getByRole('textbox',{name:'Body',exact:true})).toHaveValue(body);
  29 | });
  30 | 
```