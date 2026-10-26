import {expect, test, type Page} from '@playwright/test';
import {installNeonFixture} from './fixtures/neon-sign-in';
import type {components} from '@/services/generated/buyeros-api';

const authFixtures=new WeakMap<Page,Awaited<ReturnType<typeof installNeonFixture>>>();
const fixtureWorkspace=(id:string, roles=['operator'])=>({id,name:`Workspace ${id}`,roles,data_mode:'live'});
const fixtureProject=(id:string)=>({id,name:`Project ${id}`,status:'active'});
function b64(value: unknown) {return Buffer.from(JSON.stringify(value)).toString('base64url');}
async function setup(page:Page, input:{workspaces?: ReturnType<typeof fixtureWorkspace>[]; projects?: Record<string,ReturnType<typeof fixtureProject>[]>; wrongSubject?:boolean; wrongState?:boolean; expired?:boolean; delayFirstProjectA?:boolean; shortExpiry?:boolean}={}) {
  const workspaces=input.workspaces??[fixtureWorkspace('A')];
  const projects=input.projects??{A:[fixtureProject('P')]};
  const calls:{method:string;url:string}[]=[];
  const auth=await installNeonFixture(page,{subject:'fixture-actor',accessToken:'fixture-access',apiOrigin:'https://api.buyeros.test'});
  authFixtures.set(page,auth);
  let firstA=true;
  if(input.wrongState)await page.route('http://localhost:5173/auth/callback?**',async route=>{
    const callback=new URL(route.request().url());callback.searchParams.set('state','wrong-state');
    await route.fulfill({status:302,headers:{location:callback.href},body:''});
  },{times:1});
  if(input.wrongSubject||input.expired||input.shortExpiry){
    // Metadata-only tokens stay inside this browser fixture. Production still
    // verifies signature/trust; these cases exercise the client identity fence.
    const expires=Math.floor(Date.now()/1000)+(input.expired?-1:input.shortExpiry?35:300);
    const token=`${b64({alg:'none',typ:'JWT'})}.${b64({sub:input.wrongSubject?'other-fixture-actor':'fixture-actor',exp:expires})}.synthetic-only`;
    await page.route('http://localhost:5173/api/auth/token',route=>route.fulfill({status:200,
      contentType:'application/json',body:JSON.stringify({token})}));
  }
  await page.route(url=>['https://api.buyeros.test','http://127.0.0.1:8000','http://localhost:5173'].includes(url.origin)&&url.pathname.startsWith('/v1/'),async route=>{
    const request=route.request(), url=new URL(request.url()); calls.push({method:request.method(),url:url.toString()});
    expect(request.headers().authorization).toMatch(/^Bearer \S+$/);
    let data:unknown={items:[],offset:0,limit:100,total:0};
    if(url.pathname==='/v1/workspaces') {const offset=Number(url.searchParams.get('offset')||0);data={items:workspaces.slice(offset,offset+100),offset,limit:100,total:workspaces.length};}
    else {
      const match=url.pathname.match(/^\/v1\/workspaces\/([^/]+)\/projects$/);
      const usage=url.pathname.match(/^\/v1\/workspaces\/([^/]+)\/projects\/([^/]+)\/usage$/);
      if(url.pathname.match(/^\/v1\/workspaces\/[^/]+\/preferences$/)) data={locale:'en',default_markets:[],version:1};
      else if(usage) data={
        workspace_id:usage[1],project_id:usage[2],from:url.searchParams.get('from')!,to:url.searchParams.get('to')!,
        as_of:new Date().toISOString(),categories:[],
        total_settled:{amount:'0.000000',currency:'USD'},total_reserved:{amount:'0.000000',currency:'USD'},remaining:{amount:'0.000000',currency:'USD'},
        accepted_company_count:0,eligible_contactable_company_count:0,cost_per_accepted_company:null,cost_per_contactable_accepted_company:null,
        denominator_definition:'Synthetic empty usage for scope-only browser fixtures.',includes_partial_runs:true,
      } satisfies components['schemas']['Usage'];
      else if(match) {if(match[1]==='A' && input.delayFirstProjectA && firstA) {firstA=false;await new Promise(resolve=>setTimeout(resolve,800));} const items=projects[match[1]]||[],offset=Number(url.searchParams.get('offset')||0);data={items:items.slice(offset,offset+100),offset,limit:100,total:items.length};}
      else if(url.pathname.includes('/icp-versions')) data={items:[],offset:0,limit:100,total:0};
      else if(url.pathname.includes('/projects/')) data={id:url.pathname.split('/').at(-1),name:'Selected project',version:1,active_icp_version_id:null};
    }
    await route.fulfill({status:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},body:JSON.stringify({data,request_id:'fixture-request',data_mode:'live'})});
  });
  return calls;
}
async function signIn(page:Page,path='/app') {await page.goto(path);const auth=authFixtures.get(page);if(!auth)throw new Error('Install the owned Neon fixture before sign-in');await auth.signIn();}

