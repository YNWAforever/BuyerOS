import {expect,test} from '@playwright/test';
import {registerStaffJourney,signIn} from './fixtures/staff-journey';
const workspace='e0000000-0000-4000-8000-000000000001';
const project='e1000000-0000-4000-8000-000000000001';
const scope=`workspace=${workspace}&project=${project}`;
registerStaffJourney('cloudflare');

test('CF07 real second page, 101-row native bulk and persistent Workflow restart',async({page,request})=>{
  test.setTimeout(240_000);
  await signIn(page,'fixture-access',`/app/discover?${scope}`);
  await expect(page.getByText('101 in snapshot')).toBeVisible();
  await page.getByRole('button',{name:'Next page'}).click();
  await expect(page.getByText('Rows 13–24 of 101')).toBeVisible();
  await expect(page.getByText('Buyer Fixture 13',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Previous page'}).click();
  expect((await request.post('http://127.0.0.1:8000/fixture/cloudflare/barrier/true')).ok()).toBe(true);
  try{
    await page.getByRole('button',{name:'Select all filtered'}).click();
    await page.getByRole('textbox',{name:'Assignment reason'}).fill('Fictional Cloudflare restart batch');
    await page.getByRole('checkbox',{name:'Confirm owner assignment'}).check();
    await page.getByRole('button',{name:'Assign selected buyers'}).click();
    await expect(page).toHaveURL(/bulk_job=[0-9a-f-]{36}/);
    const jobId=new URL(page.url()).searchParams.get('bulk_job');
    expect(jobId).toMatch(/^[0-9a-f-]{36}$/);
    const state=async()=>{
      const response=await request.get(`http://127.0.0.1:8000/fixture/cloudflare/bulk/${jobId}`);
      expect(response.ok()).toBe(true);return response.json();
    };
    await expect.poll(async()=>(await state()).processed,{timeout:60_000}).toBe(50);
    await expect.poll(async()=>(await state()).barrier_hits,{timeout:60_000}).toBeGreaterThan(0);
    const restarted=await request.post('http://127.0.0.1:8788/fixture/restart',{headers:{'x-buyeros-fixture':'local-only'},timeout:60_000});
    expect(restarted.ok()).toBe(true);expect((await restarted.json()).restarts).toBe(1);
    expect((await request.post('http://127.0.0.1:8000/fixture/cloudflare/barrier/false')).ok()).toBe(true);
    await expect.poll(async()=>(await state()).status,{timeout:180_000}).toBe('completed');
    expect(await state()).toMatchObject({processed:101,updated:101,conflicts:0,platform_receipts:3});
    await page.getByRole('button',{name:'Refresh job'}).click();
    await expect(page.getByRole('region',{name:'Bulk job progress'})).toContainText('completed: 101 of 101 processed');
    await page.reload();await page.getByRole('button',{name:'Sign in'}).click();
    await expect(page.getByRole('region',{name:'Bulk job progress'})).toContainText('completed: 101 of 101 processed');
    await page.locator('header select').selectOption('zh-HK');
    await page.setViewportSize({width:390,height:844});
    await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await page.screenshot({path:'artifacts/cloudflare/screenshots/CF07-bulk-restart-zh-HK-mobile.png',fullPage:true});
  }finally{await request.post('http://127.0.0.1:8000/fixture/cloudflare/barrier/false');}
});

test('CF07 optional lookup unknown acceptance retains one hold and never blindly resubmits',async({page,request})=>{
  test.setTimeout(180_000);
  await signIn(page,'fixture-access',`/app/discover?${scope}`);
  await page.getByRole('button',{name:'Details'}).first().click();
  await page.getByRole('tab',{name:'Contacts'}).click();
  const preview=page.locator('.contact-quote');
  await preview.getByRole('button',{name:'View contact quote'}).click();
  await preview.getByRole('button',{name:'Confirm lookup'}).click();
  await expect(page).toHaveURL(/contact_job=[0-9a-f-]{36}/);
  const jobId=new URL(page.url()).searchParams.get('contact_job');
  expect(jobId).toMatch(/^[0-9a-f-]{36}$/);
  const state=async()=>{const r=await request.get(`http://127.0.0.1:8000/fixture/cloudflare/contact/${jobId}`);expect(r.ok()).toBe(true);return r.json();};
  await expect.poll(async()=>(await state()).status,{timeout:60_000}).toBe('unknown');
  expect(await state()).toMatchObject({hold:'0.300000',hold_state:'active',operations:['unknown'],fixture_submit_count:1});
  await preview.getByRole('button',{name:'Refresh lookup job'}).click();
  await expect(preview.getByText(/Held cost: USD 0.300000/)).toBeVisible();
  await expect(preview).toContainText('An unknown provider result keeps the hold');
  await preview.getByRole('button',{name:'Refresh lookup job'}).click();
  expect((await state()).fixture_submit_count).toBe(1);
  await page.screenshot({path:'artifacts/cloudflare/screenshots/CF07-unknown-contact-hold-en.png',fullPage:true});
});

test('CF07 viewer and reviewer negative roles; a late real buyer response cannot overwrite another project',async({page,browser,request})=>{
  test.setTimeout(180_000);
  const viewerContext=await browser.newContext();const viewer=await viewerContext.newPage();
  await signIn(viewer,'fixture-viewer',`/app/discover?${scope}`);
  await expect(viewer.getByRole('button',{name:'Assign selected buyers'})).toHaveCount(0);
  await expect(viewer.getByRole('button',{name:'Apply review'})).toHaveCount(0);
  const denied=await request.patch(`http://127.0.0.1:8000/v1/workspaces/${workspace}/memberships/e0000000-0000-4000-8000-000000000007`,{
    headers:{Authorization:'Bearer fixture-reviewer','Idempotency-Key':'cf07-role-denied','If-Match':'"1"' },data:{roles:['workspace_admin'],active:true,reason:'Fictional denied grant'}});
  expect(denied.status()).toBe(403);
  await viewerContext.close();
  await signIn(page,'fixture-access',`/app/discover?${scope}`);
  let release:()=>void=()=>{};let seen:()=>void=()=>{};
  const held=new Promise<void>(r=>release=r);const intercepted=new Promise<void>(r=>seen=r);let delayOnce=true;
  await page.route(`http://localhost:5173/v1/workspaces/${workspace}/projects/${project}/buyers?**`,async route=>{
    const response=await route.fetch();
    if(delayOnce){delayOnce=false;seen();await held;}
    await route.fulfill({response});
  });
  await page.getByRole('button',{name:'Refresh results'}).click();await intercepted;
  const other='e9100000-0000-4000-8000-000000000001';
  await page.getByRole('combobox',{name:'Project',exact:true}).selectOption(other);
  await expect(page.getByRole('combobox',{name:'Project',exact:true})).toHaveValue(other);
  release();
  await expect(page.getByText('Buyer Fixture 01',{exact:true})).toHaveCount(0);
  await page.getByRole('combobox',{name:'Project',exact:true}).selectOption(project);
  await expect(page.getByText('101 in snapshot')).toBeVisible();
  await expect(page.getByText('Buyer Fixture 01',{exact:true})).toBeVisible();
  await page.unrouteAll({behavior:'wait'});
});
