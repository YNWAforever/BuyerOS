import {expect,test,type Page} from '@playwright/test';
import {webcrypto} from 'node:crypto';

async function fixtureIssuer(page:Page) {
  const keys=await webcrypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
  const publicKey={...(await webcrypto.subtle.exportKey('jwk',keys.publicKey)),kid:'cors-fixture',use:'sig'};
  let nonce='';
  const encode=(value:unknown)=>Buffer.from(JSON.stringify(value)).toString('base64url');
  await page.route('https://oidc.buyeros.test/authorize**',async route=>{
    const query=new URL(route.request().url()).searchParams;nonce=query.get('nonce')||'';
    await route.fulfill({status:302,headers:{location:`http://localhost:5173/auth/callback?code=cors-fixture&state=${query.get('state')}`},body:''});
  });
  await page.route('https://oidc.buyeros.test/oauth/token',async route=>{
    const unsigned=`${encode({alg:'RS256',kid:'cors-fixture'})}.${encode({iss:'https://oidc.buyeros.test/',aud:'fixture-public-client',sub:'cors-actor',nonce,exp:Math.floor(Date.now()/1000)+300})}`;
    const signature=await webcrypto.subtle.sign('RSASSA-PKCS1-v1_5',keys.privateKey,new TextEncoder().encode(unsigned));
    await route.fulfill({status:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},body:JSON.stringify({access_token:'fixture-access',id_token:`${unsigned}.${Buffer.from(signature).toString('base64url')}`,expires_in:300})});
  });
  await page.route('https://oidc.buyeros.test/.well-known/jwks.json',async route=>route.fulfill({status:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},body:JSON.stringify({keys:[publicKey]})}));
}
async function signIn(page:Page) {await fixtureIssuer(page);await page.goto('/app');await page.getByRole('button',{name:'Sign in'}).click();}

test('browser preflight and bearer read reach disposable API with readable request ID',async({page})=>{
  await signIn(page);
  await expect(page.getByRole('combobox',{name:'Workspace'})).toHaveValue('e0000000-0000-4000-8000-000000000001');
  await expect(page.getByText('No projects yet.')).toBeVisible();
  const result=await page.evaluate(async()=>{
    const response=await fetch('http://127.0.0.1:8000/v1/workspaces?offset=0&limit=20',{headers:{Authorization:'Bearer fixture-access','Idempotency-Key':'read-fixture-key'}});
    return {status:response.status,requestId:response.headers.get('X-Request-ID'),body:await response.json()};
  });
  expect(result.status).toBe(200);expect(result.requestId).toBeTruthy();
  expect(result.body).toMatchObject({data:{items:[{name:'E2E fixture workspace'}]}});
  await page.screenshot({path:'test-results/t06-cors-disposable-db.png',fullPage:true});
});

test('browser can read 422 envelope and correlation header across origins',async({page})=>{
  await signIn(page);
  const result=await page.evaluate(async()=>{
    const response=await fetch('http://127.0.0.1:8000/v1/workspaces?limit=0',{headers:{Authorization:'Bearer fixture-access'}});
    return {status:response.status,requestId:response.headers.get('X-Request-ID'),body:await response.json()};
  });
  expect(result.status).toBe(422);expect(result.requestId).toBeTruthy();
  expect(result.body).toMatchObject({code:'INVALID_REQUEST',request_id:result.requestId});
});

test('network failure stays an error and never reveals demo fixtures',async({page})=>{
  await fixtureIssuer(page);
  await page.route('http://127.0.0.1:8000/v1/workspaces?**',route=>route.abort('failed'));
  await page.goto('/app');await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByRole('alert')).toContainText('Service temporarily unavailable');
  await expect(page.getByText('HarbourSense Instruments')).toHaveCount(0);
});
