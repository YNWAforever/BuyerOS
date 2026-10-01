import {expect,test,type Page} from '@playwright/test';
import {webcrypto} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {resolve} from 'node:path';
import {readFile} from 'node:fs/promises';
import {awaitCloudflareIntent} from './cloudflare-stack';

const execFileAsync=promisify(execFile);
const workspace='e0000000-0000-4000-8000-000000000001';
const project='e9100000-0000-4000-8000-000000000001';

export async function signIn(page:Page,accessToken='fixture-access',initialPath=`/app/runs?workspace=${workspace}&project=${project}`,locale:'en'|'zh-HK'='en'){
  const keys=await webcrypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,
    publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
  const publicKey={...(await webcrypto.subtle.exportKey('jwk',keys.publicKey)),kid:'research-fixture',use:'sig'};
  const encode=(value:unknown)=>Buffer.from(JSON.stringify(value)).toString('base64url');let nonce='';
  await page.route('https://oidc.buyeros.test/authorize**',async route=>{const q=new URL(route.request().url()).searchParams;
    nonce=q.get('nonce')||'';await route.fulfill({status:302,headers:{location:`http://localhost:5173/auth/callback?code=research-fixture&state=${q.get('state')}`},body:''});});
  await page.route('https://oidc.buyeros.test/oauth/token',async route=>{
    const unsigned=`${encode({alg:'RS256',kid:'research-fixture'})}.${encode({iss:'https://oidc.buyeros.test/',
      aud:'fixture-public-client',sub:accessToken,nonce,exp:Math.floor(Date.now()/1000)+900})}`;
    const signature=await webcrypto.subtle.sign('RSASSA-PKCS1-v1_5',keys.privateKey,new TextEncoder().encode(unsigned));
    await route.fulfill({status:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},
      body:JSON.stringify({access_token:accessToken,id_token:`${unsigned}.${Buffer.from(signature).toString('base64url')}`,expires_in:900})});});
  await page.route('https://oidc.buyeros.test/.well-known/jwks.json',async route=>route.fulfill({status:200,
    contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},body:JSON.stringify({keys:[publicKey]})}));
  await page.goto(initialPath);
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByRole('combobox',{name:/^(Project|專案)$/})).toHaveValue(new URL(initialPath,'http://localhost:5173').searchParams.get('project')!,{timeout:30_000});
  await page.locator('header select').selectOption(locale);
  await expect(page.locator('html')).toHaveAttribute('lang',locale);
}

// Fixed UI expectations; never import the application translation map.
const journeyZh:Record<string,string>={
  "Add selected to list": "將已選買家加入清單",
  "Approve exact revision": "批准此精確版本",
  "Approve profile": "批准輪廓",
  "Assign to me": "指派給我",
  "Authorized export": "授權匯出",
  "Body": "內容",
  "Business email": "工作電郵",
  "Buyer details: T30 Fictional Industrial Buyer": "買家詳情：T30 Fictional Industrial Buyer",
  "Buyer list": "買家清單",
  "Buyers": "買家",
  "Company name": "公司名稱",
  "Continue": "繼續",
  "Create list": "建立清單",
  "Details": "詳情",
  "Display name": "顯示名稱",
  "Distributor": "分銷商",
  "Download text": "下載文字",
  "Draft copy format": "草稿副本格式",
  "Draft list": "草稿列表",
  "Drafts": "草稿",
  "Edit offer": "編輯產品資料",
  "Evidence": "證據",
  "Exact revision review": "精確版本審核",
  "Generate addressed draft": "產生已指定收件人的草稿",
  "I confirm this sender identity": "我確認此寄件人身份",
  "Individual review reason": "個別審閱原因",
  "Languages (codes or names)": "語言（代碼或名稱）",
  "Language": "語言",
  "List name": "清單名稱",
  "Log outcome": "記錄成果",
  "Manual outcomes": "人手記錄成果",
  "Markets (country codes or names)": "市場（國家代碼或名稱）",
  "Maximum research cost (USD)": "研究費用上限（美元）",
  "Must have": "必要條件",
  "New project": "新增專案",
  "Open draft": "開啟草稿",
  "Organization": "機構",
  "Outcome notes": "成果備註",
  "Prepare approved copy": "準備已批准副本",
  "Prepare grounded draft": "準備有證據草稿",
  "Product / service": "產品／服務",
  "Profile version 1": "輪廓版本 1",
  "Profile version 2": "輪廓版本 2",
  "Project selection": "專案選擇",
  "Reason for change": "更改原因",
  "Recipient (optional)": "收件人（可選）",
  "Record manual outcome": "記錄人手成果",
  "Refresh job": "重新整理工作",
  "Request exact review": "要求審核此版本",
  "Research runs": "研究進度",
  "Results": "結果",
  "Save profile": "儲存輪廓",
  "Save sender": "儲存寄件人",
  "Select T30 Fictional Industrial Buyer": "選取 T30 Fictional Industrial Buyer",
  "Sender identity": "寄件人身份",
  "Show list buyers": "顯示清單買家",
  "Sign in": "Sign in",
  "Start research": "開始研究",
  "Target companies": "目標公司數",
  "Value proposition": "價值主張"
};

