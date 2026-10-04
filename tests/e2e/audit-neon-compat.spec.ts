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
