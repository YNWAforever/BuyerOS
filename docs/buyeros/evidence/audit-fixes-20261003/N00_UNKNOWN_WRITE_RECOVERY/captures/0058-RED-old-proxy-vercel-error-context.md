# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-neon-runtime-flow.spec.ts >> NA01 runtime flow: committed sign-out with refused redirect keeps unknown hold through UI retry
- Location: tests\e2e\audit-neon-runtime-flow.spec.ts:64:1

# Error details

```
Error: expect(received).toBe(expected) // Object.is equality

Expected: 1
Received: 0
```

# Page snapshot

```yaml
- main [ref=f1e2]:
  - heading "N00 session and token diagnostic" [level=1] [ref=f1e3]
  - paragraph [ref=f1e4]: Protocol experiment only. This subject is not a BuyerOS user ID or workspace role.
  - status [ref=f1e5]: fictional-flow-user
  - status [ref=f1e6]: 6a9c863059969a92fb42c3bd04e7a377ab02e524e1b966582b08e39ebc111cfb
  - generic [ref=f1e7]:
    - button "Continue with Google" [ref=f1e8]
    - button "Session" [ref=f1e9]
    - button "Verify token" [ref=f1e10]
    - button "Logout" [ref=f1e11]
    - status [ref=f1e12]: request-unknown
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
  25 |  expect(verified.status()).toBe(200);expect(await verified.json()).toEqual({subject:'fictional-flow-user',fingerprint:await page.getByTestId('runtime-fingerprint').textContent(),protocol_fixture_only:true,external_verified:false});
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
  63 | 
  64 | test('NA01 runtime flow: committed sign-out with refused redirect keeps unknown hold through UI retry',async({page,request},testInfo)=>{
  65 |  await page.route('**/*',route=>['localhost','127.0.0.1'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort());
  66 |  await page.goto('/compat');await page.getByRole('button',{name:'Continue with Google'}).click();
  67 |  await expect(page).toHaveURL('http://localhost:44890/compat/return');await expect(page.getByTestId('server-session')).toHaveText('fictional-flow-user');
  68 |  const control='http://127.0.0.1:44901/n00-flow-refuse-sign-out-redirect';
  69 |  expect((await request.post(control,{headers:{'X-N00-Owner':'foreign'}})).status()).toBe(403);
  70 |  const armed=await request.post(control,{headers:{'X-N00-Owner':String(testInfo.config.metadata.n00RunId)}});expect(armed.status()).toBe(200);
  71 |  expect(await armed.json()).toEqual({fixture_only:true,external_verified:false});
  72 |  const before=await(await request.get('http://127.0.0.1:44891/n00-fixture-budget')).json();
  73 |  const first=page.waitForResponse(r=>r.url().endsWith('/api/auth/sign-out'));
  74 |  await page.getByRole('button',{name:'Logout'}).click();expect((await first).status()).toBe(502);await expect(page.getByTestId('client-status')).toHaveText('request-unknown');
  75 |  const middle=await(await request.get('http://127.0.0.1:44891/n00-fixture-budget')).json();
> 76 |  expect(middle.reserved).toBe(before.reserved+1);expect(middle.forwarded).toBe(before.forwarded+1);expect(middle.unknown).toBe(before.unknown+1);expect(middle.pending).toBe(0);
     |                                                                                                                           ^ Error: expect(received).toBe(expected) // Object.is equality
  77 |  const retry=page.waitForResponse(r=>r.url().endsWith('/api/auth/sign-out'));
  78 |  await page.getByRole('button',{name:'Logout'}).click();expect((await retry).status()).toBe(409);await expect(page.getByTestId('client-status')).toHaveText('request-unknown');
  79 |  const after=await(await request.get('http://127.0.0.1:44891/n00-fixture-budget')).json();
  80 |  expect(after.reserved).toBe(middle.reserved+1);expect(after.forwarded).toBe(middle.forwarded);expect(after.unknown).toBe(middle.unknown);expect(after.rejected).toBe(middle.rejected+1);expect(after.external_requests).toBe(0);
  81 |  // A read reconciles the fixture's actual committed sign-out; it never resends it.
  82 |  expect(await(await request.get('/api/auth/get-session?disableCookieCache=true')).json()).toBeNull();
  83 |  assertProtocolStorage(await page.evaluate(()=>Object.entries(localStorage)));expect(await page.evaluate(()=>Object.keys(sessionStorage))).toEqual([]);
  84 |  await page.screenshot({path:testInfo.outputPath('unknown-sign-out-held.png')});
  85 | });
  86 | 
```