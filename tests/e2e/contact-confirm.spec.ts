import {expect,test,type Page} from '@playwright/test';
import {webcrypto} from 'node:crypto';

const workspace='e0000000-0000-4000-8000-000000000001';
const project='e1000000-0000-4000-8000-000000000001';

async function signIn(page:Page,subject='fixture-access'){
  const keys=await webcrypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,
    publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
  const publicKey={...(await webcrypto.subtle.exportKey('jwk',keys.publicKey)),kid:'confirm-fixture',use:'sig'};
  const encode=(value:unknown)=>Buffer.from(JSON.stringify(value)).toString('base64url');
  let nonce='';
  await page.route('https://oidc.buyeros.test/authorize**',async route=>{
    const query=new URL(route.request().url()).searchParams;nonce=query.get('nonce')||'';
    await route.fulfill({status:302,headers:{location:`http://localhost:5173/auth/callback?code=confirm-fixture&state=${query.get('state')}`},body:''});
  });
  await page.route('https://oidc.buyeros.test/oauth/token',async route=>{
    const unsigned=`${encode({alg:'RS256',kid:'confirm-fixture'})}.${encode({iss:'https://oidc.buyeros.test/',
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

test('T22 quote confirmation queues one bounded job and shows a hold without a found contact',async({page,request})=>{
  test.setTimeout(180_000);
  await signIn(page);
  await page.getByRole('button',{name:'Details'}).first().click();
  await page.getByRole('tab',{name:'Contacts'}).click();
  const preview=page.locator('.contact-quote');
  await preview.getByRole('button',{name:'View contact quote'}).click();
  await expect(preview.getByText(/Maximum cost: USD 0.300000/)).toBeVisible();
  const before=await request.get('http://127.0.0.1:8000/fixture/quote-counts');
  expect(await before.json()).toEqual({enrichment_quotes:1,budget_reservations:0,
    provider_operations:0,outbox_events:0,enrichment_jobs:0});
  await preview.getByRole('button',{name:'Confirm lookup'}).click();
  await expect(preview.getByText(/Lookup accepted and queued/)).toBeVisible();
  await expect(preview.getByText(/Held cost: USD 0.300000/)).toBeVisible();
  await expect(preview.getByText(/Quote status: consumed/)).toBeVisible();
  const after=await request.get('http://127.0.0.1:8000/fixture/quote-counts');
  expect(await after.json()).toEqual({enrichment_quotes:1,budget_reservations:1,
    provider_operations:1,outbox_events:1,enrichment_jobs:1});
  await page.screenshot({path:'test-results/t22-confirm-en-fixture.png',fullPage:true});
  await page.getByRole('combobox',{name:'Language'}).selectOption('zh-HK');
  await page.setViewportSize({width:390,height:844});
  await expect(preview.getByText(/已接受查找並列隊/)).toBeVisible();
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:'test-results/t22-confirm-zh-mobile-fixture.png',fullPage:true});
});

test('T22 viewer cannot confirm a quote directly',async({page,request})=>{
  await signIn(page,'fixture-viewer');
  const denied=await request.post(`http://127.0.0.1:8000/v1/workspaces/${workspace}/enrichment-quotes/e2000000-0000-4000-8000-000000000001/confirm`,{
    headers:{Authorization:'Bearer fixture-viewer','Idempotency-Key':'confirm-viewer-denied'},
    data:{quote_hash:'a'.repeat(64),confirm_eligible_only:true},
  });
  expect(denied.status()).toBe(403);
});
