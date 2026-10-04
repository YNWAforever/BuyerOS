import {test,expect} from '@playwright/test';
import {assertProtocolStorage} from '../../scripts/neon-compatibility-harness.mjs';
test('NA01 runtime flow: real-only diagnostic UI has no build-time Auth configuration',async({page})=>{
 await page.route('**/*',route=>['localhost','127.0.0.1'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort());
 await page.goto('/compat');await expect(page.getByRole('heading',{name:'N00 session and token diagnostic'})).toBeVisible();
 await expect(page.getByTestId('server-session')).toHaveText('anonymous');
 await expect(page.getByRole('button',{name:'Continue with Google'})).toBeEnabled();
 assertProtocolStorage(await page.evaluate(()=>Object.entries(localStorage)));
});

test('NA01 runtime flow: browser Google model, managed callback, server/client session, token/API, reload and logout',async({page,context},testInfo)=>{
 await page.route('**/*',route=>['localhost','127.0.0.1'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort());
 await page.goto('/compat');await expect(page.getByTestId('server-session')).toHaveText('anonymous');
 await page.getByRole('button',{name:'Continue with Google'}).click();
 await expect(page).toHaveURL('http://localhost:44890/compat/return');
 await expect(page.getByTestId('server-session')).toHaveText('fictional-flow-user');
 const cookies=await context.cookies(),session=cookies.find(v=>v.name==='__Secure-neon-auth.session_token');
 expect(session).toBeDefined();expect(session?.httpOnly).toBe(true);expect(session?.secure).toBe(true);expect(session?.sameSite).toBe('Lax');expect(session?.domain).toBe('localhost');
 expect(cookies.some(v=>v.name==='__Secure-neon-auth.local.session_data')).toBe(true);
 expect(cookies.some(v=>v.name==='__Secure-neon-auth.session_challenge')).toBe(false);
 await page.getByRole('button',{name:'Session',exact:true}).click();await expect(page.getByTestId('client-status')).toHaveText('fictional-flow-user');
 await page.reload();await expect(page.getByTestId('server-session')).toHaveText('fictional-flow-user');
 const apiResponse=page.waitForResponse(r=>r.url().endsWith('/api/n00/verify'));
 await page.getByRole('button',{name:'Verify token'}).click();const verified=await apiResponse;
 expect(verified.status()).toBe(200);expect(await verified.json()).toEqual({subject:'fictional-flow-user',fingerprint:await page.getByTestId('runtime-fingerprint').textContent(),protocol_fixture_only:true,external_verified:false});
 await expect(page.getByTestId('client-status')).toHaveText('api-verified');
 assertProtocolStorage(await page.evaluate(()=>Object.entries(localStorage)));expect(await page.evaluate(()=>Object.keys(sessionStorage))).toEqual([]);
 await page.screenshot({path:testInfo.outputPath('signed-in.png')});
 await page.getByRole('button',{name:'Logout'}).click();await expect(page.getByTestId('client-status')).toHaveText('signed-out');
 await page.goto('/compat');await page.reload();await expect(page.getByTestId('server-session')).toHaveText('anonymous');
 expect((await context.cookies()).filter(v=>v.name.startsWith('__Secure-neon-auth'))).toEqual([]);
});
test('NA01 runtime flow: explicit issuer differs from Auth URL; wrong trust/key/algorithm/expiry are refused by FastAPI',async({request})=>{
 const configuration=await (await request.get('http://127.0.0.1:44901/n00-flow-context')).json();
 expect(configuration.fixture_only).toBe(true);expect(configuration.external_verified).toBe(false);
 expect(new URL(configuration.trust.issuer).origin).not.toBe(new URL(configuration.auth_base_url).origin);
 expect((await request.post('/api/n00/verify',{headers:{Origin:'http://localhost:44890'}})).status()).toBe(401);
 for(const kind of ['wrong-issuer','wrong-audience','array-audience','expired','unknown-kid','wrong-algorithm']){
  const token=(await (await request.get('http://127.0.0.1:44891/fixture-token?kind='+kind)).json()).token;
  const response=await request.post('/api/n00/verify',{headers:{Origin:'http://localhost:44890',Authorization:'Bearer '+token}});
  expect(response.status(),kind).toBe(401);expect(await response.json()).toEqual({code:'N00_DIAGNOSTIC_TOKEN_REFUSED',external_verified:false});
 }
});
test('NA01 runtime flow: foreign origin refuses before diagnostic/JWKS; each direct SDK upstream request is charged',async({request})=>{
 const before=await (await request.get('http://127.0.0.1:44891/n00-fixture-budget')).json();
 expect((await request.post('/api/n00/verify',{headers:{Origin:'https://foreign.invalid',Authorization:'Bearer a.b.c'}})).status()).toBe(403);
 const middle=await (await request.get('http://127.0.0.1:44891/n00-fixture-budget')).json();expect(middle.reserved).toBe(before.reserved);
 expect((await request.get('/api/auth/get-session?disableCookieCache=true')).status()).toBe(200);
 const after=await (await request.get('http://127.0.0.1:44891/n00-fixture-budget')).json();
 expect(after.reserved).toBe(before.reserved+1);expect(after.forwarded).toBe(before.forwarded+1);expect(after.pending).toBe(0);expect(after.external_requests).toBe(0);
});
test('NA01 runtime flow: consumed verifier cannot create a session in a second browser',async({context})=>{
 const start=await context.request.post('/api/auth/sign-in/social',{data:{provider:'google',callbackURL:'http://localhost:44890/compat/return'},headers:{Origin:'http://localhost:44890'}});
 expect(start.status()).toBe(200);const challenge=(await context.cookies()).find(v=>v.name==='__Secure-neon-auth.session_challenge');expect(challenge).toBeDefined();
 const providerURL=new URL((await start.json()).url);expect(providerURL.origin).toBe('http://127.0.0.1:44891');
 const provider=await context.request.get(providerURL.href,{maxRedirects:0});expect(provider.status()).toBe(302);const callbackURL=provider.headers().location;
 const owner=await context.request.get(callbackURL,{maxRedirects:0});expect(owner.status()).toBe(307);
 const replay=await context.browser()!.newContext({baseURL:'http://localhost:44890'});
 try{await replay.addCookies([challenge!]);const rejected=await replay.request.get(callbackURL,{maxRedirects:0});expect(rejected.status()).toBe(307);expect(new URL(rejected.headers().location,callbackURL).pathname).toBe('/auth/sign-in');expect((await replay.cookies()).some(v=>v.name==='__Secure-neon-auth.session_token')).toBe(false);}
 finally{await replay.close();await context.request.post('/api/auth/sign-out');}
});


test('NA01 runtime flow: committed sign-out with refused redirect keeps unknown hold through UI retry',async({page,request},testInfo)=>{
 await page.route('**/*',route=>['localhost','127.0.0.1'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort());
 await page.goto('/compat');await page.getByRole('button',{name:'Continue with Google'}).click();
 await expect(page).toHaveURL('http://localhost:44890/compat/return');await expect(page.getByTestId('server-session')).toHaveText('fictional-flow-user');
 const control='http://127.0.0.1:44901/n00-flow-refuse-sign-out-redirect';
 expect((await request.post(control,{headers:{'X-N00-Owner':'foreign'}})).status()).toBe(403);
 const armed=await request.post(control,{headers:{'X-N00-Owner':String(testInfo.config.metadata.n00RunId)}});expect(armed.status()).toBe(200);
 expect(await armed.json()).toEqual({fixture_only:true,external_verified:false});
 const before=await(await request.get('http://127.0.0.1:44891/n00-fixture-budget')).json();
 const first=page.waitForResponse(r=>r.url().endsWith('/api/auth/sign-out'));
 await page.getByRole('button',{name:'Logout'}).click();expect((await first).status()).toBe(502);await expect(page.getByTestId('client-status')).toHaveText('request-unknown');
 const middle=await(await request.get('http://127.0.0.1:44891/n00-fixture-budget')).json();
 expect(middle.reserved).toBe(before.reserved+1);expect(middle.forwarded).toBe(before.forwarded+1);expect(middle.unknown).toBe(before.unknown+1);expect(middle.pending).toBe(0);
 const retry=page.waitForResponse(r=>r.url().endsWith('/api/auth/sign-out'));
 await page.getByRole('button',{name:'Logout'}).click();expect((await retry).status()).toBe(409);await expect(page.getByTestId('client-status')).toHaveText('request-unknown');
 const after=await(await request.get('http://127.0.0.1:44891/n00-fixture-budget')).json();
 expect(after.reserved).toBe(middle.reserved+1);expect(after.forwarded).toBe(middle.forwarded);expect(after.unknown).toBe(middle.unknown);expect(after.rejected).toBe(middle.rejected+1);expect(after.external_requests).toBe(0);
 // A read reconciles the fixture's actual committed sign-out; it never resends it.
 expect(await(await request.get('/api/auth/get-session?disableCookieCache=true')).json()).toBeNull();
 assertProtocolStorage(await page.evaluate(()=>Object.entries(localStorage)));expect(await page.evaluate(()=>Object.keys(sessionStorage))).toEqual([]);
 await page.screenshot({path:testInfo.outputPath('unknown-sign-out-held.png')});
});
