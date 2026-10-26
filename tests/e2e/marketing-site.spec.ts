import {expect, test} from '@playwright/test';

const slugs = ['', '/features', '/how-it-works', '/pricing', '/faq', '/demo', '/privacy', '/terms'];
const locales = ['zh-HK', 'en'];

test('public navigation leads with the workflow and home links to the detailed feature anchors', async ({page}) => {
  await page.setViewportSize({width: 1440, height: 900});
  for (const locale of locales) {
    await page.goto(`/${locale}`);
    await expect(page.locator('.m-desktop-nav a')).toHaveCount(4);
    expect(await page.locator('.m-desktop-nav a').evaluateAll(links => links.map(link => link.getAttribute('href'))))
      .toEqual([`/${locale}/how-it-works`, `/${locale}/features`, `/${locale}/pricing`, `/${locale}/faq`]);
    await expect(page.locator('main .sample-workflow')).toHaveCount(1);
    await expect(page.locator('main #sample .sample-workflow')).toHaveCount(1);
    await expect(page.locator('main .m-faq-list details')).toHaveCount(4);
    expect(await page.locator('main > section[id]').evaluateAll(elements=>elements.map(element=>element.id)))
      .toEqual(['why','sample','capabilities','teams','plans','questions']);
    await expect(page.locator('.m-hero img')).toHaveAttribute('src', `/marketing/product-overview-${locale}.png`);
    const links = page.locator('main a[href*="/features#"]');
    expect(await links.evaluateAll(elements => elements.map(link => link.getAttribute('href'))))
      .toEqual([`/${locale}/features#define`, `/${locale}/features#review`, `/${locale}/features#drafts`]);
    await links.first().click();
    await expect(page).toHaveURL(new RegExp(`/${locale}/features#define$`));
    await expect(page.locator('#define')).toBeVisible();
    await expect(page.locator('#review')).toHaveCount(1);
    await expect(page.locator('#drafts')).toHaveCount(1);
    await expect(page.locator('.m-feature-card')).toHaveCount(6);
    await page.goto(`/${locale}/faq`);
    await expect(page.locator('.m-faq-list details')).toHaveCount(10);
    await expect(page.locator('main .m-faq-group')).toHaveCount(3);
  }
});

test('all sixteen public pages deliver localized SSR without product providers', async ({request}) => {
  const titles = new Set<string>();
  for (const locale of locales) for (const slug of slugs) {
    const path = `/${locale}${slug}`;
    const response = await request.get(path);
    expect(response.status(), path).toBe(200);
    const html = await response.text();
    const head = html.split('</head>')[0];
    expect(html, path).toContain(`<html lang="${locale}"`);
    expect(html, path).toMatch(/<h1\b[^>]*>[^<]{4,}/);
    expect(head, path).toMatch(/name="description" content="[^"]{20,}/);
    expect(head, path).toMatch(/name="robots" content="noindex, nofollow"/);
    expect(html, path).not.toMatch(/WorkspaceSessionProvider|DataModeProvider|synthetic-public-client/);
    const title = html.match(/<title>([^<]+)<\/title>/)?.[1];
    expect(title, path).toContain('BuyerOS');
    expect(titles.has(title!), path).toBe(false); titles.add(title!);
  }
  expect(titles.size).toBe(16);
});

test('public aliases, missing assets and unknown pages preserve routing boundaries', async ({request}) => {
  for (const slug of slugs.slice(1)) {
    const response = await request.get(slug, {maxRedirects: 0});
    expect([307, 308]).toContain(response.status());
    expect(response.headers().location).toBe(`/zh-HK${slug}`);
  }
  for (const path of ['/fr', '/en/unknown', '/zh-HK/unknown', '/unknown/nested', '/marketing-missing.svg']) {
    expect((await request.get(path)).status(), path).toBe(404);
  }
  for (const locale of locales) {
    expect((await request.get(`/${locale}/login`, {maxRedirects: 0})).headers().location).toBe('/app');
    expect((await request.get(`/${locale}/contact`, {maxRedirects: 0})).headers().location).toBe(`/${locale}/demo`);
  }
  const response = await request.get('/api/marketing/leads/challenge');
  expect(response.status()).toBe(503);
  expect((await request.get('/v1/workspaces')).status()).toBe(503);
  expect((await request.get('/api/auth/get-session')).status()).toBe(503);
});

