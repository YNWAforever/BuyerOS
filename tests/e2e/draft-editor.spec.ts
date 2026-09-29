import {expect,test,type Page} from '@playwright/test';
import {webcrypto} from 'node:crypto';

const workspace='e0000000-0000-4000-8000-000000000001';
const project='e1000000-0000-4000-8000-000000000001';

async function fakeSignIn(page:Page){
  const keys=await webcrypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,
    publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
  const publicKey={...(await webcrypto.subtle.exportKey('jwk',keys.publicKey)),kid:'draft-fixture',use:'sig'};
  const encode=(value:unknown)=>Buffer.from(JSON.stringify(value)).toString('base64url');
  let nonce='';
  await page.route('https://oidc.buyeros.test/authorize**',async route=>{
    const query=new URL(route.request().url()).searchParams;nonce=query.get('nonce')||'';
    await route.fulfill({status:302,headers:{location:`http://localhost:5173/auth/callback?code=draft-fixture&state=${query.get('state')}`},body:''});
  });
  await page.route('https://oidc.buyeros.test/oauth/token',async route=>{
    const unsigned=`${encode({alg:'RS256',kid:'draft-fixture'})}.${encode({iss:'https://oidc.buyeros.test/',
      aud:'fixture-public-client',sub:'fixture-access',nonce,exp:Math.floor(Date.now()/1000)+300})}`;
    const signature=await webcrypto.subtle.sign('RSASSA-PKCS1-v1_5',keys.privateKey,new TextEncoder().encode(unsigned));
    await route.fulfill({status:200,contentType:'application/json',
      headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},
      body:JSON.stringify({access_token:'fixture-access',
        id_token:`${unsigned}.${Buffer.from(signature).toString('base64url')}`,expires_in:300})});
  });
  await page.route('https://oidc.buyeros.test/.well-known/jwks.json',async route=>route.fulfill({status:200,
    contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},
    body:JSON.stringify({keys:[publicKey]})}));
}

const buyer='e2000000-0000-4000-8000-000000000001';
const seededDraft='ec000000-0000-4000-8000-000000000001';

test('T24 staff prepares an unaddressed draft and recovers immutable edits',async({page,request})=>{
  test.setTimeout(180_000);
  await fakeSignIn(page);
  await page.goto(`/app/outreach?workspace=${workspace}&project=${project}&buyer=${buyer}`);
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue(project);
  await expect(page.getByText(/Fixture Alex/)).toBeVisible();
  await expect(page.getByText('Fictional industrial sensors',{exact:true})).toBeVisible();
  await expect(page.getByText(/Fixture public catalog lists industrial sensors/)).toBeVisible();
  await page.getByRole('button',{name:'Generate unaddressed draft'}).click();
  await expect(page.getByText(/queued/)).toBeVisible();
  const jobId=new URL(page.url()).searchParams.get('draft_job');
  expect(jobId).toMatch(/^[0-9a-f-]{36}$/);
  await page.getByRole('button',{name:'Refresh job'}).click();
  await expect(page.getByText(/queued/)).toBeVisible();
  await page.screenshot({path:'test-results/t24-draft-en-fixture.png',fullPage:true});

  await page.getByRole('button',{name:'Open draft'}).first().click();
  await expect(page).toHaveURL(new RegExp(`draft=${seededDraft}`));
  await expect(page.getByRole('textbox',{name:'Body'})).toContainText('fictional industrial sensors');
  await page.getByRole('textbox',{name:'Body'}).fill('Human edited draft, pending grounding review.');
  await page.getByRole('button',{name:'Save revision'}).click();
  await expect(page.getByRole('status').filter({hasText:/Human edits require a new grounding review/})).toBeVisible();
  await expect(page.getByText(/Revision: 2/)).toBeVisible();
  await page.reload();
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByRole('textbox',{name:'Body'})).toContainText('Human edited draft, pending grounding review.');
  const denied=await request.patch(`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${seededDraft}`,{
    headers:{Authorization:'Bearer fixture-viewer','Idempotency-Key':'viewer-draft-edit',
      'If-Match':'"2"'},data:{body:'Viewer edit'},
  });
  expect(denied.status()).toBe(403);
  await page.getByRole('button',{name:'Prepare follow-up'}).click();
  await expect(page.getByText(`Follow-up: ${seededDraft}`)).toBeVisible();
  await page.getByRole('button',{name:'Generate unaddressed draft'}).click();
  await expect(page.getByRole('status').filter({hasText:/queued/})).toBeVisible();
  await page.getByRole('combobox',{name:'Language'}).first().selectOption('zh-HK');
  await page.setViewportSize({width:390,height:844});
  await expect(page.getByRole('heading',{name:'草稿',exact:true})).toBeVisible();
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:'test-results/t24-draft-zh-mobile-fixture.png',fullPage:true});
});
