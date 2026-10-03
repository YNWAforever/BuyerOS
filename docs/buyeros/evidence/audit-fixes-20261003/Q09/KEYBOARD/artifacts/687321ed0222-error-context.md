# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-keyboard.spec.ts >> T30 keyboard en mobile UI-created offer through research, grounded addressed approval, export and outcome on one dataset
- Location: tests\e2e\fixtures\staff-journey.ts:105:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('heading', { name: 'Profile version 2' })
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('heading', { name: 'Profile version 2' }) with timeout 5000ms
  - waiting for getByRole('heading', { name: 'Profile version 2' })

```

```yaml
- main:
  - text: FIMMICK BuyerOS 正式工作區 語言
  - combobox "語言":
    - option "English"
    - option "繁體中文" [selected]
  - button "登出"
  - navigation "BuyerOS sections":
    - button "總覽"
    - button "產品資料" [disabled]
    - button "買家"
    - button "結果"
    - button "研究進度"
    - button "草稿"
    - button "設定"
    - button "營運工作台"
  - region "工作區選擇":
    - heading "工作區" [level=2]
    - text: 工作區
    - combobox "工作區":
      - option "選擇工作區"
      - option "E2E fixture workspace" [selected]
    - paragraph: "角色: 審批員"
  - region "專案選擇":
    - heading "專案" [level=2]
    - text: 專案
    - combobox "專案":
      - option "選擇專案"
      - option "Buyer Fixture Project"
      - option "Run Fixture Project"
      - option "T30 Fictional Seller"
      - option "T30 Fictional Seller"
      - option "T30 Fictional Seller"
      - option "T30 Fictional Seller"
      - option "Q14 project B"
      - option "T30 Fictional Seller"
      - option "T30 Fictional Seller" [selected]
  - region "每日工作佇列":
    - heading "每日工作佇列" [level=2]
    - paragraph: "截至: 10/4/2026, 5:18:19 AM"
    - group: 技術資料
    - text: 待審買家
    - button "開啟"
    - text: 待批准事項
    - button "開啟"
    - text: 未分派買家
    - button "開啟"
    - text: 失敗工作
    - paragraph: "0"
    - button "開啟"
    - text: 適合度未明
    - button "開啟"
    - text: 供應商接納狀態未明
    - button "開啟"
  - region "使用量":
    - heading "使用量" [level=2]
    - paragraph: 以 UTC 半開區間計算；更改語言不會改動日期。
    - text: 開始日期（UTC）
    - textbox "開始日期（UTC）": 2026-10-01
    - text: 結束日期（UTC）
    - textbox "結束日期（UTC）": 2026-11-01
    - button "套用區間"
    - button "更新使用量"
    - paragraph: "截至: 4/10/2026 上午5:18:19"
    - group: 技術資料
    - text: 已結算計量費用
    - paragraph: 0.000000 USD
    - text: 有效預留金額
    - paragraph: 0.000000 USD
    - text: 剩餘已批准預算
    - paragraph: 10.000000 USD
    - text: 新接納公司
    - paragraph: "0"
    - text: 可聯絡的已接納公司
    - paragraph: "0"
    - text: 每家已接納公司的期間平均費用
    - paragraph: —
    - text: 每家可聯絡公司的期間平均費用
    - paragraph: —
    - paragraph: 實際入帳費用包括失敗、部分完成工作及有正負號的退款；預留款項分開顯示。分母為零時顯示「—」。
    - group: 費用類別
  - region "輪廓詳情":
    - heading "輪廓詳情" [level=2]
    - paragraph: T30 Fictional Seller · 專案版本 2
    - paragraph: "目前已批准: —"
    - heading "輪廓歷史" [level=3]
    - group "輪廓歷史":
      - button "v2 · 已儲存" [pressed]
      - button "v1 · 已儲存"
    - article:
      - heading "輪廓版本 2 · 已儲存" [level=3]
      - heading "產品事實" [level=4]
      - list:
        - listitem: "產品: Industrial sensor platform · 用戶輸入"
        - listitem: "價值主張: Fictional monitoring lowers production downtime. · 用戶輸入"
      - paragraph: "來源: —"
      - heading "買家條件" [level=4]
      - list:
        - listitem: "必要: industrial sensors"
      - paragraph: "市場: US · 語言: en"
      - paragraph: "買家類型: distributor · 期望買家職位（選填）: —"
      - heading "與上一版本的差異" [level=4]
      - paragraph: 產品事實
      - checkbox "確認批准此確切版本 v2"
      - text: 確認批准此確切版本 v2
      - button "批准輪廓" [disabled]
