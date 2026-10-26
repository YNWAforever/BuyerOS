import {expect,test,type Page} from '@playwright/test';
import {installNeonFixture} from './fixtures/neon-sign-in';

const workspace='e0000000-0000-4000-8000-000000000001';
async function signIn(page:Page,accessToken='fixture-reviewer',initialPath='/app'){
  const auth=await installNeonFixture(page,{accessToken});
  await page.goto(initialPath);await auth.signIn();
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

test('UK rice intake keeps complete criteria and roles through summary, save and edit',async({page})=>{
  test.setTimeout(120_000);
  const must='Wholesale buyers serving UK retail / foodservice\nCan qualify importer, distribution and purchasing responsibilities';
  const nice='Handles 5 kg retail / 10–20 kg foodservice packs';
  const exclude='No online-resale / e-commerce partnership pitches\nNo unverified brand, origin or certification claims';
  const roles='Category buyer / Purchasing manager\nImport manager';
  await signIn(page,'fixture-access');
  await page.getByRole('button',{name:'New project'}).click();
  await expect(page.getByText(/Save the project first, then use Edit offer/)).toBeVisible();
  await page.getByLabel('Company name').fill('UK Rice Pilot Fixture');
  await page.getByLabel('Product / service').fill('Thai jasmine rice pilot');
  await page.getByLabel('Value proposition').fill('Proposed wholesale supply; specifications and brand rights await review.');
  await page.getByRole('button',{name:'Continue'}).click();
  await page.getByLabel('Markets (country codes or names)').fill('United Kingdom，英國');
  await page.getByLabel('Languages (codes or names)').fill('English，英文');
  await page.getByRole('checkbox',{name:'Importer',exact:true}).check();
  await page.getByRole('checkbox',{name:'Wholesaler',exact:true}).check();
  await page.getByLabel('Desired buyer roles (optional)').fill(roles);
  await page.getByRole('button',{name:'Continue'}).click();
  await page.getByLabel('Must have',{exact:true}).fill(must);
  await page.getByLabel('Nice to have',{exact:true}).fill(nice);
  await page.getByLabel('Exclude',{exact:true}).fill(exclude);
  await page.getByRole('checkbox',{name:/I confirm these buyer requirements/}).check();
  await page.getByRole('button',{name:'Continue'}).click();
  const summary=page.getByRole('region',{name:'Profile summary'});
  for(const value of [must,nice,exclude,roles,'Importer, Wholesaler']){
    await expect(summary.getByText(value,{exact:true})).toBeVisible();
  }
  for(const width of [320,390]){
    await page.setViewportSize({width,height:844});
    await expect(summary.getByText(exclude,{exact:true})).toBeVisible();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    const overflowingSteps=await page.getByRole('navigation',{name:'Offer steps'}).getByRole('button').evaluateAll(buttons=>
      buttons.filter(button=>button.scrollWidth>button.clientWidth+1).map(button=>button.textContent));
    expect(overflowingSteps,`Step labels must fit their controls at ${width}px`).toEqual([]);
  }
  await page.screenshot({path:'test-results/uk-rice-intake-summary.png',fullPage:true});
  await page.getByRole('button',{name:'Save profile'}).click();
  await expect(page.getByRole('heading',{name:'Profile version 1'})).toBeVisible();
  await page.reload();
  await page.getByRole('button',{name:'Edit offer'}).click();
  await page.getByRole('button',{name:'Continue'}).click();
  await expect(page.getByLabel('Markets (country codes or names)')).toHaveValue('GB');
  await expect(page.getByLabel('Languages (codes or names)')).toHaveValue('en');
  await expect(page.getByLabel('Desired buyer roles (optional)')).toHaveValue('Category buyer / Purchasing manager, Import manager');
  await page.getByRole('button',{name:'Continue'}).click();
  await expect(page.getByRole('textbox',{name:'Must have',exact:true})).toHaveValue(must);
  await expect(page.getByRole('textbox',{name:'Nice to have',exact:true})).toHaveValue(nice);
  await expect(page.getByRole('textbox',{name:'Exclude',exact:true})).toHaveValue(exclude);
  await expect(page.getByRole('checkbox',{name:/I confirm these buyer requirements/})).not.toBeChecked();
});

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

    await operator.reload();
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
    await operator.reload();
    await expect(operator.getByRole('heading',{name:'Profile version 2'})).toBeVisible();
    await expect(operator.getByText(/offer facts/)).toBeVisible();
    await reviewer.reload();
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
    await page.reload();
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
    await page.locator('.live-project-management > summary').click();
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
