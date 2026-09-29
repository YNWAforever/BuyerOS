import {expect,test,type Page} from '@playwright/test';
import {readFile} from 'node:fs/promises';
import {webcrypto} from 'node:crypto';

const workspace='e0000000-0000-4000-8000-000000000001';
const project='e1000000-0000-4000-8000-000000000001';
const draft='ec000000-0000-4000-8000-000000000002';

async function fakeReviewerSignIn(page:Page){
  const keys=await webcrypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,
    publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
  const publicKey={...(await webcrypto.subtle.exportKey('jwk',keys.publicKey)),kid:'export-fixture',use:'sig'};
  const encode=(value:unknown)=>Buffer.from(JSON.stringify(value)).toString('base64url');
  let nonce='';
  await page.route('https://oidc.buyeros.test/authorize**',async route=>{
    const query=new URL(route.request().url()).searchParams;nonce=query.get('nonce')||'';
    await route.fulfill({status:302,headers:{location:`http://localhost:5173/auth/callback?code=export-fixture&state=${query.get('state')}`},body:''});
  });
  await page.route('https://oidc.buyeros.test/oauth/token',async route=>{
    const unsigned=`${encode({alg:'RS256',kid:'export-fixture'})}.${encode({iss:'https://oidc.buyeros.test/',
      aud:'fixture-public-client',sub:'reviewer',nonce,exp:Math.floor(Date.now()/1000)+900})}`;
    const signature=await webcrypto.subtle.sign('RSASSA-PKCS1-v1_5',keys.privateKey,new TextEncoder().encode(unsigned));
    await route.fulfill({status:200,contentType:'application/json',
      headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},
      body:JSON.stringify({access_token:'fixture-reviewer',
        id_token:`${unsigned}.${Buffer.from(signature).toString('base64url')}`,expires_in:900})});
  });
  await page.route('https://oidc.buyeros.test/.well-known/jwks.json',async route=>route.fulfill({status:200,
    contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},
    body:JSON.stringify({keys:[publicKey]})}));
}

test('T26 authorized copy and CSV download stay actor-bound and do not deliver',async({page,request})=>{
  test.setTimeout(240_000);
  await page.context().grantPermissions(['clipboard-read','clipboard-write'],{origin:'http://localhost:5173'});
  await fakeReviewerSignIn(page);
  await page.goto(`/app/outreach?workspace=${workspace}&project=${project}&draft=${draft}`);
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByRole('heading',{name:'Exact revision review'})).toBeVisible();
  await page.getByRole('button',{name:'Request exact review'}).click();
  await expect(page.getByText('recipient@fixture.example.test')).toBeVisible();
  await page.getByRole('checkbox',{name:/I confirm the exact recipient/}).check();
  await page.getByRole('button',{name:'Approve exact revision'}).click();
  const exportRegion=page.getByRole('region',{name:'Authorized export'});
  await expect(exportRegion).toBeVisible();
  await exportRegion.getByRole('combobox',{name:'Draft copy format'}).selectOption('clipboard');
  await exportRegion.getByRole('button',{name:'Prepare approved copy'}).click();
  await expect(exportRegion).toContainText('Allowed: 1');
  const exportId=new URL(page.url()).searchParams.get('export');
  expect(exportId).toBeTruthy();
  const viewer=await request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/exports/${exportId}/content`,{
    headers:{Authorization:'Bearer fixture-viewer'}});
  expect(viewer.status()).toBe(403);
  await exportRegion.getByRole('button',{name:'Copy to clipboard'}).click();
  await expect(exportRegion).toContainText('Content copied after current authorization.');
  const copied=await page.evaluate(()=>navigator.clipboard.readText());
  expect(copied).toContain('recipient@fixture.example.test');
  expect(copied).toContain('fictional industrial sensors');
  await exportRegion.getByRole('combobox',{name:'Draft copy format'}).selectOption('text');
  await exportRegion.getByRole('button',{name:'Prepare approved copy'}).click();
  const draftDownloadPromise=page.waitForEvent('download');
  await exportRegion.getByRole('button',{name:'Download text'}).click();
  const draftDownload=await draftDownloadPromise;
  expect(await readFile(await draftDownload.path()!,'utf8')).toContain('recipient@fixture.example.test');
  await page.screenshot({path:'test-results/t26-draft-export-en-fixture.png',fullPage:true});

  await page.getByRole('button',{name:'Buyers',exact:true}).click();
  await expect(page.getByRole('button',{name:'Select this page'})).toBeVisible();
  await page.getByRole('button',{name:'Select this page'}).click();
  const buyerExport=page.getByRole('region',{name:'Authorized export'});
  await expect(buyerExport).toContainText('12');
  await buyerExport.getByRole('button',{name:'Prepare export'}).click();
  await expect(buyerExport).toContainText('Allowed: 11');
  await expect(buyerExport).toContainText('Excluded: 1');
  const csvDownloadPromise=page.waitForEvent('download');
  await buyerExport.getByRole('button',{name:'Download CSV'}).click();
  const csvDownload=await csvDownloadPromise;
  const csv=await readFile(await csvDownload.path()!,'utf8');
  expect(csv).toContain('"data_mode"');
  expect(csv).toContain('"live"');
  expect(csv).not.toContain('contact_value');
  expect(csv).not.toContain('Buyer Fixture 02');
  const counts=await (await request.get('http://127.0.0.1:8000/fixture/export-counts')).json();
  expect(counts).toEqual({exports:3,outcomes:0,delivery_events:0});
  await page.locator('header select').selectOption('zh-HK');
  await page.setViewportSize({width:390,height:844});
  await expect(page.getByRole('region',{name:'授權匯出'})).toBeVisible();
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:'test-results/t26-buyer-export-zh-mobile-fixture.png',fullPage:true});
});
