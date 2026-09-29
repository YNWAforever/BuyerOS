import {expect,test,type Page} from '@playwright/test';
import {webcrypto} from 'node:crypto';

const workspace='e0000000-0000-4000-8000-000000000001';
const project='e1000000-0000-4000-8000-000000000001';
const draft='ec000000-0000-4000-8000-000000000002';

async function fakeReviewerSignIn(page:Page){
  const keys=await webcrypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,
    publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
  const publicKey={...(await webcrypto.subtle.exportKey('jwk',keys.publicKey)),kid:'approval-fixture',use:'sig'};
  const encode=(value:unknown)=>Buffer.from(JSON.stringify(value)).toString('base64url');
  let nonce='';
  await page.route('https://oidc.buyeros.test/authorize**',async route=>{
    const query=new URL(route.request().url()).searchParams;nonce=query.get('nonce')||'';
    await route.fulfill({status:302,headers:{location:`http://localhost:5173/auth/callback?code=approval-fixture&state=${query.get('state')}`},body:''});
  });
  await page.route('https://oidc.buyeros.test/oauth/token',async route=>{
    const unsigned=`${encode({alg:'RS256',kid:'approval-fixture'})}.${encode({iss:'https://oidc.buyeros.test/',
      aud:'fixture-public-client',sub:'reviewer',nonce,exp:Math.floor(Date.now()/1000)+300})}`;
    const signature=await webcrypto.subtle.sign('RSASSA-PKCS1-v1_5',keys.privateKey,new TextEncoder().encode(unsigned));
    await route.fulfill({status:200,contentType:'application/json',
      headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},
      body:JSON.stringify({access_token:'fixture-reviewer',
        id_token:`${unsigned}.${Buffer.from(signature).toString('base64url')}`,expires_in:300})});
  });
  await page.route('https://oidc.buyeros.test/.well-known/jwks.json',async route=>route.fulfill({status:200,
    contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},
    body:JSON.stringify({keys:[publicKey]})}));
}

test('T25 reviewer confirms exact draft while delivery stays disabled',async({page,request})=>{
  test.setTimeout(180_000);
  await fakeReviewerSignIn(page);
  await page.goto(`/app/outreach?workspace=${workspace}&project=${project}&draft=${draft}`);
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue(project);
  await expect(page.getByRole('heading',{name:'Exact revision review'})).toBeVisible();
  await expect(page.getByRole('button',{name:'Request exact review'})).toBeVisible();
  await page.getByRole('button',{name:'Request exact review'}).click();
  await expect(page.getByText('recipient@fixture.example.test')).toBeVisible();
  await expect(page.getByRole('region',{name:'Exact revision review'}).getByText(/Fixture Alex/)).toBeVisible();
  const approve=page.getByRole('button',{name:'Approve exact revision'});
  await expect(approve).toBeDisabled();
  await page.getByRole('checkbox',{name:/I confirm the exact recipient/}).check();
  await expect(approve).toBeEnabled();
  await approve.click();
  await expect(page.getByText(/Approval recorded; delivery remains disabled/)).toBeVisible();
  await expect(page.getByText(/approved/).first()).toBeVisible();
  await expect(page.getByRole('button',{name:/^Send(?:\s|$)/i})).toHaveCount(0);
  const counts=await (await request.get('http://127.0.0.1:8000/fixture/approval-counts')).json();
  expect(counts).toEqual({approvals:1,delivery_events:0});
  const denied=await request.post(`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${draft}/deliver`,{
    headers:{Authorization:'Bearer fixture-reviewer','Idempotency-Key':'disabled-delivery-fixture'}});
  expect(denied.status()).toBe(403);
  expect((await denied.json()).code).toBe('DELIVERY_DISABLED');
  const viewer=await request.post(`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${draft}/review`,{
    headers:{Authorization:'Bearer fixture-viewer','Idempotency-Key':'viewer-review-fixture','If-Match':'"3"'},
    data:{revision_id:'ee000000-0000-4000-8000-000000000002',content_hash:'0'.repeat(64),context_hash:'0'.repeat(64)}});
  expect(viewer.status()).toBe(403);
  await page.screenshot({path:'test-results/t25-approval-en-fixture.png',fullPage:true});
  await page.reload();
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByRole('heading',{name:'Exact revision review'})).toBeVisible();
  await expect(page.getByText(/approved/).first()).toBeVisible();
  await page.locator('header select').selectOption('zh-HK');
  await page.setViewportSize({width:390,height:844});
  await expect(page.getByRole('heading',{name:'精確版本審核'})).toBeVisible();
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:'test-results/t25-approval-zh-mobile-fixture.png',fullPage:true});
  const after=await (await request.get('http://127.0.0.1:8000/fixture/approval-counts')).json();
  expect(after).toEqual({approvals:1,delivery_events:0});
});
