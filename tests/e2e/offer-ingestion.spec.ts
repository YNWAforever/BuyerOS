import {expect,test,type Page} from '@playwright/test';
import {webcrypto} from 'node:crypto';

async function signIn(page:Page,accessToken='fixture-access',initialPath='/app'){
  const keys=await webcrypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,
    publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
  const publicKey={...(await webcrypto.subtle.exportKey('jwk',keys.publicKey)),kid:'ingest-fixture',use:'sig'};
  let nonce='';const encode=(value:unknown)=>Buffer.from(JSON.stringify(value)).toString('base64url');
  await page.route('https://oidc.buyeros.test/authorize**',async route=>{
    const query=new URL(route.request().url()).searchParams;
    nonce=query.get('nonce')||'';
    await route.fulfill({status:302,headers:{location:`http://localhost:5173/auth/callback?code=fixture&state=${query.get('state')}`},body:''});
  });
  await page.route('https://oidc.buyeros.test/oauth/token',async route=>{
    const unsigned=`${encode({alg:'RS256',kid:'ingest-fixture'})}.${encode({
      iss:'https://oidc.buyeros.test/',aud:'fixture-public-client',sub:accessToken,
      nonce,exp:Math.floor(Date.now()/1000)+300})}`;
    const signature=await webcrypto.subtle.sign('RSASSA-PKCS1-v1_5',keys.privateKey,new TextEncoder().encode(unsigned));
    await route.fulfill({status:200,contentType:'application/json',
      headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},
      body:JSON.stringify({access_token:accessToken,
        id_token:`${unsigned}.${Buffer.from(signature).toString('base64url')}`,expires_in:300})});
  });
  await page.route('https://oidc.buyeros.test/.well-known/jwks.json',async route=>
    route.fulfill({status:200,contentType:'application/json',
      headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},
      body:JSON.stringify({keys:[publicKey]})}));
  await page.goto(initialPath);
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByRole('combobox',{name:'Workspace'})).toHaveValue('e0000000-0000-4000-8000-000000000001',{timeout:30_000});
}

test('T16 live offer upload status survives reload and is role scoped',async({page,browser})=>{
  test.setTimeout(240_000);
  await signIn(page);
  await page.getByRole('button',{name:'New project'}).click();
  await page.getByLabel('Company name').fill('Fixture Offer Documents');
  await page.getByLabel('Product / service').fill('Industrial sensors');
  await page.getByLabel('Value proposition').fill('Improves production monitoring reliability.');
  await page.getByRole('button',{name:'Continue'}).click();
  await page.getByLabel('Markets (country codes or names)').fill('DE');
  await page.getByLabel('Languages (codes or names)').fill('en');
  await page.getByRole('checkbox',{name:'Distributor'}).check();
  await page.getByRole('button',{name:'Continue'}).click();
  await page.getByLabel('Must have').fill('Distributes industrial sensors');
  await page.getByRole('checkbox',{name:/I confirm these buyer requirements/}).check();
  await page.getByRole('button',{name:'Continue'}).click();
  await page.getByRole('button',{name:'Save profile'}).click();
  await expect(page.getByRole('heading',{name:'Profile version 1'})).toBeVisible();
  const selectedUrl=new URL(page.url());
  await page.getByRole('button',{name:'Edit offer'}).click();
  await expect(page.getByRole('heading',{name:'Offer documents'})).toBeVisible();
  await page.getByLabel('Offer file').setInputFiles({
    name:'fixture-offer.txt',mimeType:'text/plain',
    buffer:Buffer.from('Product: Industrial sensors\nValue proposition: Reliable monitoring\n'),
  });
  await page.getByRole('button',{name:'Upload document'}).click();
  await expect(page.getByText('fixture-offer.txt')).toBeVisible();
  await expect(page.getByText('quarantined')).toBeVisible();
  const uploadBox=await page.getByRole('button',{name:'Upload document'}).boundingBox();
  const refreshBox=await page.getByRole('button',{name:'Refresh document status'}).boundingBox();
  expect(uploadBox&&refreshBox&&refreshBox.x-uploadBox.x-uploadBox.width).toBeGreaterThanOrEqual(8);
  await page.screenshot({path:'test-results/t16-offer-upload-en-fixture.png',fullPage:true});

  await page.reload();
  await page.getByRole('button',{name:'Sign in'}).click();
  await page.getByRole('button',{name:'Edit offer'}).click();
  await expect(page.getByText('fixture-offer.txt')).toBeVisible();
  await page.getByRole('combobox',{name:'Language'}).selectOption('zh-HK');
  await expect(page.getByRole('heading',{name:'產品文件'})).toBeVisible();
  await page.screenshot({path:'test-results/t16-offer-upload-zh-fixture.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:'test-results/t16-offer-upload-zh-mobile-fixture.png',fullPage:true});

  const viewerContext=await browser.newContext();
  const viewer=await viewerContext.newPage();
  await signIn(viewer,'fixture-viewer',
    `/app?workspace=${selectedUrl.searchParams.get('workspace')}&project=${selectedUrl.searchParams.get('project')}`);
  await expect(viewer.getByRole('button',{name:'Edit offer'})).toHaveCount(0);
  await viewerContext.close();
});
