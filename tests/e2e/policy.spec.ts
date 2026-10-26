import {expect,test,type Page} from '@playwright/test';
import {installNeonFixture} from './fixtures/neon-sign-in';

const workspace='e0000000-0000-4000-8000-000000000001';
const project='e1000000-0000-4000-8000-000000000001';
async function signIn(page:Page,subject:'fixture-admin'|'fixture-viewer'='fixture-admin'){
  const auth=await installNeonFixture(page,{accessToken:subject});
  await page.goto(`/app/settings?workspace=${workspace}&project=${project}`);
  await auth.signIn();
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue(project);
}

test('T10 live policy settings block permit activation and manage a domain suppression',async({page})=>{
  test.setTimeout(240_000);
  await signIn(page,'fixture-admin');
  await expect(page.getByRole('heading',{name:'Policy and suppression'})).toBeVisible();
  await expect(page.getByText('Permitted decisions cannot be activated here.')).toBeVisible();
  await expect(page.getByRole('option',{name:'permitted'})).toHaveCount(0);
  const policy=page.getByRole('region',{name:'Policy and suppression',exact:true});
  await policy.getByRole('textbox',{name:'Policy version',exact:true}).fill('fixture-policy-v1');
  await policy.getByRole('textbox',{name:'Basis reference',exact:true}).fill('Fixture controller review pending');
  await policy.getByRole('textbox',{name:'Provenance',exact:true}).fill('Fixture staff decision');
  await policy.getByLabel('Expiry',{exact:true}).fill('2030-01-01T12:00');
  await policy.getByRole('button',{name:'Record policy',exact:true}).click();
  await expect(policy.getByRole('status').filter({hasText:'Policy recorded.'})).toBeVisible();
  await expect(policy.getByRole('heading',{name:/Policy history/})).toContainText('(1)');
  await policy.getByRole('textbox',{name:'Domain',exact:true}).fill('FIXTURE-01.EXAMPLE.TEST.');
  await policy.getByRole('textbox',{name:'Reason',exact:true}).fill('Fixture controller stop');
  await policy.getByRole('button',{name:'Add suppression',exact:true}).click();
  await expect(policy.getByRole('status').filter({hasText:'Suppression added.'})).toBeVisible();
  await expect(policy.getByRole('heading',{name:/Suppression history/})).toContainText('(1)');
  await expect(policy.getByText('fixture-01.example.test')).toBeVisible();
  await policy.getByRole('textbox',{name:'Reason',exact:true}).fill('Fixture removal after review');
  await policy.getByRole('button',{name:'Remove with reason above',exact:true}).click();
  await expect(policy.getByRole('status').filter({hasText:'Suppression removed.'})).toBeVisible();
  await expect(policy.getByText('Removed',{exact:true})).toBeVisible();
  await page.getByRole('combobox',{name:'Language'}).selectOption('zh-HK');
  await expect(page.getByRole('heading',{name:'政策與拒絕清單'})).toBeVisible();
  await expect(page.getByRole('status').filter({hasText:'拒絕紀錄已移除'})).toBeVisible();
  await page.screenshot({path:'test-results/t10-policy-disposable-db-zhHK.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await expect(page.getByRole('heading',{name:'政策與拒絕清單'})).toBeVisible();
  await page.screenshot({path:'test-results/t10-policy-disposable-db-mobile-zhHK.png',fullPage:true});
});

test('T10 viewer sees the policy next step without admin records or write controls',async({page})=>{
  test.setTimeout(180_000);
  await signIn(page,'fixture-viewer');
  await expect(page.getByRole('heading',{name:'Policy and suppression'})).toBeVisible();
  await expect(page.getByRole('alert').filter({hasText:'Your role cannot view policy records'})).toBeVisible();
  await expect(page.getByRole('button',{name:'Record policy'})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Add suppression'})).toHaveCount(0);
});
