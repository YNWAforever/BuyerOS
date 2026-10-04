import {test,expect} from '@playwright/test';
const scenario=process.env.BUYEROS_N00_PROBE_SCENARIO??'valid';
// Each invocation selects a meaningful scenario; none is skipped or marked expected-fail.
if(scenario==='valid'){
 test('NA01 runtime kernel: built page explains fixture scope',async({page},testInfo)=>{
  await page.goto('/');await expect(page.getByRole('heading',{name:'N00 runtime-only SDK fixture'})).toBeVisible();
  await expect(page.getByText(/session, token and real login verification are pending/i)).toBeVisible();
  await page.screenshot({path:testInfo.outputPath('runtime-kernel.png'),fullPage:true});
 });
 test('NA01 runtime kernel: official built SDK initializes with runtime-only trust',async({request},testInfo)=>{
  const response=await request.get('/api/n00-runtime');expect(response.status()).toBe(200);
  const body=await response.json();expect(body).toMatchObject({fixture_only:true,external_verified:false,sdk_initialized:true,egress_denied:false,transport:{fixture_only:true,blocked:0,forwarded:0},trust:{algorithm:'EdDSA',keyType:'OKP',curve:'Ed25519'}});
  const nonce=String(testInfo.config.metadata.n00RunId);
  for(const [key,kind] of [['projectId','project'],['branchId','branch'],['authId','auth']])expect(body[key]).toBe(`fictional-probe-${kind}-${nonce}`);
  expect(body.trust).toEqual({issuer:`https://${nonce}.fixture.invalid`,audience:`fictional-probe-audience-${nonce}`,jwksUrl:`https://${nonce}.fixture.invalid/auth/jwks`,algorithm:'EdDSA',keyType:'OKP',curve:'Ed25519'});
  expect(body.trust.issuer).toMatch(/^https:\/\/.+\.fixture\.invalid$/);expect(body.trust.jwksUrl).toMatch(/^https:\/\/.+\.fixture\.invalid\/auth\/jwks$/);
  expect(body.trust.audience).toMatch(/^fictional-probe-/);expect(body.fingerprint).toMatch(/^[a-f0-9]{64}$/);
  expect(body).not.toHaveProperty('cookies');expect(body).not.toHaveProperty('sdk');expect(JSON.stringify(body)).not.toMatch(/secret|password|bearer/i);
  await testInfo.attach('runtime-response',{body:JSON.stringify(body,null,2),contentType:'application/json'});
 });
 test('NA01 runtime kernel: built fetch guard rejects before transport dispatch',async({request},testInfo)=>{
  const response=await request.get('/api/n00-runtime?egress=test');expect(response.status()).toBe(200);
  const body=await response.json();expect(body).toMatchObject({fixture_only:true,external_verified:false,sdk_initialized:true,egress_denied:true,transport:{fixture_only:true,blocked:1,forwarded:0}});
  await testInfo.attach('runtime-egress-response',{body:JSON.stringify(body,null,2),contentType:'application/json'});
 });
}else{
 const code={missing:'N00_REAL_RUNTIME_REQUIRED',mismatch:'N00_REAL_RUNTIME_MISMATCH',expired:'N00_REAL_EXPIRED'}[scenario];
 test(`NA01 runtime kernel: ${scenario} request configuration fails closed`,async({request},testInfo)=>{
  const response=await request.get('/api/n00-runtime');expect(response.status()).toBe(503);
  const body=await response.json();expect(body).toEqual({fixture_only:true,external_verified:false,code});
  await testInfo.attach('runtime-rejection',{body:JSON.stringify(body,null,2),contentType:'application/json'});
 });
}
