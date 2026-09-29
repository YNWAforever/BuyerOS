import {expect,test,type Page} from '@playwright/test';
import {webcrypto} from 'node:crypto';

const workspace='e0000000-0000-4000-8000-000000000001';
async function signIn(page:Page,accessToken='fixture-reviewer',initialPath='/app'){
  const keys=await webcrypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
  const publicKey={...(await webcrypto.subtle.exportKey('jwk',keys.publicKey)),kid:'offer-fixture',use:'sig'};
  let nonce='';const encode=(value:unknown)=>Buffer.from(JSON.stringify(value)).toString('base64url');
  await page.route('https://oidc.buyeros.test/authorize**',async route=>{const query=new URL(route.request().url()).searchParams;
    nonce=query.get('nonce')||'';await route.fulfill({status:302,headers:{location:`http://localhost:5173/auth/callback?code=offer-fixture&state=${query.get('state')}`},body:''});});
  await page.route('https://oidc.buyeros.test/oauth/token',async route=>{const unsigned=`${encode({alg:'RS256',kid:'offer-fixture'})}.${encode({iss:'https://oidc.buyeros.test/',aud:'fixture-public-client',sub:accessToken,nonce,exp:Math.floor(Date.now()/1000)+300})}`;
    const signature=await webcrypto.subtle.sign('RSASSA-PKCS1-v1_5',keys.privateKey,new TextEncoder().encode(unsigned));
    await route.fulfill({status:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},body:JSON.stringify({access_token:accessToken,id_token:`${unsigned}.${Buffer.from(signature).toString('base64url')}`,expires_in:300})});});
  await page.route('https://oidc.buyeros.test/.well-known/jwks.json',async route=>route.fulfill({status:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},body:JSON.stringify({keys:[publicKey]})}));
  await page.goto(initialPath);await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByRole('combobox',{name:'Workspace'})).toHaveValue(workspace);
}
async function fillOffer(page:Page,name:string){
  await page.getByLabel('Company name').fill(name);
  await page.getByLabel('Product / service').fill('Industrial sensors');
  await page.getByLabel('Value proposition').fill('Reduces production downtime with reliable monitoring.');
  await page.getByRole('button',{name:'Continue'}).click();
  await page.getByLabel('Markets (country codes or names)').fill('DE, NL');
  await page.getByLabel('Languages (codes or names)').fill('en, de');
  await page.getByRole('checkbox',{name:'Distributor'}).check();
  await page.getByRole('button',{name:'Continue'}).click();
  await page.getByLabel('Must have').fill('Industrial sensor distributor');
  await page.getByLabel('Nice to have').fill('Regional service team');
  await page.getByLabel('Exclude').fill('Existing customer');
  await page.getByRole('checkbox',{name:/I confirm these buyer requirements/}).check();
  await page.getByRole('button',{name:'Continue'}).click();
}

