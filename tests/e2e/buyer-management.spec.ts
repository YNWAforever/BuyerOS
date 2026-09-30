import {expect,test,type Page} from '@playwright/test';
import {webcrypto} from 'node:crypto';

const workspace='e0000000-0000-4000-8000-000000000001';
const project='e1000000-0000-4000-8000-000000000001';
async function signIn(page:Page,subject:'fixture-reviewer'|'fixture-viewer'='fixture-reviewer'){
  const keys=await webcrypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
  const publicKey={...(await webcrypto.subtle.exportKey('jwk',keys.publicKey)),kid:'management-fixture',use:'sig'};
  let nonce='';const encode=(value:unknown)=>Buffer.from(JSON.stringify(value)).toString('base64url');
  await page.route('https://oidc.buyeros.test/authorize**',async route=>{const query=new URL(route.request().url()).searchParams;
    nonce=query.get('nonce')||'';await route.fulfill({status:302,headers:{location:`http://localhost:5173/auth/callback?code=management-fixture&state=${query.get('state')}`},body:''});});
  await page.route('https://oidc.buyeros.test/oauth/token',async route=>{
    const unsigned=`${encode({alg:'RS256',kid:'management-fixture'})}.${encode({iss:'https://oidc.buyeros.test/',aud:'fixture-public-client',sub:subject,nonce,exp:Math.floor(Date.now()/1000)+300})}`;
    const signature=await webcrypto.subtle.sign('RSASSA-PKCS1-v1_5',keys.privateKey,new TextEncoder().encode(unsigned));
    await route.fulfill({status:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},body:JSON.stringify({access_token:subject,id_token:`${unsigned}.${Buffer.from(signature).toString('base64url')}`,expires_in:300})});});
  await page.route('https://oidc.buyeros.test/.well-known/jwks.json',async route=>route.fulfill({status:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},body:JSON.stringify({keys:[publicKey]})}));
  await page.goto(`/app/discover?workspace=${workspace}&project=${project}`);
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue(project);
  await expect(page.getByText('24 in snapshot')).toBeVisible();
}

