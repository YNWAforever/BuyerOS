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
Received: 500
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
  33 | 
  34 | test('NA01 fixture: managed callback exchanges verifier in built middleware and keeps app cookies',async({page,context})=>{
  35 |  await page.route('**/*',route=>['localhost','127.0.0.1'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort());
  36 |  const start=await context.request.post('/api/auth/sign-in/social',{data:{provider:'google',callbackURL:'http://localhost:44890/compat/return?keep=fixture'},headers:{Origin:'http://localhost:44890'}});
  37 |  expect(start.status()).toBe(200);
  38 |  const data=await start.json();expect(data.redirect).toBe(true);
  39 |  const providerURL=new URL(data.url);expect(providerURL.origin).toBe('http://127.0.0.1:44891');expect(providerURL.pathname).toBe('/fixture/auth/callback/google');
  40 |  const challenge=(await context.cookies()).find(c=>c.name==='__Secure-neon-auth.session_challenge');
  41 |  expect(challenge).toBeDefined();expect(challenge?.domain).toBe('localhost');expect(challenge?.httpOnly).toBe(true);expect(challenge?.secure).toBe(true);expect(challenge?.sameSite).toBe('Lax');
  42 |  expect((await context.cookies()).some(c=>c.name==='__Secure-neon-auth.session_token')).toBe(false);
  43 |  const provider=await context.request.get(providerURL.href,{maxRedirects:0});expect(provider.status()).toBe(302);
  44 |  const callbackURL=new URL(provider.headers().location);expect(callbackURL.origin).toBe('http://localhost:44890');expect(callbackURL.pathname).toBe('/compat/return');expect(callbackURL.searchParams.get('keep')).toBe('fixture');expect(callbackURL.searchParams.get('neon_auth_session_verifier')).toBeTruthy();
  45 |  const callback=await context.request.get(callbackURL.href,{maxRedirects:0});expect(callback.status()).toBe(307);
  46 |  expect(new URL(callback.headers().location,callbackURL.href).href).toBe('http://localhost:44890/compat/return?keep=fixture');
  47 |  const cookies=await context.cookies();const session=cookies.find(c=>c.name==='__Secure-neon-auth.session_token');
  48 |  expect(session?.domain).toBe('localhost');expect(session?.httpOnly).toBe(true);expect(session?.secure).toBe(true);expect(session?.sameSite).toBe('Lax');
  49 |  expect(cookies.some(c=>c.name==='__Secure-neon-auth.local.session_data')).toBe(true);expect(cookies.some(c=>c.name==='__Secure-neon-auth.session_challenge')).toBe(false);
  50 |  await page.goto(callback.headers().location);await expect(page.getByTestId('server-session')).toHaveText('n00-user');
  51 |  await page.reload();await expect(page.getByTestId('server-session')).toHaveText('n00-user');
  52 |  await page.getByRole('button',{name:'Verify token'}).click();await expect(page.getByTestId('client-status')).toHaveText('api-verified');
  53 |  assertProtocolStorage(await page.evaluate(()=>Object.entries(localStorage)));expect(await page.evaluate(()=>Object.keys(sessionStorage))).toEqual([]);
  54 |  // A consumed verifier must not mint a session in a different browser context.
  55 |  const replay=await context.browser()!.newContext({baseURL:'http://localhost:44890'});
  56 |  try{
  57 |   await replay.addCookies([{name:'__Secure-neon-auth.session_challenge',value:challenge!.value,url:'http://localhost:44890',httpOnly:true,secure:true,sameSite:'Lax'}]);
  58 |   const rejected=await replay.request.get(callbackURL.href,{maxRedirects:0});expect(rejected.status()).toBe(307);expect(new URL(rejected.headers().location,callbackURL.href).pathname).toBe('/auth/sign-in');
  59 |   expect((await replay.cookies()).some(c=>c.name==='__Secure-neon-auth.session_token')).toBe(false);
  60 |   expect(await(await replay.request.get('/api/auth/get-session?disableCookieCache=true')).json()).toBeNull();
  61 |  }finally{await replay.close();}
  62 |  await page.screenshot({path:'test-results/neon-compatibility/'+process.env.BUYEROS_N00_TARGET+'-managed-callback.png'});
  63 |  await page.getByRole('button',{name:'Logout'}).click();await expect(page.getByTestId('client-status')).toHaveText('signed-out');
  64 |  await page.goto('/compat');await expect(page.getByTestId('server-session')).toHaveText('anonymous');expect((await context.cookies()).filter(c=>c.name.startsWith('__Secure-neon-auth'))).toEqual([]);
  65 |  // Also follow the managed redirect in the actual browser with the shared challenge cookie.
  66 |  const browserStart=await context.request.post('/api/auth/sign-in/social',{data:{provider:'google',callbackURL:'http://localhost:44890/compat/return?keep=browser'},headers:{Origin:'http://localhost:44890'}});expect(browserStart.status()).toBe(200);
  67 |  const browserProvider=new URL((await browserStart.json()).url);expect(browserProvider.origin).toBe('http://127.0.0.1:44891');
  68 |  await page.goto(browserProvider.href);await expect(page).toHaveURL('http://localhost:44890/compat/return?keep=browser');await expect(page.getByTestId('server-session')).toHaveText('n00-user');
  69 |  await page.getByRole('button',{name:'Logout'}).click();await expect(page.getByTestId('client-status')).toHaveText('signed-out');await page.goto('/compat');await expect(page.getByTestId('server-session')).toHaveText('anonymous');expect((await context.cookies()).filter(c=>c.name.startsWith('__Secure-neon-auth'))).toEqual([]);
  70 | });
  71 | 
  72 | test('NA01 fixture: missing or mismatched challenge cannot exchange a fresh verifier',async({context})=>{
  73 |  const start=await context.request.post('/api/auth/sign-in/social',{data:{provider:'google',callbackURL:'http://localhost:44890/compat/return?keep=negative'},headers:{Origin:'http://localhost:44890'}});expect(start.status()).toBe(200);
  74 |  const providerURL=new URL((await start.json()).url);expect(providerURL.origin).toBe('http://127.0.0.1:44891');
  75 |  const provider=await context.request.get(providerURL.href,{maxRedirects:0});expect(provider.status()).toBe(302);const callbackURL=provider.headers().location;expect(new URL(callbackURL).origin).toBe('http://localhost:44890');
  76 |  for(const challenge of [null,'fictional-wrong-challenge']){
  77 |   const negative=await context.browser()!.newContext({baseURL:'http://localhost:44890'});
  78 |   try{
  79 |    if(challenge)await negative.addCookies([{name:'__Secure-neon-auth.session_challenge',value:challenge,url:'http://localhost:44890',httpOnly:true,secure:true,sameSite:'Lax'}]);
  80 |    const response=await negative.request.get(callbackURL,{maxRedirects:0});expect(response.status()).toBe(307);expect(new URL(response.headers().location,callbackURL).pathname).toBe('/auth/sign-in');
  81 |    expect((await negative.cookies()).some(c=>c.name==='__Secure-neon-auth.session_token')).toBe(false);expect(await(await negative.request.get('/api/auth/get-session?disableCookieCache=true')).json()).toBeNull();
  82 |   }finally{await negative.close();}
  83 |  }
  84 |  // Rejected attempts must not consume the owner's challenge/verifier.
  85 |  const accepted=await context.request.get(callbackURL,{maxRedirects:0});expect(accepted.status()).toBe(307);expect(new URL(accepted.headers().location,callbackURL).href).toBe('http://localhost:44890/compat/return?keep=negative');
  86 |  expect((await context.cookies()).some(c=>c.name==='__Secure-neon-auth.session_token')).toBe(true);
  87 | });
  88 | 
```