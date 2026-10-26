import {expect,test,type Page} from '@playwright/test';
import {installNeonFixture} from './fixtures/neon-sign-in';

const workspace='e0000000-0000-4000-8000-000000000001';
const project='e1000000-0000-4000-8000-000000000001';

async function openContact(page:Page){
  await page.getByRole('button',{name:'Details'}).first().click();
  await page.getByRole('tab',{name:'Contacts'}).click();
  return page.locator('.contact-quote');
}

test('T23 staff can refresh a durable job, recover it after sign-in, and cancel before dispatch',async({page,request})=>{
  test.setTimeout(180_000);
  const auth=await installNeonFixture(page,{accessToken:'fixture-access'});
  await page.goto(`/app/discover?workspace=${workspace}&project=${project}`);
  await auth.signIn();
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue(project);
  let preview=await openContact(page);
  await preview.getByRole('button',{name:'View contact quote'}).click();
  await preview.getByRole('button',{name:'Confirm lookup'}).click();
  await expect(preview.getByText(/Job status: reserved/)).toBeVisible();
  const jobId=new URL(page.url()).searchParams.get('contact_job');
  expect(jobId).toMatch(/^[0-9a-f-]{36}$/);
  await preview.getByRole('button',{name:'Refresh lookup job'}).click();
  await expect(preview.getByText(/Held cost: USD 0.300000/)).toBeVisible();
  await page.screenshot({path:'test-results/t23-job-en-fixture.png',fullPage:true});

  await page.reload();
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue(project);
  preview=await openContact(page);
  await expect(preview.getByText(`Job ID: ${jobId}`)).toBeVisible();
  await preview.getByRole('button',{name:'Cancel lookup job'}).click();
  await expect(preview.getByText(/Job status: cancelled/)).toBeVisible();
  await expect(preview.getByText(/Held cost: USD 0.000000/)).toBeVisible();
  const denied=await request.post(`http://127.0.0.1:8000/v1/workspaces/${workspace}/enrichment-jobs/${jobId}/cancel`,{
    headers:{Authorization:'Bearer fixture-viewer','Idempotency-Key':'viewer-job-cancel',
      'If-Match':'"2"'},data:{reason:'Viewer cannot cancel'},
  });
  expect(denied.status()).toBe(403);
  await page.getByRole('combobox',{name:'Language'}).selectOption('zh-HK');
  await page.setViewportSize({width:390,height:844});
  await expect(preview.getByText(/工作狀態: 已取消/)).toBeVisible();
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:'test-results/t23-job-zh-mobile-fixture.png',fullPage:true});
});
