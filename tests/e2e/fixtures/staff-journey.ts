import {expect,test,type Page} from '@playwright/test';
import {webcrypto} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {resolve} from 'node:path';
import {readFile} from 'node:fs/promises';
import {awaitCloudflareIntent} from './cloudflare-stack';
import {createJourneyInput,observeWorkspaceLocale,type JourneyInputMode} from './journey-input';

const execFileAsync=promisify(execFile);
const workspace='e0000000-0000-4000-8000-000000000001';
const project='e9100000-0000-4000-8000-000000000001';

export async function signIn(page:Page,accessToken='fixture-access',initialPath=`/app/runs?workspace=${workspace}&project=${project}`,locale:'en'|'zh-HK'='en',inputMode:JourneyInputMode='pointer',providedInput?:ReturnType<typeof createJourneyInput>){
  const input=providedInput??createJourneyInput(inputMode);await input.install(page);
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
  const localeRead=inputMode==='keyboard'?observeWorkspaceLocale(page,workspace):null;
  try{
    await page.goto(initialPath);
    await input.activate(page.getByRole('button',{name:/^(Sign in|登入)$/}));
    await expect(page.getByRole('combobox',{name:/^(Project|專案)$/})).toHaveValue(new URL(initialPath,'http://localhost:5173').searchParams.get('project')!,{timeout:30_000});
    if(localeRead)await localeRead.settle();
  }finally{localeRead?.dispose();}
  await input.choose(page.locator('header select'),locale);
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
  "Template language": "模板語言",
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
  "Sign in": "登入",
  "Start research": "開始研究",
  "Target companies": "目標公司數",
  "Value proposition": "價值主張"
};

