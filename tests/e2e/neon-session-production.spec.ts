import {test,expect,type BrowserContext} from '@playwright/test';
const origin='https://c61-session.example.test',loopback='http://127.0.0.1:5189';
async function ownedRoute(context:BrowserContext){
 await context.route('**/*',async route=>{
  const request=route.request(),url=new URL(request.url());
  if(url.origin!==origin)return route.abort('blockedbyclient');
  const headers={...request.headers(),host:new URL(origin).host};
  const response=await context.request.fetch(loopback+url.pathname+url.search,{method:request.method(),headers,data:request.postDataBuffer()??undefined,maxRedirects:0});
  await route.fulfill({response});
 });
}
test.beforeEach(async({request})=>{await request.get(loopback+'/__owned_reset');});

test('empty workspace shows the current account and a clear way to switch it',async({browser})=>{
 const context=await browser.newContext();await ownedRoute(context);const page=await context.newPage();
 await page.route('**/v1/workspaces?**',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({data_mode:'live',request_id:'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',data:{items:[],offset:0,limit:100,total:0}})}));
 try{
  await page.goto('/app');await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.getByRole('textbox',{name:'Email',exact:true}).fill('synthetic@example.test');
  await page.getByLabel('Password',{exact:true}).fill('synthetic-only');
  await page.getByRole('button',{name:'Sign in with email',exact:true}).click();
  await expect(page.getByText('Signed in as: synthetic@example.test',{exact:true})).toBeVisible();
  await expect(page.getByText('No workspace membership. Ask an administrator for access.')).toBeVisible();
  await expect(page.getByText('Check that you used the account invited to this workspace. Use Sign out to change accounts.')).toBeVisible();
  await page.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');
  await expect(page.getByText('目前登入帳戶: synthetic@example.test',{exact:true})).toBeVisible();
  await expect(page.getByText('請確認你使用獲邀加入工作區的帳戶。按「登出」即可切換帳戶。')).toBeVisible();
  await page.setViewportSize({width:320,height:800});
  const label=page.locator('.live-account-email');
  expect(await label.evaluate(el=>el.scrollWidth<=el.clientWidth)).toBe(true);
  await page.screenshot({path:'test-results/neon-session/account-recovery-zh.png',fullPage:true});
  await page.getByRole('button',{name:'登出',exact:true}).click();
  await expect(page.getByRole('button',{name:'登入',exact:true})).toBeVisible();
  await expect(page.getByText('synthetic@example.test',{exact:true})).toHaveCount(0);
 }finally{await context.close().catch(()=>{});}
});
test('C11 actual built email/token/API/reload/deep-link and two-tab logout; synthetic protocol only',async({browser,request})=>{
 const context=await browser.newContext();await ownedRoute(context);const page=await context.newPage();const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.addInitScript(()=>{const observed:unknown[]=[];(window as typeof window & {__c61InvalidationEvents:unknown[]}).__c61InvalidationEvents=observed;const original=BroadcastChannel.prototype.postMessage;BroadcastChannel.prototype.postMessage=function(value:unknown){observed.push(value);return original.call(this,value);};});
  await page.goto('/app/runs?workspace=A&project=P');await expect(page.getByRole('button',{name:/^(Sign in|登入)$/})).toBeVisible({timeout:5000});await page.getByRole('button',{name:/^(Sign in|登入)$/}).click();
  await expect(page.getByRole('textbox',{name:'Email',exact:true})).toBeVisible();
  await page.getByRole('textbox',{name:'Email',exact:true}).fill('synthetic@example.test');await page.getByLabel('Password',{exact:true}).fill('synthetic-only');
  await page.getByRole('button',{name:'Sign in with email',exact:true}).click();
  await expect(page.getByRole('combobox',{name:/^(Project|專案)$/})).toHaveValue('P');await expect(page.locator('html')).toHaveAttribute('lang','zh-HK');
  const cookies=await context.cookies();const sessionCookie=cookies.find(row=>row.name==='__Secure-neon-auth.session_token');expect(sessionCookie?.httpOnly).toBe(true);expect(sessionCookie?.secure).toBe(true);
  const storage=await page.evaluate(()=>({local:Object.fromEntries(Object.entries(localStorage)),session:Object.fromEntries(Object.entries(sessionStorage))}));
  expect(JSON.stringify(storage)).not.toContain('synthetic-only');expect(JSON.stringify(storage)).not.toContain('synthetic-opaque-cookie');expect(JSON.stringify(storage)).not.toMatch(/eyJ[a-zA-Z0-9_-]+\./);
  await page.reload();await expect(page.getByRole('combobox',{name:/^(Project|專案)$/})).toHaveValue('P');
  const second=await context.newPage();await second.addInitScript(()=>{const received:unknown[]=[];(window as typeof window & {__c61Received:unknown[]}).__c61Received=received;const channel=new BroadcastChannel('buyeros-session-invalidation');channel.addEventListener('message',event=>received.push(event.data));});await second.goto(origin+'/app/runs?workspace=A&project=P');await expect(second.getByRole('combobox',{name:/^(Project|專案)$/})).toHaveValue('P');
  await page.getByRole('button',{name:/^(Sign out|登出)$/}).click();await expect(second.getByRole('button',{name:/^(Sign in|登入)$/})).toBeVisible();
  await expect(page.getByRole('button',{name:/^(Sign in|登入)$/})).toBeVisible();
  const received=await second.evaluate(()=>(window as typeof window & {__c61Received:unknown[]}).__c61Received);expect(received).toContainEqual({type:'logout'});for(const event of received)expect(Object.keys(event as object)).toEqual(['type']);
  const state=await(await request.get(loopback+'/__owned_state')).json();expect(state.emailCalls).toBe(1);expect(state.tokenReads).toBeGreaterThanOrEqual(3);expect(state.apiCalls).toBeGreaterThan(0);expect(state.signedIn).toBe(false);expect(errors).toEqual([]);
 }finally{await context.close().catch(()=>{});}
});

