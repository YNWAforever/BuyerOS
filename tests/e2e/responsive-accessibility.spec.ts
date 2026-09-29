import { expect, test } from '@playwright/test';

const widths = [390, 768, 1280, 1440];
const routes = ['/app', '/app/discover', '/app/lists', '/app/outreach', '/app/results', '/app/settings'];

async function expectNoPageOverflow(page: import('@playwright/test').Page) {
  const pixels = await page.evaluate(() =>
    Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)
    - document.documentElement.clientWidth,
  );
  expect(pixels).toBeLessThanOrEqual(1);
}

for (const locale of ['en', 'zh-HK'] as const) {
  test(`fictional demo routes remain usable at four widths in ${locale}`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/app/settings');
    await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
    if (locale === 'zh-HK') {
      await page.getByRole('combobox', { name: 'Language' }).click();
      await page.getByRole('option', { name: '繁體中文' }).click();
      await expect(page.locator('html')).toHaveAttribute('lang', 'zh-HK');
    }
    await page.emulateMedia({ reducedMotion: 'reduce' });
    for (const width of widths) {
      await page.setViewportSize({ width, height: 900 });
      for (const route of routes) {
        await page.goto(route);
        await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
        await expectNoPageOverflow(page);
      }
      if (width === 390 || width === 1440) {
        await page.screenshot({ path: `test-results/t29-demo-${locale}-${width}.png`, fullPage: true });
      }
    }
    await expect(page.locator('html')).toHaveAttribute('lang', locale);
  });
}

test('fictional full buyer route retains dossier and missing-buyer return', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto('/app/discover');
  await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
  const table = page.locator('.results-panel').getByRole('table');
  const name = await table.locator('tbody .company-cell b').first().innerText();
  await table.getByRole('button', { name: 'Open ' + name }).click();
  await expect(page.getByRole('dialog')).toContainText(name);
  await page.getByRole('dialog').getByRole('button', { name: 'Full-page view' }).click();
  await expect(page).toHaveURL(/\/app\/buyers\/[^/]+$/);
  await expect(page.locator('.full-dossier')).toContainText(name);
  await expect(page.locator('.full-dossier').getByRole('button', { name: 'Return to buyers' })).toBeVisible();
  await page.locator('.full-dossier').getByRole('button', { name: 'Return to buyers' }).click();
  await expect(page).toHaveURL(/\/app\/discover$/);
  await page.goto('/app/buyers/missing-fixture');
  await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
  await expect(page.getByText('Buyer not found')).toBeVisible();
  await page.getByRole('button', { name: 'Return to buyers' }).click();
  await expect(page).toHaveURL(/\/app\/discover$/);
});

test('zh-HK full buyer dossier and return remain usable at 390px', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/app/settings');
  await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
  await page.getByRole('combobox', { name: 'Language' }).click();
  await page.getByRole('option', { name: '繁體中文' }).click();
  await page.goto('/app/buyers/buyer-1');
  await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('lang', 'zh-HK');
  await expect(page.locator('.full-dossier')).toContainText('Rheinwerk Controls GmbH');
  await expect(page.locator('.full-dossier textarea')).toHaveAttribute('placeholder', '為團隊加入背景資料…');
  await expectNoPageOverflow(page);
  await page.screenshot({ path: 'artifacts/t29-screenshots/zh-buyer-full-390-post-extraction.png', fullPage: true });
  await page.locator('.full-dossier').getByRole('button', { name: '返回買家頁面' }).click();
  await expect(page).toHaveURL(/\/app\/discover$/);
});

test('fictional buyer drawer returns focus to its trigger', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto('/app/discover');
  await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
  const trigger = page.getByRole('table').getByRole('button', { name: /^Open / }).first();
  await trigger.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toBeHidden();
  await expect(trigger).toBeFocused();
});

for (const locale of ['en', 'zh-HK'] as const) {
  test(`fictional demo reflows at a 200% effective viewport in ${locale}`, async ({ page }) => {
    // A 1440px physical viewport at 200% zoom offers about 720 CSS pixels.
    // The 320px case probes the narrow reflow boundary independently.
    await page.setViewportSize({ width: 720, height: 450 });
    await page.goto('/app/settings');
    await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
    if (locale === 'zh-HK') {
      await page.getByRole('combobox', { name: 'Language' }).click();
      await page.getByRole('option', { name: '繁體中文' }).click();
    }
    for (const width of [720, 320]) {
      await page.setViewportSize({ width, height: 450 });
      for (const route of routes) {
        await page.goto(route);
        await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
        await expectNoPageOverflow(page);
      }
    }
    await expect(page.locator('html')).toHaveAttribute('lang', locale);
  });
}

