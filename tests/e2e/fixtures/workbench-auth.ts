// Fake OIDC identity for the isolated HTTP/PostgreSQL workbench fixture only.
import {expect,type Page} from '@playwright/test';
import {webcrypto} from 'node:crypto';
export const workspace='e0000000-0000-4000-8000-000000000001';
export const project='e1000000-0000-4000-8000-000000000001';

export async function signInWorkbench(page:Page,waitForProject=true){
  const keys=await webcrypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,
    publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
  const publicKey={...(await webcrypto.subtle.exportKey('jwk',keys.publicKey)),kid:'workbench-fixture',use:'sig'};
  const encode=(value:unknown)=>Buffer.from(JSON.stringify(value)).toString('base64url');let nonce='';
  await page.route('https://oidc.buyeros.test/authorize**',async route=>{const q=new URL(route.request().url()).searchParams;
    nonce=q.get('nonce')||'';await route.fulfill({status:302,headers:{location:`http://localhost:5173/auth/callback?code=workbench-fixture&state=${q.get('state')}`},body:''});});
  await page.route('https://oidc.buyeros.test/oauth/token',async route=>{
    const unsigned=`${encode({alg:'RS256',kid:'workbench-fixture'})}.${encode({iss:'https://oidc.buyeros.test/',
      aud:'fixture-public-client',sub:'fixture-reviewer',nonce,exp:Math.floor(Date.now()/1000)+900})}`;
    const signature=await webcrypto.subtle.sign('RSASSA-PKCS1-v1_5',keys.privateKey,new TextEncoder().encode(unsigned));
    await route.fulfill({status:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},
      body:JSON.stringify({access_token:'fixture-reviewer',id_token:`${unsigned}.${Buffer.from(signature).toString('base64url')}`,expires_in:900})});
  });
  await page.route('https://oidc.buyeros.test/.well-known/jwks.json',async route=>route.fulfill({status:200,
    contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},body:JSON.stringify({keys:[publicKey]})}));
  const apiEvents:string[]=[];
  page.on('request',request=>{if(new URL(request.url()).pathname.startsWith('/v1/'))apiEvents.push(`request ${request.method()} ${request.url()}`);});
  page.on('requestfailed',request=>{if(new URL(request.url()).pathname.startsWith('/v1/'))apiEvents.push(`failed ${request.url()} ${request.failure()?.errorText}`);});
  page.on('response',response=>{if(new URL(response.url()).pathname.startsWith('/v1/'))apiEvents.push(`${response.status()} ${response.url()}`);});
  page.on('pageerror',error=>apiEvents.push(`pageerror ${error.name}: ${error.message}`));
  await page.goto(`/app?workspace=${workspace}&project=${project}`);
  await page.getByRole('button',{name:'Sign in'}).click();
  if(waitForProject){
    try{await expect(page.locator('section[aria-label="Project selection"] select')).toHaveValue(project,{timeout:30_000});}
    catch(error){throw new Error(`Project selection did not settle; API events: ${apiEvents.join(' | ')}`,{cause:error});}
  }
}