test('C11 actual dirty draft cancels local logout and survives remote logout plus reauthentication',async({browser})=>{
 const context=await browser.newContext();await ownedRoute(context);const page=await context.newPage();
 try{
  await page.goto('/app/outreach?workspace=A&project=P&draft=D');await page.getByRole('button',{name:/^(Sign in|登入)$/}).click();
  await page.getByRole('textbox',{name:'Email',exact:true}).fill('synthetic@example.test');await page.getByLabel('Password',{exact:true}).fill('synthetic-only');await page.getByRole('button',{name:'Sign in with email',exact:true}).click();
  const body=page.getByRole('textbox',{name:/^(Body|內容)$/});await expect(body).toHaveValue('Original synthetic body');await body.fill('Keep this unsaved text across logout');
  await page.getByRole('button',{name:/^(Sign out|登出)$/}).click();const dialog=page.getByRole('dialog');await expect(dialog).toBeVisible();await dialog.getByRole('button',{name:/^(Cancel|取消)$/}).click();
  await expect(body).toHaveValue('Keep this unsaved text across logout');await expect(page.getByRole('button',{name:/^(Sign out|登出)$/})).toBeVisible();
  const second=await context.newPage();await second.goto(origin+'/app/runs?workspace=A&project=P');await expect(second.getByRole('combobox',{name:/^(Project|專案)$/})).toHaveValue('P');
  await second.getByRole('button',{name:/^(Sign out|登出)$/}).click();await expect(page.getByRole('button',{name:/^(Sign in|登入)$/})).toBeVisible();
  const retained=await page.evaluate(()=>sessionStorage.getItem('buyeros-private-draft-recovery'));expect(retained).toContain('Keep this unsaved text across logout');expect(retained).not.toContain('synthetic-opaque-cookie');
  await page.getByRole('button',{name:/^(Sign in|登入)$/}).click();await page.getByRole('textbox',{name:'Email',exact:true}).fill('synthetic@example.test');await page.getByLabel('Password',{exact:true}).fill('synthetic-only');await page.getByRole('button',{name:'Sign in with email',exact:true}).click();
  await expect(body).toHaveValue('Keep this unsaved text across logout');await expect(page.getByRole('status').filter({hasText:'Unsaved draft recovered'})).toBeVisible();
  let unexpectedNativeDialogs=0;page.on('dialog',dialog=>{unexpectedNativeDialogs++;void dialog.dismiss();});
  await page.getByRole('button',{name:/^(Sign out|登出)$/}).click();await expect(dialog).toBeVisible();await dialog.getByRole('button',{name:/^(Discard|捨棄)$/}).click();
  await page.waitForURL(origin+'/app',{waitUntil:'load'});await expect(page.getByRole('button',{name:/^(Sign in|登入)$/})).toBeVisible();expect(unexpectedNativeDialogs).toBe(0);
  expect(await page.evaluate(()=>sessionStorage.getItem('buyeros-private-draft-recovery'))).toBeNull();
 }finally{await context.close().catch(()=>{});}
});
