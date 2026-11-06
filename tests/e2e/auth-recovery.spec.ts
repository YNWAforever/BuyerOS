import {test,expect} from '@playwright/test';
const origin='https://c61-session.example.test',loopback='http://127.0.0.1:5189';
test.beforeEach(async({context,request})=>{
 await request.get(loopback+'/__owned_reset');
 await context.route('**/*',async route=>{
  const req=route.request(),url=new URL(req.url());
  if(url.origin!==origin)return route.abort('blockedbyclient');
  const response=await context.request.fetch(loopback+url.pathname+url.search,{method:req.method(),headers:{...req.headers(),host:new URL(origin).host},data:req.postDataBuffer()??undefined,maxRedirects:0});
  await route.fulfill({response});
 });
});
test('copied sign-in URL works and exposes recovery and registration',async({page})=>{
 await page.goto('/auth/sign-in?state=stale-link');
 await expect(page.getByRole('link',{name:'Forgot password?'})).toHaveAttribute('href','/auth/forgot-password');
 await expect(page.getByRole('link',{name:'Create account'})).toHaveAttribute('href','/auth/sign-up');
 await page.getByLabel('Email',{exact:true}).fill('synthetic@example.test');
 await page.getByLabel('Password',{exact:true}).fill('synthetic-only');
 await page.getByRole('button',{name:'Sign in with email'}).click();
 await expect(page).toHaveURL(/\/app/);
 await expect(page.getByRole('button',{name:/^(Sign out|登出)$/})).toBeVisible();
});
test('forgot password submits once and gives a neutral confirmation',async({page})=>{
 let calls=0;
 await page.route('**/api/auth/request-password-reset',async route=>{calls++;expect(route.request().postDataJSON()).toEqual({email:'synthetic@example.test',redirectTo:origin+'/auth/reset-password'});await route.fulfill({json:{status:true}});});
 await page.goto('/auth/sign-in');await page.getByRole('link',{name:'Forgot password?'}).click();
 await page.getByLabel('Email',{exact:true}).fill('synthetic@example.test');await page.getByRole('button',{name:'Send reset link'}).click();
 await expect(page.getByRole('status')).toContainText('If this email has an eligible account');expect(calls).toBe(1);
 await expect(page.getByRole('link',{name:'Back to sign in'})).toBeVisible();
});
test('new account validates confirmation and explains verification and workspace access',async({page})=>{
 let calls=0;
 await page.route('**/api/auth/sign-up/email',async route=>{calls++;expect(route.request().postDataJSON().callbackURL).toBe(origin+'/auth/sign-in?verified=1');await route.fulfill({json:{token:null,user:{id:'synthetic'}}});});
 await page.goto('/auth/sign-up');
 await expect(page.getByText(/Creating an account does not grant workspace access/)).toBeVisible();
 await page.getByLabel('Name',{exact:true}).fill('Synthetic Buyer');await page.getByLabel('Email',{exact:true}).fill('synthetic@example.test');
 await page.getByLabel('New password',{exact:true}).fill('synthetic-password');await page.getByLabel('Confirm password',{exact:true}).fill('different-password');
 await page.getByRole('button',{name:'Create account'}).click();await expect(page.getByRole('alert')).toHaveText('Passwords do not match.');expect(calls).toBe(0);
 await page.getByLabel('Confirm password',{exact:true}).fill('synthetic-password');await page.getByRole('button',{name:'Create account'}).click();
 await expect(page.getByRole('heading',{name:'Verify email'})).toBeVisible();expect(calls).toBe(1);
 await expect(page.getByLabel('Email',{exact:true})).toHaveValue('synthetic@example.test');
 await page.route('**/api/auth/send-verification-email',route=>route.fulfill({json:{status:true}}));
 await page.getByRole('button',{name:'Resend verification code'}).click();
 await expect(page.getByRole('status')).toContainText('If this account needs verification');
 await page.route('**/api/auth/email-otp/verify-email',async route=>{expect(route.request().postDataJSON()).toEqual({email:'synthetic@example.test',otp:'123456'});await route.fulfill({json:{status:true}});});
 await page.getByLabel('Verification code',{exact:true}).fill('123456');await page.getByRole('button',{name:'Verify email',exact:true}).click();
 await expect(page.getByRole('status')).toHaveText('Email verified. You can now sign in.');
 expect(await page.evaluate(()=>JSON.stringify({local:{...localStorage},session:{...sessionStorage}}))).not.toContain('123456');
});
test('verification supports existing accounts, invalid codes, resend, and Traditional Chinese',async({page})=>{
 let calls=0;
 await page.route('**/api/auth/email-otp/verify-email',async route=>{calls++;await route.fulfill({status:400,json:{code:'INVALID_OTP'}});});
 await page.goto('/auth/verify-email');await page.getByRole('combobox',{name:'Language'}).selectOption('zh-HK');
 await page.getByLabel('電郵',{exact:true}).fill('synthetic@example.test');await page.getByLabel('驗證碼',{exact:true}).fill('123456');
 await page.getByRole('button',{name:'驗證電郵',exact:true}).click();
 await expect(page.getByRole('alert')).toContainText('驗證碼無效或已過期');expect(calls).toBe(1);
 await expect(page.getByLabel('驗證碼',{exact:true})).toHaveValue('');
 await page.route('**/api/auth/send-verification-email',route=>route.fulfill({json:{status:true}}));
 await page.getByRole('button',{name:'重新發送驗證碼'}).click();
 await expect(page.getByRole('status')).toContainText('收到新的驗證碼');
});
test('reset link is scrubbed, rejects duplicate tokens, and handles expired and successful resets',async({page})=>{
 await page.goto('/auth/reset-password?token=one&token=two');await expect(page.getByRole('alert')).toContainText('missing or invalid');
 await expect(page).toHaveURL(origin+'/auth/reset-password');
 let calls=0;
 await page.route('**/api/auth/reset-password',async route=>{calls++;expect(route.request().postDataJSON()).toEqual({token:'synthetic-reset',newPassword:'synthetic-new-password'});await route.fulfill(calls===1?{status:400,json:{code:'INVALID_TOKEN'}}:{json:{status:true}});});
 await page.goto('/auth/reset-password?token=synthetic-reset');
 await expect(page.getByLabel('New password',{exact:true})).toBeVisible();await expect(page).toHaveURL(origin+'/auth/reset-password');
 await expect(page.locator('meta[name="referrer"]')).toHaveAttribute('content','no-referrer');
 for(let attempt=0;attempt<2;attempt++){
  await page.getByLabel('New password',{exact:true}).fill('synthetic-new-password');await page.getByLabel('Confirm password',{exact:true}).fill('synthetic-new-password');
  await page.getByRole('button',{name:'Save new password'}).click();
  if(attempt===0)await expect(page.getByRole('alert')).toContainText('expired or already been used');
 }
 await expect(page.getByRole('status')).toHaveText('Password updated. Sign in with your new password.');expect(calls).toBe(2);
 expect(await page.evaluate(()=>JSON.stringify({local:{...localStorage},session:{...sessionStorage}}))).not.toMatch(/synthetic-reset|synthetic-new-password/);
});
test('recovery is usable on mobile in Traditional Chinese and rate limits remain retryable',async({page})=>{
 await page.setViewportSize({width:320,height:800});await page.goto('/auth/forgot-password');
 await page.getByRole('combobox',{name:'Language'}).selectOption('zh-HK');
 await page.route('**/api/auth/request-password-reset',route=>route.fulfill({status:429,json:{code:'RATE_LIMIT'}}));
 await page.getByLabel('電郵',{exact:true}).fill('synthetic@example.test');await page.getByRole('button',{name:'發送重設連結'}).click();
 await expect(page.getByRole('alert')).toHaveText('嘗試次數過多，請稍後再試。');
 await expect(page.getByRole('button',{name:'發送重設連結'})).toBeEnabled();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
 await page.screenshot({path:'test-results/auth-recovery/mobile-recovery.png',fullPage:true});
});