test('fictional demo interactive controls expose accessible names in both locales', async ({ page }) => {
  const cdp = await page.context().newCDPSession(page);
  for (const locale of ['en', 'zh-HK'] as const) {
    await page.goto('/app/settings');
    await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
    if (locale === 'zh-HK') {
      await page.getByRole('combobox', { name: 'Language' }).click();
      await page.getByRole('option', { name: '繁體中文' }).click();
    }
    for (const width of [390, 1280]) {
      await page.setViewportSize({ width, height: 900 });
      for (const route of routes) {
        await page.goto(route);
        await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
        const tree = await cdp.send('Accessibility.getFullAXTree');
        const unnamed = tree.nodes.filter((node: { ignored?: boolean; role?: { value?: string }; name?: { value?: string } }) =>
          !node.ignored && ['button', 'link', 'textbox', 'combobox', 'checkbox', 'radio'].includes(node.role?.value ?? '')
          && !(node.name?.value ?? '').trim(),
        );
        expect(unnamed.map((node: { nodeId: string; role?: { value?: string } }) =>
          `${node.role?.value}:${node.nodeId}`), `${locale} ${route} at ${width}px has unnamed controls`).toEqual([]);
      }
    }
  }
});

test('fictional sidebar navigation keeps routes and usage action wired', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto('/app');
  await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
  const sidebar = page.locator('.brand-sidebar');
  await sidebar.getByRole('button', { name: 'Find Buyers' }).click();
  await expect(page).toHaveURL(/\/app\/discover$/);
  await sidebar.getByRole('button', { name: /Buyer Lists/ }).click();
  await expect(page).toHaveURL(/\/app\/lists$/);
  await sidebar.getByRole('button', { name: 'Open usage' }).click();
  await expect(page).toHaveURL(/\/app\/results$/);
  await expect(page.getByRole('tab', { name: 'Usage' })).toHaveAttribute('aria-selected', 'true');
});

test('fictional source and connection dialogs retain their context', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto('/app/discover');
  await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
  await page.getByRole('table').getByRole('button', { name: /^Open / }).first().click();
  const buyerSheet = page.locator('.buyer-sheet');
  await buyerSheet.getByRole('tab', { name: 'Evidence' }).click();
  await buyerSheet.locator('.evidence-card').first().click();
  const source = page.locator('.source-dialog');
  await expect(source).toBeVisible();
  await expect(source).toContainText('No source was fetched from the web.');
  await page.keyboard.press('Escape');
  await expect(source).toBeHidden();

  await page.goto('/app/settings');
  await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
  await page.getByRole('button', { name: 'View requirements' }).first().click();
  const connection = page.getByRole('dialog');
  await expect(connection).toContainText('Future backend integration requirements');
  await expect(connection).toContainText('No credentials are collected here.');
});

test('fictional project strip and route heading preserve navigation', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto('/app');
  await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
  await page.locator('.project-select').click();
  const projectDialog = page.getByRole('dialog');
  await expect(projectDialog).toContainText('HarbourSense Instruments');
  await projectDialog.getByRole('button', { name: 'Use sample project' }).click();
  await expect(page).toHaveURL(/\/app\/discover$/);
  await expect(page.locator('.page-heading').getByRole('heading', { name: 'Find Buyers' })).toBeVisible();
  await page.locator('.page-heading').getByRole('button', { name: 'New buyer search' }).click();
  await expect(page).toHaveURL(/\/app\/discover\/new$/);
});