export function registerStaffJourney(transport:'celery'|'cloudflare'='celery'){
for(const locale of ['en','zh-HK'] as const){
for(const layout of ['desktop','mobile'] as const){
test(`${transport==='cloudflare'?'CF07':'T30'} ${locale} ${layout} UI-created offer through research, grounded addressed approval, export and outcome on one dataset`,async({page,browser,request})=>{
  test.setTimeout(360_000);
  page.setDefaultTimeout(10_000);
  const failedApi:string[]=[];
  page.on('response',async response=>{
    if(response.url().startsWith('http://127.0.0.1:8000/v1/')&&response.status()>=400){
      const body=await response.json().catch(()=>({}));
      failedApi.push(`${response.status()} ${new URL(response.url()).pathname} ${body.code??'unknown'} ${body.request_id??''}`);
      console.error('Fixture API failure:',failedApi.at(-1));
    }
  });
  const viewport=layout==='desktop'?{width:1280,height:800}:{width:390,height:844};
  await page.setViewportSize(viewport);
  const fits=async(target:Page)=>expect.poll(()=>target.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  const ui=(text:string)=>locale==='zh-HK'?(journeyZh[text]??text):text;
  await signIn(page,'fixture-access',undefined,locale);
  await page.getByRole('region',{name:ui('Project selection')}).getByRole('button',{name:ui('New project'),exact:true}).click();
  await page.getByLabel(ui('Company name')).fill('T30 Fictional Seller');
  await page.getByLabel(ui('Product / service')).fill('Industrial sensors');
  await page.getByLabel(ui('Value proposition')).fill('Fictional monitoring lowers production downtime.');
  await fits(page);
  await page.getByRole('button',{name:ui('Continue')}).click();
  await page.getByLabel(ui('Markets (country codes or names)')).fill('US');
  await page.getByLabel(ui('Languages (codes or names)')).fill('en');
  await page.getByRole('checkbox',{name:ui('Distributor'),exact:true}).check();
  await page.getByRole('button',{name:ui('Continue')}).click();
  await page.getByLabel(ui('Must have'),{exact:true}).fill('industrial sensors');
  await page.getByRole('checkbox',{name:locale==='en'?/I confirm these buyer requirements/:/我確認以上買家條件/}).check();
  await page.getByRole('button',{name:ui('Continue')}).click();
  await page.getByRole('button',{name:ui('Save profile')}).click();
  await expect(page.getByRole('heading',{name:ui('Profile version 1')})).toBeVisible();
  await fits(page);
  const project=new URL(page.url()).searchParams.get('project')!;
  expect(project).toMatch(/^[0-9a-f-]{36}$/);
  expect(project).not.toBe('e9100000-0000-4000-8000-000000000001');
  const workerRoot=resolve('services/worker');
  const python=resolve(workerRoot,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
  const prerequisites=await execFileAsync(python,['tests/fixtures/prepare_browser_project.py','prepare',project],
    {cwd:workerRoot,timeout:30_000});
  const prepared=JSON.parse(prerequisites.stdout);
  expect(prepared.fixture_prerequisites).toBe(true);
  expect(prepared.fixture_initial_rate_windows_reset).toBe(true);

  await page.getByRole('button',{name:ui('Edit offer')}).click();
  await expect(page.getByLabel(ui('Product / service'))).toHaveValue('Industrial sensors');
  await page.getByLabel(ui('Product / service')).fill('Industrial sensor platform');
  await page.getByLabel(ui('Value proposition')).fill('Fictional monitoring lowers production downtime.');
  await page.getByRole('button',{name:ui('Continue')}).click();
  await page.getByRole('button',{name:ui('Continue')}).click();
  await page.getByRole('checkbox',{name:locale==='en'?/I confirm these buyer requirements/:/我確認以上買家條件/}).check();
  await page.getByRole('button',{name:ui('Continue')}).click();
  await page.getByRole('button',{name:ui('Save profile')}).click();
  await expect(page.getByRole('heading',{name:ui('Profile version 2')})).toBeVisible();
  const reviewerContext=await browser.newContext({viewport});
  const reviewer=await reviewerContext.newPage();
  await signIn(reviewer,'fixture-reviewer',`/app?workspace=${workspace}&project=${project}`,locale);
  await expect(reviewer.getByRole('heading',{name:ui('Profile version 2')})).toBeVisible();
  await reviewer.getByRole('checkbox',{name:locale==='en'?/Confirm approval of this exact version v2/:/確認批准此確切版本 v2/}).check();
  await reviewer.getByRole('button',{name:ui('Approve profile')}).click();
  await expect(reviewer.getByText(locale==='en'?'Current approved: v2':'目前已批准: v2')).toBeVisible();
  await reviewer.getByRole('button',{name:ui('Drafts'),exact:true}).click();
  const sender=reviewer.getByRole('region',{name:ui('Sender identity')});
  await sender.getByLabel(ui('Display name')).fill('Fixture Alex');
  await sender.getByLabel(ui('Organization')).fill('T30 Fictional Seller');
  await sender.getByLabel(ui('Business email')).fill('alex@example.test');
  await sender.getByLabel(ui('Reason for change')).fill('Fictional sender reviewed for disposable journey');
  await sender.getByRole('checkbox',{name:ui('I confirm this sender identity')}).check();
  await sender.getByRole('button',{name:ui('Save sender')}).click();
  await expect(sender.getByText(locale==='en'?/Reviewed sender:/:/已審核寄件人:/)).toBeVisible();
  await page.reload();
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByText(locale==='en'?'Current approved: v2':'目前已批准: v2')).toBeVisible();
  await page.getByRole('button',{name:ui('Research runs')}).click();
  await page.getByLabel(ui('Target companies')).fill('1');
  await page.getByLabel(ui('Maximum research cost (USD)')).fill('2.000000');
  const admissionResponse=page.waitForResponse(response=>response.request().method()==='POST'
    &&new URL(response.url()).pathname.endsWith('/runs'));
  await page.getByRole('button',{name:ui('Start research')}).click();
  const admission=await admissionResponse;
  expect(admission.status(),await admission.text()).toBe(202);
  expect((await admission.json()).data.status).toBe('queued');
  await expect(page).toHaveURL(/\/app\/discover\/[0-9a-f-]{36}/);
  const runId=new URL(page.url()).pathname.split('/').at(-1)!;
  // Automatic dispatch can finish before navigation renders the first snapshot.
  const visibleStatus=transport==='cloudflare'
    ?(locale==='en'?/Status:\s*(queued|running|completed)\s*·/:/狀態:\s*(排隊中|進行中|已完成)\s*·/)
    :(locale==='en'?/Status:\s*queued\s*·/:/狀態:\s*排隊中\s*·/);
  await expect(page.getByText(visibleStatus)).toBeVisible();
  await fits(page);
  const {stdout}=transport==='cloudflare'?await awaitCloudflareIntent(runId,project):await execFileAsync(python,['tests/fixtures/run_browser_research.py',runId,project],
    {cwd:workerRoot,timeout:180_000,maxBuffer:1024*1024});
  const report=JSON.parse(stdout.trim().split(/\r?\n/).at(-1)!) as {run_id:string;status:string;evidence:number;buyers:number;fit_verdicts:string[];published:string[]};
  expect(report.run_id).toBe(runId);
  expect(report.evidence).toBeGreaterThanOrEqual(1);
  expect(report.buyers).toBeGreaterThanOrEqual(1);
  expect(report.published.length).toBeGreaterThanOrEqual(1);
  const contactInput=await execFileAsync(python,['tests/fixtures/prepare_browser_project.py','contact',project,runId],
    {cwd:workerRoot,timeout:30_000});
  const existingContact=JSON.parse(contactInput.stdout) as {buyer_id:string;contact_id:string;fixture_existing_contact:boolean};
  expect(existingContact.fixture_existing_contact).toBe(true);
  await page.getByRole('button',{name:ui('Buyers'),exact:true}).click();
  await expect(page.getByText('T30 Fictional Industrial Buyer',{exact:true})).toBeVisible({timeout:30_000});
  await page.getByRole('button',{name:ui('Details')}).first().click();
  const dossier=page.getByRole('dialog',{name:ui('Buyer details: T30 Fictional Industrial Buyer')});
  await dossier.getByRole('tab',{name:ui('Evidence')}).click();
  await expect(dossier).toContainText('Fictional distributor lists industrial sensors');
  await fits(page);
  await reviewer.getByRole('button',{name:ui('Buyers'),exact:true}).click();
  await expect(reviewer.getByText('T30 Fictional Industrial Buyer',{exact:true})).toBeVisible();
  await reviewer.getByRole('button',{name:ui('Details')}).first().click();
  const reviewDossier=reviewer.getByRole('dialog',{name:ui('Buyer details: T30 Fictional Industrial Buyer')});
  await expect(reviewDossier).toContainText(locale==='en'?'Fit: match':'配對: 符合');
  await reviewDossier.getByRole('textbox',{name:ui('Individual review reason')}).fill('Verified cited industrial buyer');
  await reviewDossier.getByRole('button',{name:locale==='en'?/^Save review/:/^儲存審閱/}).click();
  await reviewer.getByRole('checkbox',{name:ui('Select T30 Fictional Industrial Buyer')}).check();
  await reviewer.getByRole('textbox',{name:ui('List name')}).fill('T30 generated buyer');
  await reviewer.getByRole('button',{name:ui('Create list')}).click();
  await reviewer.getByRole('button',{name:ui('Add selected to list')}).click();
  await expect(reviewer.getByRole('combobox',{name:ui('Buyer list')})).toContainText('T30 generated buyer (1)');
  await reviewer.getByRole('button',{name:ui('Show list buyers')}).click();
  await expect(reviewer.getByText(locale==='en'?'1 in snapshot':'1 項快照')).toBeVisible();
  await reviewer.getByRole('button',{name:ui('Details')}).first().click();
  const assigned=reviewer.getByRole('dialog',{name:ui('Buyer details: T30 Fictional Industrial Buyer')});
  await expect(assigned).toContainText(locale==='en'?'Human review: accepted':'人手審閱: 已接納');
  await assigned.getByRole('button',{name:ui('Assign to me')}).click();
  await expect(assigned).toContainText(`${locale==='en'?'Owner membership:':'負責人成員:'} e0000000-0000-4000-8000-000000000005`);
  await page.reload();
  await page.getByRole('button',{name:'Sign in'}).click();
  await page.getByRole('button',{name:ui('Buyers'),exact:true}).click();
  try{await expect(page.getByText('T30 Fictional Industrial Buyer',{exact:true})).toBeVisible();}
  catch(cause){throw new Error(`Post-refresh buyer read failed: ${failedApi.join(' | ')}`,{cause});}
  await page.getByRole('button',{name:ui('Details')}).first().click();
  const operatorDossier=page.getByRole('dialog',{name:ui('Buyer details: T30 Fictional Industrial Buyer')});
  await expect(operatorDossier).toContainText(locale==='en'?'Human review: accepted':'人手審閱: 已接納');
  await operatorDossier.getByRole('button',{name:ui('Prepare grounded draft')}).click();
  await expect(page).toHaveURL(/\/app\/outreach\?/);
  await expect(page.getByText(locale==='en'?/Reviewed sender:/:/已審核寄件人:/)).toBeVisible();
  await expect(page.getByText('Industrial sensor platform',{exact:true})).toBeVisible();
  await expect(page.getByText(/Fictional distributor lists industrial sensors/)).toBeVisible();
  await page.getByRole('combobox',{name:ui('Recipient (optional)')}).selectOption(existingContact.contact_id);
  await page.getByRole('region',{name:ui('Prepare grounded draft')}).getByRole('combobox',{name:ui('Language'),exact:true}).selectOption(locale);
  await page.getByRole('button',{name:ui('Generate addressed draft')}).click();
  await expect.poll(()=>new URL(page.url()).searchParams.get('draft_job'),{timeout:30_000}).toMatch(/^[0-9a-f-]{36}$/);
  const draftJobId=new URL(page.url()).searchParams.get('draft_job')!;
  const draftRun=transport==='cloudflare'?await awaitCloudflareIntent(runId,project,draftJobId):await execFileAsync(python,['tests/fixtures/run_browser_research.py',runId,project,draftJobId!],
    {cwd:workerRoot,timeout:180_000,maxBuffer:1024*1024});
  const draftReport=JSON.parse(draftRun.stdout.trim().split(/\r?\n/).at(-1)!) as {job_id:string;status:string;draft_id:string;grounding_status:string};
  expect(draftReport.job_id).toBe(draftJobId);
  expect(draftReport.status).toBe('completed');
  expect(draftReport.grounding_status).toBe('grounded');
  await page.getByRole('button',{name:ui('Refresh job')}).click();
  await expect(page.getByRole('region',{name:ui('Draft list')}).getByRole('button',{name:ui('Open draft')})).toHaveCount(1);
  await page.getByRole('region',{name:ui('Draft list')}).getByRole('button',{name:ui('Open draft')}).click();
  await expect(page.getByRole('textbox',{name:ui('Body')})).toContainText('Industrial sensor platform');
  await expect(page.getByRole('textbox',{name:ui('Body')})).toContainText('Fictional distributor lists industrial sensors');
  await fits(page);
  const generatedDraft=new URL(page.url()).searchParams.get('draft')!;
  expect(generatedDraft).toBe(draftReport.draft_id);
  await page.getByRole('button',{name:ui('Request exact review')}).click();
  await expect(page.getByRole('region',{name:ui('Exact revision review')}).getByText('recipient@fixture.example.test',{exact:false})).toBeVisible();
  await signIn(reviewer,'fixture-reviewer',`/app/outreach?workspace=${workspace}&project=${project}&draft=${generatedDraft}`,locale);
  await expect(reviewer.getByRole('checkbox',{name:locale==='en'?/I confirm the exact recipient/:/我確認以上精確收件人/})).toBeVisible();
  await reviewer.getByRole('checkbox',{name:locale==='en'?/I confirm the exact recipient/:/我確認以上精確收件人/}).check();
  await reviewer.getByRole('button',{name:ui('Approve exact revision')}).click();
  await expect(reviewer.getByText(locale==='en'?/Approval recorded; delivery remains disabled/:/審批已記錄；發送功能仍停用/)).toBeVisible();
  const exportRegion=reviewer.getByRole('region',{name:ui('Authorized export')});
  await exportRegion.getByRole('combobox',{name:ui('Draft copy format')}).selectOption('text');
  await exportRegion.getByRole('button',{name:ui('Prepare approved copy')}).click();
  await expect(exportRegion).toContainText(locale==='en'?'Allowed: 1':'允許: 1');
  await fits(reviewer);
  await reviewer.screenshot({path:`test-results/${transport}-continuity-${locale}-${layout}-approved-export-fixture.png`,fullPage:true});
  const exportId=new URL(reviewer.url()).searchParams.get('export')!;
  const downloadPromise=reviewer.waitForEvent('download');
  await exportRegion.getByRole('button',{name:ui('Download text')}).click();
  const downloaded=await downloadPromise;
  const copy=await readFile((await downloaded.path())!,'utf8');
  expect(copy).toContain('recipient@fixture.example.test');
  expect(copy).toContain('Industrial sensor platform');
  expect(copy).toContain(locale==='en'?'Hello,':'你好，');
  const viewer=await request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/exports/${exportId}/content`,
    {headers:{Authorization:'Bearer fixture-viewer'}});
  expect(viewer.status()).toBe(403);
  const deliver=await request.post(`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${generatedDraft}/deliver`,
    {headers:{Authorization:'Bearer fixture-reviewer','Idempotency-Key':'t30-continuity-delivery-disabled'}});
  expect(deliver.status()).toBe(403);
  expect((await deliver.json()).code).toBe('DELIVERY_DISABLED');
  await page.getByRole('button',{name:ui('Results'),exact:true}).click();
  await page.getByRole('button',{name:ui('Log outcome')}).first().click();
  await page.getByRole('textbox',{name:ui('Outcome notes')}).fill('T30 continuous fixture outcome after approved copy');
  await page.getByRole('button',{name:ui('Record manual outcome')}).click();
  const outcomes=page.getByRole('region',{name:ui('Manual outcomes')});
  await expect(outcomes).toContainText('T30 continuous fixture outcome after approved copy');
  await page.reload();await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByRole('region',{name:ui('Manual outcomes')})).toContainText('T30 continuous fixture outcome after approved copy');
  await fits(page);
  await page.screenshot({path:`test-results/${transport}-continuity-${locale}-${layout}-outcome-fixture.png`,fullPage:true});
  await reviewerContext.close();
  await page.setViewportSize({width:390,height:844});
  await expect(page.locator('html')).toHaveAttribute('lang',locale);
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:`test-results/${transport}-continuity-${locale}-${layout}-mobile-readback-fixture.png`,fullPage:true});
});
}
}

}
