# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-neon-compat.spec.ts >> NA01 fixture: official handler/client, server session, bearer verification, reload and logout
- Location: tests\e2e\audit-neon-compat.spec.ts:2:1

# Error details

```
Test timeout of 45000ms exceeded.
```

```
Error: locator.click: Test timeout of 45000ms exceeded.
Call log:
  - waiting for getByRole('button', { name: 'Fixture login' })
    - locator resolved to <button>Fixture login</button>
  - attempting click action
    2 × waiting for element to be visible, enabled and stable
      - element is visible, enabled and stable
      - scrolling into view if needed
      - done scrolling
      - <div data-sidebar="footer" data-slot="sidebar-footer" class="flex flex-col gap-2 p-2">…</div> from <div data-slot="sidebar-wrapper" class="group/sidebar-wrapper flex min-h-svh w-full has-data-[variant=inset]:bg-sidebar">…</div> subtree intercepts pointer events
    - retrying click action
    - waiting 20ms
    2 × waiting for element to be visible, enabled and stable
      - element is visible, enabled and stable
      - scrolling into view if needed
      - done scrolling
      - <div data-sidebar="footer" data-slot="sidebar-footer" class="flex flex-col gap-2 p-2">…</div> from <div data-slot="sidebar-wrapper" class="group/sidebar-wrapper flex min-h-svh w-full has-data-[variant=inset]:bg-sidebar">…</div> subtree intercepts pointer events
    - retrying click action
      - waiting 100ms
    84 × waiting for element to be visible, enabled and stable
       - element is visible, enabled and stable
       - scrolling into view if needed
       - done scrolling
       - <div data-sidebar="footer" data-slot="sidebar-footer" class="flex flex-col gap-2 p-2">…</div> from <div data-slot="sidebar-wrapper" class="group/sidebar-wrapper flex min-h-svh w-full has-data-[variant=inset]:bg-sidebar">…</div> subtree intercepts pointer events
     - retrying click action
       - waiting 500ms

```

# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - generic [ref=e2]:
    - generic [ref=e5]:
      - generic [ref=e6]:
        - generic [ref=e7]:
          - generic [ref=e8]: f
          - generic [ref=e9]:
            - text: FIMMICK
            - generic [ref=e10]: BuyerOS
        - generic [ref=e11]:
          - generic [ref=e12]: F
          - generic [ref=e13]:
            - text: Fimmick workspace
            - generic [ref=e14]: Demo workspace
      - generic [ref=e17]:
        - generic [ref=e18]:
          - generic [ref=e19]: WORKSPACE
          - list [ref=e20]:
            - listitem [ref=e21]:
              - button "Overview" [ref=e22] [cursor=pointer]
            - listitem [ref=e29]:
              - button "Find Buyers" [ref=e30] [cursor=pointer]
            - listitem [ref=e35]:
              - button "Buyer Lists 1" [ref=e36] [cursor=pointer]:
                - generic [ref=e39]: Buyer Lists
                - generic [ref=e40]: "1"
            - listitem [ref=e41]:
              - button "Outreach" [ref=e42] [cursor=pointer]
            - listitem [ref=e47]:
              - button "Results" [ref=e48] [cursor=pointer]
        - generic [ref=e52]:
          - generic [ref=e53]: ACTIVE PROJECT
          - text: HarbourSense
          - paragraph [ref=e60]: European market discovery
          - generic [ref=e61]:
            - generic [ref=e62]: 3 markets
            - generic [ref=e63]: ·
            - generic [ref=e64]: Profile v1
      - generic [ref=e65]:
        - generic [ref=e66]:
          - generic [ref=e67]:
            - generic [ref=e71]: Budget & usage
            - button "Open usage" [ref=e72] [cursor=pointer]
          - paragraph [ref=e76]:
            - text: USD 6.60
            - generic [ref=e77]: illustrative spend
          - progressbar [ref=e78]
          - text: No charge · demo only
        - list [ref=e80]:
          - listitem [ref=e81]:
            - button "Settings" [ref=e82] [cursor=pointer]
        - generic [ref=e86]:
          - generic [ref=e87]: WL
          - generic [ref=e88]:
            - text: Willy Lai
            - generic [ref=e89]: Fimmick workspace
          - generic [ref=e90]: DEMO
    - main [ref=e91]:
      - generic [ref=e92]:
        - generic [ref=e93]:
          - generic [ref=e94]: Workspace
          - generic [ref=e97]: Find Buyers
        - generic [ref=e98]:
          - generic [ref=e99]: Demo mode · No live services connected
          - combobox "Language" [ref=e101] [cursor=pointer]:
            - generic: English
          - generic [ref=e102]: WL
      - generic [ref=e103]:
        - generic [ref=e104]:
          - button "HarbourSense Instruments" [ref=e105] [cursor=pointer]
          - generic [ref=e113]: European sensor partners
          - generic [ref=e114]: DEMO PROJECT
        - generic [ref=e115]:
          - generic [ref=e116]:
            - heading "Find Buyers" [level=1] [ref=e117]
            - paragraph [ref=e118]: Find the right companies. Know why they belong on your list.
          - generic [ref=e119]:
            - button "Use sample project" [ref=e120] [cursor=pointer]
            - button "New buyer search" [ref=e121] [cursor=pointer]
        - generic [ref=e122]:
          - generic [ref=e123]:
            - generic [ref=e131]:
              - heading "Industrial sensor buyers in Europe" [level=2] [ref=e132]
              - paragraph [ref=e133]: Germany, Netherlands, Belgium· Distributors & system integrators
            - generic [ref=e134]:
              - generic [ref=e135]: Completed
              - generic [ref=e138]: Sample run · Profile v1
          - generic [ref=e139]:
            - generic [ref=e140]:
              - strong [ref=e141]: "24"
              - generic [ref=e142]: Unique companies
            - button "14 Match Fit your requirements" [ref=e143] [cursor=pointer]:
              - strong [ref=e144]:
                - text: "14"
                - generic [ref=e145]: Match
              - generic [ref=e146]: Fit your requirements
            - button "6 Review Need a closer look" [ref=e147] [cursor=pointer]:
              - strong [ref=e148]:
                - text: "6"
                - generic [ref=e149]: Review
              - generic [ref=e150]: Need a closer look
            - generic [ref=e151]:
              - strong [ref=e152]: USD 6.60
              - generic [ref=e153]: Illustrative discovery spend
        - generic [ref=e154]:
          - generic [ref=e159]:
            - text: Review your best-fit buyers
            - paragraph [ref=e160]: Review evidence before accepting a company. Contact lookup stays optional.
          - button "Review matches" [ref=e161] [cursor=pointer]
        - generic [ref=e162]:
          - generic [ref=e163]:
            - generic [ref=e164]:
              - heading "Buyer results" [level=3] [ref=e165]
              - generic [ref=e166]: "24"
            - button "Export sample CSV" [ref=e168] [cursor=pointer]
          - generic [ref=e169]:
            - textbox "Search companies…" [ref=e174]
            - combobox "All markets" [ref=e176] [cursor=pointer]
            - button "Filters" [ref=e177] [cursor=pointer]
          - generic [ref=e178]:
            - generic [ref=e179]: 24 companies · 0 selected
            - combobox "Best fit first" [ref=e181] [cursor=pointer]
          - table [ref=e184]:
            - rowgroup [ref=e185]:
              - row [ref=e186]:
                - columnheader [ref=e187]:
                  - checkbox "Select current page" [ref=e188] [cursor=pointer]
                - columnheader "Company" [ref=e189]
                - columnheader "Why it fits" [ref=e190]
                - columnheader "Contact status" [ref=e191]
                - columnheader "Review status" [ref=e192]
                - columnheader "Open buyer" [ref=e193]
            - rowgroup [ref=e195]:
              - row [ref=e196]:
                - cell [ref=e197]:
                  - checkbox "Select Rheinwerk Controls GmbH" [ref=e198] [cursor=pointer]
                - cell [ref=e199]:
                  - button "RH Rheinwerk Controls GmbH Germany · rheinwerk.example" [ref=e200] [cursor=pointer]:
                    - generic [ref=e201]: RH
                    - generic [ref=e202]:
                      - generic [ref=e203]: Rheinwerk Controls GmbH
                      - generic [ref=e204]: Germany · rheinwerk.example
                - cell [ref=e205]:
                  - button [ref=e206] [cursor=pointer]:
                    - generic [ref=e207]:
                      - generic [ref=e208]: Match
                      - generic [ref=e211]: 3 sources
                    - paragraph [ref=e215]: Distributes industrial sensors through a regional B2B network.
                - cell "Provider-marked valid" [ref=e216]
                - cell "Accepted" [ref=e221]
                - cell [ref=e225]:
                  - button "Open Rheinwerk Controls GmbH" [ref=e226] [cursor=pointer]
              - row [ref=e227]:
                - cell [ref=e228]:
                  - checkbox "Select DeltaGrid Automation BV" [ref=e229] [cursor=pointer]
                - cell [ref=e230]:
                  - button "DE DeltaGrid Automation BV Netherlands · deltagrid.example" [ref=e231] [cursor=pointer]:
                    - generic [ref=e232]: DE
                    - generic [ref=e233]:
                      - generic [ref=e234]: DeltaGrid Automation BV
                      - generic [ref=e235]: Netherlands · deltagrid.example
                - cell [ref=e236]:
                  - button [ref=e237] [cursor=pointer]:
                    - generic [ref=e238]:
                      - generic [ref=e239]: Match
                      - generic [ref=e242]: 3 sources
                    - paragraph [ref=e246]: Integrates industrial monitoring systems for manufacturing clients.
                - cell "Not researched" [ref=e247]
                - cell "Awaiting review" [ref=e252]
                - cell [ref=e254]:
                  - button "Open DeltaGrid Automation BV" [ref=e255] [cursor=pointer]
              - row [ref=e256]:
                - cell [ref=e257]:
                  - checkbox "Select Ardenne Systems SRL" [ref=e258] [cursor=pointer]
                - cell [ref=e259]:
                  - button "AR Ardenne Systems SRL Belgium · ardenne.example" [ref=e260] [cursor=pointer]:
                    - generic [ref=e261]: AR
                    - generic [ref=e262]:
                      - generic [ref=e263]: Ardenne Systems SRL
                      - generic [ref=e264]: Belgium · ardenne.example
                - cell [ref=e265]:
                  - button [ref=e266] [cursor=pointer]:
                    - generic [ref=e267]:
                      - generic [ref=e268]: Match
                      - generic [ref=e271]: 3 sources
                    - paragraph [ref=e275]: Distributes industrial sensors through a regional B2B network.
                - cell "Not researched" [ref=e276]
                - cell "Awaiting review" [ref=e281]
                - cell [ref=e283]:
                  - button "Open Ardenne Systems SRL" [ref=e284] [cursor=pointer]
              - row [ref=e285]:
                - cell [ref=e286]:
                  - checkbox "Select Nordline Industrial GmbH" [ref=e287] [cursor=pointer]
                - cell [ref=e288]:
                  - button "NO Nordline Industrial GmbH Germany · nordline.example" [ref=e289] [cursor=pointer]:
                    - generic [ref=e290]: "NO"
                    - generic [ref=e291]:
                      - generic [ref=e292]: Nordline Industrial GmbH
                      - generic [ref=e293]: Germany · nordline.example
                - cell [ref=e294]:
                  - button [ref=e295] [cursor=pointer]:
                    - generic [ref=e296]:
                      - generic [ref=e297]: Match
                      - generic [ref=e300]: 3 sources
                    - paragraph [ref=e304]: Integrates industrial monitoring systems for manufacturing clients.
                - cell "Catch-all" [ref=e305]
                - cell "Accepted" [ref=e310]
                - cell [ref=e314]:
                  - button "Open Nordline Industrial GmbH" [ref=e315] [cursor=pointer]
              - row [ref=e316]:
                - cell [ref=e317]:
                  - checkbox "Select Veldra Engineering BV" [ref=e318] [cursor=pointer]
                - cell [ref=e319]:
                  - button "VE Veldra Engineering BV Netherlands · veldra.example" [ref=e320] [cursor=pointer]:
                    - generic [ref=e321]: VE
                    - generic [ref=e322]:
                      - generic [ref=e323]: Veldra Engineering BV
                      - generic [ref=e324]: Netherlands · veldra.example
                - cell [ref=e325]:
                  - button [ref=e326] [cursor=pointer]:
                    - generic [ref=e327]:
                      - generic [ref=e328]: Match
                      - generic [ref=e331]: 3 sources
                    - paragraph [ref=e335]: Distributes industrial sensors through a regional B2B network.
                - cell "Not researched" [ref=e336]
                - cell "Awaiting review" [ref=e341]
                - cell [ref=e343]:
                  - button "Open Veldra Engineering BV" [ref=e344] [cursor=pointer]
              - row [ref=e345]:
                - cell [ref=e346]:
                  - checkbox "Select Beltra Process SRL" [ref=e347] [cursor=pointer]
                - cell [ref=e348]:
                  - button "BE Beltra Process SRL Belgium · beltra.example" [ref=e349] [cursor=pointer]:
                    - generic [ref=e350]: BE
                    - generic [ref=e351]:
                      - generic [ref=e352]: Beltra Process SRL
                      - generic [ref=e353]: Belgium · beltra.example
                - cell [ref=e354]:
                  - button [ref=e355] [cursor=pointer]:
                    - generic [ref=e356]:
                      - generic [ref=e357]: Match
                      - generic [ref=e360]: 3 sources
                    - paragraph [ref=e364]: Integrates industrial monitoring systems for manufacturing clients.
                - cell "Not researched" [ref=e365]
                - cell "Awaiting review" [ref=e370]
                - cell [ref=e372]:
                  - button "Open Beltra Process SRL" [ref=e373] [cursor=pointer]
              - row [ref=e374]:
                - cell [ref=e375]:
                  - checkbox "Select Westhaven Technik GmbH" [ref=e376] [cursor=pointer]
                - cell [ref=e377]:
                  - button "WE Westhaven Technik GmbH Germany · westhaven.example" [ref=e378] [cursor=pointer]:
                    - generic [ref=e379]: WE
                    - generic [ref=e380]:
                      - generic [ref=e381]: Westhaven Technik GmbH
                      - generic [ref=e382]: Germany · westhaven.example
                - cell [ref=e383]:
                  - button [ref=e384] [cursor=pointer]:
                    - generic [ref=e385]:
                      - generic [ref=e386]: Match
                      - generic [ref=e389]: 3 sources
                    - paragraph [ref=e393]: Distributes industrial sensors through a regional B2B network.
                - cell "Suppressed" [ref=e394]
                - cell "Accepted" [ref=e399]
                - cell [ref=e403]:
                  - button "Open Westhaven Technik GmbH" [ref=e404] [cursor=pointer]
              - row [ref=e405]:
                - cell [ref=e406]:
                  - checkbox "Select Maaspoint Solutions BV" [ref=e407] [cursor=pointer]
                - cell [ref=e408]:
                  - button "MA Maaspoint Solutions BV Netherlands · maaspoint.example" [ref=e409] [cursor=pointer]:
                    - generic [ref=e410]: MA
                    - generic [ref=e411]:
                      - generic [ref=e412]: Maaspoint Solutions BV
                      - generic [ref=e413]: Netherlands · maaspoint.example
                - cell [ref=e414]:
                  - button [ref=e415] [cursor=pointer]:
                    - generic [ref=e416]:
                      - generic [ref=e417]: Match
                      - generic [ref=e420]: 3 sources
                    - paragraph [ref=e424]: Integrates industrial monitoring systems for manufacturing clients.
                - cell "Not researched" [ref=e425]
                - cell "Awaiting review" [ref=e430]
                - cell [ref=e432]:
                  - button "Open Maaspoint Solutions BV" [ref=e433] [cursor=pointer]
          - generic [ref=e434]:
            - generic [ref=e435]: 1–8 of24 companies
            - generic [ref=e436]:
              - generic [ref=e437]: Rows
              - combobox "8" [ref=e438] [cursor=pointer]
              - navigation "pagination" [ref=e439]:
                - list [ref=e440]:
                  - listitem [ref=e441]:
                    - link "Previous page" [ref=e442] [cursor=pointer]:
                      - /url: "#previous"
                      - generic [ref=e443]: Previous
                  - listitem [ref=e444]:
                    - generic [ref=e445]: "1"
                  - listitem [ref=e446]:
                    - link "Next page" [ref=e447] [cursor=pointer]:
                      - /url: "#next"
                      - generic [ref=e448]: Next
        - paragraph [ref=e449]: All companies, sources and contact results are fictional. A fit match does not indicate purchase intent.
        - group [ref=e452]:
          - generic "Search run history" [ref=e453] [cursor=pointer]
    - region "Notifications alt+T"
  - main [ref=e454]:
    - heading "N00 fictional compatibility probe" [level=1] [ref=e455]
    - status [ref=e456]: anonymous
    - generic [ref=e457]:
      - button "Fixture login" [ref=e458] [cursor=pointer]
      - button "Session" [ref=e459] [cursor=pointer]
      - button "Verify token" [ref=e460] [cursor=pointer]
      - button "Logout" [ref=e461] [cursor=pointer]
      - status [ref=e462]: ready
