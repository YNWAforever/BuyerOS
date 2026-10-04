# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-neon-compat.spec.ts >> NA01 fixture: callback response preserves host cookies and redirect
- Location: tests\e2e\audit-neon-compat.spec.ts:18:1

# Error details

```
Error: expect(page).toHaveURL(expected) failed

Expected pattern: /\/compat$/
Received string:  "http://localhost:44890/api/auth/callback/fixture?state=fictional-state"
Timeout: 5000ms

Call log:
  - Expect "toHaveURL" with timeout 5000ms
    14 × locator resolved to <html lang="en">…</html>
       - unexpected value "http://localhost:44890/api/auth/callback/fixture?state=fictional-state"

```

```yaml
- main:
  - text: Language
  - combobox "Language":
    - option "English" [selected]
    - option "繁體中文"
  - status:
    - heading "Initializing sign-in…" [level=1]
- main:
  - heading "N00 fictional compatibility probe" [level=1]
  - status: anonymous
  - button "Fixture login"
  - button "Session"
  - button "Verify token"
  - button "Logout"
  - status: ready
```

# Test source

```ts
  1  | import {test,expect} from '@playwright/test';
  2  | test('NA01 fixture: official handler/client, server session, bearer verification, reload and logout',async({page,context})=>{
  3  |  await page.route('**/*',route=>['localhost','127.0.0.1'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort());
  4  |  await page.goto('/compat');await expect(page.getByTestId('server-session')).toHaveText('anonymous');
  5  |  await page.getByRole('button',{name:'Fixture login'}).click();await expect(page.getByTestId('client-status')).toHaveText('signed-in');
  6  |  const cookies=await context.cookies();const token=cookies.find(c=>c.name==='__Secure-neon-auth.session_token');
  7  |  expect(token).toBeDefined();expect(token?.httpOnly).toBe(true);expect(token?.secure).toBe(true);expect(token?.sameSite).toBe('Lax');expect(token?.domain).toBe('localhost');
  8  |  expect(cookies.some(c=>c.name==='__Secure-neon-auth.local.session_data')).toBe(true);
  9  |  await page.getByRole('button',{name:'Session',exact:true}).click();await expect(page.getByTestId('client-status')).toHaveText('n00-user');
  10 |  await page.reload();await expect(page.getByTestId('server-session')).toHaveText('n00-user');
  11 |  await page.getByRole('button',{name:'Verify token'}).click();await expect(page.getByTestId('client-status')).toHaveText('api-verified');
  12 |  expect(await page.evaluate(()=>Object.keys(localStorage))).toEqual([]);expect(await page.evaluate(()=>Object.keys(sessionStorage))).toEqual([]);
  13 |  await page.screenshot({path:`test-results/neon-compatibility/${process.env.BUYEROS_N00_TARGET}-signed-in.png`});
  14 |  await page.getByRole('button',{name:'Logout'}).click();await expect(page.getByTestId('client-status')).toHaveText('signed-out');
  15 |  await page.reload();await expect(page.getByTestId('server-session')).toHaveText('anonymous');
  16 |  expect((await context.cookies()).filter(c=>c.name.startsWith('__Secure-neon-auth'))).toEqual([]);
  17 | });
  18 | test('NA01 fixture: callback response preserves host cookies and redirect',async({page})=>{
> 19 |  await page.goto('/api/auth/callback/fixture?state=fictional-state');await expect(page).toHaveURL(/\/compat$/);
     |                                                                                         ^ Error: expect(page).toHaveURL(expected) failed
  20 |  await expect(page.getByTestId('server-session')).toHaveText('n00-user');
  21 | });
  22 | test('NA01 fixture: tokens require exact issuer/audience/algorithm, expiry and known key',async({request})=>{
  23 |  expect((await request.get('http://127.0.0.1:44892/verify')).status()).toBe(401);
  24 |  for(const kind of ['wrong-issuer','wrong-audience','expired','unknown-kid','wrong-algorithm']){
  25 |   const result=await request.get(`http://127.0.0.1:44891/fixture-token?kind=${kind}`);const {token}=await result.json();
  26 |   expect((await request.get('http://127.0.0.1:44892/verify',{headers:{Authorization:`Bearer ${token}`}})).status()).toBe(401);
  27 |  }
  28 | });
  29 | 
```