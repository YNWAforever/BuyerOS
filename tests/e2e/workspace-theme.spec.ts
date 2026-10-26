import {expect, test} from '@playwright/test';

const routes = ['/app', '/app/discover', '/app/discover/new', '/app/discover/sample-run',
  '/app/lists', '/app/lists/list-1', '/app/buyers/buyer-1', '/app/buyers/missing-fixture',
  '/app/outreach', '/app/results', '/app/settings'];

test('demo groups use Buyers and Drafts and preserve active parent navigation on deep links', async ({page}) => {
  await page.setViewportSize({width: 1440, height: 900});
  await page.goto('/app/discover/sample-run');
  await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
  const sidebar=page.locator('[data-slot="sidebar"]');
  const discovery=sidebar.getByRole('group',{name:'Discover & review',exact:true});
  await expect(discovery.getByRole('button')).toHaveText(['Buyers','Buyer Lists1']);
  await expect(discovery.getByRole('button',{name:'Buyers',exact:true})).toHaveAttribute('data-active','true');
  await sidebar.getByRole('group',{name:'Follow up',exact:true}).getByRole('button',{name:'Drafts',exact:true}).click();
  await expect.poll(()=>new URL(page.url()).pathname).toBe('/app/outreach');
  await expect(page.locator('.page-heading h1')).toHaveText('Drafts');
  await expect(sidebar.getByRole('button',{name:'Drafts',exact:true})).toHaveAttribute('data-active','true');
  await page.goto('/app/lists/list-1');
  await expect(sidebar.getByRole('button',{name:/^Buyer Lists/})).toHaveAttribute('data-active','true');
  await page.goto('/app/buyers/buyer-1');
  await expect(discovery.getByRole('button',{name:'Buyers',exact:true})).toHaveAttribute('data-active','true');
  await expect(sidebar.getByRole('group',{name:'Manage',exact:true}).getByRole('button',{name:'Settings',exact:true})).toBeVisible();
  await page.getByRole('combobox',{name:'Language',exact:true}).click();
  await page.getByRole('option',{name:'繁體中文',exact:true}).click();
  await expect(sidebar.getByRole('group',{name:'尋找與覆核',exact:true})).toBeVisible();
  await sidebar.getByRole('group',{name:'跟進',exact:true}).getByRole('button',{name:'草稿',exact:true}).click();
  await expect(page.locator('.page-heading h1')).toHaveText('草稿');
  await expect(sidebar.getByRole('group',{name:'管理',exact:true}).getByRole('button',{name:'設定',exact:true})).toBeVisible();
});

test('workspace and sign-in documents remain noindex', async ({request}) => {
  for (const route of [...routes, '/app/discover/edit', '/app/runs', '/app/operations', '/auth/sign-in', '/auth/callback']) {
    const response = await request.get(route);
    expect(response.status(), route).toBe(200);
    expect((await response.text()).split('</head>')[0], route).toMatch(/name="robots" content="noindex, nofollow"/);
  }
});

for (const locale of ['en', 'zh-HK']) for (const width of [390, 768, 1440]) {
  test(`homepage theme and usable workspace controls at ${width}px in ${locale}`, async ({page}) => {
    const external: string[] = [], errors: string[] = [];
    await page.route('**/*', route => {
      const url = new URL(route.request().url());
      if (url.origin !== 'http://127.0.0.1:5197' || /^\/(api|v1)\//.test(url.pathname)) {
        external.push(url.origin + url.pathname);
        return route.abort();
      }
      return route.continue();
    });
    page.on('pageerror', error => errors.push(error.message));
    await page.setViewportSize({width, height: 900});
    await page.goto('/en');
    const homepageButton = page.locator('main .m-button').first();
    const homepage = await homepageButton.evaluate(el => ({
      primary: getComputedStyle(el).backgroundColor,
      font: getComputedStyle(document.body).fontFamily,
      background: getComputedStyle(document.body).backgroundColor,
    }));
    await homepageButton.hover();
    const homepageHover = await homepageButton.evaluate(async el => {
      await Promise.all(el.getAnimations().map(animation => animation.finished));
      return getComputedStyle(el).backgroundColor;
    });
    await page.goto('/app/settings');
    await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
    if (locale === 'zh-HK') {
      await page.getByRole('combobox', {name: 'Language', exact: true}).click();
      await page.getByRole('option', {name: '繁體中文', exact: true}).click();
    }
    for (const route of routes) {
      await page.mouse.move(0, 0);
      await page.goto(route);
      await expect(page.locator('main[data-demo-ready="true"]')).toBeVisible();
      await expect(page.locator('html')).toHaveAttribute('lang', locale);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), route).toBe(true);
      expect(await page.locator('body').evaluate(el => getComputedStyle(el).fontFamily), route).toBe(homepage.font);
      expect(await page.locator('body').evaluate(el => getComputedStyle(el).backgroundColor), route).toBe(homepage.background);
      const primary = page.locator('main [data-slot="button"][data-variant="default"]:visible').first();
      if (await primary.count()) {
        expect(await primary.evaluate(el => getComputedStyle(el).backgroundColor), route).toBe(homepage.primary);
        if (await primary.isEnabled()) {
          await primary.focus();
          expect(await primary.evaluate(el => getComputedStyle(el).outlineStyle), route).toBe('solid');
          await primary.hover();
          await expect(primary, route).toHaveCSS('background-color', homepageHover);
        }
      }
    }
    expect(external).toEqual([]);
    expect(errors).toEqual([]);
  });
}
