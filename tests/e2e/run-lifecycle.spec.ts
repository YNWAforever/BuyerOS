import {expect,test,type Page} from '@playwright/test';
import {webcrypto} from 'node:crypto';

const workspace='e0000000-0000-4000-8000-000000000001';
const project='e9100000-0000-4000-8000-000000000001';
const seededRun='e9400000-0000-4000-8000-000000000001';
const scope=`workspace=${workspace}&project=${project}`;

async function installFakeLogin(page:Page,access='fixture-access'){
  const keys=await webcrypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,
    publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
  const publicKey={...(await webcrypto.subtle.exportKey('jwk',keys.publicKey)),kid:'run-fixture',use:'sig'};
  const encode=(value:unknown)=>Buffer.from(JSON.stringify(value)).toString('base64url');
  let nonce='';
  await page.route('https://oidc.buyeros.test/authorize**',async route=>{
    const query=new URL(route.request().url()).searchParams;nonce=query.get('nonce')||'';
    await route.fulfill({status:302,headers:{location:`http://localhost:5173/auth/callback?code=run-fixture&state=${query.get('state')}`},body:''});
  });
  await page.route('https://oidc.buyeros.test/oauth/token',async route=>{
    const unsigned=`${encode({alg:'RS256',kid:'run-fixture'})}.${encode({iss:'https://oidc.buyeros.test/',
      aud:'fixture-public-client',sub:access,nonce,exp:Math.floor(Date.now()/1000)+300})}`;
    const signature=await webcrypto.subtle.sign('RSASSA-PKCS1-v1_5',keys.privateKey,new TextEncoder().encode(unsigned));
    await route.fulfill({status:200,contentType:'application/json',
      headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},
      body:JSON.stringify({access_token:access,id_token:`${unsigned}.${Buffer.from(signature).toString('base64url')}`,expires_in:300})});
  });
  await page.route('https://oidc.buyeros.test/.well-known/jwks.json',async route=>route.fulfill({status:200,
    contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},
    body:JSON.stringify({keys:[publicKey]})}));
}

async function login(page:Page,path=`/app/runs?${scope}`){
  await page.goto(path);
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue(project);
}

test('T20 live fixture run pagination, start, SSE replay, cancellation, reload, locale and mobile',async({page,request})=>{
  test.setTimeout(240_000);
  await installFakeLogin(page);
  await login(page);
  await expect(page.getByRole('heading',{name:'Research runs'})).toBeVisible();
  await expect(page.getByText('Actual runs: 12')).toBeVisible();
  await expect(page.locator('.run-list li')).toHaveCount(10);
  await page.getByRole('button',{name:'Next'}).click();
  await expect(page.locator('.run-list li')).toHaveCount(2);
  await page.getByRole('button',{name:'Previous'}).click();
  await page.getByLabel('Target companies').fill('3');
  await page.getByLabel('Maximum research cost (USD)').fill('2.000000');
  await page.getByRole('button',{name:'Start research'}).click();
  await expect(page).toHaveURL(/\/app\/discover\/[0-9a-f-]{36}/);
  await expect(page.getByText(/Status:\s*queued/)).toBeVisible();
  const createdUrl=new URL(page.url());
  await page.getByLabel('Reason for action').fill('Stop queued fixture run');
  await page.getByRole('button',{name:'Stop new work'}).click();
  await expect(page.getByText(/Status:\s*cancelled/)).toBeVisible();
  await page.reload();
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page).toHaveURL(createdUrl.toString());
  await expect(page.getByText(/Status:\s*cancelled/)).toBeVisible();
  await page.getByRole('combobox',{name:'Language'}).selectOption('zh-HK');
  await expect(page.getByRole('heading',{name:'研究進度'})).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:'test-results/t20-run-mobile-zhHK-fixture.png',fullPage:true});
  await page.getByRole('combobox',{name:'語言'}).selectOption('en');
  await expect(page.getByRole('heading',{name:'Research runs'})).toBeVisible();
  await login(page,`/app/discover/${seededRun}?${scope}`);
  await expect(page.getByText(/Connection:\s*sse/)).toBeVisible();
  const advanced=await request.post('http://127.0.0.1:8000/fixture/advance-run',{data:{step:'partial'}});
  expect(advanced.ok()).toBe(true);
  await expect(page.getByText(/Event:\s*3/)).toBeVisible({timeout:20_000});
  await expect(page.getByText(/Status:\s*partial/)).toBeVisible();
  await page.screenshot({path:'test-results/t20-run-sse-progress-fixture.png',fullPage:true});
});

test('T20 SSE failure falls back to authenticated polling; viewer cannot mutate',async({page,request})=>{
  test.setTimeout(180_000);
  await installFakeLogin(page,'fixture-viewer');
  await page.route('http://127.0.0.1:8000/v1/workspaces/*/runs/*/events?**',async route=>{
    if(route.request().headers()['accept']?.includes('text/event-stream'))
      await route.fulfill({status:503,contentType:'application/json',
        headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},body:'{"code":"UNAVAILABLE"}'});
    else await route.continue();
  });
  await login(page,`/app/discover/${seededRun}?${scope}`);
  await expect(page.getByText(/Status:\s*partial/)).toBeVisible();
  await expect(page.getByRole('button',{name:'Stop new work'})).toHaveCount(0);
  await expect(page.getByText(/Connection:\s*poll/)).toBeVisible();
  const advanced=await request.post('http://127.0.0.1:8000/fixture/advance-run',{data:{step:'completed'}});
  expect(advanced.ok()).toBe(true);
  await expect(page.getByText(/Status:\s*completed/)).toBeVisible({timeout:20_000});
  await expect(page.getByText(/Event:\s*4/)).toBeVisible();
  await page.screenshot({path:'test-results/t20-run-polling-viewer-fixture.png',fullPage:true});
});
