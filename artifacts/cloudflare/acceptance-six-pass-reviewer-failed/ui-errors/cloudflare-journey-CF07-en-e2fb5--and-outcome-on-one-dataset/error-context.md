# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: cloudflare-journey.spec.ts >> CF07 en desktop UI-created offer through research, grounded addressed approval, export and outcome on one dataset
- Location: tests\e2e\fixtures\staff-journey.ts:102:1

# Error details

```
Error: expect(locator).toHaveValue(expected) failed

Locator: getByRole('combobox', { name: /^(Project|專案)$/ })
Expected: "57574602-cdd3-4b94-8fe9-e47c16f73288"
Timeout: 30000ms
Error: element(s) not found

Call log:
  - Expect "toHaveValue" getByRole('combobox', { name: /^(Project|專案)$/ }) with timeout 30000ms
  - waiting for getByRole('combobox', { name: /^(Project|專案)$/ })

```

```yaml
- main:
  - text: FIMMICK BuyerOS Live workspace Language
  - combobox "Language" [disabled]:
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
    - button "Settings" [disabled]
    - button "Operations" [disabled]
  - region "Workspace selection":
    - heading "Workspaces" [level=2]
    - alert: Service temporarily unavailable. Retry after checking the status.
    - button "Retry loading workspaces"
```

# Test source

```ts
  1   | import {expect,test,type Page} from '@playwright/test';
  2   | import {webcrypto} from 'node:crypto';
  3   | import {execFile} from 'node:child_process';
  4   | import {promisify} from 'node:util';
  5   | import {resolve} from 'node:path';
  6   | import {readFile} from 'node:fs/promises';
  7   | import {awaitCloudflareIntent} from './cloudflare-stack';
  8   |
  9   | const execFileAsync=promisify(execFile);
  10  | const workspace='e0000000-0000-4000-8000-000000000001';
  11  | const project='e9100000-0000-4000-8000-000000000001';
  12  |
  13  | export async function signIn(page:Page,accessToken='fixture-access',initialPath=`/app/runs?workspace=${workspace}&project=${project}`,locale:'en'|'zh-HK'='en'){
  14  |   const keys=await webcrypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,
  15  |     publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
  16  |   const publicKey={...(await webcrypto.subtle.exportKey('jwk',keys.publicKey)),kid:'research-fixture',use:'sig'};
  17  |   const encode=(value:unknown)=>Buffer.from(JSON.stringify(value)).toString('base64url');let nonce='';
  18  |   await page.route('https://oidc.buyeros.test/authorize**',async route=>{const q=new URL(route.request().url()).searchParams;
  19  |     nonce=q.get('nonce')||'';await route.fulfill({status:302,headers:{location:`http://localhost:5173/auth/callback?code=research-fixture&state=${q.get('state')}`},body:''});});
  20  |   await page.route('https://oidc.buyeros.test/oauth/token',async route=>{
  21  |     const unsigned=`${encode({alg:'RS256',kid:'research-fixture'})}.${encode({iss:'https://oidc.buyeros.test/',
  22  |       aud:'fixture-public-client',sub:accessToken,nonce,exp:Math.floor(Date.now()/1000)+900})}`;
  23  |     const signature=await webcrypto.subtle.sign('RSASSA-PKCS1-v1_5',keys.privateKey,new TextEncoder().encode(unsigned));
  24  |     await route.fulfill({status:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},
  25  |       body:JSON.stringify({access_token:accessToken,id_token:`${unsigned}.${Buffer.from(signature).toString('base64url')}`,expires_in:900})});});
  26  |   await page.route('https://oidc.buyeros.test/.well-known/jwks.json',async route=>route.fulfill({status:200,
  27  |     contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},body:JSON.stringify({keys:[publicKey]})}));
  28  |   await page.goto(initialPath);
  29  |   await page.getByRole('button',{name:'Sign in'}).click();
