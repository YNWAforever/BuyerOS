import {expect,test,type Page} from '@playwright/test';
import {webcrypto} from 'node:crypto';

const workspace='e0000000-0000-4000-8000-000000000001';
const project='e1000000-0000-4000-8000-000000000001';
const buyer='e2000000-0000-4000-8000-000000000001';

async function signIn(page:Page,subject='fixture-access'){
  const keys=await webcrypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,
    publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
  const publicKey={...(await webcrypto.subtle.exportKey('jwk',keys.publicKey)),kid:'quote-fixture',use:'sig'};
  const encode=(value:unknown)=>Buffer.from(JSON.stringify(value)).toString('base64url');
  let nonce='';
  await page.route('https://oidc.buyeros.test/authorize**',async route=>{
    const query=new URL(route.request().url()).searchParams;nonce=query.get('nonce')||'';
    await route.fulfill({status:302,headers:{location:`http://localhost:5173/auth/callback?code=quote-fixture&state=${query.get('state')}`},body:''});
  });
  await page.route('https://oidc.buyeros.test/oauth/token',async route=>{
    const unsigned=`${encode({alg:'RS256',kid:'quote-fixture'})}.${encode({iss:'https://oidc.buyeros.test/',
      aud:'fixture-public-client',sub:subject,nonce,exp:Math.floor(Date.now()/1000)+300})}`;
    const signature=await webcrypto.subtle.sign('RSASSA-PKCS1-v1_5',keys.privateKey,new TextEncoder().encode(unsigned));
    await route.fulfill({status:200,contentType:'application/json',
      headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},
      body:JSON.stringify({access_token:subject,id_token:`${unsigned}.${Buffer.from(signature).toString('base64url')}`,expires_in:300})});
  });
  await page.route('https://oidc.buyeros.test/.well-known/jwks.json',async route=>route.fulfill({status:200,
    contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},
    body:JSON.stringify({keys:[publicKey]})}));
  await page.goto(`/app/discover?workspace=${workspace}&project=${project}`);
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue(project);
}

test('T21 optional quote previews an eligible and blocked buyer without a hold or provider intent',async({page,request})=>{
  test.setTimeout(180_000);
  await signIn(page);
  await page.getByRole('button',{name:'Details'}).first().click();
  await expect(page.getByRole('dialog',{name:'Buyer details: Buyer Fixture 01'})).toBeVisible();
  await page.getByRole('tab',{name:'Contacts'}).click();
  await page.getByRole('button',{name:'View contact quote'}).click();
  const preview=page.locator('.contact-quote');
  await expect(preview.getByText(/Quote status: quoted/)).toBeVisible();
  await expect(preview.getByText(/Maximum cost: USD 0.300000/)).toBeVisible();
  await expect(preview.getByText(/Eligible buyers: 1/)).toBeVisible();
  await expect(preview.getByRole('button',{name:'Confirm lookup'})).toBeEnabled();
  expect(page.url()).not.toContain('fixture-access');
  const counts=await request.get('http://127.0.0.1:8000/fixture/quote-counts');
  expect(counts.ok()).toBe(true);
  expect(await counts.json()).toEqual({enrichment_quotes:1,budget_reservations:0,provider_operations:0,outbox_events:0});
  await page.screenshot({path:'test-results/t21-contact-quote-en-fixture.png',fullPage:true});
  await page.getByRole('combobox',{name:'Language'}).selectOption('zh-HK');
  await page.setViewportSize({width:390,height:844});
  await expect(preview.getByRole('heading',{name:'可選聯絡資料報價'})).toBeVisible();
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:'test-results/t21-contact-quote-zh-mobile-fixture.png',fullPage:true});
  await page.getByRole('button',{name:'取消未使用報價'}).click();
  await expect(preview.getByText(/報價狀態: 已取消/)).toBeVisible();
  await page.getByRole('combobox',{name:'語言'}).selectOption('en');
  await page.getByRole('button',{name:'Next buyer'}).click();
  await expect(page.getByRole('dialog',{name:'Buyer details: Buyer Fixture 02'})).toBeVisible();
  await page.getByRole('tab',{name:'Contacts'}).click();
  await page.getByRole('button',{name:'View contact quote'}).click();
  await expect(page.getByText(/Maximum cost: USD 0.000000/)).toBeVisible();
  await expect(page.getByText(/fit_not_current_match/)).toBeVisible();
});

test('T21 viewer sees no quote action and API denies direct quote creation',async({page,request})=>{
  test.setTimeout(120_000);
  await signIn(page,'fixture-viewer');
  await page.getByRole('button',{name:'Details'}).first().click();
  await page.getByRole('tab',{name:'Contacts'}).click();
  await expect(page.getByRole('button',{name:'View contact quote'})).toHaveCount(0);
  const denied=await request.post(`http://127.0.0.1:8000/v1/workspaces/${workspace}/projects/${project}/enrichment-quotes`,{
    headers:{Authorization:'Bearer fixture-viewer','Idempotency-Key':'quote-viewer-denied'},
    data:{selection:{kind:'explicit',buyers:[{id:buyer,version:1}]},purpose:'contact_research',
      roles:['Procurement manager'],contact_type:'business_email'},
  });
  expect(denied.status()).toBe(403);
});
