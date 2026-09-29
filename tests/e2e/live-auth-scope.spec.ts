import {expect, test, type Page} from '@playwright/test';
import {webcrypto} from 'node:crypto';

const issuer='https://oidc.buyeros.test/';
const fixtureWorkspace=(id:string, roles=['operator'])=>({id,name:`Workspace ${id}`,roles,data_mode:'live'});
const fixtureProject=(id:string)=>({id,name:`Project ${id}`,status:'active'});
function b64(value: unknown) {return Buffer.from(JSON.stringify(value)).toString('base64url');}
async function setup(page:Page, input:{workspaces?: ReturnType<typeof fixtureWorkspace>[]; projects?: Record<string,ReturnType<typeof fixtureProject>[]>; wrongNonce?:boolean; wrongState?:boolean; expired?:boolean; delayFirstProjectA?:boolean; shortExpiry?:boolean}={}) {
  const workspaces=input.workspaces??[fixtureWorkspace('A')];
  const projects=input.projects??{A:[fixtureProject('P')]};
  const calls:{method:string;url:string}[]=[];
  const keys=await webcrypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
  const publicKey={...(await webcrypto.subtle.exportKey('jwk',keys.publicKey)),kid:'fixture-key',use:'sig'};
  let nonce='', firstA = true;
  await page.route(`${issuer}authorize**`, async route=>{
    const url=new URL(route.request().url()); nonce=url.searchParams.get('nonce')||'';
    const state=input.wrongState?'wrong-state':url.searchParams.get('state');
    await route.fulfill({status:302,headers:{location:`http://localhost:5173/auth/callback?code=fixture-code&state=${state}`},body:''});
  });
  await page.route(`${issuer}oauth/token`,async route=>{
    const form=new URLSearchParams(route.request().postData()||'');
    expect(form.get('client_secret')).toBeNull();expect(form.get('code_verifier')).toBeTruthy();
    const payload={iss:issuer,aud:'fixture-public-client',sub:'fixture-actor',nonce:input.wrongNonce?'wrong':nonce,exp:Math.floor(Date.now()/1000)+(input.expired?-1:300)};
    const unsigned=`${b64({alg:'RS256',kid:'fixture-key'})}.${b64(payload)}`;
    const sig=await webcrypto.subtle.sign('RSASSA-PKCS1-v1_5',keys.privateKey,new TextEncoder().encode(unsigned));
    await route.fulfill({status:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},body:JSON.stringify({access_token:'fixture-access',id_token:`${unsigned}.${Buffer.from(sig).toString('base64url')}`,expires_in:input.shortExpiry?35:300})});
  });
  await page.route(`${issuer}.well-known/jwks.json`,async route=>route.fulfill({status:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},body:JSON.stringify({keys:[publicKey]})}));
  await page.route('https://oidc.buyeros.test/v2/logout**',async route=>route.fulfill({status:302,headers:{location:'http://localhost:5173/app'},body:''}));
  await page.route('https://api.buyeros.test/**',async route=>{
    const request=route.request(), url=new URL(request.url()); calls.push({method:request.method(),url:url.toString()});
    let data:unknown={items:[],offset:0,limit:100,total:0};
    if(url.pathname==='/v1/workspaces') {const offset=Number(url.searchParams.get('offset')||0);data={items:workspaces.slice(offset,offset+100),offset,limit:100,total:workspaces.length};}
    else {
      const match=url.pathname.match(/^\/v1\/workspaces\/([^/]+)\/projects$/);
      if(match) {if(match[1]==='A' && input.delayFirstProjectA && firstA) {firstA=false;await new Promise(resolve=>setTimeout(resolve,800));} const items=projects[match[1]]||[],offset=Number(url.searchParams.get('offset')||0);data={items:items.slice(offset,offset+100),offset,limit:100,total:items.length};}
      else if(url.pathname.includes('/icp-versions')) data={items:[],offset:0,limit:100,total:0};
      else if(url.pathname.includes('/projects/')) data={id:url.pathname.split('/').at(-1),name:'Selected project',version:1,active_icp_version_id:null};
    }
    await route.fulfill({status:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},body:JSON.stringify({data,request_id:'fixture-request',data_mode:'live'})});
  });
  return calls;
}
async function signIn(page:Page,path='/app') {await page.goto(path);await page.getByRole('button',{name:'Sign in'}).click();}

test('OIDC callback selects sole membership and project; no bearer reaches URL or storage',async({page})=>{
  const calls=await setup(page);
  await signIn(page);
  await expect(page.getByRole('combobox',{name:'Workspace'})).toHaveValue('A');
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue('P');
  await expect(page).toHaveURL(/workspace=A.*project=P/);
  expect(calls.some(call=>call.url.includes('/workspaces/A/projects'))).toBe(true);
  const leaked=await page.evaluate(()=>Object.values(localStorage).join('|')+location.href);
  expect(leaked).not.toContain('fixture-access');
  await page.screenshot({path:'test-results/t05-live-scope-fixture.png',fullPage:true});
});

