// Fake OIDC identity for the isolated HTTP/PostgreSQL workbench fixture only.
import {expect,type Page} from '@playwright/test';
import {webcrypto} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {resolve} from 'node:path';
import {createJourneyInput,observeWorkspaceLocale} from './journey-input';
export const workspace='e0000000-0000-4000-8000-000000000001';
export const project='e1000000-0000-4000-8000-000000000001';

/** Isolate independent cases on the guarded owned Docker fixture, before login. */
export async function resetWorkbenchFixtureRateWindows(){
  const cwd=resolve('services/worker');
  const python=resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
  const {stdout}=await promisify(execFile)(python,['tests/fixtures/prepare_browser_project.py','isolate-workbench'],
    {cwd,timeout:30_000});
  expect(JSON.parse(stdout).fixture_initial_rate_windows_reset).toBe(true);
}

export async function signInWorkbench(page:Page,waitForProject=true,actor:'reviewer'|'access'|'viewer'|'admin'='reviewer',entry=`/app?workspace=${workspace}&project=${project}`,input=createJourneyInput()){
  await input.install(page);
  const keys=await webcrypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,
    publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
  const publicKey={...(await webcrypto.subtle.exportKey('jwk',keys.publicKey)),kid:'workbench-fixture',use:'sig'};
  const encode=(value:unknown)=>Buffer.from(JSON.stringify(value)).toString('base64url');let nonce='';
  await page.route('https://oidc.buyeros.test/authorize**',async route=>{const q=new URL(route.request().url()).searchParams;
    nonce=q.get('nonce')||'';await route.fulfill({status:302,headers:{location:`http://localhost:5173/auth/callback?code=workbench-fixture&state=${q.get('state')}`},body:''});});
  await page.route('https://oidc.buyeros.test/oauth/token',async route=>{
    const unsigned=`${encode({alg:'RS256',kid:'workbench-fixture'})}.${encode({iss:'https://oidc.buyeros.test/',
      aud:'fixture-public-client',sub:`fixture-${actor}`,nonce,exp:Math.floor(Date.now()/1000)+900})}`;
    const signature=await webcrypto.subtle.sign('RSASSA-PKCS1-v1_5',keys.privateKey,new TextEncoder().encode(unsigned));
    await route.fulfill({status:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},
      body:JSON.stringify({access_token:`fixture-${actor}`,id_token:`${unsigned}.${Buffer.from(signature).toString('base64url')}`,expires_in:900})});
  });
  await page.route('https://oidc.buyeros.test/.well-known/jwks.json',async route=>route.fulfill({status:200,
    contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},body:JSON.stringify({keys:[publicKey]})}));
  const apiEvents:string[]=[];
  page.on('request',request=>{if(new URL(request.url()).pathname.startsWith('/v1/'))apiEvents.push(`request ${request.method()} ${request.url()}`);});
  page.on('requestfailed',request=>{if(new URL(request.url()).pathname.startsWith('/v1/'))apiEvents.push(`failed ${request.url()} ${request.failure()?.errorText}`);});
  page.on('response',response=>{if(new URL(response.url()).pathname.startsWith('/v1/'))apiEvents.push(`${response.status()} ${response.url()}`);});
  page.on('pageerror',error=>apiEvents.push(`pageerror ${error.name}: ${error.message}`));
  const localeRead=input.mode==='keyboard'&&waitForProject?observeWorkspaceLocale(page,workspace):null;
  try{
  await page.goto(entry);
  await input.activate(page.getByRole('button',{name:/^(Sign in|登入)$/}));
  // The fake callback exchanges/verifies its token asynchronously. Negative-access
  // cases must reach the authenticated workspace read before asserting its result.
  await expect.poll(()=>apiEvents.some(event=>event.startsWith('request GET ')&&new URL(event.slice('request GET '.length)).pathname==='/v1/workspaces'),
    {timeout:30_000,message:'Fake sign-in must complete and request workspace access'}).toBe(true);
  if(waitForProject){
    try{await expect(page.getByRole('combobox',{name:/^(Project|專案)$/})).toHaveValue(project,{timeout:30_000});}
    catch(error){throw new Error(`Project selection did not settle; API events: ${apiEvents.join(' | ')}`,{cause:error});}
  }
  if(localeRead)await localeRead.settle();
  }finally{localeRead?.dispose();}
}
