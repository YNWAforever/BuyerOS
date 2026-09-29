import { expect, test } from '@playwright/test';

test('demo UI loads beside an isolated Postgres API fixture with fake identity', async ({ page, request }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/BuyerOS/);
  await expect(page.locator('body')).toContainText(/demo mode/i);
  await page.screenshot({ path: 'test-results/t00-demo-fixture.png', fullPage: true });

  const response = await request.get('http://127.0.0.1:8000/v1/workspaces');
  expect(response.status()).toBe(200);
  const body = await response.json();
  expect(body.data_mode).toBe('live');
  expect(body.data.items).toEqual([
    {
      id: 'e0000000-0000-4000-8000-000000000001',
      name: 'E2E fixture workspace',
      roles: ['operator'],
      data_mode: 'live',
    },
  ]);
});
