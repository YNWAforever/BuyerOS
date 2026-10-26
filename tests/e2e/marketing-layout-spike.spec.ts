import {expect, test} from '@playwright/test';
import {installNeonFixture} from './fixtures/neon-sign-in';

// Catch public routes inheriting product providers, incorrect SSR language,
// catch-all interception, broken auth/API routes, and cross-root hydration.
test('public language, copy and metadata arrive in SSR without product auth', async ({request}) => {
  for (const [locale, headline, title] of [
    ['zh-HK', '買家名單不少，真正值得跟進的是誰？', 'BuyerOS｜從買家條件到有根據的跟進'],
    ['en', 'Plenty of buyer names. Who deserves a closer look?', 'BuyerOS | From buyer criteria to informed follow-up'],
  ]) {
    const response = await request.get(`/${locale}`);
    expect(response.status()).toBe(200);
    const html = await response.text();
    expect(html).toContain(`<html lang="${locale}"`);
    expect(html).toContain(headline);
    expect(html).toContain(`<title>${title}</title>`);
    expect(html).toMatch(/name="robots" content="noindex, nofollow"/);
    expect(html).not.toMatch(/OWNED_SYNTHETIC_COOKIE_SECRET|WorkspaceSessionProvider|DataModeProvider/);
  }
});

test('public entry redirects and missing routes cannot swallow app or API routes', async ({request}) => {
  for (const [path, target] of [['/', '/zh-HK'], ['/login', '/app']]) {
    const response = await request.get(path, {maxRedirects: 0});
    expect([307, 308]).toContain(response.status());
    expect(response.headers().location).toBe(target);
  }
  for (const path of ['/fr', '/zh-HK/missing', '/missing/nested']) {
    const response = await request.get(path);
    expect(response.status(), path).toBe(404);
    expect(await response.text()).not.toContain('OWNED_SYNTHETIC_COOKIE_SECRET');
  }
  const api = await request.get('/v1/workspaces?offset=2');
  expect(api.status()).toBe(503);
  expect(api.headers()['cache-control']).toBe('private, no-store');
  expect((await api.json()).code).toBe('SERVICE_UNAVAILABLE');
  const auth = await request.get('/api/auth/get-session', {headers: {Origin: 'https://untrusted.example.test'}});
  expect(auth.status()).toBe(403);
  expect(auth.headers()['content-type']).toContain('application/json');
  expect(await auth.text()).not.toContain('<html');
});

test('missing public assets return 404 without breaking subsequent SSR', async ({request}) => {
  // Nitro's fetchable RSC environment has no Node module runner. A duplicate
  // generic RSC middleware must not turn asset fallthrough into a 500.
  const missing = await request.get('/marketing-spike-missing.svg', {headers: {Accept: 'image/svg+xml'}});
  expect(missing.status()).toBe(404);
  const page = await request.get('/en');
  expect(page.status()).toBe(200);
  expect(await page.text()).toContain('Plenty of buyer names. Who deserves a closer look?');
});

test('locale links, CTA and product root transitions hydrate without public auth activity', async ({page}) => {
  const unexpected: string[] = [], errors: string[] = [], publicRequests: string[] = [];
  let onPublic = true;
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.hostname !== '127.0.0.1') {
      unexpected.push(url.origin + url.pathname);
      return route.abort();
    }
    if (onPublic && /^\/(v1|api\/auth)\//.test(url.pathname)) publicRequests.push(url.pathname);
    return route.continue();
  });
  await installNeonFixture(page,{origin:'http://127.0.0.1:5193'});
  await page.goto('/zh-HK');
  await expect(page.getByRole('heading', {level: 1})).toContainText('買家名單不少');
  await page.getByRole('link', {name: 'English', exact: true}).click();
  await expect(page).toHaveURL(/\/en$/);
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await expect(page.getByRole('heading', {level: 1})).toContainText('Plenty of buyer names');
  await page.locator('.m-hero-actions').getByRole('link', {name: 'Request a demo', exact: true}).click();
  await expect(page).toHaveURL(/\/en\/demo$/);
  await expect(page.getByRole('button', {name: 'Send demo request', exact: true})).toBeDisabled();
  onPublic = false;
  await page.locator('.m-login').click();
  await expect(page).toHaveURL(/\/app$/);
  await expect(page.getByRole('button', {name: 'Sign in', exact: true})).toBeVisible();
  await page.goBack(); onPublic = true;
  await expect(page).toHaveURL(/\/en\/demo$/);
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  expect(publicRequests).toEqual([]);
  expect(unexpected).toEqual([]);
  expect(errors).toEqual([]);
});

