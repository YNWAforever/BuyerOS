import {test,expect} from '@playwright/test';
import {assertProtocolStorage} from '../../scripts/neon-compatibility-harness.mjs';
test('NA01 fixture: official handler/client, server session, bearer verification, reload and logout',async({page,context})=>{
 await page.route('**/*',route=>['localhost','127.0.0.1'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort());
 await page.goto('/compat');await expect(page.getByTestId('server-session')).toHaveText('anonymous');
 await page.getByRole('button',{name:'Fixture login'}).click();await expect(page.getByTestId('client-status')).toHaveText('signed-in');
 const cookies=await context.cookies();const token=cookies.find(c=>c.name==='__Secure-neon-auth.session_token');
 expect(token).toBeDefined();expect(token?.httpOnly).toBe(true);expect(token?.secure).toBe(true);expect(token?.sameSite).toBe('Lax');expect(token?.domain).toBe('localhost');
 expect(cookies.some(c=>c.name==='__Secure-neon-auth.local.session_data')).toBe(true);
 await page.getByRole('button',{name:'Session',exact:true}).click();await expect(page.getByTestId('client-status')).toHaveText('n00-user');
 await page.reload();await expect(page.getByTestId('server-session')).toHaveText('n00-user');
 await page.getByRole('button',{name:'Verify token'}).click();await expect(page.getByTestId('client-status')).toHaveText('api-verified');
 assertProtocolStorage(await page.evaluate(()=>Object.entries(localStorage))); expect(await page.evaluate(()=>Object.keys(sessionStorage))).toEqual([]);
 await page.screenshot({path:`test-results/neon-compatibility/${process.env.BUYEROS_N00_TARGET}-signed-in.png`});
 await page.getByRole('button',{name:'Logout'}).click();await expect(page.getByTestId('client-status')).toHaveText('signed-out');
 await page.reload();await expect(page.getByTestId('server-session')).toHaveText('anonymous');
 expect((await context.cookies()).filter(c=>c.name.startsWith('__Secure-neon-auth'))).toEqual([]);
});
test('NA01 fixture: callback response preserves host cookies and redirect',async({page,request})=>{
 const upstream=await request.get('http://127.0.0.1:44891/fixture/auth/callback/fixture?state=fictional-state',{maxRedirects:0});expect(upstream.status()).toBe(302);expect(upstream.headers()['set-cookie']).toContain('HttpOnly');
 const callback=await request.get('/api/auth/callback/fixture?state=fictional-state',{maxRedirects:0});expect(callback.status()).toBe(302);
 await page.goto('/api/auth/callback/fixture?state=fictional-state');await expect(page).toHaveURL(/\/compat$/);
 await expect(page.getByTestId('server-session')).toHaveText('n00-user');
});
test('NA01 fixture: tokens require exact issuer/audience/algorithm, expiry and known key',async({request})=>{
 expect((await request.get('http://127.0.0.1:44892/verify')).status()).toBe(401);
 for(const kind of ['wrong-issuer','wrong-audience','expired','unknown-kid','wrong-algorithm']){
  const result=await request.get(`http://127.0.0.1:44891/fixture-token?kind=${kind}`);const {token}=await result.json();
  expect((await request.get('http://127.0.0.1:44892/verify',{headers:{Authorization:`Bearer ${token}`}})).status()).toBe(401);
 }
});


test('NA01 fixture: managed callback exchanges verifier in built middleware and keeps app cookies',async({page,context})=>{
 await page.route('**/*',route=>['localhost','127.0.0.1'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort());
 const start=await context.request.post('/api/auth/sign-in/social',{data:{provider:'google',callbackURL:'http://localhost:44890/compat/return?keep=fixture'},headers:{Origin:'http://localhost:44890'}});
 expect(start.status()).toBe(200);
 const data=await start.json();expect(data.redirect).toBe(true);
 const providerURL=new URL(data.url);expect(providerURL.origin).toBe('http://127.0.0.1:44891');expect(providerURL.pathname).toBe('/fixture/auth/callback/google');
 const challenge=(await context.cookies()).find(c=>c.name==='__Secure-neon-auth.session_challenge');
 expect(challenge).toBeDefined();expect(challenge?.domain).toBe('localhost');expect(challenge?.httpOnly).toBe(true);expect(challenge?.secure).toBe(true);expect(challenge?.sameSite).toBe('Lax');
 expect((await context.cookies()).some(c=>c.name==='__Secure-neon-auth.session_token')).toBe(false);
 const provider=await context.request.get(providerURL.href,{maxRedirects:0});expect(provider.status()).toBe(302);
 const callbackURL=new URL(provider.headers().location);expect(callbackURL.origin).toBe('http://localhost:44890');expect(callbackURL.pathname).toBe('/compat/return');expect(callbackURL.searchParams.get('keep')).toBe('fixture');expect(callbackURL.searchParams.get('neon_auth_session_verifier')).toBeTruthy();
 const callback=await context.request.get(callbackURL.href,{maxRedirects:0});expect(callback.status()).toBe(307);
 expect(new URL(callback.headers().location,callbackURL.href).href).toBe('http://localhost:44890/compat/return?keep=fixture');
 const cookies=await context.cookies();const session=cookies.find(c=>c.name==='__Secure-neon-auth.session_token');
 expect(session?.domain).toBe('localhost');expect(session?.httpOnly).toBe(true);expect(session?.secure).toBe(true);expect(session?.sameSite).toBe('Lax');
 expect(cookies.some(c=>c.name==='__Secure-neon-auth.local.session_data')).toBe(true);expect(cookies.some(c=>c.name==='__Secure-neon-auth.session_challenge')).toBe(false);
 await page.goto(callback.headers().location);await expect(page.getByTestId('server-session')).toHaveText('n00-user');
 await page.reload();await expect(page.getByTestId('server-session')).toHaveText('n00-user');
 await page.getByRole('button',{name:'Verify token'}).click();await expect(page.getByTestId('client-status')).toHaveText('api-verified');
 assertProtocolStorage(await page.evaluate(()=>Object.entries(localStorage)));expect(await page.evaluate(()=>Object.keys(sessionStorage))).toEqual([]);
 // A consumed verifier must not mint a session in a different browser context.
 const replay=await context.browser()!.newContext({baseURL:'http://localhost:44890'});
 try{
  await replay.addCookies([challenge!]);
  const rejected=await replay.request.get(callbackURL.href,{maxRedirects:0});expect(rejected.status()).toBe(307);expect(new URL(rejected.headers().location,callbackURL.href).pathname).toBe('/auth/sign-in');
  expect((await replay.cookies()).some(c=>c.name==='__Secure-neon-auth.session_token')).toBe(false);
  expect(await(await replay.request.get('/api/auth/get-session?disableCookieCache=true')).json()).toBeNull();
 }finally{await replay.close();}
 await page.screenshot({path:'test-results/neon-compatibility/'+process.env.BUYEROS_N00_TARGET+'-managed-callback.png'});
 await page.getByRole('button',{name:'Logout'}).click();await expect(page.getByTestId('client-status')).toHaveText('signed-out');
 await page.goto('/compat');await expect(page.getByTestId('server-session')).toHaveText('anonymous');expect((await context.cookies()).filter(c=>c.name.startsWith('__Secure-neon-auth'))).toEqual([]);
 // Also follow the managed redirect in the actual browser with the shared challenge cookie.
 const browserStart=await context.request.post('/api/auth/sign-in/social',{data:{provider:'google',callbackURL:'http://localhost:44890/compat/return?keep=browser'},headers:{Origin:'http://localhost:44890'}});expect(browserStart.status()).toBe(200);
 const browserProvider=new URL((await browserStart.json()).url);expect(browserProvider.origin).toBe('http://127.0.0.1:44891');
 await page.goto(browserProvider.href);await expect(page).toHaveURL('http://localhost:44890/compat/return?keep=browser');await expect(page.getByTestId('server-session')).toHaveText('n00-user');
 await page.getByRole('button',{name:'Logout'}).click();await expect(page.getByTestId('client-status')).toHaveText('signed-out');await page.goto('/compat');await expect(page.getByTestId('server-session')).toHaveText('anonymous');expect((await context.cookies()).filter(c=>c.name.startsWith('__Secure-neon-auth'))).toEqual([]);
});

test('NA01 fixture: missing or mismatched challenge cannot exchange a fresh verifier',async({context})=>{
 const start=await context.request.post('/api/auth/sign-in/social',{data:{provider:'google',callbackURL:'http://localhost:44890/compat/return?keep=negative'},headers:{Origin:'http://localhost:44890'}});expect(start.status()).toBe(200);
 const providerURL=new URL((await start.json()).url);expect(providerURL.origin).toBe('http://127.0.0.1:44891');
 const provider=await context.request.get(providerURL.href,{maxRedirects:0});expect(provider.status()).toBe(302);const callbackURL=provider.headers().location;expect(new URL(callbackURL).origin).toBe('http://localhost:44890');
 const minted=(await context.cookies()).find(c=>c.name==='__Secure-neon-auth.session_challenge');expect(minted).toBeDefined();
 for(const challenge of [null,'fictional-wrong-challenge']){
  const negative=await context.browser()!.newContext({baseURL:'http://localhost:44890'});
  try{
   if(challenge)await negative.addCookies([{...minted!,value:challenge}]);
   const response=await negative.request.get(callbackURL,{maxRedirects:0});expect(response.status()).toBe(307);expect(new URL(response.headers().location,callbackURL).pathname).toBe('/auth/sign-in');
   expect((await negative.cookies()).some(c=>c.name==='__Secure-neon-auth.session_token')).toBe(false);expect(await(await negative.request.get('/api/auth/get-session?disableCookieCache=true')).json()).toBeNull();
  }finally{await negative.close();}
 }
 // Rejected attempts must not consume the owner's challenge/verifier.
 const accepted=await context.request.get(callbackURL,{maxRedirects:0});expect(accepted.status()).toBe(307);expect(new URL(accepted.headers().location,callbackURL).href).toBe('http://localhost:44890/compat/return?keep=negative');
 expect((await context.cookies()).some(c=>c.name==='__Secure-neon-auth.session_token')).toBe(true);
});