test('zh-HK Results retains manual outcomes and localizes usage labels', async ({ page }) => {
  await page.goto('/app/settings');
  await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
  await page.getByRole('combobox', { name: 'Language' }).click();
  await page.getByRole('option', { name: '繁體中文' }).click();
  await expect(page.locator('.connection').first()).toContainText('\u641c\u5c0b\u670d\u52d9');
  await page.goto('/app/results');
  await expect(page.locator('html')).toHaveAttribute('lang', 'zh-HK');

  const outcome = page.locator('.outcome-row').first();
  await expect(outcome).toBeVisible();
  await outcome.getByRole('combobox', { name: '記錄示範成效' }).click();
  await page.getByRole('option', { name: '會議' }).click();
  await expect(outcome.getByRole('combobox')).toContainText('會議');
  await expect(page.locator('.pipeline')).toContainText('會議');

  await page.getByRole('tab', { name: '用量' }).click();
  await expect(page.locator('.overview-cards').last()).toContainText('示範總費用');
  await expect(page.locator('.overview-cards').last()).toContainText('已預留聯絡人預算');
  await expect(page.locator('.usage-row').first()).toContainText('搜尋');
  await page.setViewportSize({ width: 390, height: 844 });
  await expectNoPageOverflow(page);
  await page.screenshot({ path: 'artifacts/t29-screenshots/zh-results-usage-390-post-extraction.png', fullPage: true });
});

test('demo buyer search and filter boundaries meet measured non-text contrast', async ({ page }) => {
  for (const locale of ['en', 'zh-HK'] as const) {
    await page.goto('/app/settings');
    await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
    if (locale === 'zh-HK') {
      await page.getByRole('combobox', { name: 'Language' }).click();
      await page.getByRole('option', { name: '繁體中文' }).click();
    }
    await page.goto('/app/discover');
    await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
    for (const width of [390, 1280]) {
      await page.setViewportSize({ width, height: 900 });
      const result = await page.evaluate(() => {
        const luminance = (rgb: number[]) => {
          const channel = (value: number) => {
            const x = value / 255;
            return x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4;
          };
          return 0.2126 * channel(rgb[0]) + 0.7152 * channel(rgb[1]) + 0.0722 * channel(rgb[2]);
        };
        const ratio = (rgb: number[]) => (1.05 / (luminance(rgb) + 0.05));
        const selectors = ['.results-panel .searchbox', '.results-panel .desktop-filters .pick'];
        return selectors.flatMap(selector => {
          const element = document.querySelector<HTMLElement>(selector);
          if (!element || !element.getBoundingClientRect().width) return [];
          const style = getComputedStyle(element);
          const channels = style.borderTopColor.match(/[\d.]+/g)?.slice(0, 3).map(Number);
          return [{ selector, border: style.borderTopColor, ratio: channels ? Number(ratio(channels).toFixed(2)) : 0 }];
        });
      });
      expect(result.length, locale + ' ' + width + 'px visible buyer controls').toBeGreaterThanOrEqual(width === 390 ? 1 : 2);
      expect(result.filter(item => item.ratio < 3), locale + ' ' + width + 'px boundary contrast').toEqual([]);
    }
  }
});

test('buyer pagination keeps page selection, bulk save and row-size changes coherent', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto('/app/discover');
  await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
  const table = page.locator('.results-panel').getByRole('table');
  const names = () => table.locator('tbody .company-cell b').allTextContents();
  await expect(table.locator('tbody tr')).toHaveCount(8);
  const firstPage = await names();

  await page.getByRole('link', { name: 'Next page' }).click();
  await expect(page.locator('.table-footer .page-number')).toHaveText('2');
  await expect(table.locator('tbody tr')).toHaveCount(8);
  const secondPage = await names();
  expect(secondPage).not.toEqual(firstPage);
  await expect(page.locator('.table-footer')).toContainText('9–16');
  await page.screenshot({ path: 'artifacts/t29-screenshots/en-buyer-page-2-1280-post-extraction.png', fullPage: true });

  await table.getByRole('checkbox', { name: 'Select current page' }).click();
  const bulk = page.locator('.bulkbar');
  await expect(bulk).toContainText('8 selected');
  await bulk.getByRole('button', { name: 'Save to list' }).click();
  const save = page.getByRole('dialog');
  await save.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(save).toBeHidden();

  await page.locator('.table-footer').getByRole('combobox').click();
  await page.getByRole('option', { name: '24' }).click();
  await expect(table.locator('tbody tr')).toHaveCount(24);
  await expect(page.locator('.table-footer .page-number')).toHaveText('1');
  await expect(page.locator('.table-footer')).toContainText('1–24');
  await page.locator('.brand-sidebar').getByRole('button', { name: /Buyer Lists/ }).click();
  await expect(page).toHaveURL(/\/app\/lists$/);
  await expect(page.locator('.results-panel')).toContainText(secondPage[0]);
  await expectNoPageOverflow(page);
});

