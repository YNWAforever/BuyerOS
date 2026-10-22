import {test,expect} from '@playwright/test';
async function form(page:import('@playwright/test').Page){
 await page.goto('/app');await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByLabel('Email',{exact:true})).toBeVisible();
}
test('N21-AUTH-04 locale switching preserves entered email and localizes errors',async({page})=>{
 await form(page);await page.getByLabel('Email',{exact:true}).fill('synthetic@example.test');
 await page.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');
 await expect(page.getByLabel('電郵',{exact:true})).toHaveValue('synthetic@example.test');
 await page.route('**/api/auth/sign-in/social',route=>route.fulfill({status:503,contentType:'application/json',body:'{"message":"synthetic-private-provider-body"}'}));
 await page.getByRole('button',{name:'使用 Google 登入',exact:true}).click();
 await expect(page.getByRole('alert')).toContainText('登入失敗');
 await expect(page.getByText('synthetic-private-provider-body',{exact:true})).toHaveCount(0);
});
test('N21-AUTH-05 synthetic exact-branch social handoff reaches only the mocked provider and can cancel',async({page})=>{
 let providerReached=false;
 await page.route('https://ep-c61-session.neonauth.us-east-2.aws.neon.tech/**',async route=>{
   const url=new URL(route.request().url());expect(url.pathname).toBe('/neondb/auth/sign-in/social/init');
   providerReached=true;await route.fulfill({status:200,contentType:'text/html',body:'<h1>Fictional consent only</h1><a href="http://127.0.0.1:5197/app">Cancel fictional consent</a>'});
 });
 await form(page);await page.getByRole('button',{name:'Sign in with Google',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Fictional consent only',exact:true})).toBeVisible();
 expect(providerReached).toBe(true);
 await page.getByRole('link',{name:'Cancel fictional consent',exact:true}).click();
 await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeVisible();
});
test('N21-AUTH-05 untrusted branch is refused before navigation with no opaque value in support text',async({page})=>{
 await form(page);const current=page.url();
 await page.route('**/api/auth/sign-in/social',route=>route.fulfill({status:200,contentType:'application/json',
   body:JSON.stringify({url:'https://ep-other.neonauth.us-east-2.aws.neon.tech/neondb/auth/sign-in/social/init?token=synthetic-opaque-canary'})}));
 await page.getByRole('button',{name:'Sign in with Google',exact:true}).click();
 await expect(page.getByRole('alert')).toBeVisible();expect(page.url()).toBe(current);
 await expect(page.getByTestId('auth-support-reference')).toContainText('redirect_validation');
 await expect(page.locator('body')).not.toContainText('synthetic-opaque-canary');
});
test('N21-AUTH-05 double Google submit is bounded while locale changes keep the transaction',async({page})=>{
 await form(page);let release!:()=>void,calls=0;
 const held=new Promise<void>(resolve=>{release=resolve;});
 await page.route('**/api/auth/sign-in/social',async route=>{calls++;await held;await route.fulfill({status:503,contentType:'application/json',body:'{}'});});
 const google=page.getByRole('button',{name:'Sign in with Google',exact:true});
 await google.evaluate(element=>{(element as HTMLButtonElement).click();(element as HTMLButtonElement).click();});
 await expect(google).toBeDisabled();
 await page.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');release();
 await expect(page.getByRole('alert')).toBeVisible();expect(calls).toBe(1);
 await expect(page.getByRole('button',{name:'使用 Google 登入',exact:true})).toBeEnabled();
});

test('N21-AUTH-09 keyboard recovery focuses the new main and starts a new transaction',async({page})=>{
 await form(page);const previous=new URL(page.url()).searchParams.get('state');
 await page.getByRole('link',{name:'Start again',exact:true}).press('Enter');
 await expect(page.getByRole('main')).toBeFocused();
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 const current=new URL(page.url()).searchParams.get('state');
 expect(Boolean(current&&current!==previous)).toBe(true);
});
