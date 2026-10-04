# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-neon-compat.spec.ts >> NA01 fixture: official handler/client, server session, bearer verification, reload and logout
- Location: tests\e2e\audit-neon-compat.spec.ts:2:1

# Error details

```
Error: expect(received).toEqual(expected) // deep equality

- Expected  - 1
+ Received  + 3

- Array []
+ Array [
+   "buyeros-prefs-v1",
+ ]
```

# Page snapshot

```yaml
- generic [ref=f1e1]:
  - generic [ref=f1e2]:
    - generic [ref=f1e5]:
      - generic [ref=f1e6]:
        - generic [ref=f1e7]:
          - generic [ref=f1e8]: f
          - generic [ref=f1e9]:
            - text: FIMMICK
            - generic [ref=f1e10]: BuyerOS
        - generic [ref=f1e11]:
          - generic [ref=f1e12]: F
          - generic [ref=f1e13]:
            - text: Fimmick workspace
            - generic [ref=f1e14]: Demo workspace
      - generic [ref=f1e17]:
        - generic [ref=f1e18]:
          - generic [ref=f1e19]: WORKSPACE
          - list [ref=f1e20]:
            - listitem [ref=f1e21]:
              - button "Overview" [ref=f1e22] [cursor=pointer]
            - listitem [ref=f1e29]:
              - button "Find Buyers" [ref=f1e30] [cursor=pointer]
            - listitem [ref=f1e35]:
              - button "Buyer Lists 1" [ref=f1e36] [cursor=pointer]:
                - generic [ref=f1e39]: Buyer Lists
                - generic [ref=f1e40]: "1"
            - listitem [ref=f1e41]:
              - button "Outreach" [ref=f1e42] [cursor=pointer]
            - listitem [ref=f1e47]:
              - button "Results" [ref=f1e48] [cursor=pointer]
        - generic [ref=f1e52]:
          - generic [ref=f1e53]: ACTIVE PROJECT
          - text: HarbourSense
          - paragraph [ref=f1e60]: European market discovery
          - generic [ref=f1e61]:
            - generic [ref=f1e62]: 3 markets
            - generic [ref=f1e63]: ·
            - generic [ref=f1e64]: Profile v1
      - generic [ref=f1e65]:
        - generic [ref=f1e66]:
          - generic [ref=f1e67]:
            - generic [ref=f1e71]: Budget & usage
            - button "Open usage" [ref=f1e72] [cursor=pointer]
          - paragraph [ref=f1e76]:
            - text: USD 6.60
            - generic [ref=f1e77]: illustrative spend
          - progressbar [ref=f1e78]
          - text: No charge · demo only
        - list [ref=f1e80]:
          - listitem [ref=f1e81]:
            - button "Settings" [ref=f1e82] [cursor=pointer]
        - generic [ref=f1e86]:
          - generic [ref=f1e87]: WL
          - generic [ref=f1e88]:
            - text: Willy Lai
            - generic [ref=f1e89]: Fimmick workspace
          - generic [ref=f1e90]: DEMO
    - main [ref=f1e91]:
      - generic [ref=f1e92]:
        - generic [ref=f1e93]:
          - generic [ref=f1e94]: Workspace
          - generic [ref=f1e97]: Find Buyers
        - generic [ref=f1e98]:
          - generic [ref=f1e99]: Demo mode · No live services connected
          - combobox "Language" [ref=f1e101] [cursor=pointer]:
            - generic: English
          - generic [ref=f1e102]: WL
      - generic [ref=f1e103]:
        - generic [ref=f1e104]:
          - button "HarbourSense Instruments" [ref=f1e105] [cursor=pointer]
          - generic [ref=f1e113]: European sensor partners
          - generic [ref=f1e114]: DEMO PROJECT
        - generic [ref=f1e115]:
          - generic [ref=f1e116]:
            - heading "Find Buyers" [level=1] [ref=f1e117]
            - paragraph [ref=f1e118]: Find the right companies. Know why they belong on your list.
          - generic [ref=f1e119]:
            - button "Use sample project" [ref=f1e120] [cursor=pointer]
            - button "New buyer search" [ref=f1e121] [cursor=pointer]
        - generic [ref=f1e122]:
          - generic [ref=f1e123]:
            - generic [ref=f1e131]:
              - heading "Industrial sensor buyers in Europe" [level=2] [ref=f1e132]
              - paragraph [ref=f1e133]: Germany, Netherlands, Belgium· Distributors & system integrators
            - generic [ref=f1e134]:
              - generic [ref=f1e135]: Completed
              - generic [ref=f1e138]: Sample run · Profile v1
          - generic [ref=f1e139]:
            - generic [ref=f1e140]:
              - strong [ref=f1e141]: "24"
              - generic [ref=f1e142]: Unique companies
            - button "14 Match Fit your requirements" [ref=f1e143] [cursor=pointer]:
              - strong [ref=f1e144]:
                - text: "14"
                - generic [ref=f1e145]: Match
              - generic [ref=f1e146]: Fit your requirements
            - button "6 Review Need a closer look" [ref=f1e147] [cursor=pointer]:
              - strong [ref=f1e148]:
                - text: "6"
                - generic [ref=f1e149]: Review
              - generic [ref=f1e150]: Need a closer look
            - generic [ref=f1e151]:
              - strong [ref=f1e152]: USD 6.60
              - generic [ref=f1e153]: Illustrative discovery spend
        - generic [ref=f1e154]:
          - generic [ref=f1e159]:
            - text: Review your best-fit buyers
            - paragraph [ref=f1e160]: Review evidence before accepting a company. Contact lookup stays optional.
          - button "Review matches" [ref=f1e161] [cursor=pointer]
        - generic [ref=f1e162]:
          - generic [ref=f1e163]:
            - generic [ref=f1e164]:
              - heading "Buyer results" [level=3] [ref=f1e165]
              - generic [ref=f1e166]: "24"
            - button "Export sample CSV" [ref=f1e168] [cursor=pointer]
          - generic [ref=f1e169]:
            - textbox "Search companies…" [ref=f1e174]
            - combobox "All markets" [ref=f1e176] [cursor=pointer]
            - button "Filters" [ref=f1e177] [cursor=pointer]
          - generic [ref=f1e178]:
            - generic [ref=f1e179]: 24 companies · 0 selected
            - combobox "Best fit first" [ref=f1e181] [cursor=pointer]
          - table [ref=f1e184]:
            - rowgroup [ref=f1e185]:
              - row [ref=f1e186]:
                - columnheader [ref=f1e187]:
                  - checkbox "Select current page" [ref=f1e188] [cursor=pointer]
                - columnheader "Company" [ref=f1e189]
                - columnheader "Why it fits" [ref=f1e190]
                - columnheader "Contact status" [ref=f1e191]
                - columnheader "Review status" [ref=f1e192]
                - columnheader "Open buyer" [ref=f1e193]
            - rowgroup [ref=f1e195]:
              - row [ref=f1e196]:
                - cell [ref=f1e197]:
                  - checkbox "Select Rheinwerk Controls GmbH" [ref=f1e198] [cursor=pointer]
                - cell [ref=f1e199]:
                  - button "RH Rheinwerk Controls GmbH Germany · rheinwerk.example" [ref=f1e200] [cursor=pointer]:
                    - generic [ref=f1e201]: RH
                    - generic [ref=f1e202]:
                      - generic [ref=f1e203]: Rheinwerk Controls GmbH
                      - generic [ref=f1e204]: Germany · rheinwerk.example
                - cell [ref=f1e205]:
                  - button [ref=f1e206] [cursor=pointer]:
                    - generic [ref=f1e207]:
                      - generic [ref=f1e208]: Match
                      - generic [ref=f1e211]: 3 sources
                    - paragraph [ref=f1e215]: Distributes industrial sensors through a regional B2B network.
                - cell "Provider-marked valid" [ref=f1e216]
                - cell "Accepted" [ref=f1e221]
                - cell [ref=f1e225]:
                  - button "Open Rheinwerk Controls GmbH" [ref=f1e226] [cursor=pointer]
              - row [ref=f1e227]:
                - cell [ref=f1e228]:
                  - checkbox "Select DeltaGrid Automation BV" [ref=f1e229] [cursor=pointer]
                - cell [ref=f1e230]:
                  - button "DE DeltaGrid Automation BV Netherlands · deltagrid.example" [ref=f1e231] [cursor=pointer]:
                    - generic [ref=f1e232]: DE
                    - generic [ref=f1e233]:
                      - generic [ref=f1e234]: DeltaGrid Automation BV
                      - generic [ref=f1e235]: Netherlands · deltagrid.example
                - cell [ref=f1e236]:
                  - button [ref=f1e237] [cursor=pointer]:
                    - generic [ref=f1e238]:
                      - generic [ref=f1e239]: Match
                      - generic [ref=f1e242]: 3 sources
                    - paragraph [ref=f1e246]: Integrates industrial monitoring systems for manufacturing clients.
                - cell "Not researched" [ref=f1e247]
                - cell "Awaiting review" [ref=f1e252]
                - cell [ref=f1e254]:
                  - button "Open DeltaGrid Automation BV" [ref=f1e255] [cursor=pointer]
              - row [ref=f1e256]:
                - cell [ref=f1e257]:
                  - checkbox "Select Ardenne Systems SRL" [ref=f1e258] [cursor=pointer]
                - cell [ref=f1e259]:
                  - button "AR Ardenne Systems SRL Belgium · ardenne.example" [ref=f1e260] [cursor=pointer]:
                    - generic [ref=f1e261]: AR
                    - generic [ref=f1e262]:
                      - generic [ref=f1e263]: Ardenne Systems SRL
                      - generic [ref=f1e264]: Belgium · ardenne.example
                - cell [ref=f1e265]:
                  - button [ref=f1e266] [cursor=pointer]:
                    - generic [ref=f1e267]:
                      - generic [ref=f1e268]: Match
                      - generic [ref=f1e271]: 3 sources
                    - paragraph [ref=f1e275]: Distributes industrial sensors through a regional B2B network.
                - cell "Not researched" [ref=f1e276]
                - cell "Awaiting review" [ref=f1e281]
                - cell [ref=f1e283]:
                  - button "Open Ardenne Systems SRL" [ref=f1e284] [cursor=pointer]
              - row [ref=f1e285]:
                - cell [ref=f1e286]:
                  - checkbox "Select Nordline Industrial GmbH" [ref=f1e287] [cursor=pointer]
                - cell [ref=f1e288]:
                  - button "NO Nordline Industrial GmbH Germany · nordline.example" [ref=f1e289] [cursor=pointer]:
                    - generic [ref=f1e290]: "NO"
                    - generic [ref=f1e291]:
                      - generic [ref=f1e292]: Nordline Industrial GmbH
                      - generic [ref=f1e293]: Germany · nordline.example
                - cell [ref=f1e294]:
                  - button [ref=f1e295] [cursor=pointer]:
                    - generic [ref=f1e296]:
                      - generic [ref=f1e297]: Match
                      - generic [ref=f1e300]: 3 sources
                    - paragraph [ref=f1e304]: Integrates industrial monitoring systems for manufacturing clients.
                - cell "Catch-all" [ref=f1e305]
                - cell "Accepted" [ref=f1e310]
                - cell [ref=f1e314]:
                  - button "Open Nordline Industrial GmbH" [ref=f1e315] [cursor=pointer]
              - row [ref=f1e316]:
                - cell [ref=f1e317]:
                  - checkbox "Select Veldra Engineering BV" [ref=f1e318] [cursor=pointer]
                - cell [ref=f1e319]:
                  - button "VE Veldra Engineering BV Netherlands · veldra.example" [ref=f1e320] [cursor=pointer]:
                    - generic [ref=f1e321]: VE
                    - generic [ref=f1e322]:
                      - generic [ref=f1e323]: Veldra Engineering BV
                      - generic [ref=f1e324]: Netherlands · veldra.example
                - cell [ref=f1e325]:
                  - button [ref=f1e326] [cursor=pointer]:
                    - generic [ref=f1e327]:
                      - generic [ref=f1e328]: Match
                      - generic [ref=f1e331]: 3 sources
                    - paragraph [ref=f1e335]: Distributes industrial sensors through a regional B2B network.
                - cell "Not researched" [ref=f1e336]
                - cell "Awaiting review" [ref=f1e341]
                - cell [ref=f1e343]:
                  - button "Open Veldra Engineering BV" [ref=f1e344] [cursor=pointer]
              - row [ref=f1e345]:
                - cell [ref=f1e346]:
                  - checkbox "Select Beltra Process SRL" [ref=f1e347] [cursor=pointer]
                - cell [ref=f1e348]:
                  - button "BE Beltra Process SRL Belgium · beltra.example" [ref=f1e349] [cursor=pointer]:
                    - generic [ref=f1e350]: BE
                    - generic [ref=f1e351]:
                      - generic [ref=f1e352]: Beltra Process SRL
                      - generic [ref=f1e353]: Belgium · beltra.example
                - cell [ref=f1e354]:
                  - button [ref=f1e355] [cursor=pointer]:
                    - generic [ref=f1e356]:
                      - generic [ref=f1e357]: Match
                      - generic [ref=f1e360]: 3 sources
                    - paragraph [ref=f1e364]: Integrates industrial monitoring systems for manufacturing clients.
                - cell "Not researched" [ref=f1e365]
                - cell "Awaiting review" [ref=f1e370]
                - cell [ref=f1e372]:
                  - button "Open Beltra Process SRL" [ref=f1e373] [cursor=pointer]
              - row [ref=f1e374]:
                - cell [ref=f1e375]:
                  - checkbox "Select Westhaven Technik GmbH" [ref=f1e376] [cursor=pointer]
                - cell [ref=f1e377]:
                  - button "WE Westhaven Technik GmbH Germany · westhaven.example" [ref=f1e378] [cursor=pointer]:
                    - generic [ref=f1e379]: WE
                    - generic [ref=f1e380]:
                      - generic [ref=f1e381]: Westhaven Technik GmbH
                      - generic [ref=f1e382]: Germany · westhaven.example
                - cell [ref=f1e383]:
                  - button [ref=f1e384] [cursor=pointer]:
                    - generic [ref=f1e385]:
                      - generic [ref=f1e386]: Match
                      - generic [ref=f1e389]: 3 sources
                    - paragraph [ref=f1e393]: Distributes industrial sensors through a regional B2B network.
                - cell "Suppressed" [ref=f1e394]
                - cell "Accepted" [ref=f1e399]
                - cell [ref=f1e403]:
                  - button "Open Westhaven Technik GmbH" [ref=f1e404] [cursor=pointer]
              - row [ref=f1e405]:
                - cell [ref=f1e406]:
                  - checkbox "Select Maaspoint Solutions BV" [ref=f1e407] [cursor=pointer]
                - cell [ref=f1e408]:
                  - button "MA Maaspoint Solutions BV Netherlands · maaspoint.example" [ref=f1e409] [cursor=pointer]:
                    - generic [ref=f1e410]: MA
                    - generic [ref=f1e411]:
                      - generic [ref=f1e412]: Maaspoint Solutions BV
                      - generic [ref=f1e413]: Netherlands · maaspoint.example
                - cell [ref=f1e414]:
                  - button [ref=f1e415] [cursor=pointer]:
                    - generic [ref=f1e416]:
                      - generic [ref=f1e417]: Match
                      - generic [ref=f1e420]: 3 sources
                    - paragraph [ref=f1e424]: Integrates industrial monitoring systems for manufacturing clients.
                - cell "Not researched" [ref=f1e425]
                - cell "Awaiting review" [ref=f1e430]
                - cell [ref=f1e432]:
                  - button "Open Maaspoint Solutions BV" [ref=f1e433] [cursor=pointer]
          - generic [ref=f1e434]:
            - generic [ref=f1e435]: 1–8 of24 companies
            - generic [ref=f1e436]:
              - generic [ref=f1e437]: Rows
              - combobox "8" [ref=f1e438] [cursor=pointer]
              - navigation "pagination" [ref=f1e439]:
                - list [ref=f1e440]:
                  - listitem [ref=f1e441]:
                    - link "Previous page" [ref=f1e442] [cursor=pointer]:
                      - /url: "#previous"
                      - generic [ref=f1e443]: Previous
                  - listitem [ref=f1e444]:
                    - generic [ref=f1e445]: "1"
                  - listitem [ref=f1e446]:
                    - link "Next page" [ref=f1e447] [cursor=pointer]:
                      - /url: "#next"
                      - generic [ref=f1e448]: Next
        - paragraph [ref=f1e449]: All companies, sources and contact results are fictional. A fit match does not indicate purchase intent.
        - group [ref=f1e452]:
          - generic "Search run history" [ref=f1e453] [cursor=pointer]
    - region "Notifications alt+T"
  - main [ref=f1e454]:
    - heading "N00 fictional compatibility probe" [level=1] [ref=f1e455]
    - status [ref=f1e456]: n00-user
    - generic [ref=f1e457]:
      - button "Fixture login" [ref=f1e458] [cursor=pointer]
      - button "Session" [ref=f1e459] [cursor=pointer]
      - button "Verify token" [active] [ref=f1e460] [cursor=pointer]
      - button "Logout" [ref=f1e461] [cursor=pointer]
      - status [ref=f1e462]: api-verified
```

