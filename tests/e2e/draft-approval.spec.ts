import {expect,test} from '@playwright/test';
import {installNeonFixture} from './fixtures/neon-sign-in';

const workspace='e0000000-0000-4000-8000-000000000001';
const project='e1000000-0000-4000-8000-000000000001';
const draft='ec000000-0000-4000-8000-000000000002';

test('T25 reviewer confirms exact draft while delivery stays disabled',async({page,request})=>{
  test.setTimeout(180_000);
  const auth=await installNeonFixture(page,{subject:'reviewer',accessToken:'fixture-reviewer'});
  await page.goto(`/app/outreach?workspace=${workspace}&project=${project}&draft=${draft}`);
  await auth.signIn();
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue(project);
  await expect(page.getByRole('heading',{name:'Exact revision review'})).toBeVisible();
  await expect(page.getByRole('button',{name:'Request exact review'})).toBeVisible();
  await page.getByRole('button',{name:'Request exact review'}).click();
  await expect(page.getByText('recipient@fixture.example.test')).toBeVisible();
  await expect(page.getByRole('region',{name:'Exact revision review'}).getByText(/Fixture Alex/)).toBeVisible();
  const approve=page.getByRole('button',{name:'Approve exact revision'});
  await expect(approve).toBeDisabled();
  await page.getByRole('checkbox',{name:/I confirm the exact recipient/}).check();
  await expect(approve).toBeEnabled();
  await approve.click();
  await expect(page.getByText(/Approval recorded; delivery remains disabled/)).toBeVisible();
  await expect(page.getByText(/approved/).first()).toBeVisible();
  await expect(page.getByRole('button',{name:/^Send(?:\s|$)/i})).toHaveCount(0);
  const counts=await (await request.get('http://127.0.0.1:8000/fixture/approval-counts')).json();
  expect(counts).toEqual({approvals:1,delivery_events:0});
  const denied=await request.post(`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${draft}/deliver`,{
    headers:{Authorization:'Bearer fixture-reviewer','Idempotency-Key':'disabled-delivery-fixture'}});
  expect(denied.status()).toBe(403);
  expect((await denied.json()).code).toBe('DELIVERY_DISABLED');
  const viewer=await request.post(`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${draft}/review`,{
    headers:{Authorization:'Bearer fixture-viewer','Idempotency-Key':'viewer-review-fixture','If-Match':'"3"'},
    data:{revision_id:'ee000000-0000-4000-8000-000000000002',content_hash:'0'.repeat(64),context_hash:'0'.repeat(64)}});
  expect(viewer.status()).toBe(403);
  await page.screenshot({path:'test-results/t25-approval-en-fixture.png',fullPage:true});
  await page.reload();
  await expect(page.getByRole('heading',{name:'Exact revision review'})).toBeVisible();
  await expect(page.getByText(/approved/).first()).toBeVisible();
  await page.locator('header select').selectOption('zh-HK');
  await page.setViewportSize({width:390,height:844});
  await expect(page.getByRole('heading',{name:'精確版本審核'})).toBeVisible();
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:'test-results/t25-approval-zh-mobile-fixture.png',fullPage:true});
  const after=await (await request.get('http://127.0.0.1:8000/fixture/approval-counts')).json();
  expect(after).toEqual({approvals:1,delivery_events:0});
});