```

# Test source

```ts
  62  |   "Generate addressed draft": "產生已指定收件人的草稿",
  63  |   "I confirm this sender identity": "我確認此寄件人身份",
  64  |   "Individual review reason": "個別審閱原因",
  65  |   "Languages (codes or names)": "語言（代碼或名稱）",
  66  |   "Language": "語言",
  67  |   "Template language": "模板語言",
  68  |   "List name": "清單名稱",
  69  |   "Log outcome": "記錄成果",
  70  |   "Manual outcomes": "人手記錄成果",
  71  |   "Markets (country codes or names)": "市場（國家代碼或名稱）",
  72  |   "Maximum research cost (USD)": "研究費用上限（美元）",
  73  |   "Must have": "必要條件",
  74  |   "New project": "新增專案",
  75  |   "Open draft": "開啟草稿",
  76  |   "Organization": "機構",
  77  |   "Outcome notes": "成果備註",
  78  |   "Prepare approved copy": "準備已批准副本",
  79  |   "Prepare grounded draft": "準備有證據草稿",
  80  |   "Product / service": "產品／服務",
  81  |   "Profile version 1": "輪廓版本 1",
  82  |   "Profile version 2": "輪廓版本 2",
  83  |   "Project selection": "專案選擇",
  84  |   "Reason for change": "更改原因",
  85  |   "Recipient (optional)": "收件人（可選）",
  86  |   "Record manual outcome": "記錄人手成果",
  87  |   "Refresh job": "重新整理工作",
  88  |   "Request exact review": "要求審核此版本",
  89  |   "Research runs": "研究進度",
  90  |   "Results": "結果",
  91  |   "Save profile": "儲存輪廓",
  92  |   "Save sender": "儲存寄件人",
  93  |   "Select T30 Fictional Industrial Buyer": "選取 T30 Fictional Industrial Buyer",
  94  |   "Sender identity": "寄件人身份",
  95  |   "Show list buyers": "顯示清單買家",
  96  |   "Sign in": "登入",
  97  |   "Start research": "開始研究",
  98  |   "Target companies": "目標公司數",
  99  |   "Value proposition": "價值主張"
  100 | };
  101 | 
  102 | export function registerStaffJourney(transport:'celery'|'cloudflare'='celery',inputMode:JourneyInputMode='pointer'){
  103 | for(const locale of ['en','zh-HK'] as const){
  104 | for(const layout of ['desktop','mobile'] as const){
  105 | test(`${transport==='cloudflare'?'CF07':'T30'} ${inputMode==='keyboard'?'keyboard ':''}${locale} ${layout} UI-created offer through research, grounded addressed approval, export and outcome on one dataset`,async({page,browser,request})=>{
  106 |   test.setTimeout(inputMode==='keyboard'?600_000:360_000);
  107 |   const input=createJourneyInput(inputMode);await input.install(page);
  108 |   page.setDefaultTimeout(10_000);
  109 |   const failedApi:string[]=[];
  110 |   page.on('response',async response=>{
  111 |     if(response.url().startsWith('http://127.0.0.1:8000/v1/')&&response.status()>=400){
  112 |       const body=await response.json().catch(()=>({}));
  113 |       failedApi.push(`${response.status()} ${new URL(response.url()).pathname} ${body.code??'unknown'} ${body.request_id??''}`);
  114 |       console.error('Fixture API failure:',failedApi.at(-1));
  115 |     }
  116 |   });
  117 |   const viewport=layout==='desktop'?{width:1280,height:800}:{width:390,height:844};
  118 |   await page.setViewportSize(viewport);
  119 |   const fits=async(target:Page)=>expect.poll(()=>target.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  120 |   const ui=(text:string)=>locale==='zh-HK'?(journeyZh[text]??text):text;
  121 |   await signIn(page,'fixture-access',undefined,locale,inputMode,input);
  122 |   await input.activate(page.getByRole('region',{name:ui('Project selection')}).getByRole('button',{name:ui('New project'),exact:true}));
  123 |   await input.fill(page.getByLabel(ui('Company name')),'T30 Fictional Seller');
  124 |   await input.fill(page.getByLabel(ui('Product / service')),'Industrial sensors');
  125 |   await input.fill(page.getByLabel(ui('Value proposition')),'Fictional monitoring lowers production downtime.');
  126 |   await fits(page);
  127 |   await input.activate(page.getByRole('button',{name:ui('Continue')}));
  128 |   await input.fill(page.getByLabel(ui('Markets (country codes or names)')),'US');
  129 |   await input.fill(page.getByLabel(ui('Languages (codes or names)')),'en');
  130 |   await input.check(page.getByRole('checkbox',{name:ui('Distributor'),exact:true}));
  131 |   await input.activate(page.getByRole('button',{name:ui('Continue')}));
  132 |   await input.fill(page.getByRole('textbox',{name:ui('Must have'),exact:true}),'industrial sensors');
  133 |   await input.check(page.getByRole('checkbox',{name:locale==='en'?/I confirm these buyer requirements/:/我確認以上買家條件/}));
  134 |   await input.activate(page.getByRole('button',{name:ui('Continue')}));
  135 |   await input.activate(page.getByRole('button',{name:ui('Save profile')}));
  136 |   await expect(page.getByRole('heading',{name:ui('Profile version 1')})).toBeVisible();
  137 |   await fits(page);
  138 |   const project=new URL(page.url()).searchParams.get('project')!;
  139 |   expect(project).toMatch(/^[0-9a-f-]{36}$/);
  140 |   expect(project).not.toBe('e9100000-0000-4000-8000-000000000001');
  141 |   const workerRoot=resolve('services/worker');
  142 |   const python=resolve(workerRoot,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
  143 |   const prerequisites=await execFileAsync(python,['tests/fixtures/prepare_browser_project.py','prepare',project],
  144 |     {cwd:workerRoot,timeout:30_000});
  145 |   const prepared=JSON.parse(prerequisites.stdout);
  146 |   expect(prepared.fixture_prerequisites).toBe(true);
  147 |   expect(prepared.fixture_initial_rate_windows_reset).toBe(true);
  148 | 
  149 |   await input.activate(page.getByRole('button',{name:ui('Edit offer')}));
  150 |   await expect(page.getByLabel(ui('Product / service'))).toHaveValue('Industrial sensors');
  151 |   await input.fill(page.getByLabel(ui('Product / service')),'Industrial sensor platform');
  152 |   await input.fill(page.getByLabel(ui('Value proposition')),'Fictional monitoring lowers production downtime.');
  153 |   await input.activate(page.getByRole('button',{name:ui('Continue')}));
  154 |   await input.activate(page.getByRole('button',{name:ui('Continue')}));
  155 |   await input.check(page.getByRole('checkbox',{name:locale==='en'?/I confirm these buyer requirements/:/我確認以上買家條件/}));
  156 |   await input.activate(page.getByRole('button',{name:ui('Continue')}));
  157 |   await input.activate(page.getByRole('button',{name:ui('Save profile')}));
  158 |   await expect(page.getByRole('heading',{name:ui('Profile version 2')})).toBeVisible();
  159 |   const reviewerContext=await browser.newContext({viewport});
  160 |   const reviewer=await reviewerContext.newPage();await input.install(reviewer);
  161 |   await signIn(reviewer,'fixture-reviewer',`/app?workspace=${workspace}&project=${project}`,locale,inputMode,input);
> 162 |   await expect(reviewer.getByRole('heading',{name:ui('Profile version 2')})).toBeVisible();
      |                                                                              ^ Error: expect(locator).toBeVisible() failed
  163 |   await input.check(reviewer.getByRole('checkbox',{name:locale==='en'?/Confirm approval of this exact version v2/:/確認批准此確切版本 v2/}));
  164 |   await input.activate(reviewer.getByRole('button',{name:ui('Approve profile')}));
  165 |   await expect(reviewer.getByText(locale==='en'?'Current approved: v2':'目前已批准: v2')).toBeVisible();
  166 |   await input.activate(reviewer.getByRole('button',{name:ui('Drafts'),exact:true}));
  167 |   const sender=reviewer.getByRole('region',{name:ui('Sender identity')});
  168 |   await input.fill(sender.getByLabel(ui('Display name')),'Fixture Alex');
  169 |   await input.fill(sender.getByLabel(ui('Organization')),'T30 Fictional Seller');
  170 |   await input.fill(sender.getByLabel(ui('Business email')),'alex@example.test');
  171 |   await input.fill(sender.getByLabel(ui('Reason for change')),'Fictional sender reviewed for disposable journey');
  172 |   await input.check(sender.getByRole('checkbox',{name:ui('I confirm this sender identity')}));
  173 |   await input.activate(sender.getByRole('button',{name:ui('Save sender')}));
  174 |   await expect(sender.getByText(locale==='en'?/Reviewed sender:/:/已審核寄件人:/)).toBeVisible();
  175 |   await page.reload();
  176 |   await input.activate(page.getByRole('button',{name:/^(Sign in|登入)$/,exact:true}));
  177 |   await expect(page.locator('html')).toHaveAttribute('lang',locale);
  178 |   await expect(page.getByText(locale==='en'?'Current approved: v2':'目前已批准: v2')).toBeVisible();
  179 |   await input.activate(page.getByRole('button',{name:ui('Research runs')}));
  180 |   await input.fill(page.getByLabel(ui('Target companies')),'1');
  181 |   await input.fill(page.getByLabel(ui('Maximum research cost (USD)')),'2.000000');
  182 |   const admissionResponse=page.waitForResponse(response=>response.request().method()==='POST'
  183 |     &&new URL(response.url()).pathname.endsWith('/runs'));
  184 |   await input.activate(page.getByRole('button',{name:ui('Start research')}));
  185 |   const admission=await admissionResponse;
  186 |   expect(admission.status(),await admission.text()).toBe(202);
  187 |   expect((await admission.json()).data.status).toBe('queued');
  188 |   await expect(page).toHaveURL(/\/app\/discover\/[0-9a-f-]{36}/);
  189 |   const runId=new URL(page.url()).pathname.split('/').at(-1)!;
  190 |   // Automatic dispatch can finish before navigation renders the first snapshot.
  191 |   const visibleStatus=transport==='cloudflare'
  192 |     ?(locale==='en'?/Status:\s*(queued|running|completed)\s*·/:/狀態:\s*(排隊中|進行中|已完成)\s*·/)
  193 |     :(locale==='en'?/Status:\s*queued\s*·/:/狀態:\s*排隊中\s*·/);
  194 |   await expect(page.getByText(visibleStatus)).toBeVisible();
  195 |   await fits(page);
  196 |   const {stdout}=transport==='cloudflare'?await awaitCloudflareIntent(runId,project):await execFileAsync(python,['tests/fixtures/run_browser_research.py',runId,project],
  197 |     {cwd:workerRoot,timeout:180_000,maxBuffer:1024*1024});
  198 |   const report=JSON.parse(stdout.trim().split(/\r?\n/).at(-1)!) as {run_id:string;status:string;evidence:number;buyers:number;fit_verdicts:string[];published:string[]};
  199 |   expect(report.run_id).toBe(runId);
  200 |   expect(report.evidence).toBeGreaterThanOrEqual(1);
  201 |   expect(report.buyers).toBeGreaterThanOrEqual(1);
  202 |   expect(report.published.length).toBeGreaterThanOrEqual(1);
  203 |   const contactInput=await execFileAsync(python,['tests/fixtures/prepare_browser_project.py','contact',project,runId],
  204 |     {cwd:workerRoot,timeout:30_000});
  205 |   const existingContact=JSON.parse(contactInput.stdout) as {buyer_id:string;contact_id:string;fixture_existing_contact:boolean};
  206 |   expect(existingContact.fixture_existing_contact).toBe(true);
  207 |   await input.activate(page.getByRole('button',{name:ui('Buyers'),exact:true}));
  208 |   await expect(page.getByText('T30 Fictional Industrial Buyer',{exact:true})).toBeVisible({timeout:30_000});
  209 |   await input.activate(page.getByRole('button',{name:ui('Details')}).first());
  210 |   const dossier=page.getByRole('dialog',{name:ui('Buyer details: T30 Fictional Industrial Buyer')});
  211 |   await input.activate(dossier.getByRole('tab',{name:ui('Evidence')}));
  212 |   await expect(dossier).toContainText('Fictional distributor lists industrial sensors');
  213 |   await fits(page);
  214 |   await input.activate(reviewer.getByRole('button',{name:ui('Buyers'),exact:true}));
  215 |   await expect(reviewer.getByText('T30 Fictional Industrial Buyer',{exact:true})).toBeVisible();
  216 |   await input.activate(reviewer.getByRole('button',{name:ui('Details')}).first());
  217 |   const reviewDossier=reviewer.getByRole('dialog',{name:ui('Buyer details: T30 Fictional Industrial Buyer')});
  218 |   await expect(reviewDossier).toContainText(locale==='en'?'Fit: match':'配對: 符合');
  219 |   await input.fill(reviewDossier.getByRole('textbox',{name:ui('Individual review reason')}),'Verified cited industrial buyer');
  220 |   await input.activate(reviewDossier.getByRole('button',{name:locale==='en'?/^Save review/:/^儲存審閱/}));
  221 |   await input.check(reviewer.getByRole('checkbox',{name:ui('Select T30 Fictional Industrial Buyer')}));
  222 |   await input.fill(reviewer.getByRole('textbox',{name:ui('List name')}),'T30 generated buyer');
  223 |   await input.activate(reviewer.getByRole('button',{name:ui('Create list')}));
  224 |   await input.activate(reviewer.getByRole('button',{name:ui('Add selected to list')}));
  225 |   await expect(reviewer.getByRole('combobox',{name:ui('Buyer list')})).toContainText('T30 generated buyer (1)');
  226 |   await input.activate(reviewer.getByRole('button',{name:ui('Show list buyers')}));
  227 |   await expect(reviewer.getByText(locale==='en'?'1 in snapshot':'1 項快照')).toBeVisible();
  228 |   await input.activate(reviewer.getByRole('button',{name:ui('Details')}).first());
  229 |   const assigned=reviewer.getByRole('dialog',{name:ui('Buyer details: T30 Fictional Industrial Buyer')});
  230 |   await expect(assigned).toContainText(locale==='en'?'Human review: accepted':'人手審閱: 已接納');
  231 |   await input.activate(assigned.getByRole('button',{name:ui('Assign to me')}));
  232 |   await expect(assigned).toContainText(`${locale==='en'?'Owner membership:':'負責人成員:'} e0000000-0000-4000-8000-000000000005`);
  233 |   await page.reload();
  234 |   await input.activate(page.getByRole('button',{name:/^(Sign in|登入)$/,exact:true}));
  235 |   await input.activate(page.getByRole('button',{name:ui('Buyers'),exact:true}));
  236 |   try{await expect(page.getByText('T30 Fictional Industrial Buyer',{exact:true})).toBeVisible();}
  237 |   catch(cause){throw new Error(`Post-refresh buyer read failed: ${failedApi.join(' | ')}`,{cause});}
  238 |   await input.activate(page.getByRole('button',{name:ui('Details')}).first());
  239 |   const operatorDossier=page.getByRole('dialog',{name:ui('Buyer details: T30 Fictional Industrial Buyer')});
  240 |   await expect(operatorDossier).toContainText(locale==='en'?'Human review: accepted':'人手審閱: 已接納');
  241 |   await input.activate(operatorDossier.getByRole('button',{name:ui('Prepare grounded draft')}));
  242 |   await expect(page).toHaveURL(/\/app\/outreach\?/);
  243 |   await expect(page.getByText(locale==='en'?/Reviewed sender:/:/已審核寄件人:/)).toBeVisible();
  244 |   await expect(page.getByText('Industrial sensor platform',{exact:true})).toBeVisible();
  245 |   await expect(page.getByText(/Fictional distributor lists industrial sensors/)).toBeVisible();
  246 |   await input.choose(page.getByRole('combobox',{name:ui('Recipient (optional)')}),existingContact.contact_id);
  247 |   await input.choose(page.getByRole('region',{name:ui('Prepare grounded draft')}).getByRole('combobox',{name:ui('Template language'),exact:true}),locale);
  248 |   await input.activate(page.getByRole('button',{name:ui('Generate addressed draft')}));
  249 |   await expect.poll(()=>new URL(page.url()).searchParams.get('draft_job'),{timeout:30_000}).toMatch(/^[0-9a-f-]{36}$/);
  250 |   const draftJobId=new URL(page.url()).searchParams.get('draft_job')!;
  251 |   const draftRun=transport==='cloudflare'?await awaitCloudflareIntent(runId,project,draftJobId):await execFileAsync(python,['tests/fixtures/run_browser_research.py',runId,project,draftJobId!],
  252 |     {cwd:workerRoot,timeout:180_000,maxBuffer:1024*1024});
  253 |   const draftReport=JSON.parse(draftRun.stdout.trim().split(/\r?\n/).at(-1)!) as {job_id:string;status:string;draft_id:string;grounding_status:string};
  254 |   expect(draftReport.job_id).toBe(draftJobId);
  255 |   expect(draftReport.status).toBe('completed');
  256 |   expect(draftReport.grounding_status).toBe('grounded');
  257 |   await input.activate(page.getByRole('button',{name:ui('Refresh job')}));
  258 |   await expect(page.getByRole('region',{name:ui('Draft list')}).getByRole('button',{name:ui('Open draft')})).toHaveCount(1);
  259 |   await input.activate(page.getByRole('region',{name:ui('Draft list')}).getByRole('button',{name:ui('Open draft')}));
  260 |   await expect(page.getByRole('textbox',{name:ui('Body'),exact:true})).toContainText('Industrial sensor platform');
  261 |   await expect(page.getByRole('textbox',{name:ui('Body'),exact:true})).toContainText('Fictional distributor lists industrial sensors');
  262 |   await fits(page);
```