# Test source

```ts
  1  | import {test,expect} from '@playwright/test';
  2  | test('NA01 fixture: official handler/client, server session, bearer verification, reload and logout',async({page,context})=>{
  3  |  await page.route('**/*',route=>['localhost','127.0.0.1'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort());
  4  |  await page.goto('/compat');await expect(page.getByTestId('server-session')).toHaveText('anonymous');
  5  |  await page.getByRole('button',{name:'Fixture login'}).click();await expect(page.getByTestId('client-status')).toHaveText('signed-in');
  6  |  const cookies=await context.cookies();const token=cookies.find(c=>c.name==='__Secure-neon-auth.session_token');
  7  |  expect(token).toBeDefined();expect(token?.httpOnly).toBe(true);expect(token?.secure).toBe(true);expect(token?.sameSite).toBe('Lax');expect(token?.domain).toBe('localhost');
  8  |  expect(cookies.some(c=>c.name==='__Secure-neon-auth.local.session_data')).toBe(true);
  9  |  await page.getByRole('button',{name:'Session',exact:true}).click();await expect(page.getByTestId('client-status')).toHaveText('n00-user');
  10 |  await page.reload();await expect(page.getByTestId('server-session')).toHaveText('n00-user');
  11 |  await page.getByRole('button',{name:'Verify token'}).click();await expect(page.getByTestId('client-status')).toHaveText('api-verified');
> 12 |  expect(await page.evaluate(()=>Object.keys(localStorage))).toEqual([]);expect(await page.evaluate(()=>Object.keys(sessionStorage))).toEqual([]);
     |                                                             ^ Error: expect(received).toEqual(expected) // deep equality
  13 |  await page.screenshot({path:`test-results/neon-compatibility/${process.env.BUYEROS_N00_TARGET}-signed-in.png`});
  14 |  await page.getByRole('button',{name:'Logout'}).click();await expect(page.getByTestId('client-status')).toHaveText('signed-out');
  15 |  await page.reload();await expect(page.getByTestId('server-session')).toHaveText('anonymous');
  16 |  expect((await context.cookies()).filter(c=>c.name.startsWith('__Secure-neon-auth'))).toEqual([]);
  17 | });
  18 | test('NA01 fixture: callback response preserves host cookies and redirect',async({page,request})=>{
  19 |  const upstream=await request.get('http://127.0.0.1:44891/fixture/auth/callback/fixture?state=fictional-state',{maxRedirects:0});expect(upstream.status()).toBe(302);expect(upstream.headers()['set-cookie']).toContain('HttpOnly');
  20 |  const callback=await request.get('/api/auth/callback/fixture?state=fictional-state',{maxRedirects:0});expect(callback.status()).toBe(302);
  21 |  await page.goto('/api/auth/callback/fixture?state=fictional-state');await expect(page).toHaveURL(/\/compat$/);
  22 |  await expect(page.getByTestId('server-session')).toHaveText('n00-user');
  23 | });
  24 | test('NA01 fixture: tokens require exact issuer/audience/algorithm, expiry and known key',async({request})=>{
  25 |  expect((await request.get('http://127.0.0.1:44892/verify')).status()).toBe(401);
  26 |  for(const kind of ['wrong-issuer','wrong-audience','expired','unknown-kid','wrong-algorithm']){
  27 |   const result=await request.get(`http://127.0.0.1:44891/fixture-token?kind=${kind}`);const {token}=await result.json();
  28 |   expect((await request.get('http://127.0.0.1:44892/verify',{headers:{Authorization:`Bearer ${token}`}})).status()).toBe(401);
  29 |  }
  30 | });
  31 | 
```