export function registerStaffJourney(transport:'celery'|'cloudflare'='celery',inputMode:JourneyInputMode='pointer'){
for(const locale of ['en','zh-HK'] as const){
for(const layout of ['desktop','mobile'] as const){
test(`${transport==='cloudflare'?'CF07':'T30'} ${inputMode==='keyboard'?'keyboard ':''}${locale} ${layout} UI-created offer through research, grounded addressed approval, export and outcome on one dataset`,async({page,browser,request})=>{
  test.setTimeout(inputMode==='keyboard'?600_000:360_000);
  const input=createJourneyInput(inputMode);await input.install(page);
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
  await signIn(page,'fixture-access',undefined,locale,inputMode,input);
  await input.activate(page.getByRole('region',{name:ui('Project selection')}).getByRole('button',{name:ui('New project'),exact:true}));
  await input.fill(page.getByLabel(ui('Company name')),'T30 Fictional Seller');
  await input.fill(page.getByLabel(ui('Product / service')),'Industrial sensors');
  await input.fill(page.getByLabel(ui('Value proposition')),'Fictional monitoring lowers production downtime.');
  await fits(page);
  await input.activate(page.getByRole('button',{name:ui('Continue')}));
  await input.fill(page.getByLabel(ui('Markets (country codes or names)')),'US');
  await input.fill(page.getByLabel(ui('Languages (codes or names)')),'en');
  await input.check(page.getByRole('checkbox',{name:ui('Distributor'),exact:true}));
  await input.activate(page.getByRole('button',{name:ui('Continue')}));
  await input.fill(page.getByRole('textbox',{name:ui('Must have'),exact:true}),'industrial sensors');
  await input.check(page.getByRole('checkbox',{name:locale==='en'?/I confirm these buyer requirements/:/我確認以上買家條件/}));
  await input.activate(page.getByRole('button',{name:ui('Continue')}));
  await input.activate(page.getByRole('button',{name:ui('Save profile')}));
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

  await input.activate(page.getByRole('button',{name:ui('Edit offer')}));
  await expect(page.getByLabel(ui('Product / service'))).toHaveValue('Industrial sensors');
  await input.fill(page.getByLabel(ui('Product / service')),'Industrial sensor platform');
  await input.fill(page.getByLabel(ui('Value proposition')),'Fictional monitoring lowers production downtime.');
  await input.activate(page.getByRole('button',{name:ui('Continue')}));
  await input.activate(page.getByRole('button',{name:ui('Continue')}));
  await input.check(page.getByRole('checkbox',{name:locale==='en'?/I confirm these buyer requirements/:/我確認以上買家條件/}));
  await input.activate(page.getByRole('button',{name:ui('Continue')}));
  await input.activate(page.getByRole('button',{name:ui('Save profile')}));
  await expect(page.getByRole('heading',{name:ui('Profile version 2')})).toBeVisible();
  const reviewerContext=await browser.newContext({viewport});
  const reviewer=await reviewerContext.newPage();await input.install(reviewer);
  await signIn(reviewer,'fixture-reviewer',`/app?workspace=${workspace}&project=${project}`,locale,inputMode,input);
  await expect(reviewer.getByRole('heading',{name:ui('Profile version 2')})).toBeVisible();
  await input.check(reviewer.getByRole('checkbox',{name:locale==='en'?/Confirm approval of this exact version v2/:/確認批准此確切版本 v2/}));
  await input.activate(reviewer.getByRole('button',{name:ui('Approve profile')}));
  await expect(reviewer.getByText(locale==='en'?'Current approved: v2':'目前已批准: v2')).toBeVisible();
  await input.activate(reviewer.getByRole('button',{name:ui('Drafts'),exact:true}));
  const sender=reviewer.getByRole('region',{name:ui('Sender identity')});
  await input.fill(sender.getByLabel(ui('Display name')),'Fixture Alex');
  await input.fill(sender.getByLabel(ui('Organization')),'T30 Fictional Seller');
  await input.fill(sender.getByLabel(ui('Business email')),'alex@example.test');
  await input.fill(sender.getByLabel(ui('Reason for change')),'Fictional sender reviewed for disposable journey');
  await input.check(sender.getByRole('checkbox',{name:ui('I confirm this sender identity')}));
  await input.activate(sender.getByRole('button',{name:ui('Save sender')}));
  await expect(sender.getByText(locale==='en'?/Reviewed sender:/:/已審核寄件人:/)).toBeVisible();
  await page.reload();
  await input.activate(page.getByRole('button',{name:/^(Sign in|登入)$/,exact:true}));
  await expect(page.locator('html')).toHaveAttribute('lang',locale);
  await expect(page.getByText(locale==='en'?'Current approved: v2':'目前已批准: v2')).toBeVisible();
  await input.activate(page.getByRole('button',{name:ui('Research runs')}));
  await input.fill(page.getByLabel(ui('Target companies')),'1');
  await input.fill(page.getByLabel(ui('Maximum research cost (USD)')),'2.000000');
  const admissionResponse=page.waitForResponse(response=>response.request().method()==='POST'
    &&new URL(response.url()).pathname.endsWith('/runs'));
  await input.activate(page.getByRole('button',{name:ui('Start research')}));
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
  await input.activate(page.getByRole('button',{name:ui('Buyers'),exact:true}));
  await expect(page.getByText('T30 Fictional Industrial Buyer',{exact:true})).toBeVisible({timeout:30_000});
  await input.activate(page.getByRole('button',{name:ui('Details')}).first());
  const dossier=page.getByRole('dialog',{name:ui('Buyer details: T30 Fictional Industrial Buyer')});
  await input.activate(dossier.getByRole('tab',{name:ui('Evidence')}));
  await expect(dossier).toContainText('Fictional distributor lists industrial sensors');
  await fits(page);
  await input.activate(reviewer.getByRole('button',{name:ui('Buyers'),exact:true}));
  await expect(reviewer.getByText('T30 Fictional Industrial Buyer',{exact:true})).toBeVisible();
  await input.activate(reviewer.getByRole('button',{name:ui('Details')}).first());
  const reviewDossier=reviewer.getByRole('dialog',{name:ui('Buyer details: T30 Fictional Industrial Buyer')});
  await expect(reviewDossier).toContainText(locale==='en'?'Fit: match':'配對: 符合');
  await input.fill(reviewDossier.getByRole('textbox',{name:ui('Individual review reason')}),'Verified cited industrial buyer');
  await input.activate(reviewDossier.getByRole('button',{name:locale==='en'?/^Save review/:/^儲存審閱/}));
  await input.check(reviewer.getByRole('checkbox',{name:ui('Select T30 Fictional Industrial Buyer')}));
  await input.fill(reviewer.getByRole('textbox',{name:ui('List name')}),'T30 generated buyer');
  await input.activate(reviewer.getByRole('button',{name:ui('Create list')}));
  await input.activate(reviewer.getByRole('button',{name:ui('Add selected to list')}));
  await expect(reviewer.getByRole('combobox',{name:ui('Buyer list')})).toContainText('T30 generated buyer (1)');
  await input.activate(reviewer.getByRole('button',{name:ui('Show list buyers')}));
  await expect(reviewer.getByText(locale==='en'?'1 in snapshot':'1 項快照')).toBeVisible();
  await input.activate(reviewer.getByRole('button',{name:ui('Details')}).first());
  const assigned=reviewer.getByRole('dialog',{name:ui('Buyer details: T30 Fictional Industrial Buyer')});
  await expect(assigned).toContainText(locale==='en'?'Human review: accepted':'人手審閱: 已接納');
  await input.activate(assigned.getByRole('button',{name:ui('Assign to me')}));
  await expect(assigned).toContainText(`${locale==='en'?'Owner membership:':'負責人成員:'} e0000000-0000-4000-8000-000000000005`);
  await page.reload();
  await input.activate(page.getByRole('button',{name:/^(Sign in|登入)$/,exact:true}));
  await input.activate(page.getByRole('button',{name:ui('Buyers'),exact:true}));
  try{await expect(page.getByText('T30 Fictional Industrial Buyer',{exact:true})).toBeVisible();}
  catch(cause){throw new Error(`Post-refresh buyer read failed: ${failedApi.join(' | ')}`,{cause});}
  await input.activate(page.getByRole('button',{name:ui('Details')}).first());
  const operatorDossier=page.getByRole('dialog',{name:ui('Buyer details: T30 Fictional Industrial Buyer')});
  await expect(operatorDossier).toContainText(locale==='en'?'Human review: accepted':'人手審閱: 已接納');
  await input.activate(operatorDossier.getByRole('button',{name:ui('Prepare grounded draft')}));
  await expect(page).toHaveURL(/\/app\/outreach\?/);
  await expect(page.getByText(locale==='en'?/Reviewed sender:/:/已審核寄件人:/)).toBeVisible();
  await expect(page.getByText('Industrial sensor platform',{exact:true})).toBeVisible();
  await expect(page.getByText(/Fictional distributor lists industrial sensors/)).toBeVisible();
  await input.choose(page.getByRole('combobox',{name:ui('Recipient (optional)')}),existingContact.contact_id);
  await input.choose(page.getByRole('region',{name:ui('Prepare grounded draft')}).getByRole('combobox',{name:ui('Template language'),exact:true}),locale);
  await input.activate(page.getByRole('button',{name:ui('Generate addressed draft')}));
  await expect.poll(()=>new URL(page.url()).searchParams.get('draft_job'),{timeout:30_000}).toMatch(/^[0-9a-f-]{36}$/);
  const draftJobId=new URL(page.url()).searchParams.get('draft_job')!;
  const draftRun=transport==='cloudflare'?await awaitCloudflareIntent(runId,project,draftJobId):await execFileAsync(python,['tests/fixtures/run_browser_research.py',runId,project,draftJobId!],
    {cwd:workerRoot,timeout:180_000,maxBuffer:1024*1024});
  const draftReport=JSON.parse(draftRun.stdout.trim().split(/\r?\n/).at(-1)!) as {job_id:string;status:string;draft_id:string;grounding_status:string};
  expect(draftReport.job_id).toBe(draftJobId);
  expect(draftReport.status).toBe('completed');
  expect(draftReport.grounding_status).toBe('grounded');
  await input.activate(page.getByRole('button',{name:ui('Refresh job')}));
  await expect(page.getByRole('region',{name:ui('Draft list')}).getByRole('button',{name:ui('Open draft')})).toHaveCount(1);
  await input.activate(page.getByRole('region',{name:ui('Draft list')}).getByRole('button',{name:ui('Open draft')}));
  await expect(page.getByRole('textbox',{name:ui('Body'),exact:true})).toContainText('Industrial sensor platform');
  await expect(page.getByRole('textbox',{name:ui('Body'),exact:true})).toContainText('Fictional distributor lists industrial sensors');
  await fits(page);
  const generatedDraft=new URL(page.url()).searchParams.get('draft')!;
  expect(generatedDraft).toBe(draftReport.draft_id);
  if(inputMode==='keyboard'){
    const editor=page.getByRole('region',{name:ui('Open draft'),exact:true});
    const manualBody=[locale==='en'?'Hello,':'你好，','Industrial sensor platform','Fictional distributor lists industrial sensors',locale==='en'?'Thank you.':'謝謝！'].join('\n');
    await input.fill(editor.getByRole('textbox',{name:locale==='en'?'Subject':'主旨',exact:true}),'Keyboard invitation😀');
    await input.fill(editor.getByRole('textbox',{name:ui('Body'),exact:true}),manualBody);
    await expect(editor).toHaveAttribute('data-live-unsaved','true');
    await input.activate(editor.getByRole('button',{name:locale==='en'?'Save revision':'儲存修訂',exact:true}));
    await expect(editor).not.toHaveAttribute('data-live-unsaved','true');
    const grounding=editor.getByRole('region',{name:locale==='en'?'Manual source review':'人工來源覆核',exact:true});
    await expect(grounding).toBeVisible();
    await expect(grounding.getByRole('button',{name:locale==='en'?'Submit source review':'提交來源覆核',exact:true})).toHaveCount(0);
    await expect(editor.getByRole('textbox',{name:ui('Body'),exact:true})).toHaveValue(manualBody);
  }else{
    await input.activate(page.getByRole('button',{name:ui('Request exact review')}));
    await expect(page.getByRole('region',{name:ui('Exact revision review')}).getByText('recipient@fixture.example.test',{exact:false})).toBeVisible();
  }
  await signIn(reviewer,'fixture-reviewer',`/app/outreach?workspace=${workspace}&project=${project}&draft=${generatedDraft}`,locale,inputMode,input);
  if(inputMode==='keyboard'){
    const grounding=reviewer.getByRole('region',{name:locale==='en'?'Manual source review':'人工來源覆核',exact:true});
    const groups=grounding.getByRole('group');await expect(groups).toHaveCount(5);
    for(let i=0;i<5;i++){
      const group=groups.nth(i),text=await group.locator('pre').innerText();
      const offer=text==='Industrial sensor platform',evidence=text==='Fictional distributor lists industrial sensors';
      await input.choose(group.getByRole('combobox'),offer||evidence?'factual':'non_factual');
      await input.fill(group.getByRole('textbox'),offer||evidence?'Read exact retained versioned source':'Greeting, invitation or closing without a factual claim');
      if(offer)await input.check(group.getByRole('checkbox',{name:locale==='en'?/^Offer fact: Industrial sensor platform/:/^產品事實: Industrial sensor platform/}));
      if(evidence)await input.check(group.getByRole('checkbox',{name:locale==='en'?/^Evidence.*Fictional distributor lists industrial sensors/:/^證據.*Fictional distributor lists industrial sensors/}));
    }
    await input.fill(grounding.getByRole('textbox',{name:locale==='en'?'Overall review reason':'整體覆核理由',exact:true}),'Reviewed the full keyboard-edited message and exact retained sources');
    await input.check(grounding.getByRole('checkbox',{name:locale==='en'?/^I read the entire exact message/:/^我已閱讀整篇精確訊息/}));
    const reviewed=reviewer.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/grounding-reviews'));
    await input.activate(grounding.getByRole('button',{name:locale==='en'?'Submit source review':'提交來源覆核',exact:true}));expect((await reviewed).status()).toBe(200);
    await expect(reviewer.getByRole('textbox',{name:ui('Body'),exact:true})).toHaveValue([locale==='en'?'Hello,':'你好，','Industrial sensor platform','Fictional distributor lists industrial sensors',locale==='en'?'Thank you.':'謝謝！'].join('\n'));
    await input.activate(reviewer.getByRole('button',{name:ui('Request exact review'),exact:true}));
  }
  await expect(reviewer.getByRole('checkbox',{name:locale==='en'?/I confirm the exact recipient/:/我確認以上精確收件人/})).toBeVisible();
  await input.check(reviewer.getByRole('checkbox',{name:locale==='en'?/I confirm the exact recipient/:/我確認以上精確收件人/}));
  await input.activate(reviewer.getByRole('button',{name:ui('Approve exact revision')}));
  await expect(reviewer.getByText(locale==='en'?/Approval recorded; delivery remains disabled/:/審批已記錄；發送功能仍停用/)).toBeVisible();
  const exportRegion=reviewer.getByRole('region',{name:ui('Authorized export')});
  await input.choose(exportRegion.getByRole('combobox',{name:ui('Draft copy format')}),'text');
  await input.activate(exportRegion.getByRole('button',{name:ui('Prepare approved copy')}));
  await expect(exportRegion).toContainText(locale==='en'?'Allowed: 1':'允許: 1');
  await fits(reviewer);
  await reviewer.screenshot({path:`test-results/${transport}${inputMode==='keyboard'?'-keyboard':''}-continuity-${locale}-${layout}-approved-export-fixture.png`,fullPage:true});
  const exportId=new URL(reviewer.url()).searchParams.get('export')!;
  const downloadPromise=reviewer.waitForEvent('download');
  await input.activate(exportRegion.getByRole('button',{name:ui('Download text')}));
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
  await input.activate(page.getByRole('button',{name:ui('Results'),exact:true}));
  await input.activate(page.getByRole('button',{name:ui('Log outcome')}).first());
  await input.fill(page.getByRole('textbox',{name:ui('Outcome notes')}),'T30 continuous fixture outcome after approved copy');
  await input.activate(page.getByRole('button',{name:ui('Record manual outcome')}));
  const outcomes=page.getByRole('region',{name:ui('Manual outcomes')});
  await expect(outcomes).toContainText('T30 continuous fixture outcome after approved copy');
  await page.reload();await input.activate(page.getByRole('button',{name:/^(Sign in|登入)$/,exact:true}));await expect(page.locator('html')).toHaveAttribute('lang',locale);
  await expect(page.getByRole('region',{name:ui('Manual outcomes')})).toContainText('T30 continuous fixture outcome after approved copy');
  await fits(page);
  await page.screenshot({path:`test-results/${transport}${inputMode==='keyboard'?'-keyboard':''}-continuity-${locale}-${layout}-outcome-fixture.png`,fullPage:true});
  if(inputMode==='keyboard'){
    await test.info().attach('operator-keyboard-input',{body:JSON.stringify(await input.verify(page),null,2),contentType:'application/json'});
    await test.info().attach('reviewer-keyboard-input',{body:JSON.stringify(await input.verify(reviewer),null,2),contentType:'application/json'});
  }
  await reviewerContext.close();
  await page.setViewportSize({width:390,height:844});
  await expect(page.locator('html')).toHaveAttribute('lang',locale);
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:`test-results/${transport}${inputMode==='keyboard'?'-keyboard':''}-continuity-${locale}-${layout}-mobile-readback-fixture.png`,fullPage:true});
});
}
}

}