> 30  |   await expect(page.getByRole('combobox',{name:/^(Project|專案)$/})).toHaveValue(new URL(initialPath,'http://localhost:5173').searchParams.get('project')!,{timeout:30_000});
      |                                                                    ^ Error: expect(locator).toHaveValue(expected) failed
  31  |   await page.locator('header select').selectOption(locale);
  32  |   await expect(page.locator('html')).toHaveAttribute('lang',locale);
  33  | }
  34  |
  35  | // Fixed UI expectations; never import the application translation map.
  36  | const journeyZh:Record<string,string>={
  37  |   "Add selected to list": "將已選買家加入清單",
  38  |   "Approve exact revision": "批准此精確版本",
  39  |   "Approve profile": "批准輪廓",
  40  |   "Assign to me": "指派給我",
  41  |   "Authorized export": "授權匯出",
  42  |   "Body": "內容",
  43  |   "Business email": "工作電郵",
  44  |   "Buyer details: T30 Fictional Industrial Buyer": "買家詳情：T30 Fictional Industrial Buyer",
  45  |   "Buyer list": "買家清單",
  46  |   "Buyers": "買家",
  47  |   "Company name": "公司名稱",
  48  |   "Continue": "繼續",
  49  |   "Create list": "建立清單",
  50  |   "Details": "詳情",
  51  |   "Display name": "顯示名稱",
  52  |   "Distributor": "分銷商",
  53  |   "Download text": "下載文字",
  54  |   "Draft copy format": "草稿副本格式",
  55  |   "Draft list": "草稿列表",
  56  |   "Drafts": "草稿",
  57  |   "Edit offer": "編輯產品資料",
  58  |   "Evidence": "證據",
  59  |   "Exact revision review": "精確版本審核",
  60  |   "Generate addressed draft": "產生已指定收件人的草稿",
  61  |   "I confirm this sender identity": "我確認此寄件人身份",
  62  |   "Individual review reason": "個別審閱原因",
  63  |   "Languages (codes or names)": "語言（代碼或名稱）",
  64  |   "Language": "語言",
  65  |   "List name": "清單名稱",
  66  |   "Log outcome": "記錄成果",
  67  |   "Manual outcomes": "人手記錄成果",
  68  |   "Markets (country codes or names)": "市場（國家代碼或名稱）",
  69  |   "Maximum research cost (USD)": "研究費用上限（美元）",
  70  |   "Must have": "必要條件",
  71  |   "New project": "新增專案",
  72  |   "Open draft": "開啟草稿",
  73  |   "Organization": "機構",
  74  |   "Outcome notes": "成果備註",
  75  |   "Prepare approved copy": "準備已批准副本",
  76  |   "Prepare grounded draft": "準備有證據草稿",
  77  |   "Product / service": "產品／服務",
  78  |   "Profile version 1": "輪廓版本 1",
  79  |   "Profile version 2": "輪廓版本 2",
  80  |   "Project selection": "專案選擇",
  81  |   "Reason for change": "更改原因",
  82  |   "Recipient (optional)": "收件人（可選）",
  83  |   "Record manual outcome": "記錄人手成果",
  84  |   "Refresh job": "重新整理工作",
  85  |   "Request exact review": "要求審核此版本",
  86  |   "Research runs": "研究進度",
  87  |   "Results": "結果",
  88  |   "Save profile": "儲存輪廓",
  89  |   "Save sender": "儲存寄件人",
  90  |   "Select T30 Fictional Industrial Buyer": "選取 T30 Fictional Industrial Buyer",
  91  |   "Sender identity": "寄件人身份",
  92  |   "Show list buyers": "顯示清單買家",
  93  |   "Sign in": "Sign in",
  94  |   "Start research": "開始研究",
  95  |   "Target companies": "目標公司數",
  96  |   "Value proposition": "價值主張"
  97  | };
  98  |
  99  | export function registerStaffJourney(transport:'celery'|'cloudflare'='celery'){
  100 | for(const locale of ['en','zh-HK'] as const){
  101 | for(const layout of ['desktop','mobile'] as const){
  102 | test(`${transport==='cloudflare'?'CF07':'T30'} ${locale} ${layout} UI-created offer through research, grounded addressed approval, export and outcome on one dataset`,async({page,browser,request})=>{
  103 |   test.setTimeout(360_000);
  104 |   page.setDefaultTimeout(10_000);
  105 |   const failedApi:string[]=[];
  106 |   page.on('response',async response=>{
  107 |     if(response.url().startsWith('http://127.0.0.1:8000/v1/')&&response.status()>=400){
  108 |       const body=await response.json().catch(()=>({}));
  109 |       failedApi.push(`${response.status()} ${new URL(response.url()).pathname} ${body.code??'unknown'} ${body.request_id??''}`);
  110 |       console.error('Fixture API failure:',failedApi.at(-1));
  111 |     }
  112 |   });
  113 |   const viewport=layout==='desktop'?{width:1280,height:800}:{width:390,height:844};
  114 |   await page.setViewportSize(viewport);
  115 |   const fits=async(target:Page)=>expect.poll(()=>target.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  116 |   const ui=(text:string)=>locale==='zh-HK'?(journeyZh[text]??text):text;
  117 |   await signIn(page,'fixture-access',undefined,locale);
  118 |   await page.getByRole('region',{name:ui('Project selection')}).getByRole('button',{name:ui('New project'),exact:true}).click();
  119 |   await page.getByLabel(ui('Company name')).fill('T30 Fictional Seller');
  120 |   await page.getByLabel(ui('Product / service')).fill('Industrial sensors');
  121 |   await page.getByLabel(ui('Value proposition')).fill('Fictional monitoring lowers production downtime.');
  122 |   await fits(page);
  123 |   await page.getByRole('button',{name:ui('Continue')}).click();
  124 |   await page.getByLabel(ui('Markets (country codes or names)')).fill('US');
  125 |   await page.getByLabel(ui('Languages (codes or names)')).fill('en');
  126 |   await page.getByRole('checkbox',{name:ui('Distributor'),exact:true}).check();
  127 |   await page.getByRole('button',{name:ui('Continue')}).click();
  128 |   await page.getByLabel(ui('Must have'),{exact:true}).fill('industrial sensors');
  129 |   await page.getByRole('checkbox',{name:locale==='en'?/I confirm these buyer requirements/:/我確認以上買家條件/}).check();
  130 |   await page.getByRole('button',{name:ui('Continue')}).click();
```