test('390px buyer cards support selection and bulk list action without overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/app/discover');
  await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
  await page.getByRole('link', { name: 'Next page' }).click();
  await expect(page.locator('.table-footer .page-number')).toHaveText('2');
  const card = page.locator('.mobile-cards .buyer-card').first();
  await expect(card).toBeVisible();
  const buyerName = await card.locator('b').first().innerText();
  await card.getByRole('checkbox', { name: `Select ${buyerName}` }).click();
  const bulk = page.locator('.bulkbar');
  await expect(bulk).toBeVisible();
  await expectNoPageOverflow(page);
  await bulk.getByRole('button', { name: 'Save to list' }).click();
  const save = page.getByRole('dialog');
  await expect(save).toBeVisible();
  await save.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(save).toBeHidden();
  await page.locator('.topbar [data-sidebar="trigger"]').click();
  await page.locator('[data-sidebar="sidebar"][data-mobile="true"]').getByRole('button', { name: /Buyer Lists/ }).click();
  await expect(page).toHaveURL(/\/app\/lists$/);
  await expect(page.locator('[data-sidebar="sidebar"][data-mobile="true"]')).toBeHidden();
  await expect(page.locator('.mobile-cards')).toContainText(buyerName);
  await expect(page.locator('.results-panel')).toContainText('4 companies');
  await expectNoPageOverflow(page);
  await expect(page.getByText('Saved to list. Duplicate memberships are ignored.')).toBeHidden({ timeout: 10000 });
  await page.screenshot({ path: 'artifacts/t29-screenshots/en-buyer-list-390-post-extraction.png', fullPage: true });
});

test('demo Settings preserves local-save privacy and suppression controls', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/app/settings');
  await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
  await page.getByRole('button', { name: 'Save locally' }).click();
  await expect(page.getByText('Saved. Draft content remains session-only.')).toBeVisible();
  const saved = await page.evaluate(() => JSON.parse(localStorage.getItem('buyeros-demo-v1') || '{}'));
  expect(saved.drafts).toEqual([]);
  expect(saved.companies.every((company: { note: string }) => company.note === '')).toBe(true);
  expect(saved.lists.every((list: { name: string }) => list.name.startsWith('Saved demo list '))).toBe(true);

  await page.getByRole('combobox', { name: 'Company' }).click();
  const buyerName = await page.getByRole('option').nth(1).innerText();
  await page.getByRole('option').nth(1).click();
  await page.getByRole('button', { name: 'Add suppression' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('textbox', { name: 'Reason (required)' }).fill('Fixture privacy review');
  await dialog.getByRole('button', { name: 'Confirm' }).click();
  await expect(dialog).toBeHidden();
  await expect(page.locator('.suppression-row').filter({ hasText: buyerName })).toBeVisible();
  await page.locator('.suppression-row').filter({ hasText: buyerName }).getByRole('button', { name: 'Remove suppression' }).click();
  await dialog.getByRole('textbox', { name: 'Reason (required)' }).fill('Fixture reversal review');
  await dialog.getByRole('button', { name: 'Confirm' }).click();
  await expect(page.locator('.suppression-row').filter({ hasText: buyerName })).toBeHidden();
  await expectNoPageOverflow(page);
});

test('demo contact quote cancel releases reservation and confirm updates buyer', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto('/app/discover');
  await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
  await page.locator('.table-footer').getByRole('combobox').click();
  await page.getByRole('option', { name: '24' }).click();
  const candidate = page.getByRole('table').getByRole('row')
    .filter({ hasText: 'Accepted' }).filter({ hasText: 'Not researched' }).first();
  await expect(candidate).toBeVisible();
  const buyerName = await candidate.locator('.company-cell b').innerText();
  await candidate.getByRole('checkbox').click();
  const bulk = page.locator('.bulkbar');
  await bulk.getByRole('button', { name: 'Find business contacts' }).click();
  const quote = page.getByRole('dialog');
  await expect(quote).toContainText('1 eligible');
  await expect(quote).toContainText('reserved');
  await quote.getByRole('button', { name: 'Cancel' }).click();
  await expect(quote).toBeHidden();

  await bulk.getByRole('button', { name: 'Find business contacts' }).click();
  await expect(quote).toContainText('1 eligible');
  await quote.getByRole('button', { name: 'Confirm sample lookup' }).click();
  await expect(quote).toBeHidden();
  await expect(page.getByRole('table').getByRole('row').filter({ hasText: buyerName })).toContainText(/Provider-marked valid|Catch-all|Unavailable/);
});

