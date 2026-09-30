import { chromium, expect, test } from '@playwright/test';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { relative, resolve, sep } from 'node:path';
import { signInWorkbench } from './fixtures/workbench-auth';

const fixtureRoot = resolve('test-results/t29-api-actual-zoom');
const baseURL = 'http://localhost:5173';
const sections = [
  { index: 0, path: '/app' },
  { index: 2, path: '/app/discover' },
  { index: 3, path: '/app/results' },
  { index: 5, path: '/app/outreach' },
  { index: 6, path: '/app/settings' },
  { index: 7, path: '/app/operations' },
];

function assertOwned(path: string) {
  const relativePath = relative(fixtureRoot, path);
  if (!relativePath || relativePath === '..' || relativePath.startsWith(`..${sep}`)) {
    throw new Error('Refusing to remove a path outside the API zoom fixture root');
  }
}

for (const locale of ['en', 'zh-HK'] as const) {
  test(`T29 actual Chromium 200% zoom preserves API workbench content in ${locale}`, async () => {
    test.setTimeout(300_000);
    await mkdir(fixtureRoot, { recursive: true });
    const extensionDir = await mkdtemp(resolve(fixtureRoot, 'extension-'));
    const profileDir = await mkdtemp(resolve(fixtureRoot, 'profile-'));
    let context: Awaited<ReturnType<typeof chromium.launchPersistentContext>> | undefined;
    try {
      await writeFile(resolve(extensionDir, 'manifest.json'), JSON.stringify({
        manifest_version: 3,
        name: 'BuyerOS isolated API zoom verification',
        version: '1.0',
        permissions: ['tabs'],
        host_permissions: [`${baseURL}/*`],
        background: { service_worker: 'background.js' },
      }));
      await writeFile(resolve(extensionDir, 'background.js'), 'chrome.runtime.onInstalled.addListener(() => {});');
      context = await chromium.launchPersistentContext(profileDir, {
        channel: 'chromium', headless: true, baseURL,
        viewport: { width: 1440, height: 900 },
        args: [`--disable-extensions-except=${extensionDir}`, `--load-extension=${extensionDir}`],
      });
      const page = context.pages()[0] ?? await context.newPage();
      await signInWorkbench(page);
      await expect(page.locator('header select')).toBeEnabled({ timeout: 30_000 });
      await page.locator('header select').selectOption(locale);
      await expect(page.locator('html')).toHaveAttribute('lang', locale);
      const before = await page.evaluate(() => ({ width: innerWidth, dpr: devicePixelRatio }));
      expect(before).toEqual({ width: 1440, dpr: 1 });

      const worker = context.serviceWorkers()[0]
        ?? await context.waitForEvent('serviceworker', { timeout: 10_000 });
      const { tabId, zoom } = await worker.evaluate(async (siteURL) => {
        const api = (globalThis as unknown as { chrome: { tabs: {
          query: (filter: object) => Promise<Array<{ id?: number; url?: string }>>;
          setZoom: (id: number, factor: number) => Promise<void>;
          getZoom: (id: number) => Promise<number>;
        } } }).chrome;
        const tab = (await api.tabs.query({})).find((item) => item.url?.startsWith(siteURL));
        if (!tab?.id) throw new Error('Isolated workbench tab not found');
        await api.tabs.setZoom(tab.id, 2);
        return { tabId: tab.id, zoom: await api.tabs.getZoom(tab.id) };
      }, baseURL);
      expect(zoom).toBe(2);
      const nav = page.getByRole('navigation', { name: 'BuyerOS sections' });
      const measurements = [];
      for (const section of sections) {
        await nav.getByRole('button').nth(section.index).click();
        await expect.poll(() => new URL(page.url()).pathname).toBe(section.path);
        await expect(page.locator('main')).toBeVisible();
        await expect(page.locator('html')).toHaveAttribute('lang', locale);
        await expect.poll(() => page.evaluate(() => innerWidth)).toBe(720);
        if (section.path === '/app/discover') {
          const buyers = page.getByRole('region', { name: locale === 'en' ? 'Buyer results' : '買家結果' });
          await expect(buyers.getByRole('heading', { name: locale === 'en' ? 'Buyers' : '買家', exact: true }))
            .toBeVisible({ timeout: 30_000 });
          await expect(buyers.getByText(locale === 'en' ? '24 in snapshot' : '24 項快照', { exact: true }))
            .toBeVisible({ timeout: 30_000 });
          await buyers.getByRole('button', { name: locale === 'en' ? 'Next page' : '下一頁', exact: true }).click();
          await expect(buyers.getByText(locale === 'en' ? 'Rows 13–24 of 24' : '第 13–24 項，共 24 項', { exact: true }))
            .toBeVisible({ timeout: 30_000 });
          await expect(buyers.getByText('Buyer Fixture 13', { exact: true })).toBeVisible();
          await expect(buyers.getByText('Buyer Fixture 01', { exact: true })).toHaveCount(0);
          await buyers.getByRole('button', { name: locale === 'en' ? 'Previous page' : '上一頁', exact: true }).click();
          await expect(buyers.getByText(locale === 'en' ? 'Rows 1–12 of 24' : '第 1–12 項，共 24 項', { exact: true }))
            .toBeVisible({ timeout: 30_000 });
          await expect(buyers.getByText('Buyer Fixture 01', { exact: true })).toBeVisible();
          await expect(buyers.getByText('Buyer Fixture 13', { exact: true })).toHaveCount(0);
          await buyers.getByRole('textbox', { name: locale === 'en' ? 'Search buyers' : '搜尋買家', exact: true })
            .fill('Buyer Fixture 24');
          await buyers.getByRole('button', { name: locale === 'en' ? 'Apply filters' : '套用篩選', exact: true }).click();
          await expect(buyers.getByText(locale === 'en' ? '1 in snapshot' : '1 項快照', { exact: true }))
            .toBeVisible({ timeout: 30_000 });
          await expect(buyers.getByText('Buyer Fixture 24', { exact: true })).toBeVisible();
          await buyers.getByRole('button', { name: locale === 'en' ? 'Select this page' : '選取本頁', exact: true }).click();
          await expect(buyers.getByText(locale === 'en' ? '1 selected explicitly' : '已明確選取 1 項', { exact: true }))
            .toBeVisible();
          await buyers.getByRole('textbox', { name: locale === 'en' ? 'Search buyers' : '搜尋買家', exact: true }).fill('');
          await buyers.getByRole('button', { name: locale === 'en' ? 'Apply filters' : '套用篩選', exact: true }).click();
          await expect(buyers.getByText(locale === 'en' ? '24 in snapshot' : '24 項快照', { exact: true }))
            .toBeVisible({ timeout: 30_000 });
          await expect(buyers.getByText(locale === 'en' ? '0 selected explicitly' : '已明確選取 0 項', { exact: true }))
            .toBeVisible();
          await expect(buyers.getByRole('combobox', { name: locale === 'en' ? 'Work queue filter' : '工作佇列篩選' })
            .getByRole('option', { name: locale === 'en' ? 'All' : '全部', exact: true })).toHaveCount(1);
        }
        if (section.path === '/app/results') {
          const usage = page.getByRole('region', { name: locale === 'en' ? 'Usage' : '使用量' });
          await expect(usage).not.toContainText(/Loading usage|載入使用量/, { timeout: 30_000 });
        }
        if (section.path === '/app/operations') {
          const queue = page.getByRole('region', { name: locale === 'en' ? 'Work queue' : '工作佇列' });
          await expect(queue).not.toContainText(/Loading|載入中/, { timeout: 30_000 });
        }
        const metrics = await page.evaluate(() => {
          const visible = (element: Element) => {
            const style = getComputedStyle(element), rect = element.getBoundingClientRect();
            return style.display !== 'none' && style.visibility === 'visible' && rect.width > 0 && rect.height > 0;
          };
          const bounds = [...document.querySelectorAll('header,main,nav')]
            .filter(visible).map((element) => {
              const rect = element.getBoundingClientRect();
              return { tag: element.tagName, left: rect.left, right: rect.right };
            });
          const clippedText = [...document.querySelectorAll('main h1,main h2,main h3,main p,main legend')]
            .filter(visible).filter((element) => element.clientWidth > 0 && element.scrollWidth > element.clientWidth + 1)
            .map((element) => ({ tag: element.tagName, text: element.textContent?.trim().slice(0,100),
              overflow: element.scrollWidth - element.clientWidth }));
          return { css_width: innerWidth, dpr: devicePixelRatio,
            overflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)
              - document.documentElement.clientWidth,
            bounds, clippedText };
        });
        expect(metrics.dpr).toBe(2);
        expect(metrics.overflow, `${locale} ${section.path} page overflow`).toBeLessThanOrEqual(1);
        expect(metrics.bounds.filter(({ left, right }) => left < -1 || right > 721),
          `${locale} ${section.path} workbench outside viewport`).toEqual([]);
        expect(metrics.clippedText, `${locale} ${section.path} clipped text at actual 200% zoom`).toEqual([]);
        const routeZoom = await worker.evaluate(async (id) => {
          const api = (globalThis as unknown as { chrome: { tabs: { getZoom: (id: number) => Promise<number> } } }).chrome;
          return api.tabs.getZoom(id);
        }, tabId);
        expect(routeZoom).toBe(2);
        measurements.push({ route: section.path, zoom: routeZoom, ...metrics });
        if (section.path === '/app/discover' || section.path === '/app/operations') {
          const name = section.path === '/app/discover' ? 'buyers' : 'operations';
          // Chromium fullPage clips half the physical viewport at tabs.setZoom(2).
          // Capture the unscrolled physical viewport; zoomed scroll offsets also
          // distort the headless capture. DOM measurements above cover the route.
          await page.evaluate(() => window.scrollTo(0, 0));
          await expect.poll(() => page.evaluate(() => scrollY)).toBe(0);
          await page.screenshot({ path: `test-results/t29-api-actual-zoom-${locale}-${name}.png`, fullPage: false });
        }
      }
      await writeFile(resolve('test-results', `t29-api-actual-zoom-${locale}.json`), JSON.stringify({
        fixture_only: true, identity: 'fake OIDC reviewer', database: 'disposable PostgreSQL',
        browser: context.browser()?.version() ?? await page.evaluate(() => navigator.userAgent),
        locale, viewport: { width: 1440, height: 900 }, before, measurements,
      }, null, 2));
    } finally {
      if (context) await context.close();
      for (const path of [profileDir, extensionDir]) {
        assertOwned(path);
        await rm(path, { recursive: true, force: true });
      }
    }
  });
}
