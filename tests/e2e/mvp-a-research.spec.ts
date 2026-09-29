import {expect,test,type Page} from '@playwright/test';
import {webcrypto} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {resolve} from 'node:path';

const execFileAsync=promisify(execFile);
const workspace='e0000000-0000-4000-8000-000000000001';
const project='e9100000-0000-4000-8000-000000000001';

async function signIn(page:Page,accessToken='fixture-access',initialPath=`/app/runs?workspace=${workspace}&project=${project}`){
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
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue(project,{timeout:30_000});
}

test('T30 approved offer drives bounded research and grounded draft through disposable broker and worker',async({page,browser})=>{
  test.setTimeout(360_000);
  page.setDefaultTimeout(10_000);
  await signIn(page);
  await page.getByRole('button',{name:'Overview'}).click();
  await page.getByRole('button',{name:'Edit offer'}).click();
  await expect(page.getByLabel('Product / service')).toHaveValue('Industrial sensors');
  await page.getByLabel('Product / service').fill('Industrial sensor platform');
  await page.getByLabel('Value proposition').fill('Fictional monitoring lowers production downtime.');
  await page.getByRole('button',{name:'Continue'}).click();
  await page.getByRole('button',{name:'Continue'}).click();
  await page.getByRole('checkbox',{name:/I confirm these buyer requirements/}).check();
  await page.getByRole('button',{name:'Continue'}).click();
  await page.getByRole('button',{name:'Save profile'}).click();
  await expect(page.getByRole('heading',{name:'Profile version 2'})).toBeVisible();
  const reviewerContext=await browser.newContext();
  const reviewer=await reviewerContext.newPage();
  await signIn(reviewer,'fixture-reviewer',`/app?workspace=${workspace}&project=${project}`);
  await expect(reviewer.getByRole('heading',{name:'Profile version 2'})).toBeVisible();
  await reviewer.getByRole('checkbox',{name:/Confirm approval of this exact version v2/}).check();
  await reviewer.getByRole('button',{name:'Approve profile'}).click();
  await expect(reviewer.getByText('Current approved: v2')).toBeVisible();
  await page.reload();
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByText('Current approved: v2')).toBeVisible();
  await page.getByRole('button',{name:'Research runs'}).click();
  await page.getByLabel('Target companies').fill('1');
  await page.getByLabel('Maximum research cost (USD)').fill('2.000000');
  await page.getByRole('button',{name:'Start research'}).click();
  await expect(page).toHaveURL(/\/app\/discover\/[0-9a-f-]{36}/);
  const runId=new URL(page.url()).pathname.split('/').at(-1)!;
  await expect(page.getByText(/Status:\s*queued/)).toBeVisible();
  const workerRoot=resolve('services/worker');
  const python=resolve(workerRoot,'.venv/Scripts/python.exe');
  const {stdout}=await execFileAsync(python,['tests/fixtures/run_browser_research.py',runId,project],
    {cwd:workerRoot,timeout:180_000,maxBuffer:1024*1024});
  const report=JSON.parse(stdout.trim().split(/\r?\n/).at(-1)!) as {run_id:string;status:string;evidence:number;buyers:number;fit_verdicts:string[];published:string[]};
  expect(report.run_id).toBe(runId);
  expect(report.evidence).toBeGreaterThanOrEqual(1);
  expect(report.buyers).toBeGreaterThanOrEqual(1);
  expect(report.published.length).toBeGreaterThanOrEqual(1);
  await page.getByRole('button',{name:'Buyers',exact:true}).click();
  await expect(page.getByText('T30 Fictional Industrial Buyer',{exact:true})).toBeVisible({timeout:30_000});
  await page.getByRole('button',{name:'Details'}).first().click();
  const dossier=page.getByRole('dialog',{name:'Buyer details: T30 Fictional Industrial Buyer'});
  await dossier.getByRole('tab',{name:'Evidence'}).click();
  await expect(dossier).toContainText('Fictional distributor lists industrial sensors');
  await reviewer.getByRole('button',{name:'Buyers',exact:true}).click();
  await expect(reviewer.getByText('T30 Fictional Industrial Buyer',{exact:true})).toBeVisible();
  await reviewer.getByRole('button',{name:'Details'}).first().click();
  const reviewDossier=reviewer.getByRole('dialog',{name:'Buyer details: T30 Fictional Industrial Buyer'});
  await expect(reviewDossier).toContainText('Fit: match');
  await reviewDossier.getByRole('textbox',{name:'Individual review reason'}).fill('Verified cited industrial buyer');
  await reviewDossier.getByRole('button',{name:/^Save review/}).click();
  await reviewer.getByRole('checkbox',{name:'Select T30 Fictional Industrial Buyer'}).check();
  await reviewer.getByRole('textbox',{name:'List name'}).fill('T30 generated buyer');
  await reviewer.getByRole('button',{name:'Create list'}).click();
  await reviewer.getByRole('button',{name:'Add selected to list'}).click();
  await expect(reviewer.getByRole('combobox',{name:'Buyer list'})).toContainText('T30 generated buyer (1)');
  await reviewer.getByRole('button',{name:'Show list buyers'}).click();
  await expect(reviewer.getByText('1 in snapshot')).toBeVisible();
  await reviewer.getByRole('button',{name:'Details'}).first().click();
  const assigned=reviewer.getByRole('dialog',{name:'Buyer details: T30 Fictional Industrial Buyer'});
  await expect(assigned).toContainText('Human review: accepted');
  await assigned.getByRole('button',{name:'Assign to me'}).click();
  await expect(assigned).toContainText('Owner membership: e0000000-0000-4000-8000-000000000005');
  await reviewerContext.close();
  await page.reload();
  await page.getByRole('button',{name:'Sign in'}).click();
  await page.getByRole('button',{name:'Buyers',exact:true}).click();
  await page.getByRole('button',{name:'Details'}).first().click();
  const operatorDossier=page.getByRole('dialog',{name:'Buyer details: T30 Fictional Industrial Buyer'});
  await expect(operatorDossier).toContainText('Human review: accepted');
  await operatorDossier.getByRole('button',{name:'Prepare grounded draft'}).click();
  await expect(page).toHaveURL(/\/app\/outreach\?/);
  await expect(page.getByText(/Reviewed sender:/)).toBeVisible();
  await expect(page.getByText('Industrial sensor platform',{exact:true})).toBeVisible();
  await expect(page.getByText(/Fictional distributor lists industrial sensors/)).toBeVisible();
  await page.getByRole('button',{name:'Generate unaddressed draft'}).click();
  await expect.poll(()=>new URL(page.url()).searchParams.get('draft_job'),{timeout:30_000}).toMatch(/^[0-9a-f-]{36}$/);
  const draftJobId=new URL(page.url()).searchParams.get('draft_job')!;
  const draftRun=await execFileAsync(python,['tests/fixtures/run_browser_research.py',runId,project,draftJobId!],
    {cwd:workerRoot,timeout:180_000,maxBuffer:1024*1024});
  const draftReport=JSON.parse(draftRun.stdout.trim().split(/\r?\n/).at(-1)!) as {job_id:string;status:string;draft_id:string;grounding_status:string};
  expect(draftReport.job_id).toBe(draftJobId);
  expect(draftReport.status).toBe('completed');
  expect(draftReport.grounding_status).toBe('grounded');
  await page.getByRole('button',{name:'Refresh job'}).click();
  await expect(page.getByRole('region',{name:'Draft list'}).getByRole('button',{name:'Open draft'})).toHaveCount(1);
  await page.getByRole('region',{name:'Draft list'}).getByRole('button',{name:'Open draft'}).click();
  await expect(page.getByRole('textbox',{name:'Body'})).toContainText('Industrial sensor platform');
  await expect(page.getByRole('textbox',{name:'Body'})).toContainText('Fictional distributor lists industrial sensors');
  await page.screenshot({path:'test-results/t30-ui-worker-research-en-fixture.png',fullPage:true});
  await page.locator('header select').selectOption('zh-HK');
  await page.setViewportSize({width:390,height:844});
  await expect(page.locator('html')).toHaveAttribute('lang','zh-HK');
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:'test-results/t30-ui-worker-research-zh-mobile-fixture.png',fullPage:true});
});