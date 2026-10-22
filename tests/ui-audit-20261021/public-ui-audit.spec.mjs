import {test,expect} from '@playwright/test';

// Acceptance tests for the observed public entry defects. These do not sign in,
// submit credentials, call paid providers, modify workspace data or send mail.
// Current implementation is expected to fail several assertions; never weaken
// them just to turn the report green. No stored browser session is loaded.
async function openForm(page,locale='en') {
  await page.goto('/app');
  await page.getByRole('combobox',{name:/^(Language|語言)$/}).selectOption(locale);
  await page.getByRole('button',{name:/^(Sign in|登入)$/,exact:true}).click();
  await expect(page).toHaveURL(/\/auth\/sign-in(?:\?|$)/);
  await expect(page.locator('input[type=email]')).toBeVisible();
}

for(const size of [{width:1440,height:900},{width:768,height:1024},{width:390,height:844},{width:320,height:740}]) {
  test(`N21-AUTH-02/03 first-screen form ${size.width}x${size.height}`,async({page})=>{
    await page.setViewportSize(size);await openForm(page);
    const email=page.locator('input[type=email]');
    const password=page.locator('input[type=password]');
    const submit=page.locator('form button[type=submit]');
    await expect(page.getByRole('main')).toHaveCount(1);
    for(const control of [email,password,submit]) await expect(control).toBeInViewport({ratio:1});
    const dimensions=await page.evaluate(()=>({width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth}));
    expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.width+1);
  });
}

test('N21-AUTH-04 zh-HK form uses localized labels and recovery',async({page})=>{
  await openForm(page,'zh-HK');
  await expect(page.locator('html')).toHaveAttribute('lang','zh-HK');
  await expect(page.getByLabel(/^(電郵|電子郵件)$/)).toBeVisible();
  await expect(page.getByLabel('密碼',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:/Google.*登入|使用 Google/})).toBeVisible();
  await expect(page.getByRole('link',{name:/重新開始|返回登入/})).toBeVisible();
  await expect(page.getByText('Sign in with email',{exact:true})).toHaveCount(0);
});

test('N21-AUTH-04 English labels remain understandable',async({page})=>{
  await openForm(page,'en');
  await expect(page.getByLabel('Email',{exact:true})).toBeVisible();
  await expect(page.getByLabel('Password',{exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Sign in with Google',exact:true})).toBeVisible();
});

test('N21-AUTH-06 empty submit stays local and focuses invalid email',async({page})=>{
  await openForm(page);const email=page.locator('input[type=email]');
  const credentialPosts=[];
  page.on('request',request=>{if(request.method()==='POST'&&new URL(request.url()).pathname==='/api/auth/sign-in/email')credentialPosts.push(1);});
  await page.locator('form button[type=submit]').click();
  await expect(email).toBeFocused();
  expect(await email.evaluate(el=>el.validity.valid)).toBe(false);
  expect(credentialPosts).toHaveLength(0);
});

test('N21-AUTH-07 malformed email is rejected before a credential POST',async({page})=>{
  await openForm(page);const email=page.locator('input[type=email]');
  const credentialPosts=[];
  page.on('request',request=>{if(request.method()==='POST'&&new URL(request.url()).pathname==='/api/auth/sign-in/email')credentialPosts.push(1);});
  await email.fill('not-an-email');await page.locator('form button[type=submit]').click();
  await expect(email).toBeFocused();expect(await email.evaluate(el=>el.validity.typeMismatch)).toBe(true);
  expect(credentialPosts).toHaveLength(0);
});

test('N21-AUTH-08 Start again works with a pointer',async({page})=>{
  await openForm(page);await page.getByRole('link',{name:'Start again',exact:true}).click();
  await expect(page).toHaveURL(/\/app(?:\?|$)/);
  await expect(page.locator('input[type=password]')).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeVisible();
});

test('N21-AUTH-09 Start again works with Enter',async({page})=>{
  await openForm(page);await page.getByRole('link',{name:'Start again',exact:true}).press('Enter');
  await expect(page).toHaveURL(/\/app(?:\?|$)/);
  await expect(page.locator('input[type=password]')).toHaveCount(0);
});

test('N21-AUTH-02 auth route has one main and one primary heading',async({page})=>{
  await openForm(page);await expect(page.getByRole('main')).toHaveCount(1);
  await expect(page.getByRole('heading',{level:1})).toHaveCount(1);
});

test('N21-AUTH-02/03 primary auth controls meet the proposed 44px product target',async({page})=>{
  await openForm(page);
  for(const control of [page.locator('form button[type=submit]'),page.getByRole('button',{name:'Sign in with Google',exact:true})]) {
    const box=await control.boundingBox();expect(box).not.toBeNull();expect(box.height).toBeGreaterThanOrEqual(44);
  }
});
