import {expect,test} from '@playwright/test';
import {signInWorkbench,workspace,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';
const api='http://localhost:5173';
const headers={'Access-Control-Allow-Origin':'http://localhost:5173'};
test.beforeEach(async()=>{await resetWorkbenchFixtureRateWindows();});

test('U13 initialization has no false configuration alert before hydration',async({browser})=>{
  const context=await browser.newContext({javaScriptEnabled:false});
  try {
    const page=await context.newPage();await page.goto('http://localhost:5173/auth/callback');
    await expect(page.getByRole('alert')).toHaveCount(0);
    await expect(page.getByRole('status')).toContainText(/sign-in/i);
  } finally {await context.close();}
});

test('U02 U03 no membership permits locale switching and read-only access retry',async({page})=>{
  let reads=0;const writes:string[]=[];
  page.on('request',r=>{if(r.url().startsWith(api+'/v1/')&&r.method()!=='GET')writes.push(r.method()+' '+r.url());});
  await page.route(api+'/v1/workspaces?**',route=>{reads++;return route.fulfill({status:200,headers,contentType:'application/json',
    body:JSON.stringify({data_mode:'live',request_id:'11111111-1111-4111-8111-111111111111',data:{items:[],offset:0,limit:100,total:0}})});});
  await signInWorkbench(page,false);
  await expect(page.getByText('No workspace membership. Ask an administrator for access.')).toBeVisible();
  await page.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');
  await expect(page.getByText('沒有工作區會員資格。請向管理員申請存取。')).toBeVisible();
  const before=reads;await page.getByRole('button',{name:'重新檢查存取'}).click();
  await expect.poll(()=>reads).toBeGreaterThan(before);
  await expect(page.getByText('沒有工作區會員資格。請向管理員申請存取。')).toBeVisible();
  await expect(page.getByText('請聯絡工作區管理員。')).toBeVisible();
  await expect(page.getByRole('button',{name:'複製診斷資料'})).toBeVisible();
  expect(writes).toEqual([]);
  await page.screenshot({path:'test-results/audit-auth-empty-zh.png',fullPage:true});
  await page.reload();await page.getByRole('button',{name:/^(Sign in|登入)$/}).click();
  await expect(page.getByRole('combobox',{name:'語言',exact:true})).toHaveValue('zh-HK');
});

for(const status of [403,404,500]) test(`U03 ${status} access errors retain locale and retry`,async({page})=>{
  let reads=0;
  await page.route(api+'/v1/workspaces?**',route=>{reads++;return route.fulfill({status,headers,contentType:'application/json',
    body:JSON.stringify({code:status===403?'FORBIDDEN':status===404?'NOT_FOUND':'INTERNAL_ERROR',message:'fixture access error',
      request_id:'11111111-1111-4111-8111-111111111111',retryable:status===500})});});
  await signInWorkbench(page,false);await expect(page.getByRole('alert').first()).toBeVisible();
  await page.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');
  await expect(page.locator('html')).toHaveAttribute('lang','zh-HK');
  await expect(page.getByRole('alert').first()).toContainText(status===403?'你沒有執行此操作的權限':status===404?'找不到所選項目':'服務暫時無法使用');
  const before=reads;await page.getByRole('button',{name:'重試載入工作區'}).click();
  await expect.poll(()=>reads).toBeGreaterThan(before);
  await expect(page.getByRole('alert').first()).toContainText('11111111-1111-4111-8111-111111111111');
});

test('U03 manual locale choice survives a delayed member preference response',async({page})=>{
  let release:()=>void=()=>{};const held=new Promise<void>(resolve=>{release=resolve;});
  await page.route(`${api}/v1/workspaces/${workspace}/preferences`,async route=>{
    if(route.request().method()!=='GET')return route.continue();
    await held;return route.fulfill({status:200,headers,contentType:'application/json',body:JSON.stringify({data_mode:'live',request_id:'11111111-1111-4111-8111-111111111111',data:{locale:'en',version:1}})});
  });
  try {await signInWorkbench(page);await page.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');}
  finally {release();}
  await expect(page.locator('html')).toHaveAttribute('lang','zh-HK');
  await page.waitForTimeout(300);await expect(page.locator('html')).toHaveAttribute('lang','zh-HK');
});

test('U03 expired access returns to sign-in with the selected locale',async({page})=>{
  await page.addInitScript(()=>localStorage.setItem('buyeros.locale','zh-HK'));
  await page.route(api+'/v1/workspaces?**',route=>route.fulfill({status:401,contentType:'application/json',body:JSON.stringify({code:'UNAUTHENTICATED',request_id:'11111111-1111-4111-8111-111111111111'})}));
  await signInWorkbench(page,false);
  await expect(page.getByRole('button',{name:'登入',exact:true})).toBeVisible();
  await expect(page.getByRole('combobox',{name:'語言',exact:true})).toHaveValue('zh-HK');
});
