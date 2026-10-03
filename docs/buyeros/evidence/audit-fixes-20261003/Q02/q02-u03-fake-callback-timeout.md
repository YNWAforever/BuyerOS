# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-auth-entry.spec.ts >> U03 403 access errors retain locale and retry
- Location: tests\e2e\audit-auth-entry.spec.ts:36:36

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('alert').first()
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('alert').first() with timeout 5000ms
  - waiting for getByRole('alert').first()

```

```yaml
- main:
  - status: Completing sign-in…
```

# Test source

```ts
  1  | import {expect,test} from '@playwright/test';
  2  | import {signInWorkbench,workspace,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';
  3  | const api='http://localhost:5173';
  4  | const headers={'Access-Control-Allow-Origin':'http://localhost:5173'};
  5  | test.beforeEach(async()=>{await resetWorkbenchFixtureRateWindows();});
  6  | 
  7  | test('U13 initialization has no false configuration alert before hydration',async({browser})=>{
  8  |   const context=await browser.newContext({javaScriptEnabled:false});
  9  |   try {
  10 |     const page=await context.newPage();await page.goto('http://localhost:5173/auth/callback');
  11 |     await expect(page.getByRole('alert')).toHaveCount(0);
  12 |     await expect(page.getByRole('status')).toContainText(/sign-in/i);
  13 |   } finally {await context.close();}
  14 | });
  15 | 
  16 | test('U02 U03 no membership permits locale switching and read-only access retry',async({page})=>{
  17 |   let reads=0;const writes:string[]=[];
  18 |   page.on('request',r=>{if(r.url().startsWith(api+'/v1/')&&r.method()!=='GET')writes.push(r.method()+' '+r.url());});
  19 |   await page.route(api+'/v1/workspaces?**',route=>{reads++;return route.fulfill({status:200,headers,contentType:'application/json',
  20 |     body:JSON.stringify({data_mode:'live',request_id:'11111111-1111-4111-8111-111111111111',data:{items:[],offset:0,limit:100,total:0}})});});
  21 |   await signInWorkbench(page,false);
  22 |   await expect(page.getByText('No workspace membership. Ask an administrator for access.')).toBeVisible();
  23 |   await page.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');
  24 |   await expect(page.getByText('沒有工作區會員資格。請向管理員申請存取。')).toBeVisible();
  25 |   const before=reads;await page.getByRole('button',{name:'重新檢查存取'}).click();
  26 |   await expect.poll(()=>reads).toBeGreaterThan(before);
  27 |   await expect(page.getByText('沒有工作區會員資格。請向管理員申請存取。')).toBeVisible();
  28 |   await expect(page.getByText('請聯絡工作區管理員。')).toBeVisible();
  29 |   await expect(page.getByRole('button',{name:'複製診斷資料'})).toBeVisible();
  30 |   expect(writes).toEqual([]);
  31 |   await page.screenshot({path:'test-results/audit-auth-empty-zh.png',fullPage:true});
  32 |   await page.reload();await page.getByRole('button',{name:/^(Sign in|登入)$/}).click();
  33 |   await expect(page.getByRole('combobox',{name:'語言',exact:true})).toHaveValue('zh-HK');
  34 | });
  35 | 
  36 | for(const status of [403,404,500]) test(`U03 ${status} access errors retain locale and retry`,async({page})=>{
  37 |   let reads=0;
  38 |   await page.route(api+'/v1/workspaces?**',route=>{reads++;return route.fulfill({status,headers,contentType:'application/json',
  39 |     body:JSON.stringify({code:status===403?'FORBIDDEN':status===404?'NOT_FOUND':'INTERNAL_ERROR',message:'fixture access error',
  40 |       request_id:'11111111-1111-4111-8111-111111111111',retryable:status===500})});});
> 41 |   await signInWorkbench(page,false);await expect(page.getByRole('alert').first()).toBeVisible();
     |                                                                                   ^ Error: expect(locator).toBeVisible() failed
  42 |   await page.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');
  43 |   await expect(page.locator('html')).toHaveAttribute('lang','zh-HK');
  44 |   await expect(page.getByRole('alert').first()).toContainText(status===403?'你沒有執行此操作的權限':status===404?'找不到所選項目':'服務暫時無法使用');
  45 |   const before=reads;await page.getByRole('button',{name:'重試載入工作區'}).click();
  46 |   await expect.poll(()=>reads).toBeGreaterThan(before);
  47 |   await expect(page.getByRole('alert').first()).toContainText('11111111-1111-4111-8111-111111111111');
  48 | });
  49 | 
  50 | test('U03 manual locale choice survives a delayed member preference response',async({page})=>{
  51 |   let release:()=>void=()=>{};const held=new Promise<void>(resolve=>{release=resolve;});
  52 |   await page.route(`${api}/v1/workspaces/${workspace}/preferences`,async route=>{
  53 |     if(route.request().method()!=='GET')return route.continue();
  54 |     await held;return route.fulfill({status:200,headers,contentType:'application/json',body:JSON.stringify({data_mode:'live',request_id:'11111111-1111-4111-8111-111111111111',data:{locale:'en',version:1}})});
  55 |   });
  56 |   try {await signInWorkbench(page);await page.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');}
  57 |   finally {release();}
  58 |   await expect(page.locator('html')).toHaveAttribute('lang','zh-HK');
  59 |   await page.waitForTimeout(300);await expect(page.locator('html')).toHaveAttribute('lang','zh-HK');
  60 | });
  61 | 
  62 | test('U03 expired access returns to sign-in with the selected locale',async({page})=>{
  63 |   await page.addInitScript(()=>localStorage.setItem('buyeros.locale','zh-HK'));
  64 |   await page.route(api+'/v1/workspaces?**',route=>route.fulfill({status:401,contentType:'application/json',body:JSON.stringify({code:'UNAUTHENTICATED',request_id:'11111111-1111-4111-8111-111111111111'})}));
  65 |   await signInWorkbench(page,false);
  66 |   await expect(page.getByRole('button',{name:'登入',exact:true})).toBeVisible();
  67 |   await expect(page.getByRole('combobox',{name:'語言',exact:true})).toHaveValue('zh-HK');
  68 | });
  69 | 
```