test('language switch keeps each public page and discards private query parameters', async ({page}) => {
  const errors: string[] = [], external: string[] = [], authRequests: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin !== 'http://127.0.0.1:5195') {external.push(url.origin); return route.abort();}
    if (/^\/(api\/auth|v1)\//.test(url.pathname)) authRequests.push(url.pathname);
    return route.continue();
  });
  for (const slug of slugs) {
    await page.goto(`/zh-HK${slug}?workspace=private&token=do-not-copy`);
    await page.locator('header').getByRole('link', {name: 'English', exact: true}).click();
    await expect(page).toHaveURL(`http://127.0.0.1:5195/en${slug}`);
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
    await page.locator('header').getByRole('link', {name: '繁體中文', exact: true}).click();
    await expect(page).toHaveURL(`http://127.0.0.1:5195/zh-HK${slug}`);
  }
  expect(external).toEqual([]); expect(authRequests).toEqual([]); expect(errors).toEqual([]);
});

for (const width of [390, 768, 1440]) test(`both languages and all pages fit ${width}px`, async ({page}) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => {if (message.type() === 'error') errors.push(message.text());});
  await page.setViewportSize({width, height: 900});
  await page.goto('/en');
  const heroStyle = await page.locator('main h1').evaluate(el => {
    const css = getComputedStyle(el);
    return {fontSize: css.fontSize, lineHeight: css.lineHeight, letterSpacing: css.letterSpacing, fontWeight: css.fontWeight};
  });
  const introStyle = await page.locator('.m-hero-intro').evaluate(el => {
    const css = getComputedStyle(el);
    return {fontSize: css.fontSize, lineHeight: css.lineHeight, color: css.color};
  });
  for (const locale of locales) for (const slug of slugs) {
    await page.goto(`/${locale}${slug}`);
    await expect(page.locator('main h1')).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${locale}${slug}`).toBe(true);
    if (slug) {
      expect(await page.locator('main h1').evaluate(el => {
        const css = getComputedStyle(el);
        return {fontSize: css.fontSize, lineHeight: css.lineHeight, letterSpacing: css.letterSpacing, fontWeight: css.fontWeight};
      }), `${locale}${slug}: homepage title scale`).toEqual(heroStyle);
      expect(await page.locator('.m-page-hero .m-hero-intro').evaluate(el => {
        const css = getComputedStyle(el);
        return {fontSize: css.fontSize, lineHeight: css.lineHeight, color: css.color};
      }), `${locale}${slug}: homepage introduction`).toEqual(introStyle);
      if (['/privacy', '/terms', '/faq'].includes(slug)) {
        const hero = await page.locator('.m-page-hero').boundingBox();
        const body = await page.locator(slug === '/faq' ? 'main .m-section.m-faq-section' : '.m-legal').boundingBox();
        expect(hero!.x, `${locale}${slug}: aligned reading column`).toBeCloseTo(body!.x, 0);
      }
    }
    await page.locator('main img').evaluateAll(elements => Promise.all(elements.map(el => {
      const image = el as HTMLImageElement;
      image.loading = 'eager';
      return image.decode();
    })));
    // Hiding the caret mutates input style attributes while streamed React is hydrating.
    await page.screenshot({path: `outputs/marketing-full/${locale}-${slug.slice(1) || 'home'}-${width}.png`, fullPage: true, caret: 'initial'});
  }
  expect(errors).toEqual([]);
});

test('native navigation and FAQ work without JS; keyboard menu and reduced motion remain usable', async ({browser, page}) => {
  const context = await browser.newContext({javaScriptEnabled: false, viewport: {width: 390, height: 844}});
  try {
    const noJS = await context.newPage();
    for (const slug of slugs) {
      await noJS.goto(`http://127.0.0.1:5195/en${slug}`);
      await expect(noJS.locator('main h1')).toBeVisible();
      await noJS.locator('header').getByRole('link', {name: '繁體中文', exact: true}).click();
      await expect(noJS).toHaveURL(`http://127.0.0.1:5195/zh-HK${slug}`);
    }
    await noJS.goto('http://127.0.0.1:5195/en/faq');
    await noJS.locator('main details summary').first().click();
    await expect(noJS.locator('main details').first()).toHaveAttribute('open', '');
  } finally {await context.close();}
  await page.setViewportSize({width: 390, height: 844});
  await page.emulateMedia({reducedMotion: 'reduce'});
  await page.goto('/zh-HK');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', {name: '跳至主要內容'})).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('main')).toBeFocused();
  await page.locator('header details summary').click();
  await expect(page.locator('header details[open]')).toBeVisible();
  await expect(page.locator('header details nav a').first()).toBeVisible();
  expect(await page.locator('.sample-workflow').evaluateAll(elements => elements.map(el => getComputedStyle(el).animationName))).toEqual(['none']);
});

