import {expect,test,type Page} from '@playwright/test';
import {webcrypto} from 'node:crypto';

const workspace='e0000000-0000-4000-8000-000000000001';
const project='e1000000-0000-4000-8000-000000000001';
async function signIn(page:Page,subject:'fixture-admin'|'fixture-viewer'){
  const keys=await webcrypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
  const publicKey={...(await webcrypto.subtle.exportKey('jwk',keys.publicKey)),kid:'admin-fixture',use:'sig'};
  let nonce='';const encode=(value:unknown)=>Buffer.from(JSON.stringify(value)).toString('base64url');
  await page.route('https://oidc.buyeros.test/authorize**',async route=>{const query=new URL(route.request().url()).searchParams;
    nonce=query.get('nonce')||'';await route.fulfill({status:302,headers:{location:`http://localhost:5173/auth/callback?code=admin-fixture&state=${query.get('state')}`},body:''});});
  await page.route('https://oidc.buyeros.test/oauth/token',async route=>{
    const unsigned=`${encode({alg:'RS256',kid:'admin-fixture'})}.${encode({iss:'https://oidc.buyeros.test/',aud:'fixture-public-client',sub:subject,nonce,exp:Math.floor(Date.now()/1000)+900})}`;
    const signature=await webcrypto.subtle.sign('RSASSA-PKCS1-v1_5',keys.privateKey,new TextEncoder().encode(unsigned));
    await route.fulfill({status:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},body:JSON.stringify({access_token:subject,id_token:`${unsigned}.${Buffer.from(signature).toString('base64url')}`,expires_in:900})});});
  await page.route('https://oidc.buyeros.test/.well-known/jwks.json',async route=>route.fulfill({status:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},body:JSON.stringify({keys:[publicKey]})}));
  await page.goto(`/app/settings?workspace=${workspace}&project=${project}`);
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue(project,{timeout:30_000});
}

test('T12 admin settings, durable zh-HK preferences, member audit and operations',async({page})=>{
  test.setTimeout(360_000);await signIn(page,'fixture-admin');
  await expect(page.getByRole('region',{name:'Workspace settings'})).toBeVisible();
  await expect(page.getByText('Research provider')).toBeVisible();
  await expect(page.getByText('NaN',{exact:true})).toHaveCount(0);
  await page.getByRole('textbox',{name:'Default markets'}).fill('HK, US');
  await page.getByRole('button',{name:'Save preferences'}).click();
  await expect(page.getByRole('status').filter({hasText:'Preferences saved.'})).toBeVisible();
  await page.getByRole('textbox',{name:'Change reason'}).fill('Duty rotation test');
  const reviewer=page.getByRole('group',{name:'Roles 00000004'});
  await expect(reviewer).toBeVisible({timeout:15_000});
  await reviewer.getByRole('checkbox',{name:'reviewer',exact:true}).uncheck();
  await reviewer.getByRole('checkbox',{name:'viewer',exact:true}).check();
  await reviewer.locator('..').getByRole('button',{name:'Save member'}).click();
  await expect(page.getByRole('status').filter({hasText:'Membership updated.'})).toBeVisible();
  const localeSaved=page.waitForResponse(r=>r.url().includes(`/v1/workspaces/${workspace}/preferences`)&&r.request().method()==='PATCH');
  await page.getByRole('combobox',{name:'Language'}).selectOption('zh-HK');
  const localeResponse=await localeSaved;
  expect(localeResponse.status()).toBe(200);
  expect((await localeResponse.json()).data.locale).toBe('zh-HK');
  await expect(page.locator('html')).toHaveAttribute('lang','zh-HK');
  await expect(page.getByRole('status').filter({hasText:'成員資料已更新。'})).toBeVisible();
  await expect(page.getByRole('region',{name:'工作區設定'})).toBeVisible();
  await page.screenshot({path:'test-results/t12-admin-settings-zhHK.png',fullPage:true});
  await page.reload();
  await expect(page.getByRole('button',{name:'Sign in'})).toBeVisible();
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByRole('combobox',{name:/Project|專案/})).toHaveValue(project,{timeout:60_000});
  await expect(page.locator('html')).toHaveAttribute('lang','zh-HK',{timeout:60_000});
  await expect(page.getByRole('textbox',{name:'預設市場'})).toHaveValue('HK, US');
  await page.getByRole('button',{name:'營運工作台'}).click();
  await expect(page.getByRole('region',{name:'營運工作台'})).toBeVisible();
  await expect(page.getByRole('region',{name:'就緒狀態'})).toContainText('資料庫: ready');
  await expect(page.getByRole('region',{name:'就緒狀態'})).toContainText('未就緒');
  await expect(page.getByRole('region',{name:'審計紀錄'})).toContainText('membership.updated');
  await expect(page.getByRole('region',{name:'批量工作'})).toContainText('0');
  await expect(page.getByRole('region',{name:'工作佇列'})).toContainText('失敗工作: 0');
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
  await page.screenshot({path:'test-results/t12-operations-mobile-zhHK.png',fullPage:true});
});

