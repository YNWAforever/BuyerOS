import {expect,test,type Page} from '@playwright/test';
import {signInWorkbench,workspace,project} from './fixtures/workbench-auth';

const buyerId='e2000000-0000-4000-8000-000000000001';
const entry=`/app/discover?workspace=${workspace}&project=${project}`;
const sourceCheckPath=/\/source-checks(?:\?.*)?$/;
const checkRecord={id:'f2000000-0000-4000-8000-000000000001',checked_on:'2026-10-15',grade:'A',
  rationale:'Official catalog confirms UK food import capability.',limitations:null,
  sources:[{title:'Official catalog',url:'https://example.test/catalog'},
    {title:'Unsafe source title',url:'javascript:alert(1)'},
    {title:'Credential source',url:'https://user:secret@example.test/catalog'}],
  recorded_by_user_id:'reviewer',created_at:'2026-10-15T08:00:00Z'};
const envelope=(data:unknown)=>({data_mode:'live',request_id:'source-check-fixture',data});

async function openEvidence(page:Page,actor:'reviewer'|'viewer'='reviewer',locale:'en'|'zh-HK'='en'){
  await signInWorkbench(page,true,actor,entry);
  await page.getByRole('combobox',{name:/^(Language|語言)$/}).selectOption(locale);
  await expect(page.getByRole('button',{name:/^(Details|詳情)$/}).first()).toBeVisible();
  await page.getByRole('button',{name:/^(Details|詳情)$/}).first().click();
  await page.getByRole('tab',{name:/^(Evidence|證據)$/}).click();
  await expect(page.getByRole('tabpanel')).toBeVisible();
  page.setDefaultTimeout(5_000);
}

async function fillSourceCheck(page:Page,rationale='Official sources confirm the company is a UK buyer of Thai rice.'){
  await page.getByLabel('Evidence grade').selectOption('A');
  await page.getByLabel('Match rationale').fill(rationale);
  await page.getByLabel('Source title 1').fill('Official buyer information');
  await page.getByLabel('Source URL 1').fill('https://example.test/buyer');
}

test('test_shows_checks_separately_in_en_and_zh_hk',async({page})=>{
  test.setTimeout(60_000);
  await openEvidence(page,'reviewer','en');
  await expect(page.getByRole('region',{name:'Public source checks'})).toBeVisible();
  await expect(page.getByText('No public source checks recorded.')).toBeVisible();
  await expect(page.getByText('Fixture public catalog lists industrial sensors.')).toBeVisible();

  const chinese=await page.context().newPage();
  await openEvidence(chinese,'reviewer','zh-HK');
  await expect(chinese.getByRole('region',{name:'公開來源查核'})).toBeVisible();
  await expect(chinese.getByText('此買家尚無公開來源查核紀錄。')).toBeVisible();
  await expect(chinese.getByText('Fixture public catalog lists industrial sensors.')).toBeVisible();
});

test('test_source_check_retry_reuses_exact_intent',async({page})=>{
  test.setTimeout(60_000);
  const requests:{url:string;key:string|undefined;body:string|null}[]=[];
  await page.route(sourceCheckPath,async route=>{
    if(route.request().method()!=='POST'){await route.continue();return;}
    requests.push({url:route.request().url(),key:route.request().headers()['idempotency-key'],body:route.request().postData()});
    const saved=await route.fetch();
    if(requests.length===1){
      await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({
        code:'TEMPORARY_UNAVAILABLE',message:'The result is unknown.',request_id:'fixture-uncertain',retryable:true})});
      return;
    }
    await route.fulfill({response:saved});
  });
  await openEvidence(page);
  await fillSourceCheck(page,'The public company register and official product catalog match the buyer profile.');
  await page.getByRole('button',{name:'Save source check'}).click();
  await expect(page.getByRole('alert')).toContainText('result is unknown');
  await expect(page.getByRole('button',{name:'Retry same source check'})).toBeVisible();
  await expect(page.getByLabel('Match rationale')).toBeDisabled();
  await page.getByRole('button',{name:'Retry same source check'}).click();
  await expect(page.getByText('Source check recorded.')).toBeVisible();
  expect(requests).toHaveLength(2);
  expect(requests[0].key).toBeTruthy();
  expect(new URL(requests[0].url).pathname).toBe(`/v1/workspaces/${workspace}/buyers/${buyerId}/source-checks`);
  expect(requests[1]).toEqual(requests[0]);
  await expect(page.getByText('The public company register and official product catalog match the buyer profile.')).toBeVisible();

  await page.getByRole('button',{name:'Close details'}).click();
  await page.getByRole('button',{name:'Details'}).first().click();
  await page.getByRole('tab',{name:'Evidence'}).click();
  await expect(page.getByText('The public company register and official product catalog match the buyer profile.')).toBeVisible();
});

test('test_source_check_load_error_does_not_claim_no_records',async({page})=>{
  test.setTimeout(60_000);
  await page.route(sourceCheckPath,async route=>{
    if(route.request().method()==='GET'){
      await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({
        code:'TEMPORARY_UNAVAILABLE',message:'temporarily unavailable',request_id:'fixture-load-error',retryable:true})});
      return;
    }
    await route.continue();
  });
  await openEvidence(page);
  await expect(page.getByText('Could not load public source checks.')).toBeVisible();
  await expect(page.getByText('No public source checks recorded.')).toHaveCount(0);
});

test('test_source_check_form_requires_edit_and_links_are_safe',async({page})=>{
  test.setTimeout(60_000);
  await page.route(sourceCheckPath,async route=>{
    if(route.request().method()==='GET'){
      await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(envelope({items:[checkRecord],offset:0,limit:100,total:1}))});
      return;
    }
    await route.continue();
  });
  await openEvidence(page,'viewer');
  await expect(page.getByRole('button',{name:'Save source check'})).toHaveCount(0);
  await expect(page.getByLabel('Match rationale')).toHaveCount(0);
  const official=page.getByRole('link',{name:'Official catalog'});
  await expect(official).toHaveAttribute('href','https://example.test/catalog');
  await expect(official).toHaveAttribute('target','_blank');
  await expect(official).toHaveAttribute('rel',/noopener noreferrer/);
  await expect(page.getByRole('link',{name:'Unsafe source title'})).toHaveCount(0);
  await expect(page.getByRole('link',{name:'Credential source'})).toHaveCount(0);
});

test('test_manual_check_keeps_evidence_and_fit_unchanged',async({page})=>{
  test.setTimeout(60_000);
  await openEvidence(page);
  await page.getByRole('tab',{name:'Overview'}).click();
  const fitBefore=await page.getByText(/^Fit:/).innerText();
  const countBefore=await page.getByText(/^Evidence records:/).innerText();
  await page.getByRole('tab',{name:'Evidence'}).click();
  const rationale='Independent official records confirm a UK buyer matching the target product.';
  await fillSourceCheck(page,rationale);
  await page.getByRole('button',{name:'Save source check'}).click();
  await expect(page.getByText('Source check recorded.')).toBeVisible();
  await page.getByRole('tab',{name:'Overview'}).click();
  await expect(page.getByText(/^Fit:/)).toHaveText(fitBefore);
  await expect(page.getByText(/^Evidence records:/)).toHaveText(countBefore);
  await page.getByRole('tab',{name:'Evidence'}).click();
  await expect(page.getByText('Fixture public catalog lists industrial sensors.')).toBeVisible();
  await expect(page.getByText(rationale)).toBeVisible();
});
