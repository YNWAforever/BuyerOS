import {expect,test,type Page} from '@playwright/test';
import {webcrypto} from 'node:crypto';

const workspace='e0000000-0000-4000-8000-000000000001';
const project='e1000000-0000-4000-8000-000000000001';
async function signIn(page:Page,subject:'fixture-admin'|'fixture-viewer'='fixture-admin'){
  const keys=await webcrypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
  const publicKey={...(await webcrypto.subtle.exportKey('jwk',keys.publicKey)),kid:'policy-fixture',use:'sig'};
  let nonce='';const encode=(value:unknown)=>Buffer.from(JSON.stringify(value)).toString('base64url');
  await page.route('https://oidc.buyeros.test/authorize**',async route=>{const query=new URL(route.request().url()).searchParams;
    nonce=query.get('nonce')||'';await route.fulfill({status:302,headers:{location:`http://localhost:5173/auth/callback?code=policy-fixture&state=${query.get('state')}`},body:''});});
  await page.route('https://oidc.buyeros.test/oauth/token',async route=>{
    const unsigned=`${encode({alg:'RS256',kid:'policy-fixture'})}.${encode({iss:'https://oidc.buyeros.test/',aud:'fixture-public-client',sub:subject,nonce,exp:Math.floor(Date.now()/1000)+300})}`;
    const signature=await webcrypto.subtle.sign('RSASSA-PKCS1-v1_5',keys.privateKey,new TextEncoder().encode(unsigned));
    await route.fulfill({status:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},body:JSON.stringify({access_token:subject,id_token:`${unsigned}.${Buffer.from(signature).toString('base64url')}`,expires_in:300})});});
  await page.route('https://oidc.buyeros.test/.well-known/jwks.json',async route=>route.fulfill({status:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:5173'},body:JSON.stringify({keys:[publicKey]})}));
  await page.goto(`/app/settings?workspace=${workspace}&project=${project}`);
  await page.getByRole('button',{name:'Sign in'}).click();
  await expect(page.getByRole('combobox',{name:'Project'})).toHaveValue(project);
}


test('T10 live policy settings block permit activation and manage a domain suppression',async({page})=>{
  test.setTimeout(240_000);
  await signIn(page,'fixture-admin');
  await expect(page.getByRole('heading',{name:'Policy and suppression'})).toBeVisible();
  await expect(page.getByText('Permitted decisions cannot be activated here.')).toBeVisible();
  await expect(page.getByRole('option',{name:'permitted'})).toHaveCount(0);
  await page.getByRole('textbox',{name:'Policy version'}).fill('fixture-policy-v1');
  await page.getByRole('textbox',{name:'Basis reference'}).fill('Fixture controller review pending');
  await page.getByRole('textbox',{name:'Provenance'}).fill('Fixture staff decision');
  await page.getByLabel('Expiry').fill('2030-01-01T12:00');
  await page.getByRole('button',{name:'Record policy'}).click();
  await expect(page.getByRole('status').filter({hasText:'Policy recorded.'})).toBeVisible();
  await expect(page.getByRole('heading',{name:/Policy history/})).toContainText('(1)');
  await page.getByRole('textbox',{name:'Domain'}).fill('FIXTURE-01.EXAMPLE.TEST.');
  await page.getByRole('textbox',{name:'Reason'}).fill('Fixture controller stop');
  await page.getByRole('button',{name:'Add suppression'}).click();
  await expect(page.getByRole('status').filter({hasText:'Suppression added.'})).toBeVisible();
  await expect(page.getByRole('heading',{name:/Suppression history/})).toContainText('(1)');
  await expect(page.getByText('fixture-01.example.test')).toBeVisible();
  await page.getByRole('textbox',{name:'Reason'}).fill('Fixture removal after review');
  await page.getByRole('button',{name:'Remove with reason above'}).click();
  await expect(page.getByRole('status').filter({hasText:'Suppression removed.'})).toBeVisible();
  await expect(page.getByText('Removed',{exact:true})).toBeVisible();
  await page.getByRole('combobox',{name:'Language'}).selectOption('zh-HK');
  await expect(page.getByRole('heading',{name:'政策與拒絕清單'})).toBeVisible();
  await expect(page.getByRole('status').filter({hasText:'拒絕紀錄已移除'})).toBeVisible();
  await page.screenshot({path:'test-results/t10-policy-disposable-db-zhHK.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await expect(page.getByRole('heading',{name:'政策與拒絕清單'})).toBeVisible();
  await page.screenshot({path:'test-results/t10-policy-disposable-db-mobile-zhHK.png',fullPage:true});
});

test('T10 viewer sees the policy next step without admin records or write controls',async({page})=>{
  test.setTimeout(180_000);
  await signIn(page,'fixture-viewer');
  await expect(page.getByRole('heading',{name:'Policy and suppression'})).toBeVisible();
  await expect(page.getByRole('alert').filter({hasText:'Your role cannot view policy records'})).toBeVisible();
  await expect(page.getByRole('button',{name:'Record policy'})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Add suppression'})).toHaveCount(0);
});
