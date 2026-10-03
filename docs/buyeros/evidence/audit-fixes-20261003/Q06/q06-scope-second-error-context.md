# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-operations.spec.ts >> B16 old summary cannot overwrite another scope after A-B-A
- Location: tests\e2e\audit-operations.spec.ts:112:1

# Error details

```
Error: expect(locator).toContainText(expected) failed

Locator: getByRole('region', { name: 'Bulk job progress' })
Expected substring: "completed:"
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toContainText" getByRole('region', { name: 'Bulk job progress' }) with timeout 5000ms
  - waiting for getByRole('region', { name: 'Bulk job progress' })

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
      - option "Other audit fixture"
    - paragraph: "Role: reviewer"
  - region "Project selection":
    - heading "Projects" [level=2]
    - text: Project
    - combobox "Project":
      - option "Choose project"
      - option "Buyer Fixture Project" [selected]
      - option "Run Fixture Project"
  - region "Buyer results":
    - heading "Buyers" [level=2]
    - text: 1000 in snapshot
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
    - checkbox "Select Buyer Fixture 100"
    - text: Buyer Fixture 100
    - paragraph: Fit not assessed · Not reviewed · No note
    - button "Details"
    - checkbox "Select Buyer Fixture 1000"
    - text: Buyer Fixture 1000
    - paragraph: Fit not assessed · Not reviewed · No note
    - button "Details"
    - button "Previous page" [disabled]
    - text: Rows 1–12 of 1000
    - button "Next page"
    - text: Rows per page
    - combobox "Rows per page":
      - option "8"
      - option "12" [selected]
      - option "24"
    - text: Review status
    - combobox "Review status":
      - option "accepted" [selected]
      - option "rejected"
      - option "needs_information"
    - text: Review reason
    - textbox "Review reason"
    - button "Apply review" [disabled]
    - region "Authorized export":
      - heading "Authorized export" [level=3]
      - paragraph: Only current policy and, for addressed drafts, current exact approval allow content.
      - paragraph: Copy and download never send a message.
      - paragraph: "Selected scope: No selection"
      - checkbox "Include eligible contact data"
      - text: Include eligible contact data
      - paragraph: Company-only CSV
      - button "Prepare export" [disabled]
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
  19  |   const seen:string[]=[];
  20  |   for(let offset=0;offset<count;offset+=20){
  21  |     await expect(lookup.locator('code')).toHaveCount(Math.min(20,count-offset));
  22  |     await expect(lookup.getByText(`${offset+1}–${Math.min(offset+20,count)} / ${count}`,{exact:true})).toBeVisible();
  23  |     seen.push(...await lookup.locator('code').allTextContents());
  24  |     if(offset+20<count)await lookup.getByRole('button',{name:'Next results',exact:true}).click();
  25  |   }
  26  |   expect(seen).toEqual(seeded.ids);expect(new Set(seen).size).toBe(count);
  27  |   await expect(lookup.getByRole('button',{name:'Next results',exact:true})).toBeDisabled();
  28  |   await lookup.getByRole('button',{name:'Previous results',exact:true}).click();
  29  |   await expect(lookup.locator('code').first()).toHaveText(seeded.ids[Math.max(0,Math.floor((count-1)/20)*20-20)]);
  30  |   await page.screenshot({path:`test-results/audit-operations-${count}.png`,fullPage:true});
  31  | });
  32  | test('B11 zero results and late job response cannot replace newer job',async({page})=>{
  33  |   const old=await fixture(21),fresh=await fixture(0);await signInWorkbench(page);await page.getByRole('button',{name:'Operations',exact:true}).click();
  34  |   let release:()=>void=()=>{};const held=new Promise<void>(r=>release=r);
  35  |   await page.route(`**/v1/workspaces/${workspace}/jobs/${old.job_id}?**`,async route=>{const response=await route.fetch();await held;await route.fulfill({response}).catch(()=>{});});
  36  |   const lookup=page.getByRole('region',{name:'Job lookup'});
  37  |   await lookup.getByRole('textbox',{name:'Job ID'}).fill(old.job_id);await lookup.getByRole('button',{name:'Load job',exact:true}).click();
  38  |   await lookup.getByRole('textbox',{name:'Job ID'}).fill(fresh.job_id);await lookup.getByRole('button',{name:'Load job',exact:true}).click();
  39  |   await expect(lookup.getByText('0–0 / 0',{exact:true})).toBeVisible();release();
  40  |   await expect(lookup.locator('code')).toHaveCount(0);await page.waitForTimeout(300);await expect(lookup.getByText('0–0 / 0',{exact:true})).toBeVisible();
  41  | });
  42  | 
  43  | test('B11 late result page is discarded after workspace A-B-A',async({page})=>{
  44  |   const old=await fixture(21);await signInWorkbench(page);await page.getByRole('button',{name:'Operations',exact:true}).click();
  45  |   const lookup=page.getByRole('region',{name:'Job lookup'});
  46  |   await lookup.getByRole('textbox',{name:'Job ID'}).fill(old.job_id);await lookup.getByRole('button',{name:'Load job',exact:true}).click();
  47  |   await expect(lookup.locator('code').first()).toHaveText(old.ids[0]);
  48  |   let release:()=>void=()=>{};let received:()=>void=()=>{};const held=new Promise<void>(r=>release=r),started=new Promise<void>(r=>received=r);
  49  |   await page.route(`**/v1/workspaces/${workspace}/jobs/${old.job_id}?offset=20&limit=20`,async route=>{const response=await route.fetch();received();await held;await route.fulfill({response}).catch(()=>{});});
  50  |   await lookup.getByRole('button',{name:'Next results'}).click();await started;
  51  |   await page.getByRole('combobox',{name:'Workspace',exact:true}).selectOption('e0000000-0000-4000-8000-000000000101');
  52  |   await page.getByRole('combobox',{name:'Workspace',exact:true}).selectOption(workspace);release();
  53  |   await expect(lookup.locator('code')).toHaveCount(0);await page.waitForTimeout(300);await expect(lookup.locator('code')).toHaveCount(0);
  54  | });
  55  | 
  56  | 
  57  | test('B12 unopened 1000-result job reads summary only and never walks result pages',async({page})=>{
  58  |   const seeded=await fixture(1000,'running');
  59  |   const calls:string[]=[];page.on('request',r=>{if(new URL(r.url()).pathname.includes(`/jobs/${seeded.job_id}`))calls.push(new URL(r.url()).pathname);});
  60  |   await signInWorkbench(page,true,'reviewer',`/app?workspace=${workspace}&project=e1000000-0000-4000-8000-000000000001&bulk_job=${seeded.job_id}`);
  61  |   await page.getByRole('button',{name:'Buyers',exact:true}).click();
  62  |   await expect.poll(()=>calls.length).toBeGreaterThan(0);
  63  |   expect(calls[0]).toBe(`/v1/workspaces/${workspace}/jobs/${seeded.job_id}/summary`);
  64  |   await expect(page.getByRole('region',{name:'Bulk job progress'})).toContainText('1000 of 1000');
  65  |   await page.waitForTimeout(4500);expect(calls.every(path=>path.endsWith('/summary'))).toBe(true);
  66  | });
  67  | 
  68  | async function statusFixture(job:string,state:string){
  69  |   const cwd=resolve('services/worker'),python=resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
  70  |   const result=await promisify(execFile)(python,['tests/fixtures/audit_jobs.py','status',job,state],{cwd,timeout:30_000});expect(JSON.parse(result.stdout).fixture_only).toBe(true);
  71  | }
  72  | async function openBulk(page:Parameters<typeof signInWorkbench>[0],job:string){
  73  |   await signInWorkbench(page,true,'reviewer',`/app?workspace=${workspace}&project=e1000000-0000-4000-8000-000000000001&bulk_job=${job}`);
  74  |   await page.getByRole('combobox',{name:/^(Language|語言)$/}).selectOption('en');
  75  |   await page.getByRole('button',{name:'Buyers',exact:true}).click();
  76  |   return page.getByRole('region',{name:'Bulk job progress'});
  77  | }
  78  | 
  79  | test('B12 2.5s summary RTT never overlaps or preloads results; terminal refreshes visible page once',async({page})=>{
  80  |   const seeded=await fixture(1000,'running');let active=0,max=0,calls=0;const results:string[]=[];
  81  |   page.on('request',r=>{const u=new URL(r.url());if(u.pathname===`/v1/workspaces/${workspace}/jobs/${seeded.job_id}`)results.push(u.search);});
  82  |   await page.route(`**/jobs/${seeded.job_id}/summary`,async route=>{calls++;max=Math.max(max,++active);try{const response=await route.fetch();await new Promise(r=>setTimeout(r,2500));await route.fulfill({response}).catch(()=>{});}finally{active--;}});
  83  |   const panel=await openBulk(page,seeded.job_id);await expect(panel).toContainText('1000 of 1000');await page.waitForTimeout(6500);expect(calls).toBeGreaterThanOrEqual(2);expect(max).toBe(1);expect(results).toEqual([]);
  84  |   await panel.getByRole('button',{name:'Show job results',exact:true}).click();await expect(panel.locator('code')).toHaveCount(20);expect(results).toHaveLength(1);
  85  |   await panel.getByRole('button',{name:'Next job results',exact:true}).click();await expect(panel.getByText('21–40 / 1000',{exact:true})).toBeVisible();expect(results).toHaveLength(2);
  86  |   const terminalResponse=page.waitForResponse(async r=>new URL(r.url()).pathname.endsWith(`/jobs/${seeded.job_id}/summary`)&&r.status()===200&&(await r.json()).data.status==='completed',{timeout:12_000});
  87  |   await statusFixture(seeded.job_id,'completed');await terminalResponse;await expect(panel).toContainText('completed:');await expect.poll(()=>results.length).toBe(3);expect(results.at(-1)).toBe('?offset=20&limit=20');
  88  |   const final=calls;await page.waitForTimeout(4500);expect(calls).toBe(final);expect(results).toHaveLength(3);expect(max).toBe(1);
  89  |   writeFileSync('test-results/q06-slow-terminal.json',JSON.stringify({fixture_only:true,calls,max_in_flight:max,result_requests:results},null,2));await page.screenshot({path:'test-results/q06-bulk-en.png',fullPage:true});
  90  | });
  91  | 
  92  | test('B13 hidden summary pause and double visibility resume produce exactly one refresh',async({page})=>{
  93  |   await page.addInitScript(()=>{let hidden=false;Object.defineProperty(document,'hidden',{configurable:true,get:()=>hidden});window.addEventListener('audit-hidden',()=>{hidden=true;document.dispatchEvent(new Event('visibilitychange'));});window.addEventListener('audit-visible',()=>{hidden=false;document.dispatchEvent(new Event('visibilitychange'));});});
  94  |   const seeded=await fixture(21,'running');let calls=0;page.on('request',r=>{if(new URL(r.url()).pathname.endsWith(`/jobs/${seeded.job_id}/summary`))calls++;});
  95  |   const panel=await openBulk(page,seeded.job_id);await expect(panel).toContainText('21 of 21');
  96  |   await page.evaluate(()=>window.dispatchEvent(new Event('audit-hidden')));const before=calls;await page.waitForTimeout(4500);expect(calls).toBe(before);
  97  |   await page.evaluate(()=>{window.dispatchEvent(new Event('audit-visible'));window.dispatchEvent(new Event('audit-visible'));});await expect.poll(()=>calls).toBe(before+1);
  98  |   await page.evaluate(()=>window.dispatchEvent(new Event('audit-hidden')));await page.waitForTimeout(2500);expect(calls).toBe(before+1);await expect(panel.getByRole('alert')).toHaveCount(0);
  99  | });
  100 | 
  101 | test('B13 actual 429 Retry-After and 503 recover without result-page traffic',async({page})=>{
  102 |   const seeded=await fixture(21,'running'),times:number[]=[];let details=0;
  103 |   page.on('request',r=>{if(new URL(r.url()).pathname===`/v1/workspaces/${workspace}/jobs/${seeded.job_id}`)details++;});
  104 |   await page.route(`**/jobs/${seeded.job_id}/summary`,async route=>{
  105 |     times.push(Date.now());if(times.length<3)await route.fulfill({status:times.length===1?429:503,contentType:'application/json',headers:times.length===1?{'Retry-After':'3'}:{},body:JSON.stringify({code:times.length===1?'RATE_LIMITED':'INTERNAL_ERROR',message:'fixture failure',request_id:'e0000000-0000-4000-8000-000000000010',retryable:true})});else await route.continue();
  106 |   });
  107 |   const panel=await openBulk(page,seeded.job_id);await expect(panel.getByRole('alert')).toContainText('Service temporarily unavailable');await expect(panel).toContainText('21 of 21',{timeout:20_000});
  108 |   expect(times[1]-times[0]).toBeGreaterThanOrEqual(3000);expect(times[2]-times[1]).toBeGreaterThanOrEqual(4000);expect(details).toBe(0);await expect(panel.getByRole('alert')).toHaveCount(0);
  109 |   writeFileSync('test-results/q06-backoff.json',JSON.stringify({fixture_only:true,attempt_times:times,detail_requests:details},null,2));
  110 | });
  111 | 
  112 | test('B16 old summary cannot overwrite another scope after A-B-A',async({page})=>{
  113 |   const seeded=await fixture(21,'running');let release:()=>void=()=>{};let received:()=>void=()=>{};const held=new Promise<void>(r=>release=r),started=new Promise<void>(r=>received=r);let calls=0;
  114 |   await page.route(`**/jobs/${seeded.job_id}/summary`,async route=>{calls++;const response=await route.fetch();if(calls===1){received();await held;}await route.fulfill({response}).catch(()=>{});});
  115 |   await openBulk(page,seeded.job_id);await started;await statusFixture(seeded.job_id,'completed');
  116 |   await page.getByRole('combobox',{name:'Workspace',exact:true}).selectOption('e0000000-0000-4000-8000-000000000101');
  117 |   await expect(page.getByRole('region',{name:'Bulk job progress'})).toHaveCount(0);
  118 |   await page.getByRole('combobox',{name:'Workspace',exact:true}).selectOption(workspace);await page.getByRole('combobox',{name:'Project',exact:true}).selectOption('e1000000-0000-4000-8000-000000000001');await page.getByRole('button',{name:'Buyers',exact:true}).click();release();
> 119 |   const panel=page.getByRole('region',{name:'Bulk job progress'});await expect(panel).toContainText('completed:');await page.waitForTimeout(2500);await expect(panel).not.toContainText('running:');
      |                                                                                       ^ Error: expect(locator).toContainText(expected) failed
  120 | });
  121 | 
  122 | test('B13 zh-HK 390px summary/results controls remain usable without overflow',async({page})=>{
  123 |   const seeded=await fixture(21);await page.setViewportSize({width:390,height:844});const panel=await openBulk(page,seeded.job_id);
  124 |   await page.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');const zh=page.getByRole('region',{name:'批量工作進度'});await expect(zh).toContainText('已處理 21／21');
  125 |   await zh.getByRole('button',{name:'顯示工作結果',exact:true}).click();await expect(zh.locator('code')).toHaveCount(20);await zh.getByRole('button',{name:'下一頁工作結果',exact:true}).click();await expect(zh.getByText('21–21 / 21',{exact:true})).toBeVisible();
  126 |   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);await page.screenshot({path:'test-results/q06-bulk-zh-mobile.png',fullPage:true});
  127 |   const saved=page.waitForResponse(r=>r.request().method()==='PATCH'&&new URL(r.url()).pathname.endsWith('/preferences'));await page.getByRole('combobox',{name:'語言',exact:true}).selectOption('en');expect((await saved).status()).toBe(200);
  128 |   await expect(panel).toBeVisible();
  129 | });
  130 | 
```