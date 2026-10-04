# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-neon-runtime-flow.spec.ts >> NA01 runtime flow: browser Google model, managed callback, server/client session, token/API, reload and logout
- Location: tests\e2e\audit-neon-runtime-flow.spec.ts:11:1

# Error details

```
Test timeout of 45000ms exceeded.
```

```
Error: response.json: Test timeout of 45000ms exceeded.
```

# Page snapshot

```yaml
- main [ref=f2e2]:
  - heading "N00 session and token diagnostic" [level=1] [ref=f2e3]
  - paragraph [ref=f2e4]: Protocol experiment only. This subject is not a BuyerOS user ID or workspace role.
  - status [ref=f2e5]: fictional-flow-user
  - status [ref=f2e6]: 2b2cacc622379cde9aca7ca71cd3752e38ccc6e945e70b2411eda84c94b7da67
  - generic [ref=f2e7]:
    - button "Continue with Google" [ref=f2e8]
    - button "Session" [ref=f2e9]
    - button "Verify token" [ref=f2e10]
    - button "Logout" [ref=f2e11]
    - status [ref=f2e12]: api-verified
```

# Test source

```ts
  1  | import {test,expect} from '@playwright/test';
  2  | import {assertProtocolStorage} from '../../scripts/neon-compatibility-harness.mjs';
  3  | test('NA01 runtime flow: real-only diagnostic UI has no build-time Auth configuration',async({page})=>{
  4  |  await page.route('**/*',route=>['localhost','127.0.0.1'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort());
  5  |  await page.goto('/compat');await expect(page.getByRole('heading',{name:'N00 session and token diagnostic'})).toBeVisible();
  6  |  await expect(page.getByTestId('server-session')).toHaveText('anonymous');
  7  |  await expect(page.getByRole('button',{name:'Continue with Google'})).toBeEnabled();
  8  |  assertProtocolStorage(await page.evaluate(()=>Object.entries(localStorage)));
  9  | });
  10 | 
  11 | test('NA01 runtime flow: browser Google model, managed callback, server/client session, token/API, reload and logout',async({page,context},testInfo)=>{
  12 |  await page.route('**/*',route=>['localhost','127.0.0.1'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort());
  13 |  await page.goto('/compat');await expect(page.getByTestId('server-session')).toHaveText('anonymous');
  14 |  await page.getByRole('button',{name:'Continue with Google'}).click();
  15 |  await expect(page).toHaveURL('http://localhost:44890/compat/return');
  16 |  await expect(page.getByTestId('server-session')).toHaveText('fictional-flow-user');
  17 |  const cookies=await context.cookies(),session=cookies.find(v=>v.name==='__Secure-neon-auth.session_token');
  18 |  expect(session).toBeDefined();expect(session?.httpOnly).toBe(true);expect(session?.secure).toBe(true);expect(session?.sameSite).toBe('Lax');expect(session?.domain).toBe('localhost');
  19 |  expect(cookies.some(v=>v.name==='__Secure-neon-auth.local.session_data')).toBe(true);
  20 |  expect(cookies.some(v=>v.name==='__Secure-neon-auth.session_challenge')).toBe(false);
  21 |  await page.getByRole('button',{name:'Session',exact:true}).click();await expect(page.getByTestId('client-status')).toHaveText('fictional-flow-user');
  22 |  await page.reload();await expect(page.getByTestId('server-session')).toHaveText('fictional-flow-user');
  23 |  const apiResponse=page.waitForResponse(r=>r.url().endsWith('/api/n00/verify'));
  24 |  await page.getByRole('button',{name:'Verify token'}).click();const verified=await apiResponse;
> 25 |  expect(verified.status()).toBe(200);expect(await verified.json()).toEqual({subject:'fictional-flow-user',fingerprint:await page.getByTestId('runtime-fingerprint').textContent(),protocol_fixture_only:true,external_verified:false});
     |                                                            ^ Error: response.json: Test timeout of 45000ms exceeded.
  26 |  await expect(page.getByTestId('client-status')).toHaveText('api-verified');
  27 |  assertProtocolStorage(await page.evaluate(()=>Object.entries(localStorage)));expect(await page.evaluate(()=>Object.keys(sessionStorage))).toEqual([]);
  28 |  await page.screenshot({path:testInfo.outputPath('signed-in.png')});
  29 |  await page.getByRole('button',{name:'Logout'}).click();await expect(page.getByTestId('client-status')).toHaveText('signed-out');
  30 |  await page.goto('/compat');await page.reload();await expect(page.getByTestId('server-session')).toHaveText('anonymous');
  31 |  expect((await context.cookies()).filter(v=>v.name.startsWith('__Secure-neon-auth'))).toEqual([]);
  32 | });
  33 | test('NA01 runtime flow: explicit issuer differs from Auth URL; wrong trust/key/algorithm/expiry are refused by FastAPI',async({request})=>{
  34 |  const configuration=await (await request.get('http://127.0.0.1:44901/n00-flow-context')).json();
  35 |  expect(configuration.fixture_only).toBe(true);expect(configuration.external_verified).toBe(false);
  36 |  expect(new URL(configuration.trust.issuer).origin).not.toBe(new URL(configuration.auth_base_url).origin);
  37 |  expect((await request.post('/api/n00/verify',{headers:{Origin:'http://localhost:44890'}})).status()).toBe(401);
  38 |  for(const kind of ['wrong-issuer','wrong-audience','array-audience','expired','unknown-kid','wrong-algorithm']){
  39 |   const token=(await (await request.get('http://127.0.0.1:44891/fixture-token?kind='+kind)).json()).token;
  40 |   const response=await request.post('/api/n00/verify',{headers:{Origin:'http://localhost:44890',Authorization:'Bearer '+token}});
  41 |   expect(response.status(),kind).toBe(401);expect(await response.json()).toEqual({code:'N00_DIAGNOSTIC_TOKEN_REFUSED',external_verified:false});
  42 |  }
  43 | });
  44 | test('NA01 runtime flow: foreign origin refuses before diagnostic/JWKS; each direct SDK upstream request is charged',async({request})=>{
  45 |  const before=await (await request.get('http://127.0.0.1:44891/n00-fixture-budget')).json();
  46 |  expect((await request.post('/api/n00/verify',{headers:{Origin:'https://foreign.invalid',Authorization:'Bearer a.b.c'}})).status()).toBe(403);
  47 |  const middle=await (await request.get('http://127.0.0.1:44891/n00-fixture-budget')).json();expect(middle.reserved).toBe(before.reserved);
  48 |  expect((await request.get('/api/auth/get-session?disableCookieCache=true')).status()).toBe(200);
  49 |  const after=await (await request.get('http://127.0.0.1:44891/n00-fixture-budget')).json();
  50 |  expect(after.reserved).toBe(before.reserved+1);expect(after.forwarded).toBe(before.forwarded+1);expect(after.pending).toBe(0);expect(after.external_requests).toBe(0);
  51 | });
  52 | test('NA01 runtime flow: consumed verifier cannot create a session in a second browser',async({context})=>{
  53 |  const start=await context.request.post('/api/auth/sign-in/social',{data:{provider:'google',callbackURL:'http://localhost:44890/compat/return'},headers:{Origin:'http://localhost:44890'}});
  54 |  expect(start.status()).toBe(200);const challenge=(await context.cookies()).find(v=>v.name==='__Secure-neon-auth.session_challenge');expect(challenge).toBeDefined();
  55 |  const providerURL=new URL((await start.json()).url);expect(providerURL.origin).toBe('http://127.0.0.1:44891');
  56 |  const provider=await context.request.get(providerURL.href,{maxRedirects:0});expect(provider.status()).toBe(302);const callbackURL=provider.headers().location;
  57 |  const owner=await context.request.get(callbackURL,{maxRedirects:0});expect(owner.status()).toBe(307);
  58 |  const replay=await context.browser()!.newContext({baseURL:'http://localhost:44890'});
  59 |  try{await replay.addCookies([challenge!]);const rejected=await replay.request.get(callbackURL,{maxRedirects:0});expect(rejected.status()).toBe(307);expect(new URL(rejected.headers().location,callbackURL).pathname).toBe('/auth/sign-in');expect((await replay.cookies()).some(v=>v.name==='__Secure-neon-auth.session_token')).toBe(false);}
  60 |  finally{await replay.close();await context.request.post('/api/auth/sign-out');}
  61 | });
  62 | 
```