test.describe.serial('T07 persisted offer/profile journey',()=>{
  let primaryProjectId='';
  test('operator creates and edits; reviewer approves exact v1 and v2 after reload',async({browser})=>{
    test.setTimeout(120_000);
    const operatorContext=await browser.newContext();const operator=await operatorContext.newPage();
    await signIn(operator,'fixture-access');
    await operator.getByRole('button',{name:'New project'}).click();
    await fillOffer(operator,'T07 Instruments');
    await operator.getByRole('button',{name:'Save profile'}).click();
    await expect(operator.getByRole('heading',{name:'Profile version 1'})).toBeVisible();
    await expect(operator.getByText('product: Industrial sensors')).toBeVisible();
    await expect(operator.getByRole('button',{name:'Approve profile'})).toHaveCount(0);
    expect(operator.url()).toContain('profile=');
    primaryProjectId=new URL(operator.url()).searchParams.get('project')??'';
    expect(primaryProjectId).toBeTruthy();

    const reviewerContext=await browser.newContext();const reviewer=await reviewerContext.newPage();
    const selectedUrl=new URL(operator.url());
    await signIn(reviewer,'fixture-reviewer',`/app?workspace=${selectedUrl.searchParams.get('workspace')}&project=${selectedUrl.searchParams.get('project')}`);
    await expect(reviewer.getByRole('heading',{name:'Profile version 1'})).toBeVisible();
    await expect(reviewer.getByRole('button',{name:'Edit offer'})).toHaveCount(0);
    await reviewer.getByRole('checkbox',{name:/Confirm approval of this exact version v1/}).check();
    await reviewer.getByRole('button',{name:'Approve profile'}).click();
    await expect(reviewer.getByText('Current approved: v1')).toBeVisible();
    const approvedFacts=await reviewer.evaluate(async({workspaceId,projectId})=>{
      const response=await fetch(`http://127.0.0.1:8000/v1/workspaces/${workspaceId}/projects/${projectId}/icp-versions?offset=0&limit=100`,
        {headers:{Authorization:'Bearer fixture-reviewer'}});
      const body=await response.json() as {data:{items:{number:number;offer_facts:{approved:boolean}[]}[]}};
      return body.data.items.find(item=>item.number===1)?.offer_facts.map(fact=>fact.approved);
    },{workspaceId:workspace,projectId:primaryProjectId});
    expect(approvedFacts).toEqual([true,true]);

    await operator.reload();await operator.getByRole('button',{name:'Sign in'}).click();
    await expect(operator.getByText('Current approved: v1')).toBeVisible();
    await operator.getByRole('button',{name:'Edit offer'}).click();
    await expect(operator.getByLabel('Product / service')).toHaveValue('Industrial sensors');
    await operator.getByLabel('Product / service').fill('Industrial sensor platform');
    await operator.getByLabel('Value proposition').fill('Reduces downtime with predictive sensor monitoring.');
    await operator.getByRole('button',{name:'Continue'}).click();
    await operator.getByRole('button',{name:'Continue'}).click();
    await operator.getByRole('checkbox',{name:/I confirm these buyer requirements/}).check();
    await operator.getByRole('button',{name:'Continue'}).click();
    await operator.getByRole('button',{name:'Save profile'}).click();
    await expect(operator.getByRole('heading',{name:'Profile version 2'})).toBeVisible();
    await expect(operator.getByText('product: Industrial sensor platform')).toBeVisible();
    await expect(operator.getByText('Current approved: —')).toBeVisible();
    const parentLink=await operator.evaluate(async({workspaceId,projectId})=>{
      const response=await fetch(`http://127.0.0.1:8000/v1/workspaces/${workspaceId}/projects/${projectId}/icp-versions?offset=0&limit=100`,{headers:{Authorization:'Bearer fixture-access'}});
      const body=await response.json() as {data:{items:{id:string;number:number;parent_icp_version_id?:string}[]}};
      const first=body.data.items.find(item=>item.number===1),second=body.data.items.find(item=>item.number===2);
      return {first:first?.id,parent:second?.parent_icp_version_id};
    },{workspaceId:workspace,projectId:primaryProjectId});
    expect(parentLink.parent).toBe(parentLink.first);
    await operator.reload();await operator.getByRole('button',{name:'Sign in'}).click();
    await expect(operator.getByRole('heading',{name:'Profile version 2'})).toBeVisible();
    await expect(operator.getByText(/offer facts/)).toBeVisible();
    await reviewer.reload();await reviewer.getByRole('button',{name:'Sign in'}).click();
    await expect(reviewer.getByRole('heading',{name:'Profile version 2'})).toBeVisible();
    await reviewer.getByRole('checkbox',{name:/Confirm approval of this exact version v2/}).check();
    await reviewer.getByRole('button',{name:'Approve profile'}).click();
    await expect(reviewer.getByText('Current approved: v2')).toBeVisible();
    await reviewer.getByRole('combobox',{name:'Language'}).selectOption('zh-HK');
    await expect(reviewer.getByRole('heading',{name:'輪廓詳情'})).toBeVisible();
    await reviewer.screenshot({path:'test-results/t07-offer-profile-zh.png',fullPage:true});
    await reviewerContext.close();await operatorContext.close();
  });
  test('lost ICP response replays one project and one profile with the same action',async({page})=>{
    test.setTimeout(90_000);
    let lost=false;
    await page.route('http://127.0.0.1:8000/v1/workspaces/*/projects/*/icp-versions',async route=>{
      if(route.request().method()==='POST'&&!lost){lost=true;await route.fetch();await route.abort('failed');}
      else await route.continue();
    });
    await signIn(page,'fixture-access');
    await page.getByRole('button',{name:'New project'}).click();
    const name=`Retry Instruments ${Date.now()}`;
    await fillOffer(page,name);
    await page.getByRole('button',{name:'Save profile'}).click();
    await expect(page.getByText('Project saved; profile still needs saving.')).toBeVisible();
    await page.getByRole('button',{name:'Save profile'}).click();
    await expect(page.getByRole('heading',{name:'Profile version 1'})).toBeVisible();
    const result=await page.evaluate(async(workspaceId)=>{
      const response=await fetch(`http://127.0.0.1:8000/v1/workspaces/${workspaceId}/projects?offset=0&limit=100`,{headers:{Authorization:'Bearer fixture-access'}});
      const body=await response.json() as {data:{items:{name:string}[]}};
      return body.data.items;
    },workspace);
    expect(result.filter(item=>item.name===name)).toHaveLength(1);
    expect(lost).toBe(true);
  });
  test('reload after project-only save can resume the pending profile',async({page})=>{
    test.setTimeout(90_000);
    let interrupted=false;
    await page.route('http://127.0.0.1:8000/v1/workspaces/*/projects/*/icp-versions',async route=>{
      if(route.request().method()==='POST'&&!interrupted){interrupted=true;await route.abort('failed');}
      else await route.continue();
    });
    await signIn(page,'fixture-access');
    await page.getByRole('button',{name:'New project'}).click();
    const name=`Resume Instruments ${Date.now()}`;
    await fillOffer(page,name);
    await page.getByRole('button',{name:'Save profile'}).click();
    await expect(page.getByText('Project saved; profile still needs saving.')).toBeVisible();
    await page.reload();await page.getByRole('button',{name:'Sign in'}).click();
    await page.getByRole('combobox',{name:'Project'}).selectOption({label:name});
    await page.getByRole('button',{name:'Edit offer'}).click();
    await expect(page.getByLabel('Product / service')).toHaveValue('Industrial sensors');
    await page.getByRole('button',{name:'Continue'}).click();
    await page.getByRole('checkbox',{name:'Distributor'}).check();
    await page.getByRole('button',{name:'Continue'}).click();
    await page.getByLabel('Must have').fill('Industrial sensor distributor');
    await page.getByRole('checkbox',{name:/I confirm these buyer requirements/}).check();
    await page.getByRole('button',{name:'Continue'}).click();
    await page.getByRole('button',{name:'Save profile'}).click();
    await expect(page.getByRole('heading',{name:'Profile version 1'})).toBeVisible();
    expect(interrupted).toBe(true);
  });
  test('admin archives with reason and archived project cannot be edited',async({page})=>{
    await signIn(page,'fixture-admin',`/app?workspace=${workspace}&project=${primaryProjectId}`);
    await expect(page.getByRole('region',{name:'Project management'})).toBeVisible();
    await page.getByLabel('Archive reason').fill('Pilot finished after review.');
    await page.getByRole('button',{name:'Archive project'}).click();
    await expect(page.getByRole('region',{name:'Project management'})).toHaveCount(0);
    const archived=await page.evaluate(async({workspaceId,projectId})=>{
      const response=await fetch(`http://127.0.0.1:8000/v1/workspaces/${workspaceId}/projects/${projectId}`,{headers:{Authorization:'Bearer fixture-admin'}});
      const body=await response.json() as {data:{status:string}};return body.data.status;
    },{workspaceId:workspace,projectId:primaryProjectId});
    expect(archived).toBe('archived');
    await page.getByRole('combobox',{name:'Project'}).selectOption(primaryProjectId);
    await expect(page.getByRole('button',{name:'Edit offer'})).toHaveCount(0);
    await expect(page.getByRole('button',{name:'Approve profile'})).toHaveCount(0);
  });
  test('unsaved offer navigation asks before discarding and keeps the form on cancel',async({page})=>{
    await signIn(page,'fixture-access');
    await page.getByRole('button',{name:'New project'}).click();
    await page.getByLabel('Company name').fill('Unsaved Instruments');
    page.once('dialog',dialog=>dialog.dismiss());
    await page.getByRole('button',{name:'Overview'}).click();
    await expect(page.getByLabel('Company name')).toHaveValue('Unsaved Instruments');
    page.once('dialog',dialog=>dialog.accept());
    await page.getByRole('button',{name:'Overview'}).click();
    await expect(page.getByLabel('Company name')).toHaveCount(0);
  });
  test('invalid offer step focuses its error without writing',async({page})=>{
    await signIn(page,'fixture-access');
    await page.getByRole('button',{name:'New project'}).click();
    await page.getByRole('button',{name:'Continue'}).click();
    await expect(page.getByRole('alert')).toBeFocused();
    await expect(page.getByRole('heading',{name:'Your offer'})).toBeVisible();
  });
  test('viewer cannot enter write or approval flow',async({page})=>{
    await signIn(page,'fixture-viewer');
    await expect(page.getByRole('button',{name:'New project'})).toHaveCount(0);
    await expect(page.getByRole('button',{name:'Offer'})).toBeDisabled();
    await expect(page.getByRole('button',{name:'Approve profile'})).toHaveCount(0);
  });
});
