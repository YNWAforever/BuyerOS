# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-bulk-manifest.spec.ts >> B14 clipped snapshots have a separate explicit segmented maintenance preview
- Location: tests\e2e\audit-bulk-manifest.spec.ts:4:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('region', { name: 'Buyer results', exact: true }).getByRole('button', { name: 'Preview segmented maintenance', exact: true })
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('region', { name: 'Buyer results', exact: true }).getByRole('button', { name: 'Preview segmented maintenance', exact: true }) with timeout 5000ms
  - waiting for getByRole('region', { name: 'Buyer results', exact: true }).getByRole('button', { name: 'Preview segmented maintenance', exact: true })

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
    - text: 24 in snapshot
    - group "Buyer filters":
      - text: Search buyers
      - textbox "Search buyers"
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
    - checkbox "Select Buyer Fixture 01"
    - text: Buyer Fixture 01
    - paragraph: match · accepted · No note
    - button "Details"
    - checkbox "Select Buyer Fixture 02"
    - text: Buyer Fixture 02
    - paragraph: needs_review · Not reviewed · No note
    - button "Details"
    - checkbox "Select Buyer Fixture 03"
    - text: Buyer Fixture 03
    - paragraph: Fit not assessed · Not reviewed · No note
    - button "Details"
    - checkbox "Select Buyer Fixture 04"
    - text: Buyer Fixture 04
    - paragraph: Fit not assessed · Not reviewed · No note
    - button "Details"
    - checkbox "Select Buyer Fixture 05"
    - text: Buyer Fixture 05
    - paragraph: Fit not assessed · Not reviewed · No note
    - button "Details"
    - checkbox "Select Buyer Fixture 06"
    - text: Buyer Fixture 06
    - paragraph: Fit not assessed · Not reviewed · No note
    - button "Details"
    - checkbox "Select Buyer Fixture 07"
    - text: Buyer Fixture 07
    - paragraph: Fit not assessed · Not reviewed · No note
    - button "Details"
    - checkbox "Select Buyer Fixture 08"
    - text: Buyer Fixture 08
    - paragraph: Fit not assessed · Not reviewed · No note
    - button "Details"
    - checkbox "Select Buyer Fixture 09"
    - text: Buyer Fixture 09
    - paragraph: Fit not assessed · Not reviewed · No note
    - button "Details"
    - checkbox "Select Buyer Fixture 10"
    - text: Buyer Fixture 10
    - paragraph: Fit not assessed · Not reviewed · No note
    - button "Details"
    - checkbox "Select Buyer Fixture 11"
    - text: Buyer Fixture 11
    - paragraph: Fit not assessed · Not reviewed · No note
    - button "Details"
    - checkbox "Select Buyer Fixture 12"
    - text: Buyer Fixture 12
    - paragraph: Fit not assessed · Not reviewed · No note
    - button "Details"
    - button "Previous page" [disabled]
    - text: Rows 1–12 of 24
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
  1  | import {expect,test} from '@playwright/test';
  2  | import {signInWorkbench} from './fixtures/workbench-auth';
  3  | 
  4  | test('B14 clipped snapshots have a separate explicit segmented maintenance preview',async({page})=>{
  5  |  await signInWorkbench(page,true,'access');
  6  |  await page.getByRole('combobox',{name:/^(Language|語言)$/}).selectOption('en');
  7  |  await page.getByRole('button',{name:'Buyers',exact:true}).click();
  8  |  const buyers=page.getByRole('region',{name:'Buyer results',exact:true});
  9  |  await expect(buyers.getByRole('checkbox',{name:/^Select /})).toHaveCount(12);
> 10 |  await expect(buyers.getByRole('button',{name:'Preview segmented maintenance',exact:true})).toBeVisible();
     |                                                                                             ^ Error: expect(locator).toBeVisible() failed
  11 | });
  12 | 
```