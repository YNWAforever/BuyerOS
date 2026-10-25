import {expect, test} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import {writeFileSync} from 'node:fs';

test('local synthetic form becomes available after the actual intake challenge', async ({page}) => {
  await page.goto('/en/demo');
  await expect(page.getByRole('button', {name: 'Send demo request', exact: true})).toBeEnabled();
  await expect(page.locator('.m-form-notice')).toContainText(/synthetic/i);
});

test('enabled intake cannot accept input before JavaScript hydration', async ({browser}) => {
  const context = await browser.newContext({javaScriptEnabled: false});
  try {
    const page = await context.newPage();await page.goto('http://127.0.0.1:5195/en/demo');
    await expect(page.getByRole('button', {name: 'Send demo request', exact: true})).toBeDisabled();
    await expect(page.getByLabel('Work email', {exact: true})).toBeDisabled();
    await expect(page.locator('form')).toHaveAttribute('method', 'post');
  } finally {await context.close();}
});

test('invalid email identifies the field without submitting or suggesting a retry', async ({page}) => {
  const submissions: string[] = [];
  page.on('request', request => {if (request.method() === 'POST' && request.url().endsWith('/api/marketing/leads')) submissions.push(request.url());});
  await page.goto('/en/demo');
  await page.getByLabel('Name', {exact: true}).fill('Synthetic Example');
  await page.getByLabel('Work email', {exact: true}).fill('buyer@bad..test');
  await page.getByRole('checkbox').check();
  await page.getByRole('button', {name: 'Send demo request', exact: true}).click();
  await expect(page.getByLabel('Work email', {exact: true})).toHaveAttribute('aria-invalid', 'true');
  await expect(page.getByLabel('Work email', {exact: true})).toBeFocused();
  expect(submissions).toEqual([]);
});

test('synthetic request persists, reload retains receipt, and an unknown response retries one intent', async ({page}) => {
  const requests: {key: string; payload: string}[] = [];
  const email = `browser-${crypto.randomUUID().slice(0,8)}@example.test`;
  let dropFirst = true;
  await page.route('**/api/marketing/leads', async route => {
    requests.push({key: route.request().headers()['idempotency-key'], payload: route.request().postData() ?? ''});
    if (dropFirst) {dropFirst = false; await route.fetch(); return route.abort('failed');}
    return route.continue();
  });
  await page.goto('/en/demo');
  await page.getByLabel('Name', {exact: true}).fill('Synthetic Example');
  await page.getByLabel('Work email', {exact: true}).fill(email);
  await page.getByLabel(/Company/).fill('Example Company');
  await page.getByLabel(/Which part/).fill('Synthetic browser acceptance only.');
  await page.getByRole('checkbox').check();
  await page.getByRole('button', {name: 'Send demo request', exact: true}).click();
  await expect(page.locator('.m-form-errors')).toBeVisible();
  await expect(page.getByLabel('Work email', {exact: true})).toHaveValue(email);
  await page.getByRole('button', {name: 'Send demo request', exact: true}).click();
  await expect(page.locator('.m-receipt')).toContainText(/synthetic/i);
  const id = (await page.locator('.m-receipt code').innerText()).trim();
  expect(requests).toHaveLength(2); expect(requests[1].key).toBe(requests[0].key);
  const result = JSON.parse(execFileSync('services/api/.venv/bin/python', ['services/api/tools/run_marketing_intake.py', '--readback', process.env.MARKETING_FIXTURE_CONFIG!, '--receipt-id', id], {encoding: 'utf8'}));
  expect(result.count).toBe(1);
  writeFileSync('outputs/marketing-full/browser-receipt-readback.json', JSON.stringify(result,null,2)+'\n');
  await page.screenshot({path: 'outputs/marketing-full/demo-synthetic-receipt.png', fullPage: true});
  await page.reload();
  await expect(page.locator('.m-receipt code')).toHaveText(id);
  expect(await page.evaluate(() => JSON.stringify({...sessionStorage}))).not.toContain(email);
});

for (const status of [409, 429, 503]) test(`intake ${status} preserves values and does not acknowledge success`, async ({page}) => {
  await page.route('**/api/marketing/leads', route => route.fulfill({status, contentType: 'application/json', body: JSON.stringify({code: status === 409 ? 'idempotency_conflict' : status === 429 ? 'rate_limited' : 'intake_unavailable', retryable: status !== 409})}));
  await page.goto('/zh-HK/demo');
  await page.getByLabel('姓名', {exact: true}).fill('合成測試');
  await page.getByLabel('工作電郵', {exact: true}).fill(`error-${status}@example.test`);
  await page.getByRole('checkbox').check();
  await page.getByRole('button', {name: '提交示範申請', exact: true}).click();
  await expect(page.locator('.m-form-errors')).toBeVisible();
  await expect(page.getByLabel('工作電郵', {exact: true})).toHaveValue(`error-${status}@example.test`);
  await expect(page.locator('.m-receipt')).toHaveCount(0);
});