test('T09 durable list, preset, note, owner and individual review journey',async({page})=>{
  test.setTimeout(240_000);
  await signIn(page);
  await page.getByRole('checkbox',{name:'Select Buyer Fixture 02'}).check();
  await page.getByRole('textbox',{name:'List name'}).fill('Review queue');
  await page.getByRole('button',{name:'Create list'}).click();
  await expect(page.getByRole('status').filter({hasText:'Created list Review queue'})).toBeVisible();
  await expect(page.getByRole('combobox',{name:'Buyer list'})).toContainText('Review queue (0)');
  await page.getByRole('textbox',{name:'List name'}).fill('Review queue renamed');
  await page.getByRole('button',{name:'Rename selected list'}).click({timeout:5000});
  await expect(page.getByRole('combobox',{name:'Buyer list'})).toContainText('Review queue renamed (0)');
  await page.getByRole('button',{name:'Add selected to list'}).click();
  await expect(page.getByRole('status').filter({hasText:'1 updated; 0 blocked; 0 conflicts'})).toBeVisible();
  await expect(page.getByRole('combobox',{name:'Buyer list'})).toContainText('Review queue renamed (1)');
  await page.getByRole('button',{name:'Show list buyers'}).click({timeout:5000});
  await expect(page.getByText('1 in snapshot')).toBeVisible();
  await expect(page.getByText('Rows 1–1 of 1')).toBeVisible();
  await expect(page.getByText('Buyer Fixture 02',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Show all buyers'}).click();
  await expect(page.getByText('24 in snapshot')).toBeVisible();
  await expect(page.getByRole('combobox',{name:'Buyer list'})).toContainText('Review queue renamed (1)');
  await page.getByRole('checkbox',{name:'Select Buyer Fixture 02'}).check();
  await page.getByRole('button',{name:'Remove selected from list'}).click({timeout:5000});
  await expect(page.getByRole('status').filter({hasText:'1 updated; 0 blocked; 0 conflicts'})).toBeVisible();
  await expect(page.getByRole('combobox',{name:'Buyer list'})).toContainText('Review queue renamed (0)');
  await page.getByRole('textbox',{name:'Preset name'}).fill('All buyers');
  await page.getByRole('button',{name:'Save current filter'}).click();
  await expect(page.getByRole('status').filter({hasText:'Saved preset All buyers'})).toBeVisible();
  await expect(page.getByRole('combobox',{name:'Saved filter'})).toContainText('All buyers');
  await page.getByRole('button',{name:'Apply saved filter'}).click();
  await expect(page.getByText('0 selected explicitly')).toBeVisible();
  await page.getByRole('button',{name:'Details'}).nth(1).click();
  await expect(page.getByRole('dialog',{name:'Buyer details: Buyer Fixture 02'})).toBeVisible();
  await page.getByRole('textbox',{name:'Buyer note'}).fill('');
  await page.getByRole('textbox',{name:'Buyer note'}).pressSequentially('manual');
  await expect(page.getByRole('textbox',{name:'Buyer note'})).toHaveValue('manual');
  await expect(page.getByRole('textbox',{name:'Buyer note'})).toBeFocused();
  await page.getByRole('textbox',{name:'Buyer note'}).fill('Staff reviewed the fictional public source.');
  await page.getByRole('button',{name:'Save note and next'}).click();
  await expect(page.getByRole('dialog',{name:'Buyer details: Buyer Fixture 03'})).toBeVisible();
  await page.getByRole('button',{name:'Previous buyer'}).click();
  await expect(page.getByRole('textbox',{name:'Buyer note'})).toHaveValue('Staff reviewed the fictional public source.');
  if(await page.getByRole('button',{name:'Clear owner'}).isVisible()) {
    await page.getByRole('button',{name:'Clear owner'}).click();
    await expect(page.getByRole('button',{name:'Assign to me'})).toBeVisible();
  }
  await page.getByRole('button',{name:'Assign to me'}).click();
  await expect(page.getByText('Owner membership: e0000000-0000-4000-8000-000000000005')).toBeVisible();
  await page.getByRole('textbox',{name:'Individual review reason'}).fill(`Fictional evidence reviewed by staff ${Date.now()}`);
  await page.getByRole('button',{name:'Save review and next'}).click();
  await expect(page.getByRole('dialog',{name:'Buyer details: Buyer Fixture 03'})).toBeVisible();
  await page.getByRole('button',{name:'Close details'}).click();
  await expect(page.getByText('Review: 1 updated; 0 blocked; 0 conflicts.')).toBeVisible();
  await expect(page.getByText('24 in snapshot')).toBeVisible();
  await expect(page.getByText('Rows 1–12 of 24')).toBeVisible();
  await page.screenshot({path:'test-results/t09-buyer-management-disposable-db.png',fullPage:true});
});

test('T09 viewer cannot mutate buyers or lists',async({page})=>{
  test.setTimeout(180_000);
  await signIn(page,'fixture-viewer');
  await expect(page.getByRole('button',{name:'Create list'})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Apply review'})).toHaveCount(0);
  await page.getByRole('button',{name:'Details'}).first().click();
  await expect(page.getByRole('textbox',{name:'Buyer note'})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Assign to me'})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Save review'})).toHaveCount(0);
});

test('T29 zh-HK list and saved filter actions use localized accessible names and feedback',async({page})=>{
  test.setTimeout(180_000);
  await signIn(page);
  await page.locator('header select').selectOption('zh-HK');
  const controls=page.getByRole('region',{name:'買家清單及已儲存篩選'});
  await expect(controls.getByRole('heading',{name:'清單及已儲存篩選'})).toBeVisible();
  await controls.getByRole('textbox',{name:'清單名稱'}).fill('中文工作清單');
  await controls.getByRole('button',{name:'建立清單',exact:true}).click();
  await expect(controls.getByRole('status')).toHaveText('已建立清單 中文工作清單');
  await expect(controls.getByRole('combobox',{name:'買家清單'})).toContainText('中文工作清單 (0)');
  await page.getByRole('checkbox',{name:'選取 Buyer Fixture 02'}).check();
  await controls.getByRole('button',{name:'將已選買家加入清單'}).click();
  await expect(controls.getByRole('status')).toContainText('已更新 1 項；已阻止 0 項；衝突 0 項。');
  await controls.getByRole('textbox',{name:'篩選名稱'}).fill('中文已儲存篩選');
  await controls.getByRole('button',{name:'儲存目前篩選'}).click();
  await expect(controls.getByRole('status')).toHaveText('已儲存篩選 中文已儲存篩選');
  await controls.getByRole('button',{name:'套用已儲存篩選'}).click();
  await expect(controls.getByRole('status')).toHaveText('已套用篩選 中文已儲存篩選；已清除選取。');
  await expect(controls.getByRole('button',{name:'Create list',exact:true})).toHaveCount(0);
});
