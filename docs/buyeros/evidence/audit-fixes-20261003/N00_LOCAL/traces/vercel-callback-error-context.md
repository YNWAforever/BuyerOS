# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-neon-compat.spec.ts >> NA01 fixture: callback response preserves host cookies and redirect
- Location: tests\e2e\audit-neon-compat.spec.ts:19:1

# Error details

```
Error: expect(received).toBe(expected) // Object.is equality

Expected: 302
Received: 200
```

# Test source

```ts
  1  | import {test,expect} from '@playwright/test';
  2  | import {assertProtocolStorage} from '../../scripts/neon-compatibility-harness.mjs';
  3  | test('NA01 fixture: official handler/client, server session, bearer verification, reload and logout',async({page,context})=>{
  4  |  await page.route('**/*',route=>['localhost','127.0.0.1'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort());
  5  |  await page.goto('/compat');await expect(page.getByTestId('server-session')).toHaveText('anonymous');
  6  |  await page.getByRole('button',{name:'Fixture login'}).click();await expect(page.getByTestId('client-status')).toHaveText('signed-in');
  7  |  const cookies=await context.cookies();const token=cookies.find(c=>c.name==='__Secure-neon-auth.session_token');
  8  |  expect(token).toBeDefined();expect(token?.httpOnly).toBe(true);expect(token?.secure).toBe(true);expect(token?.sameSite).toBe('Lax');expect(token?.domain).toBe('localhost');
  9  |  expect(cookies.some(c=>c.name==='__Secure-neon-auth.local.session_data')).toBe(true);
  10 |  await page.getByRole('button',{name:'Session',exact:true}).click();await expect(page.getByTestId('client-status')).toHaveText('n00-user');
  11 |  await page.reload();await expect(page.getByTestId('server-session')).toHaveText('n00-user');
  12 |  await page.getByRole('button',{name:'Verify token'}).click();await expect(page.getByTestId('client-status')).toHaveText('api-verified');
  13 |  assertProtocolStorage(await page.evaluate(()=>Object.entries(localStorage))); expect(await page.evaluate(()=>Object.keys(sessionStorage))).toEqual([]);
  14 |  await page.screenshot({path:`test-results/neon-compatibility/${process.env.BUYEROS_N00_TARGET}-signed-in.png`});
  15 |  await page.getByRole('button',{name:'Logout'}).click();await expect(page.getByTestId('client-status')).toHaveText('signed-out');
  16 |  await page.reload();await expect(page.getByTestId('server-session')).toHaveText('anonymous');
  17 |  expect((await context.cookies()).filter(c=>c.name.startsWith('__Secure-neon-auth'))).toEqual([]);
  18 | });
  19 | test('NA01 fixture: callback response preserves host cookies and redirect',async({page,request})=>{
  20 |  const upstream=await request.get('http://127.0.0.1:44891/fixture/auth/callback/fixture?state=fictional-state',{maxRedirects:0});expect(upstream.status()).toBe(302);expect(upstream.headers()['set-cookie']).toContain('HttpOnly');
> 21 |  const callback=await request.get('/api/auth/callback/fixture?state=fictional-state',{maxRedirects:0});expect(callback.status()).toBe(302);
     |                                                                                                                                  ^ Error: expect(received).toBe(expected) // Object.is equality
  22 |  await page.goto('/api/auth/callback/fixture?state=fictional-state');await expect(page).toHaveURL(/\/compat$/);
  23 |  await expect(page.getByTestId('server-session')).toHaveText('n00-user');
  24 | });
  25 | test('NA01 fixture: tokens require exact issuer/audience/algorithm, expiry and known key',async({request})=>{
  26 |  expect((await request.get('http://127.0.0.1:44892/verify')).status()).toBe(401);
  27 |  for(const kind of ['wrong-issuer','wrong-audience','expired','unknown-kid','wrong-algorithm']){
  28 |   const result=await request.get(`http://127.0.0.1:44891/fixture-token?kind=${kind}`);const {token}=await result.json();
  29 |   expect((await request.get('http://127.0.0.1:44892/verify',{headers:{Authorization:`Bearer ${token}`}})).status()).toBe(401);
  30 |  }
  31 | });
  32 | 
```