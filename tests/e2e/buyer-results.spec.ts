import {expect,test,type Page} from '@playwright/test';
import {installNeonFixture} from './fixtures/neon-sign-in';
const browserApiOrigin=process.env.BUYEROS_E2E_FRONTEND==='vercel-built'?'http://localhost:5173':'http://127.0.0.1:8000';

const workspace='e0000000-0000-4000-8000-000000000001';
const project='e1000000-0000-4000-8000-000000000001';
async function signIn(page:Page,initialPath=`/app/discover?workspace=${workspace}&project=${project}`){
  const auth=await installNeonFixture(page,{accessToken:'fixture-reviewer'});
  await page.goto(initialPath);await auth.signIn();
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue(project);
}

test('T08 real snapshot pages, selection scope, URL filters and dossier',async({page})=>{
  test.setTimeout(180_000);
  await signIn(page);
  await expect(page.getByText('24 in snapshot')).toBeVisible();
  await expect(page.getByRole('button',{name:'Details'})).toHaveCount(12);
  await page.getByRole('combobox',{name:'Rows per page'}).selectOption('8');
  await expect(page.getByRole('button',{name:'Details'})).toHaveCount(8);
  await page.getByRole('button',{name:'Next page'}).click();
  await expect(page.getByText('Buyer Fixture 09')).toBeVisible();
  await page.getByRole('combobox',{name:'Rows per page'}).selectOption('24');
  await expect(page.getByRole('button',{name:'Details'})).toHaveCount(24);
  await expect(page.getByRole('button',{name:'Next page'})).toBeDisabled();
  await page.getByRole('button',{name:'Select this page'}).click();
  await expect(page.getByText('24 selected explicitly')).toBeVisible();
  await page.getByRole('button',{name:'Select all filtered'}).click();
  await page.getByRole('checkbox',{name:'Select Buyer Fixture 02'}).uncheck();
  await expect(page.getByText('23 selected across this snapshot')).toBeVisible();
  let selection:unknown=null;
  await page.route(`${browserApiOrigin}/v1/workspaces/*/projects/*/buyer-reviews`,async route=>{
    if(route.request().method()==='POST'){selection=(route.request().postDataJSON() as {selection:unknown}).selection;await route.abort('failed');}
    else await route.continue();
  });
  await page.getByRole('textbox',{name:'Review reason'}).fill('Fixture-only selection proof');
  await page.getByRole('button',{name:'Apply review'}).click();
  await expect.poll(()=>selection).toEqual({kind:'snapshot',snapshot_id:expect.any(String),excluded_ids:['e2000000-0000-4000-8000-000000000002']});
  await page.getByRole('textbox',{name:'Search buyers'}).fill('Buyer Fixture 02');
  await page.getByRole('button',{name:'Apply filters'}).click();
  await expect(page.getByText('1 in snapshot')).toBeVisible();
  await expect(page.getByText('0 selected explicitly')).toBeVisible();
  expect(new URL(page.url()).searchParams.get('q')).toBe('Buyer Fixture 02');
  await page.reload();
  await expect(page.getByText('1 in snapshot')).toBeVisible();
  await expect(page.getByRole('textbox',{name:'Search buyers'})).toHaveValue('Buyer Fixture 02');
  await page.getByRole('textbox',{name:'Search buyers'}).fill('');
  await page.getByRole('button',{name:'Apply filters'}).click();
  await expect(page.getByText('24 in snapshot')).toBeVisible();
  await page.getByRole('combobox',{name:'Fit filter'}).selectOption('match');
  await expect(page.getByText('1 in snapshot')).toBeVisible();
  await page.getByRole('combobox',{name:'Fit filter'}).selectOption('');
  await expect(page.getByText('24 in snapshot')).toBeVisible();
  await page.getByRole('button',{name:'Details'}).first().click();
  await expect(page.getByRole('dialog',{name:'Buyer details: Buyer Fixture 01'})).toBeVisible();
  await page.getByRole('tab',{name:'Evidence'}).click();
  await expect(page.getByText('Fixture public catalog lists industrial sensors.')).toBeVisible();
  await expect(page.getByRole('link',{name:'Source'})).toHaveAttribute('href','https://example.test/fictional-buyer-01');
  await page.screenshot({path:'test-results/t08-buyer-dossier-disposable-db.png',fullPage:true});
  await page.getByRole('tab',{name:'Contacts'}).click();
  await expect(page.getByText('Contact research: not_researched')).toBeVisible();
  await page.getByRole('tab',{name:'Activity'}).click();
  await expect(page.getByText('Reason: Fixture review')).toBeVisible();
  await page.getByRole('button',{name:'Next buyer'}).click();
  await expect(page.getByRole('dialog',{name:'Buyer details: Buyer Fixture 02'})).toBeVisible();
  await page.getByRole('tab',{name:'Overview'}).click();
  await expect(page.getByText('Fit: needs_review · stale evidence')).toBeVisible();
  await page.getByRole('tab',{name:'Evidence'}).click();
  await expect(page.getByText('Source unavailable')).toBeVisible();
  await expect(page.getByText(/Requirement: .* · expired$/)).toBeVisible();
  await expect(page.getByRole('link',{name:'Source'})).toHaveCount(0);
  await page.screenshot({path:'test-results/t17-expired-buyer-evidence-fixture.png',fullPage:true});
  await page.getByRole('button',{name:'Previous buyer'}).click();
  await expect(page.getByRole('dialog',{name:'Buyer details: Buyer Fixture 01'})).toBeVisible();
  await page.getByRole('button',{name:'Close details'}).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.screenshot({path:'test-results/t08-buyer-results-disposable-db.png',fullPage:true});
});