test('product deep links and callback keep the product provider and recovery path', async ({page}) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('https://**/*', route => route.abort());
  await installNeonFixture(page,{origin:'http://127.0.0.1:5193'});
  await page.goto('/app/settings?workspace=synthetic');
  await expect(page).toHaveURL(/\/app\/settings\?workspace=synthetic$/);
  await expect(page.getByRole('button', {name: 'Sign in', exact: true})).toBeVisible();
  await expect(page.locator('.marketing-shell')).toHaveCount(0);
  await page.goto('/auth/callback?state=synthetic-invalid');
  await expect(page.getByRole('alert')).toHaveText('Sign-in failed. This page is no longer linked to your workspace. Choose Start again, then Sign in.');
  await page.getByRole('link', {name: 'Start again', exact: true}).click();
  await expect(page).toHaveURL(/\/app$/);
  await expect(page.getByRole('button', {name: 'Sign in', exact: true})).toBeVisible();
  expect(errors).toEqual([]);
});

for (const returnPath of ['/app', '/app?spike_return=preserved', '/app/settings?spike_return=preserved']) test(`synthetic Neon email login preserves callback state and return ${returnPath} after public navigation`, async ({page}) => {
  const origin = 'http://127.0.0.1:5193';
  const emailCalls: Array<{email:string;password:string;callbackURL:string}> = [];
  const unexpected: string[] = [], errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin === origin) return route.continue();
    unexpected.push(url.origin + url.pathname); return route.abort();
  });
  const auth=await installNeonFixture(page,{origin,subject:'spike-actor',accessToken:'synthetic-spike-access'});
  page.on('request',request=>{
    if(new URL(request.url()).pathname==='/api/auth/sign-in/email')emailCalls.push(request.postDataJSON());
  });
  await page.route(`${origin}/v1/workspaces?**`, route => {
    expect(route.request().headers().authorization).toBe('Bearer synthetic-spike-access');
    return route.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify({
      data_mode: 'live', request_id: 'synthetic-spike-request', data: {items: [], offset: 0, limit: 100, total: 0},
    })});
  });
  await page.goto('/en');
  await page.locator('.m-login').click();
  await page.goto(returnPath);
  await auth.signIn();
  await expect(page.getByText('No workspace membership. Ask an administrator for access.')).toBeVisible();
  await expect(page).toHaveURL(origin + returnPath);
  expect(emailCalls).toHaveLength(1);
  expect(emailCalls[0].email).toBe('spike-actor@example.test');
  const callback=new URL(emailCalls[0].callbackURL);
  expect(callback.origin).toBe(origin);expect(callback.pathname).toBe('/auth/callback');
  expect(callback.searchParams.get('state')).toMatch(/^[0-9a-f-]{36}$/);
  expect(await page.evaluate(() => location.href + JSON.stringify({...localStorage}) + JSON.stringify({...sessionStorage}))).not.toContain('synthetic-spike-access');
  expect(unexpected).toEqual([]);
  expect(errors).toEqual([]);
});

for (const width of [390, 768, 1440]) test(`public layout fits ${width}px with keyboard and no-JS content`, async ({browser, page}) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => {if (message.type() === 'error') errors.push(message.text());});
  await page.setViewportSize({width, height: 900});
  await page.goto('/zh-HK');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', {name: '跳至主要內容'})).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('main')).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path: `outputs/marketing-spike/zh-HK-${width}.png`, fullPage: true});
  const context = await browser.newContext({javaScriptEnabled: false, viewport: {width, height: 900}});
  try {
    const noJS = await context.newPage();
    await noJS.goto('http://127.0.0.1:5193/en');
    await expect(noJS.getByRole('heading', {level: 1})).toContainText('Plenty of buyer names');
    await noJS.getByRole('link', {name: '繁體中文', exact: true}).click();
    await expect(noJS.locator('html')).toHaveAttribute('lang', 'zh-HK');
  } finally { await context.close(); }
  expect(errors).toEqual([]);
});
