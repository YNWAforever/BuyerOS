import {expect,test} from '@playwright/test';
import {installNeonFixture} from './fixtures/neon-sign-in';

const workspace='e0000000-0000-4000-8000-000000000001';
const project='e1000000-0000-4000-8000-000000000001';

const buyer='e2000000-0000-4000-8000-000000000001';
const seededDraft='ec000000-0000-4000-8000-000000000001';

test('T24 staff prepares an unaddressed draft and recovers immutable edits',async({page,request})=>{
  test.setTimeout(180_000);
  const auth=await installNeonFixture(page,{accessToken:'fixture-access'});
  await page.goto(`/app/outreach?workspace=${workspace}&project=${project}&buyer=${buyer}`);
  await auth.signIn();
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
  await expect(page.getByRole('textbox',{name:'Body',exact:true})).toContainText('fictional industrial sensors');
  await page.getByRole('textbox',{name:'Body',exact:true}).fill('Human edited draft, pending grounding review.');
  await page.getByRole('button',{name:'Save revision'}).click();
  await expect(page.getByRole('status').filter({hasText:/Human edits require a new grounding review/})).toBeVisible();
  await expect(page.getByText('Revision: 2',{exact:true})).toBeVisible();
  await page.reload();
  await expect(page.getByRole('textbox',{name:'Body',exact:true})).toContainText('Human edited draft, pending grounding review.');
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
  await expect(page.getByRole('heading',{name:'草稿',exact:true,level:1})).toBeVisible();
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:'test-results/t24-draft-zh-mobile-fixture.png',fullPage:true});
});
