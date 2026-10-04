# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-neon-runtime-built.spec.ts >> NA01 runtime kernel: built page explains fixture scope
- Location: tests\e2e\audit-neon-runtime-built.spec.ts:5:2

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('heading', { name: 'N00 runtime-only SDK fixture' })
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('heading', { name: 'N00 runtime-only SDK fixture' }) with timeout 5000ms
  - waiting for getByRole('heading', { name: 'N00 runtime-only SDK fixture' })

```

```yaml
- main:
  - text: Language
  - combobox "Language":
    - option "English" [selected]
    - option "繁體中文"
  - alert:
    - heading "Live sign-in unavailable" [level=1]
    - paragraph: Configure an Auth0 public SPA client, issuer, client ID and API audience.
```

# Test source

```ts
  1  | import {test,expect} from '@playwright/test';
  2  | const scenario=process.env.BUYEROS_N00_PROBE_SCENARIO??'valid';
  3  | // Each invocation selects a meaningful scenario; none is skipped or marked expected-fail.
  4  | if(scenario==='valid'){
  5  |  test('NA01 runtime kernel: built page explains fixture scope',async({page},testInfo)=>{
> 6  |   await page.goto('/');await expect(page.getByRole('heading',{name:'N00 runtime-only SDK fixture'})).toBeVisible();
     |                                                                                                      ^ Error: expect(locator).toBeVisible() failed
  7  |   await expect(page.getByText(/session, token and real login remain pending/i)).toBeVisible();
  8  |   await page.screenshot({path:testInfo.outputPath('runtime-kernel.png'),fullPage:true});
  9  |  });
  10 |  test('NA01 runtime kernel: official built SDK initializes with runtime-only trust',async({request})=>{
  11 |   const response=await request.get('/api/n00-runtime');expect(response.status()).toBe(200);
  12 |   const body=await response.json();expect(body).toMatchObject({fixture_only:true,external_verified:false,sdk_initialized:true,egress_denied:false,transport:{fixture_only:true,blocked:0,forwarded:0},trust:{algorithm:'EdDSA',keyType:'OKP',curve:'Ed25519'}});
  13 |   for(const key of ['projectId','branchId','authId'])expect(body[key]).toMatch(/^fictional-probe-/);
  14 |   expect(body.trust.issuer).toMatch(/^https:\/\/.+\.fixture\.invalid$/);expect(body.trust.jwksUrl).toMatch(/^https:\/\/.+\.fixture\.invalid\/auth\/jwks$/);
  15 |   expect(body.trust.audience).toMatch(/^fictional-probe-/);expect(body.fingerprint).toMatch(/^[a-f0-9]{64}$/);
  16 |   expect(body).not.toHaveProperty('cookies');expect(body).not.toHaveProperty('sdk');expect(JSON.stringify(body)).not.toMatch(/secret|password|bearer/i);
  17 |  });
  18 |  test('NA01 runtime kernel: built fetch guard rejects before transport dispatch',async({request})=>{
  19 |   const response=await request.get('/api/n00-runtime?egress=test');expect(response.status()).toBe(200);
  20 |   expect(await response.json()).toMatchObject({fixture_only:true,external_verified:false,sdk_initialized:true,egress_denied:true,transport:{fixture_only:true,blocked:1,forwarded:0}});
  21 |  });
  22 | }else{
  23 |  const code={missing:'N00_REAL_RUNTIME_REQUIRED',mismatch:'N00_REAL_RUNTIME_MISMATCH',expired:'N00_REAL_EXPIRED'}[scenario];
  24 |  test(`NA01 runtime kernel: ${scenario} request configuration fails closed`,async({request})=>{
  25 |   const response=await request.get('/api/n00-runtime');expect(response.status()).toBe(503);
  26 |   expect(await response.json()).toEqual({fixture_only:true,external_verified:false,code});
  27 |  });
  28 | }
  29 | 
```