test('grouped live navigation preserves scoped destinations and viewer offer restrictions',async({page})=>{
  await setup(page,{workspaces:[fixtureWorkspace('A',['viewer'])]});
  await signIn(page,'/app/discover/synthetic-run?workspace=A&project=P');
  await expect(page.getByRole('combobox',{name:'Project',exact:true})).toHaveValue('P');
  const nav=page.getByRole('navigation',{name:'BuyerOS sections'});
  const discovery=nav.getByRole('group',{name:'Discover & review',exact:true});
  await expect(discovery.getByRole('button')).toHaveText(['Offer','Research runs','Buyers']);
  await expect(discovery.getByRole('button',{name:'Offer',exact:true})).toBeDisabled();
  await expect(discovery.getByRole('button',{name:'Research runs',exact:true})).toHaveAttribute('aria-current','page');
  await expect(nav.getByRole('group',{name:'Follow up',exact:true}).getByRole('button')).toHaveText(['Drafts','Results']);
  await expect(nav.getByRole('group',{name:'Manage',exact:true}).getByRole('button')).toHaveText(['Settings','Operations']);
  await expect(nav.getByRole('button',{name:'Buyer Lists',exact:true})).toHaveCount(0);
  await discovery.getByRole('button',{name:'Buyers',exact:true}).click();
  await expect.poll(()=>new URL(page.url()).pathname).toBe('/app/discover');
  expect(new URL(page.url()).searchParams.get('workspace')).toBe('A');
  expect(new URL(page.url()).searchParams.get('project')).toBe('P');
  await expect(discovery.getByRole('button',{name:'Buyers',exact:true})).toHaveAttribute('aria-current','page');
  await page.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');
  await expect(nav.getByRole('group',{name:'尋找與覆核',exact:true}).getByRole('button')).toHaveText(['產品資料','研究進度','買家']);
  await expect(nav.getByRole('group',{name:'跟進',exact:true}).getByRole('button')).toHaveText(['草稿','結果']);
  await expect(nav.getByRole('group',{name:'管理',exact:true}).getByRole('button')).toHaveText(['設定','營運工作台']);
});

test('overview puts daily work before progress, profile and usage while access recovery stays reachable',async({page})=>{
  await setup(page,{workspaces:[fixtureWorkspace('A',['workspace_admin'])]});await signIn(page);
  await expect(page.getByRole('combobox',{name:'Project',exact:true})).toHaveValue('P');
  const names=['Daily work queue','Pilot monthly budget','Lead workflow','Profile details','Usage'];
  for(const name of names)await expect(page.getByRole('region',{name,exact:true})).toBeVisible();
  const order=await page.locator('main section[aria-label]').evaluateAll(elements=>elements.map(element=>element.getAttribute('aria-label')));
  const indices=names.map(name=>order.indexOf(name));
  expect(indices).toEqual([...indices].sort((a,b)=>a-b));
  const access=page.locator('.live-access-details');
  await expect(access).not.toHaveAttribute('open');
  await expect(page.getByRole('button',{name:'Check access again',exact:true})).toBeVisible();
  await access.getByText('Access details',{exact:true}).click();
  await expect(access).toContainText('Role');
  await expect(page.getByRole('button',{name:'Check access again',exact:true})).toBeVisible();
  const manage=page.locator('.live-project-management');
  await expect(manage).not.toHaveAttribute('open');
  await manage.locator('summary').click();
  await expect(manage.getByRole('region',{name:'Project management',exact:true})).toBeVisible();
});

