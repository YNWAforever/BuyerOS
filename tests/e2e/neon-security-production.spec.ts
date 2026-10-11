import {test,expect,type BrowserContext} from '@playwright/test';
// Real emitted SDK routes with owned synthetic protocol. API/DB authority is proved separately.
const origin='https://c61-session.example.test',loopback='http://127.0.0.1:5189';
async function owned(context:BrowserContext){await context.route('**/*',async route=>{
 const request=route.request(),url=new URL(request.url());if(url.origin!==origin)return route.abort('blockedbyclient');
 const response=await context.request.fetch(loopback+url.pathname+url.search,{method:request.method(),headers:{...request.headers(),host:new URL(origin).host},data:request.postDataBuffer()??undefined,maxRedirects:0});await route.fulfill({response});
});}
test.beforeEach(async({request})=>{await request.get(loopback+'/__owned_reset');});

test('C12 emitted auth POST requires exact Origin before SDK or cookie mutation',async({request})=>{
 const headerCases:Record<string,string>[]=[{},{origin:'https://foreign.example.test'},{origin:'null'},{origin:origin+'.foreign.example.test'}];
 for(const headers of headerCases){
  const response=await request.post(loopback+'/api/auth/sign-in/email',{headers,data:{email:'synthetic@example.test',password:'synthetic-only',callbackURL:origin+'/auth/callback'}});
  expect(response.status()).toBe(403);expect(await response.json()).toEqual({code:'AUTH_FORBIDDEN'});expect(response.headers()['cache-control']).toBe('no-store');expect(response.headersArray().filter(h=>h.name.toLowerCase()==='set-cookie')).toEqual([]);
 }
 const state=await(await request.get(loopback+'/__owned_state')).json();expect(state.emailCalls).toBe(0);expect(state.sessionReads).toBe(0);expect(state.tokenReads).toBe(0);expect(state.signedIn).toBe(false);
});

test('C12 unpatched emitted SDK cookie is scoped, secure, HttpOnly and absent from script storage',async({browser})=>{
 const context=await browser.newContext();await owned(context);const page=await context.newPage();
 try{
  await page.goto('/auth/sign-in');
  const response=await page.evaluate(async()=>{const r=await fetch('/api/auth/sign-in/email',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({email:'synthetic@example.test',password:'synthetic-only',callbackURL:location.origin+'/auth/callback'})});return {status:r.status,cookieHeader:r.headers.get('set-cookie')};});
  expect(response).toEqual({status:200,cookieHeader:null});
  const cookies=await context.cookies(origin),cookie=cookies.find(row=>row.name==='__Secure-neon-auth.session_token');expect(cookie).toBeTruthy();expect(cookie!.path).toBe('/');expect(cookie!.sameSite).toBe('Lax');expect(cookie!.secure).toBe(true);expect(cookie!.httpOnly).toBe(true);expect(cookie!.domain).toBe('c61-session.example.test');
  const exposed=await page.evaluate(()=>JSON.stringify({cookie:document.cookie,local:Object.fromEntries(Object.entries(localStorage)),session:Object.fromEntries(Object.entries(sessionStorage))}));expect(exposed).not.toContain('synthetic-opaque-cookie');expect(exposed).not.toContain('synthetic-only');expect(exposed).not.toMatch(/eyJ[a-zA-Z0-9_-]+\./);
 }finally{await context.close();}
});

for(const kind of ['wrong-state','duplicate-state','expired','foreign-return'] as const)test('C12 actual callback rejects '+kind+' before session hydration',async({browser,request})=>{
 const context=await browser.newContext();await owned(context);const page=await context.newPage(),expected='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
 try{
  await page.addInitScript(({kind,expected})=>{sessionStorage.setItem('buyeros-neon-return',JSON.stringify({state:expected,returnPath:kind==='foreign-return'?'https://foreign.example.test/':'/app/runs?workspace=A&project=P',createdAt:Date.now()-(kind==='expired'?600001:0)}));},{kind,expected});
  await page.goto('/auth/callback?state='+(kind==='wrong-state'?'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb':expected)+(kind==='duplicate-state'?'&state='+expected:''));
  await expect(page.getByRole('alert')).toContainText('Sign-in failed');expect(new URL(page.url()).origin).toBe(origin);
  const state=await(await request.get(loopback+'/__owned_state')).json();expect(state.sessionReads).toBe(0);expect(state.tokenReads).toBe(0);expect(state.emailCalls).toBe(0);expect(state.apiCalls).toBe(0);
 }finally{await context.close();}
});
