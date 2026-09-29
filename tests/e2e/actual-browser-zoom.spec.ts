import { chromium, expect, test } from '@playwright/test';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { relative, resolve, sep } from 'node:path';

const fixtureRoot = resolve('test-results/t29-actual-zoom');
const baseURL = process.env.BUYEROS_RESPONSIVE_BASE_URL ?? 'http://localhost:5173';
const routes = ['/app', '/app/discover', '/app/lists', '/app/outreach', '/app/results', '/app/settings'];

function assertOwned(path: string) {
  const relativePath = relative(fixtureRoot, path);
  if (!relativePath || relativePath === '..' || relativePath.startsWith(`..${sep}`)) {
    throw new Error('Refusing to remove a path outside the zoom fixture root');
  }
}

for (const locale of ['en', 'zh-HK'] as const) {
  test(`actual Chromium 200% tab zoom keeps ${locale} demo routes usable`, async () => {
    test.setTimeout(180_000);
    await mkdir(fixtureRoot, { recursive: true });
    const extensionDir = await mkdtemp(resolve(fixtureRoot, 'extension-'));
    const profileDir = await mkdtemp(resolve(fixtureRoot, 'profile-'));
    let context: Awaited<ReturnType<typeof chromium.launchPersistentContext>> | undefined;
    try {
      await writeFile(resolve(extensionDir, 'manifest.json'), JSON.stringify({
        manifest_version: 3,
        name: 'BuyerOS isolated zoom verification',
        version: '1.0',
        permissions: ['tabs'],
        host_permissions: [`${baseURL}/*`],
        background: { service_worker: 'background.js' },
      }));
      await writeFile(resolve(extensionDir, 'background.js'), 'chrome.runtime.onInstalled.addListener(() => {});');
      context = await chromium.launchPersistentContext(profileDir, {
        channel: 'chromium',
        headless: true,
        viewport: { width: 1440, height: 900 },
        args: [`--disable-extensions-except=${extensionDir}`, `--load-extension=${extensionDir}`],
      });
      const page = context.pages()[0] ?? await context.newPage();
      await page.goto(`${baseURL}/app/settings`);
      await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
      if (locale === 'zh-HK') {
        await page.getByRole('combobox', { name: 'Language' }).click();
        await page.getByRole('option', { name: '繁體中文' }).click();
      }
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
        const tabs = await api.tabs.query({});
        const tab = tabs.find((item) => item.url?.startsWith(siteURL));
        if (!tab?.id) throw new Error('BuyerOS browser tab was not found');
        await api.tabs.setZoom(tab.id, 2);
        return { tabId: tab.id, zoom: await api.tabs.getZoom(tab.id) };
      }, baseURL);
      expect(zoom).toBe(2);

      for (const route of routes) {
        await page.goto(`${baseURL}${route}`);
        await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
        await expect(page.locator('html')).toHaveAttribute('lang', locale);
        await expect.poll(() => page.evaluate(() => innerWidth)).toBe(720);
        const metrics = await page.evaluate(() => ({
          dpr: devicePixelRatio,
          overflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)
            - document.documentElement.clientWidth,
        }));
        expect(metrics.dpr).toBe(2);
        expect(metrics.overflow, `${locale} ${route} horizontal overflow at real 200% zoom`).toBeLessThanOrEqual(1);
        const visibleBounds = await page.evaluate(() => {
          const selectors = ['.content', '.page-heading', '.page-heading p', '.run-summary', '.results-panel', '.filterbar', '.searchbox', '.mobile-cards'];
          return selectors.flatMap((selector) => {
            const element = document.querySelector(selector);
            if (!element || getComputedStyle(element).display === 'none') return [];
            const rect = element.getBoundingClientRect();
            return [{ selector, left: rect.left, right: rect.right }];
          });
        });
        expect(visibleBounds.filter(({ left, right }) => left < -1 || right > 721)).toEqual([]);
        const clippedText = await page.evaluate(() => {
          const selectors = ['.page-heading p', '.run-summary p', '.next-action p', '.buyer-card p'];
          return selectors.flatMap((selector) => [...document.querySelectorAll(selector)]
            .filter((element) => getComputedStyle(element).display !== 'none'
              && element.scrollWidth > element.clientWidth + 1)
            .map((element) => ({ selector, overflow: element.scrollWidth - element.clientWidth })));
        });
        expect(clippedText, `${locale} ${route} clipped visible text at real 200% zoom`).toEqual([]);
        const routeZoom = await worker.evaluate(async (id) => {
          const api = (globalThis as unknown as { chrome: { tabs: { getZoom: (tabId: number) => Promise<number> } } }).chrome;
          return api.tabs.getZoom(id);
        }, tabId);
        expect(routeZoom).toBe(2);
      }
    } finally {
      if (context) await context.close();
      for (const path of [profileDir, extensionDir]) {
        assertOwned(path);
        await rm(path, { recursive: true, force: true });
      }
    }
  });
}