test('empty membership has no project request or write',async({page})=>{
  const calls=await setup(page,{workspaces:[]});await signIn(page);
  await expect(page.getByText('No workspace membership.')).toBeVisible();
  expect(calls.some(call=>call.url.includes('/projects')||call.method!=='GET')).toBe(false);
});

test('multiple memberships need explicit choice; viewer cannot edit',async({page})=>{
  const calls=await setup(page,{workspaces:[fixtureWorkspace('A',['viewer']),fixtureWorkspace('B')],projects:{A:[fixtureProject('P')],B:[]}});
  await signIn(page);await expect(page.getByRole('combobox',{name:'Workspace'})).toHaveValue('');
  await page.getByRole('combobox',{name:'Workspace'}).selectOption('A');
  await expect(page.getByRole('button',{name:'Offer'})).toBeDisabled();
  expect(calls.some(call=>call.method!=='GET')).toBe(false);
  await page.getByRole('combobox',{name:'Workspace'}).selectOption('B');
  await expect(page.getByRole('button',{name:'Offer'})).toBeEnabled();
});

test('unknown deep-link workspace is a 404 state with no project read',async({page})=>{
  const calls=await setup(page);await signIn(page,'/app?workspace=unknown');
  await expect(page.getByText('Workspace not found (404)')).toBeVisible();
  expect(calls.some(call=>call.url.includes('/projects'))).toBe(false);
});

test('wrong state and nonce fail closed before workspace read',async({page})=>{
  for(const input of [{wrongState:true},{wrongNonce:true},{expired:true}]) {
    const calls=await setup(page,input);
    await signIn(page);
    await expect(page.getByText('Sign-in failed. Please start again.')).toBeVisible();
    expect(calls.some(call=>call.url.includes('/v1/workspaces'))).toBe(false);
    await page.context().clearCookies();
  }
});



test('unknown project deep link stays unselected with explicit 404',async({page})=>{
  const calls=await setup(page);await signIn(page,'/app?workspace=A&project=missing');
  await expect(page.getByText('Project not found (404)')).toBeVisible();
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue('');
  expect(calls.some(call=>call.method!=='GET')).toBe(false);
});

test('reload reauthenticates and revalidates workspace and project',async({page})=>{
  const calls=await setup(page);await signIn(page);
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue('P');
  const firstCount=calls.filter(call=>call.url.includes('/v1/workspaces?')).length;
  await page.reload();await expect(page.getByRole('button',{name:'Sign in'})).toBeVisible();
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue('P');
  expect(calls.filter(call=>call.url.includes('/v1/workspaces?')).length).toBeGreaterThan(firstCount);
});

test('A to B to A discards late project results',async({page})=>{
  await setup(page,{workspaces:[fixtureWorkspace('A'),fixtureWorkspace('B')],projects:{A:[fixtureProject('P')],B:[fixtureProject('Q')]},delayFirstProjectA:true});
  await signIn(page);const select=page.getByRole('combobox',{name:'Workspace'});
  await select.selectOption('A');await select.selectOption('B');
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue('Q');
  await select.selectOption('A');await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue('P');
  await page.waitForTimeout(900);
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue('P');
});

test('logout clears memory and returns to sign-in',async({page})=>{
  await setup(page);await signIn(page);
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue('P');
  await page.getByRole('button',{name:'Sign out'}).click();
  await expect(page.getByRole('button',{name:'Sign in'})).toBeVisible();
  expect(await page.evaluate(()=>Object.values(localStorage).join('|'))).not.toContain('fixture-access');
});


test('short-lived token expires reactively and hides scoped UI',async({page})=>{
  await setup(page,{shortExpiry:true});await signIn(page);
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue('P');
  await expect(page.getByRole('button',{name:'Sign in'})).toBeVisible({timeout:7000});
});

test('unknown profile deep link returns a 404 state',async({page})=>{
  await setup(page);await signIn(page,'/app?workspace=A&project=P&profile=missing');
  await expect(page.getByText('Profile not found (404)')).toBeVisible();
});

test('workspace selection traverses actual API pages',async({page})=>{
  const workspaces=Array.from({length:105},(_,index)=>fixtureWorkspace(`W${index}`));
  const calls=await setup(page,{workspaces,projects:{W104:[fixtureProject('P')]}});
  await signIn(page);
  await expect(page.getByRole('combobox',{name:'Workspace'}).locator('option')).toHaveCount(106);
  await page.getByRole('combobox',{name:'Workspace'}).selectOption('W104');
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue('P');
  expect(calls.filter(call=>call.url.includes('/v1/workspaces?')).length).toBe(2);
});