test('demo action dialog creates and renames a list', async ({ page }) => {
  await page.goto('/app/lists');
  await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
  await page.getByRole('button', { name: 'Create list' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toContainText('Create list');
  await dialog.getByRole('textbox', { name: 'List name' }).fill('Temporary demo list');
  await dialog.getByRole('button', { name: 'Save' }).click();
  await expect(dialog).toBeHidden();
  await expect(page.locator('.list-strip')).toContainText('Temporary demo list');

  await page.getByRole('button', { name: 'Rename list' }).click();
  await expect(dialog).toContainText('Rename list');
  await dialog.getByRole('textbox', { name: 'List name' }).fill('Renamed demo list');
  await dialog.getByRole('button', { name: 'Save' }).click();
  await expect(dialog).toBeHidden();
  await expect(page.locator('.list-strip')).toContainText('Renamed demo list');
  const renamedList = page.locator('.list-strip button').filter({ hasText: 'Renamed demo list' });
  await renamedList.click();
  await expect(page).toHaveURL(/\/app\/lists\/[^/]+$/);
  await expect(renamedList).toHaveClass(/active/);

});

test('fictional Overview metric cards and project actions keep their routes', async ({ page }) => {
  await page.goto('/app');
  await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
  const metrics = page.locator('.overview-cards .metric-card');
  await expect(metrics).toHaveCount(3);
  await expect(page.locator('.project-card')).toContainText('HarbourSense Instruments');
  await expect(page.getByText('Sample search completed: 26 raw candidates')).toBeVisible();

  await metrics.nth(0).click();
  await expect(page).toHaveURL(/\/app\/discover$/);
  await page.goto('/app');
  await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
  await page.locator('.overview-cards .metric-card').nth(1).click();
  await expect(page).toHaveURL(/\/app\/discover$/);
  await page.goto('/app');
  await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
  await page.locator('.overview-cards .metric-card').nth(2).click();
  await expect(page).toHaveURL(/\/app\/outreach$/);

  await page.goto('/app');
  await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page).toHaveURL(/\/app\/discover\/new$/);
  await page.goto('/app');
  await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
  await page.getByRole('button', { name: 'Continue last search' }).click();
  await expect(page).toHaveURL(/\/app\/discover$/);
});

test('fictional discovery review filter and run history retain callbacks', async ({ page }) => {
  await page.goto('/app/discover');
  await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
  await expect(page.locator('.run-summary')).toContainText('24');
  await expect(page.locator('.dedup')).toContainText('26 raw candidates');
  await page.locator('.table-footer').getByRole('combobox').click();
  await page.getByRole('option', { name: '24' }).click();

  await page.getByRole('button', { name: 'Review matches' }).click();
  await expect(page.locator('.desktop-table tbody tr')).toHaveCount(9);
  await page.locator('.run-history summary').click();
  await page.locator('.run-history button').first().click();
  await expect(page).toHaveURL(/\/app\/discover\/sample-run$/);
  await expect(page.locator('.run-summary')).toBeVisible();
});

test('fictional Outreach draft approval invalidates on edit and cannot send', async ({ page }) => {
  await page.goto('/app/discover');
  await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
  await page.getByRole('table').getByRole('button', { name: /^Open / }).first().click();
  const buyer = page.getByRole('dialog');
  await buyer.getByRole('button', { name: 'Prepare draft' }).click();
  await expect(page).toHaveURL(/\/app\/outreach$/);
  await expect(page.locator('.draft-editor')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Send email' })).toBeDisabled();

  await page.getByRole('button', { name: 'Generate sample draft' }).click();
  await expect(page.getByRole('textbox', { name: 'Subject' })).not.toBeEmpty();
  await expect(page.getByRole('textbox', { name: 'Message' })).not.toBeEmpty();
  await page.getByRole('textbox', { name: 'Sender identity · demo' }).fill('HarbourSense team');
  await page.getByRole('checkbox', { name: 'Jurisdiction / policy reviewed (demo)' }).check();
  await page.getByRole('button', { name: 'Request review' }).click();
  await page.getByRole('button', { name: 'Approve draft' }).click();
  await expect(page.locator('.draft-editor')).toContainText('Approved');

  await page.getByRole('textbox', { name: 'Subject' }).fill('Revised sample subject');
  await expect(page.locator('.draft-editor')).toContainText('Draft');
  await expect(page.getByRole('button', { name: 'Approve draft' })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Send email' })).toBeDisabled();
});