```

# Test source

```ts
  1  | import {test,expect} from '@playwright/test';
  2  | test('NA01 fixture: official handler/client, server session, bearer verification, reload and logout',async({page,context})=>{
  3  |  await page.route('**/*',route=>['localhost','127.0.0.1'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort());
  4  |  await page.goto('/compat');await expect(page.getByTestId('server-session')).toHaveText('anonymous');
> 5  |  await page.getByRole('button',{name:'Fixture login'}).click();await expect(page.getByTestId('client-status')).toHaveText('signed-in');
     |                                                        ^ Error: locator.click: Test timeout of 45000ms exceeded.
  6  |  const cookies=await context.cookies();const token=cookies.find(c=>c.name==='__Secure-neon-auth.session_token');
  7  |  expect(token).toBeDefined();expect(token?.httpOnly).toBe(true);expect(token?.secure).toBe(true);expect(token?.sameSite).toBe('Lax');expect(token?.domain).toBe('localhost');
  8  |  expect(cookies.some(c=>c.name==='__Secure-neon-auth.local.session_data')).toBe(true);
  9  |  await page.getByRole('button',{name:'Session',exact:true}).click();await expect(page.getByTestId('client-status')).toHaveText('n00-user');
  10 |  await page.reload();await expect(page.getByTestId('server-session')).toHaveText('n00-user');
  11 |  await page.getByRole('button',{name:'Verify token'}).click();await expect(page.getByTestId('client-status')).toHaveText('api-verified');
  12 |  expect(await page.evaluate(()=>Object.keys(localStorage))).toEqual([]);expect(await page.evaluate(()=>Object.keys(sessionStorage))).toEqual([]);
  13 |  await page.screenshot({path:`test-results/neon-compatibility/${process.env.BUYEROS_N00_TARGET}-signed-in.png`});
  14 |  await page.getByRole('button',{name:'Logout'}).click();await expect(page.getByTestId('client-status')).toHaveText('signed-out');
  15 |  await page.reload();await expect(page.getByTestId('server-session')).toHaveText('anonymous');
  16 |  expect((await context.cookies()).filter(c=>c.name.startsWith('__Secure-neon-auth'))).toEqual([]);
  17 | });
  18 | test('NA01 fixture: callback response preserves host cookies and redirect',async({page,request})=>{
  19 |  const callback=await request.get('/api/auth/callback/fixture?state=fictional-state',{maxRedirects:0});expect(callback.status()).toBe(302);
  20 |  await page.goto('/api/auth/callback/fixture?state=fictional-state');await expect(page).toHaveURL(/\/compat$/);
  21 |  await expect(page.getByTestId('server-session')).toHaveText('n00-user');
  22 | });
  23 | test('NA01 fixture: tokens require exact issuer/audience/algorithm, expiry and known key',async({request})=>{
  24 |  expect((await request.get('http://127.0.0.1:44892/verify')).status()).toBe(401);
  25 |  for(const kind of ['wrong-issuer','wrong-audience','expired','unknown-kid','wrong-algorithm']){
  26 |   const result=await request.get(`http://127.0.0.1:44891/fixture-token?kind=${kind}`);const {token}=await result.json();
  27 |   expect((await request.get('http://127.0.0.1:44892/verify',{headers:{Authorization:`Bearer ${token}`}})).status()).toBe(401);
  28 |  }
  29 | });
  30 | 
```