test('T12 viewer cannot access member or admin operations controls',async({page})=>{
  test.setTimeout(240_000);await signIn(page,'fixture-viewer');
  await expect(page.getByRole('region',{name:'Workspace settings'})).toBeVisible();
  await expect(page.getByRole('region',{name:'Member management'})).toHaveCount(0);
  await page.getByRole('button',{name:'Operations'}).click();
  await expect(page.getByRole('region',{name:'Readiness'})).toHaveCount(0);
  await expect(page.getByRole('region',{name:'Audit trail'})).toHaveCount(0);
  await expect(page.getByRole('region',{name:'Integrations'})).toBeVisible();
});

test('T13 admin sets a versioned zero-start budget and viewer has no budget controls',async({page,browser})=>{
  test.setTimeout(360_000);
  const preferenceResponses:string[]=[];
  page.on('response',response=>{
    if(response.url().includes(`/v1/workspaces/${workspace}/preferences`)) preferenceResponses.push(`${response.request().method()} ${response.status()} ${response.url()}`);
  });
  await signIn(page,'fixture-admin');
  const budget=page.getByRole('region',{name:/Budget settings|預算設定/});
  await expect(budget).toBeVisible({timeout:30_000});
  await expect(budget.locator('.budget-row').first()).toBeVisible({timeout:60_000});
  await expect(budget).toContainText('0.000000 USD');
  await expect(budget).toContainText(/Frozen for new spending|新支出已凍結/);
  const projectRow=budget.locator('.budget-row').filter({hasText:/project|專案/}).first();
  await expect(projectRow).toBeVisible();
  await projectRow.getByRole('textbox',{name:/Approved limit|核准上限/}).fill('12');
  await projectRow.getByRole('textbox',{name:/Change reason|變更原因/}).fill('Pilot ceiling approved in local test');
  const saved=page.waitForResponse(r=>r.url().includes('/budgets/')&&r.request().method()==='PATCH');
  await projectRow.getByRole('button',{name:/Save limit|儲存上限/}).click();
  expect((await saved).status()).toBe(200);
  await expect(projectRow).toContainText('12.000000 USD',{timeout:60_000});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
  try{await expect(page.getByRole('alert')).toHaveCount(0,{timeout:30_000});}
  catch(error){throw new Error(`Unexpected alert after budget save; preference responses: ${preferenceResponses.join(', ')}`,{cause:error});}
  await page.screenshot({path:'test-results/t13-budget-mobile-disposable-db.png',fullPage:true});
  await page.reload();
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByRole('combobox',{name:/Project|專案/})).toHaveValue(project,{timeout:60_000});
  await expect(page.getByRole('region',{name:/Budget settings|預算設定/})).toContainText('12.000000 USD',{timeout:60_000});
  await page.screenshot({path:'test-results/t13-budget-reload-disposable-db.png',fullPage:true});
  await page.getByRole('combobox',{name:'Language'}).selectOption('zh-HK');
  await expect(page.getByRole('region',{name:'預算設定'})).toContainText('12.000000 USD',{timeout:60_000});
  await expect(page.getByRole('region',{name:'預算設定'})).toContainText('核准上限');
  await expect(page.getByRole('alert')).toHaveCount(0,{timeout:30_000});
  await page.screenshot({path:'test-results/t13-budget-zhHK-disposable-db.png',fullPage:true});
  const viewer=await browser.newPage();
  await signIn(viewer,'fixture-viewer');
  await expect(viewer.getByRole('region',{name:/Budget settings|預算設定/})).toHaveCount(0);
  await viewer.close();
});
