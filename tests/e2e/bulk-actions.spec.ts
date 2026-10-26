import {expect,test,type Page} from '@playwright/test';
import {installNeonFixture} from './fixtures/neon-sign-in';
import {execFileSync} from 'node:child_process';

const workspace='e0000000-0000-4000-8000-000000000001';
const project='e1000000-0000-4000-8000-000000000001';
async function signIn(page:Page,subject:'fixture-access'|'fixture-viewer'='fixture-access'){
  const auth=await installNeonFixture(page,{accessToken:subject});
  await page.goto(`/app/discover?workspace=${workspace}&project=${project}`);
  await page.getByRole('combobox',{name:/^(Language|語言)$/,exact:true}).selectOption('en');
  await expect(page.locator('html')).toHaveAttribute('lang','en');
  await auth.signIn();
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue(project,{timeout:30_000});
  await expect(page.getByText('101 in snapshot')).toBeVisible({timeout:30_000});
}

test('T11 preview, durable progress, failed-only export, retry and reload',async({page})=>{
  test.setTimeout(360_000);
  await signIn(page);
  await page.getByRole('button',{name:'Select all filtered'}).click();
  await expect(page.getByText('101 selected across this snapshot')).toBeVisible();
  await expect(page.getByRole('region',{name:'Assign buyer owners'})).toContainText('Preview: 101 selected buyers');
  await page.getByRole('textbox',{name:'Assignment reason'}).fill('Fixture team assignment');
  await page.getByRole('checkbox',{name:'Confirm owner assignment'}).check();
  await page.getByRole('button',{name:'Assign selected buyers'}).click();
  await expect(page.getByRole('status').filter({hasText:'101 buyer rows queued'})).toBeVisible();
  await expect(page.getByRole('region',{name:'Bulk job progress'})).toContainText('0 of 101 processed');
  const jobUrl=page.url();
  expect(jobUrl).toContain('bulk_job=');
  const output=execFileSync('uv',['run','--frozen','python','tools/pump_e2e_bulk.py','--make-one-stale'],{
    cwd:'services/worker',encoding:'utf-8',timeout:120_000,
  });
  expect(output).toContain('Committed 3 disposable bulk chunks');
  await page.getByRole('button',{name:'Refresh job'}).click();
  await expect(page.getByRole('region',{name:'Bulk job progress'})).toContainText('completed: 101 of 101 processed');
  await expect(page.getByRole('region',{name:'Bulk job progress'})).toContainText('1 conflicts');
  const download=page.waitForEvent('download');
  await page.getByRole('button',{name:'Export failed IDs and reasons'}).click();
  expect((await download).suggestedFilename()).toMatch(/buyer-job-.*-failed\.csv/);
  await page.reload();
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue(project);
  await expect(page.getByRole('region',{name:'Bulk job progress'})).toContainText('completed: 101 of 101 processed');
  await page.getByRole('button',{name:'Retry failed only with current versions'}).click();
  await expect(page.getByRole('status').filter({hasText:'Retry: 1 updated'})).toBeVisible();
  await page.getByRole('combobox',{name:'Language'}).selectOption('zh-HK');
  await expect(page.locator('html')).toHaveAttribute('lang','zh-HK');
  await expect(page.getByRole('region',{name:'批量工作進度'})).toContainText('已處理 101／101 列');
  await expect(page.getByText('第 1–12 項，共 101 項')).toBeVisible();
  await page.screenshot({path:'test-results/t11-bulk-disposable-db-zhHK.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
  await page.screenshot({path:'test-results/t11-bulk-disposable-db-mobile-zhHK.png',fullPage:true});
});

test('T11 cancellation leaves pending rows unmodified in the disposable UI',async({page})=>{
  test.setTimeout(240_000);
  await signIn(page);
  await page.getByRole('button',{name:'Select all filtered'}).click();
  await page.getByRole('textbox',{name:'Assignment reason'}).fill('Cancel fixture assignment');
  await page.getByRole('checkbox',{name:'Confirm owner assignment'}).check();
  await page.getByRole('button',{name:'Assign selected buyers'}).click();
  await expect(page.getByRole('region',{name:'Bulk job progress'})).toContainText('0 of 101 processed');
  await page.getByRole('button',{name:'Cancel pending rows'}).click();
  await expect(page.getByRole('region',{name:'Bulk job progress'})).toContainText('cancel_requested');
  const output=execFileSync('uv',['run','--frozen','python','tools/pump_e2e_bulk.py'],{
    cwd:'services/worker',encoding:'utf-8',timeout:120_000,
  });
  expect(output).toContain('Committed 3 disposable bulk chunks');
  await page.getByRole('button',{name:'Refresh job'}).click();
  await expect(page.getByRole('region',{name:'Bulk job progress'})).toContainText('cancelled: 101 of 101 processed; 0 updated');
  await expect(page.getByRole('region',{name:'Bulk job progress'})).toContainText('101 cancelled');
  await page.getByRole('button',{name:'Refresh results'}).click();
  await expect(page.getByText('Rows 1–12 of 101')).toBeVisible();
});

test('T11 viewer has no bulk assignment controls',async({page})=>{
  test.setTimeout(240_000);
  await signIn(page,'fixture-viewer');
  await expect(page.getByRole('region',{name:'Assign buyer owners'})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Assign selected buyers'})).toHaveCount(0);
});