test('demo and legal pages disclose inactive collection and pending publisher values', async ({page}) => {
  await page.goto('/en/demo');
  await expect(page.getByRole('button', {name: 'Send demo request', exact: true})).toBeDisabled();
  await expect(page.locator('.m-form-notice')).toBeVisible();
  for (const slug of ['privacy', 'terms']) {
    await page.goto(`/en/${slug}`);
    await expect(page.locator('main')).toContainText(/draft|review/i);
  }
});

test('crawler endpoints expose public material while keeping preview indexing closed', async ({request}) => {
  const robots = await request.get('/robots.txt');
  expect(robots.status()).toBe(200);
  expect(await robots.text()).toContain('Disallow: /');
  const sitemap = await request.get('/sitemap.xml');
  expect(sitemap.status()).toBe(200);
  expect(await sitemap.text()).not.toMatch(/<loc>.*\/(app|auth|api|v1)/);
  const llms = await request.get('/llms.txt');
  expect(llms.status()).toBe(200);
  expect(await llms.text()).toContain('/zh-HK/features');
  expect(await llms.text()).toContain('/en/features');
});

test('FAQ structured data matches the visible bilingual answers', async ({page}) => {
  for (const locale of locales) for (const slug of ['', '/faq']) {
    await page.goto(`/${locale}${slug}`);
    const faq = await page.locator('script[type="application/ld+json"]').evaluateAll(elements =>
      elements.map(el => JSON.parse(el.textContent!)).find(value => value['@type'] === 'FAQPage'));
    const visible = await page.locator('.m-faq-list details').evaluateAll(elements => elements.map(el => ({
      question: el.querySelector('summary')!.childNodes[1].textContent,
      answer: el.querySelector('div p')!.textContent,
    })));
    expect(faq.mainEntity.map((item: {name: string; acceptedAnswer: {text: string}}) => ({question: item.name, answer: item.acceptedAnswer.text}))).toEqual(visible);
  }
});

test('local CTA and language events contain only public routing fields', async ({page}) => {
  const events: Record<string, string>[] = [];
  await page.exposeFunction('recordMarketingEvent', (detail: Record<string, string>) => events.push(detail));
  await page.addInitScript(() => window.addEventListener('buyeros:marketing', event => {
    const record = (window as unknown as {recordMarketingEvent: (detail: unknown) => void}).recordMarketingEvent;
    record((event as CustomEvent).detail);
  }));
  await page.goto('/en/pricing?token=private-value&email=private@example.test');
  await page.locator('.m-pricing-card [data-marketing-event="cta_click"]').click();
  await expect(page).toHaveURL('http://127.0.0.1:5195/en/demo');
  await page.locator('header [data-marketing-event="locale_change"]').click();
  await expect(page).toHaveURL('http://127.0.0.1:5195/zh-HK/demo');
  expect(events.map(item => item.name)).toEqual(['cta_click', 'locale_change']);
  for (const event of events) expect(Object.keys(event).sort()).toEqual(['locale', 'name', 'path', 'position']);
  expect(JSON.stringify(events)).not.toMatch(/private|token|email|workspace/);
});

test('public heading navigation has one h1 and no skipped levels', async ({page}) => {
  for (const locale of locales) for (const slug of slugs) {
    await page.goto(`/${locale}${slug}`);
    const levels = await page.locator('main :is(h1,h2,h3,h4,h5,h6)').evaluateAll(elements => elements.map(el => Number(el.tagName[1])));
    expect(levels.filter(level => level === 1), `${locale}${slug}`).toHaveLength(1);
    for (let i = 1; i < levels.length; i++) expect(levels[i], `${locale}${slug}: ${levels.join(',')}`).toBeLessThanOrEqual(levels[i-1] + 1);
  }
});

test('only the demo form loads the Tailwind product stylesheet', async ({page}) => {
  for (const locale of locales) for (const slug of slugs) {
    await page.goto(`/${locale}${slug}`);
    const productStyles = await page.evaluate(() => Array.from(document.styleSheets).some(sheet =>
      Array.from(sheet.cssRules).some(rule => rule.cssText.startsWith('@layer utilities'))));
    expect(productStyles, `${locale}${slug}: product stylesheet isolation`).toBe(slug === '/demo');
  }
});