test('initial workspace access failure announces one error and keeps retry visible',async({page})=>{
  await setup(page);
  await page.route('https://api.buyeros.test/v1/workspaces?**',route=>route.fulfill({status:503,contentType:'application/json',
    headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},
    body:JSON.stringify({code:'TEMPORARILY_UNAVAILABLE',message:'Owned fixture unavailable',request_id:'e0000000-0000-4000-8000-000000000099',retryable:true})}));
  await signIn(page);
  await expect(page.getByRole('button',{name:'Retry loading workspaces',exact:true})).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(1);
});

test('Neon cookie callback selects sole membership and project; no bearer reaches URL or storage',async({page})=>{
  const calls=await setup(page);
  const issuedToken=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/auth/token'&&response.status()===200);
  await signIn(page);
  const {token}=await (await issuedToken).json();
  await expect(page.getByRole('combobox',{name:'Workspace'})).toHaveValue('A');
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue('P');
  await expect(page).toHaveURL(/workspace=A.*project=P/);
  expect(calls.some(call=>call.url.includes('/workspaces/A/projects'))).toBe(true);
  const leaked=await page.evaluate(()=>Object.values(localStorage).join('|')+Object.values(sessionStorage).join('|')+location.href);
  expect(leaked).not.toContain('fixture-access');expect(leaked).not.toContain(token);
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

for(const [fault,input] of [['wrong state',{wrongState:true}],['changed subject',{wrongSubject:true}],['expired metadata',{expired:true}]] as const) test(`${fault} fails closed before workspace read`,async({page})=>{
    const calls=await setup(page,input);
    await signIn(page);
    await expect(page.getByRole('alert')).toContainText('Sign-in failed. Please start again.');
    expect(calls.some(call=>call.url.includes('/v1/workspaces'))).toBe(false);
});

test('unknown project deep link stays unselected with explicit 404',async({page})=>{
  const calls=await setup(page);await signIn(page,'/app?workspace=A&project=missing');
  await expect(page.getByText('Project not found (404)')).toBeVisible();
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue('');
  expect(calls.some(call=>call.method!=='GET')).toBe(false);
});

test('reload restores its cookie session and revalidates workspace and project',async({page})=>{
  const calls=await setup(page);await signIn(page);
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue('P');
  const firstCount=calls.filter(call=>call.url.includes('/v1/workspaces?')).length;
  await page.reload();
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

test('failed renewal of a short-lived token reactively hides scoped UI',async({page})=>{
  await page.clock.install({time:new Date()});
  await setup(page,{shortExpiry:true});await signIn(page);
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue('P');
  await page.clock.fastForward(6000);
  await expect(page.getByRole('button',{name:'Sign in'})).toBeVisible();
});

test('unknown profile deep link returns a 404 state',async({page})=>{
  await setup(page);await signIn(page,'/app?workspace=A&project=P&profile=missing');
  await expect(page.getByRole('region',{name:'Profile details',exact:true}).getByRole('alert')).toHaveText('Profile not found (404)');
});

test('workspace selection traverses actual API pages',async({page})=>{
  const workspaces=Array.from({length:105},(_,index)=>fixtureWorkspace(`W${index}`));
  const calls=await setup(page,{workspaces,projects:{W104:[fixtureProject('P')]}});
  await signIn(page);
  await expect(page.getByRole('combobox',{name:'Workspace'}).locator('option')).toHaveCount(106);
  const initialPages=calls.filter(call=>call.url.includes('/v1/workspaces?'));
  expect(initialPages).toHaveLength(2);
  expect(initialPages.map(call=>Number(new URL(call.url).searchParams.get('offset')||0))).toEqual([0,100]);
  await page.getByRole('combobox',{name:'Workspace'}).selectOption('W104');
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue('P');
});
