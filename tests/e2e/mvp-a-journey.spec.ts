import {expect,test,type Page} from '@playwright/test';
import {readFile} from 'node:fs/promises';
import {webcrypto} from 'node:crypto';

const workspace='e0000000-0000-4000-8000-000000000001';
const project='e1000000-0000-4000-8000-000000000001';
const draft='ec000000-0000-4000-8000-000000000002';
const buyer='e2000000-0000-4000-8000-000000000001';

async function signIn(page:Page){
  const keys=await webcrypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,
    publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
  const publicKey={...(await webcrypto.subtle.exportKey('jwk',keys.publicKey)),kid:'mvp-fixture',use:'sig'};
  const encode=(value:unknown)=>Buffer.from(JSON.stringify(value)).toString('base64url');let nonce='';
  await page.route('https://oidc.buyeros.test/authorize**',async route=>{const q=new URL(route.request().url()).searchParams;
    nonce=q.get('nonce')||'';await route.fulfill({status:302,headers:{location:`http://localhost:5173/auth/callback?code=mvp-fixture&state=${q.get('state')}`},body:''});});
  await page.route('https://oidc.buyeros.test/oauth/token',async route=>{
    const unsigned=`${encode({alg:'RS256',kid:'mvp-fixture'})}.${encode({iss:'https://oidc.buyeros.test/',
      aud:'fixture-public-client',sub:'fixture-reviewer',nonce,exp:Math.floor(Date.now()/1000)+900})}`;
    const signature=await webcrypto.subtle.sign('RSASSA-PKCS1-v1_5',keys.privateKey,new TextEncoder().encode(unsigned));
    await route.fulfill({status:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},
      body:JSON.stringify({access_token:'fixture-reviewer',id_token:`${unsigned}.${Buffer.from(signature).toString('base64url')}`,expires_in:900})});});
  await page.route('https://oidc.buyeros.test/.well-known/jwks.json',async route=>route.fulfill({status:200,
    contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},body:JSON.stringify({keys:[publicKey]})}));
  await page.goto(`/app/discover?workspace=${workspace}&project=${project}`);
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByRole('combobox',{name:'Workspace'})).toHaveValue(workspace,{timeout:30_000});
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue(project,{timeout:30_000});
}

test('T30 partial fixture walkthrough: review, list, assign, exact approval, export and manual outcome',async({page,request})=>{
  test.setTimeout(300_000);
  page.setDefaultTimeout(10_000);
  await signIn(page);
  await expect(page.getByText('24 in snapshot')).toBeVisible();
  await page.getByRole('checkbox',{name:'Select Buyer Fixture 01'}).check();
  await page.getByRole('textbox',{name:'List name'}).fill('T30 reviewed buyer');
  await page.getByRole('button',{name:'Create list'}).click();
  await page.getByRole('button',{name:'Add selected to list'}).click();
  await expect(page.getByRole('combobox',{name:'Buyer list'})).toContainText('T30 reviewed buyer (1)');
  await page.getByRole('button',{name:'Show list buyers'}).click();
  await expect(page.getByText('1 in snapshot')).toBeVisible();
  await expect(page.getByText('Buyer Fixture 01',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Details'}).first().click();
  const dossier=page.getByRole('dialog',{name:'Buyer details: Buyer Fixture 01'});
  await dossier.getByRole('tab',{name:'Evidence'}).click();
  await expect(dossier).toContainText('Fixture public catalog lists industrial sensors.');
  await dossier.getByRole('tab',{name:'Overview'}).click();
  await dossier.getByRole('button',{name:'Assign to me'}).click();
  await expect(dossier).toContainText('Owner membership: e0000000-0000-4000-8000-000000000005');
  await page.getByRole('button',{name:'Close details'}).click();

  await page.getByRole('button',{name:'Drafts',exact:true}).click();
  const list=page.getByRole('region',{name:'Draft list'});
  await expect(list.getByRole('button',{name:'Open draft'})).toHaveCount(2);
  let selected:string|null=null;
  for(let index=0;index<2;index++){
    const previous=new URL(page.url()).searchParams.get('draft');
    await list.getByRole('button',{name:'Open draft'}).nth(index).click();
    await expect.poll(()=>new URL(page.url()).searchParams.get('draft')).not.toBe(previous);
    selected=new URL(page.url()).searchParams.get('draft');
    if(selected===draft)break;
  }
  expect(selected,'the fixture must expose the addressed draft through its list').toBe(draft);
  await expect(page.getByRole('button',{name:'Request exact review'})).toBeVisible();
  await page.getByRole('button',{name:'Request exact review'}).click();
  await expect(page.getByText('recipient@fixture.example.test')).toBeVisible();
  await page.getByRole('checkbox',{name:/I confirm the exact recipient/}).check();
  await page.getByRole('button',{name:'Approve exact revision'}).click();
  await expect(page.getByText(/Approval recorded; delivery remains disabled/)).toBeVisible();
  const exportRegion=page.getByRole('region',{name:'Authorized export'});
  await exportRegion.getByRole('combobox',{name:'Draft copy format'}).selectOption('text');
  await exportRegion.getByRole('button',{name:'Prepare approved copy'}).click();
  await expect(exportRegion).toContainText('Allowed: 1');
  const exportId=new URL(page.url()).searchParams.get('export');expect(exportId).toBeTruthy();
  const downloadPromise=page.waitForEvent('download');
  await exportRegion.getByRole('button',{name:'Download text'}).click();
  const downloaded=await downloadPromise;
  expect(await readFile(await downloaded.path()!,'utf8')).toContain('recipient@fixture.example.test');
  const viewer=await request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/exports/${exportId}/content`,
    {headers:{Authorization:'Bearer fixture-viewer'}});
  expect(viewer.status()).toBe(403);
  const deliver=await request.post(`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${draft}/deliver`,
    {headers:{Authorization:'Bearer fixture-reviewer','Idempotency-Key':'t30-disabled-delivery-fixture'}});
  expect(deliver.status()).toBe(403);expect((await deliver.json()).code).toBe('DELIVERY_DISABLED');

  await page.getByRole('button',{name:'Results',exact:true}).click();
  await page.getByRole('button',{name:'Log outcome'}).first().click();
  await page.getByRole('textbox',{name:'Outcome notes'}).fill('T30 fixture outcome after authorized copy');
  await page.getByRole('button',{name:'Record manual outcome'}).click();
  const outcomes=page.getByRole('region',{name:'Manual outcomes'});
  await expect(outcomes).toContainText('1 outcome events');
  await expect(outcomes).toContainText('T30 fixture outcome after authorized copy');
  await page.reload();await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByRole('region',{name:'Manual outcomes'})).toContainText('T30 fixture outcome after authorized copy');
  await page.screenshot({path:'test-results/t30-partial-en-fixture.png',fullPage:true});
  await page.locator('header select').selectOption('zh-HK');await page.setViewportSize({width:390,height:844});
  await expect(page.getByRole('region',{name:'人手記錄成果'})).toContainText('T30 fixture outcome after authorized copy');
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:'test-results/t30-partial-zh-mobile-fixture.png',fullPage:true});
  const outcomeRead=await request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/projects/${project}/outcomes?buyer_id=${buyer}&offset=0&limit=100`,
    {headers:{Authorization:'Bearer fixture-reviewer'}});
  expect(outcomeRead.status()).toBe(200);
});