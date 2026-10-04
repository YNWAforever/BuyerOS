# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-access-revocation.spec.ts >> U05 revoked open-page read clears private scope en
- Location: tests\e2e\audit-access-revocation.spec.ts:33:45

# Error details

```
Test timeout of 60000ms exceeded.
```

```
Error: locator.click: Test timeout of 60000ms exceeded.
Call log:
  - waiting for getByRole('button', { name: /^(Sign in|登入)$/ })
    - locator resolved to <button>Sign in</button>
  - attempting click action
    2 × waiting for element to be visible, enabled and stable
      - element is visible, enabled and stable
      - scrolling into view if needed
      - done scrolling
      - <div data-vinext-dev-error-overlay="" id="__vinext_dev_error_overlay_root"></div> intercepts pointer events
    - retrying click action
    - waiting 20ms
    2 × waiting for element to be visible, enabled and stable
      - element is visible, enabled and stable
      - scrolling into view if needed
      - done scrolling
      - <div data-vinext-dev-error-overlay="" id="__vinext_dev_error_overlay_root"></div> intercepts pointer events
    - retrying click action
      - waiting 100ms
    94 × waiting for element to be visible, enabled and stable
       - element is visible, enabled and stable
       - scrolling into view if needed
       - done scrolling
       - <div data-vinext-dev-error-overlay="" id="__vinext_dev_error_overlay_root"></div> intercepts pointer events
     - retrying click action
       - waiting 500ms

```

# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - main [ref=e2]:
    - generic [ref=e3]:
      - text: Language
      - combobox "Language" [ref=e4]:
        - option "English" [selected]
        - option "繁體中文"
    - generic [ref=e5]:
      - heading "FIMMICK BuyerOS" [level=1] [ref=e6]
      - paragraph [ref=e7]: Sign in to access your workspaces.
      - button "Sign in" [ref=e8] [cursor=pointer]
  - dialog "Unhandled Script Error" [ref=e10]:
    - banner [ref=e11]:
      - generic [ref=e12]: Unhandled Script Error
      - generic [ref=e14]:
        - button "Copy Error Info" [ref=e15] [cursor=pointer]
        - button "Dismiss" [ref=e20] [cursor=pointer]: ×
    - generic [ref=e21]:
      - heading [level=2] [ref=e22]
      - generic [ref=e23]:
        - generic [ref=e24]:
          - paragraph [ref=e25]:
            - text: Call Stack
            - generic [ref=e26]: "51"
          - button "Show 9 ignore-listed frame(s)" [ref=e27] [cursor=pointer]:
            - text: Show 9 ignore-listed frame(s)
            - generic [aria-hidden] [ref=e28]: ↕
        - list [ref=e29]:
          - listitem [ref=e30]:
            - generic [ref=e31]: "- A server/client branch `if (typeof window !== 'undefined')`."
          - listitem [ref=e32]:
            - generic [ref=e33]: "- Variable input such as `Date.now()` or `Math.random()` which changes each time it's called."
          - listitem [ref=e34]:
            - generic [ref=e35]: "- Date formatting in a user's locale which doesn't match the server."
          - listitem [ref=e36]:
            - generic [ref=e37]: "- External changing data without sending a snapshot of it along with the HTML."
          - listitem [ref=e38]:
            - generic [ref=e39]: "- Invalid HTML tag nesting."
          - listitem [ref=e40]:
            - generic [ref=e41]: It can also happen if the client has a browser extension installed which messes with the HTML before React loaded.
          - listitem [ref=e42]:
            - generic [ref=e43]: https://react.dev/link/hydration-mismatch
          - listitem [ref=e44]:
            - generic [ref=e45]: ...
          - listitem [ref=e46]:
            - generic [ref=e47]: "<BfcacheSlotBoundary id=\"route:/app...\" content={<Context>}>"
          - listitem [ref=e48]:
            - generic [ref=e49]: <meta>
          - listitem [ref=e50]:
            - generic [ref=e51]: <title>
          - listitem [ref=e52]:
            - generic [ref=e53]: <meta>
          - listitem [ref=e54]:
            - generic [ref=e55]: <link>
          - listitem [ref=e56]:
            - generic [ref=e57]: <link>
          - listitem [ref=e58]:
            - generic [ref=e59]: <meta>
          - listitem [ref=e60]:
            - generic [ref=e61]: <meta>
          - listitem [ref=e62]:
            - generic [ref=e63]: <AwaitAppRenderDependencies>
          - listitem [ref=e64]:
            - generic [ref=e65]: "<GlobalErrorBoundary fallback={function DefaultGlobalError}>"
          - listitem [ref=e66]:
            - generic [ref=e67]: "<ErrorBoundaryInner pathname=\"/app/discover\" fallback={function DefaultGlobalError} ...>"
          - listitem [ref=e68]:
            - generic [ref=e69]: "<ErrorBoundary fallback={function DefaultGlobalError}>"
          - listitem [ref=e70]:
            - generic [ref=e71]: "<ErrorBoundaryInner pathname=\"/app/discover\" resetKey={undefined} fallback={function DefaultGlobalError}>"
          - listitem [ref=e72]:
            - generic [ref=e73]: "<LayoutSegmentProvider providerId=\"layout:/\" segmentMap={{children:[...]}}>"
          - listitem [ref=e74]:
            - generic [ref=e75]: <Slot id="layout:/">
          - listitem [ref=e76]:
            - generic [ref=e77]: "<BfcacheSlotBoundary id=\"layout:/\" content={<Context>}>"
          - listitem [ref=e78]:
            - generic [ref=e79]: <link>
          - listitem [ref=e80]:
            - generic [ref=e81]: <RemoveDuplicateServerCss>
          - listitem [ref=e82]:
            - generic [ref=e83]: <AwaitAppRenderDependencies>
          - listitem [ref=e84]:
            - generic [ref=e85]: <AppComponentDependencyBarrier>
          - listitem [ref=e86]:
            - generic [ref=e87]: <RootLayout>
          - listitem [ref=e88]:
            - generic [ref=e89]: <html
          - listitem [ref=e90]:
            - generic [ref=e91]: + lang="en"
          - listitem [ref=e92]:
            - generic [ref=e93]: "- lang={null}"
          - listitem [ref=e94]:
            - generic [ref=e95]: ">"
          - listitem [ref=e96]:
            - generic [ref=e97]: <body
          - listitem [ref=e98]:
            - generic [ref=e99]: + className="antialiased"
          - listitem [ref=e100]:
            - generic [ref=e101]: "- className={null}"
          - listitem [ref=e102]:
            - generic [ref=e103]: ">"
          - listitem [ref=e104]:
            - generic [ref=e105]: ...
          - listitem [ref=e106]:
            - generic [ref=e107]: <Workspace mode="live">
          - listitem [ref=e108]:
            - generic [ref=e109]: <LiveWorkspace>
          - listitem [ref=e110]:
            - generic [ref=e111]: + <main className="main-shell">
          - listitem [ref=e112]:
            - generic [ref=e113]: ...
```

# Test source

```ts
  1  | import {expect,type Locator,type Page,type Response} from '@playwright/test';
  2  | 
  3  | export type JourneyInputMode='pointer'|'keyboard';
  4  | type Action={kind:string;name:string;tabs:number;focusVisible:boolean;outline:string};
  5  | 
  6  | /** Test driver: keyboard mode reaches controls through actual browser tab order. */
  7  | export function createJourneyInput(mode:JourneyInputMode='pointer'){
  8  |   const actions=new Map<Page,Action[]>(),pointers=new Map<Page,string[]>();
  9  |   async function install(page:Page){
  10 |     if(mode==='pointer'||pointers.has(page))return;
  11 |     pointers.set(page,[]);actions.set(page,[]);
  12 |     await page.exposeBinding('__buyerosKeyboardPointer',(_source,type:string)=>pointers.get(page)!.push(type));
  13 |     await page.addInitScript(()=>{
  14 |       for(const type of ['pointerdown','mousedown','touchstart'])document.addEventListener(type,event=>{
  15 |         if(event.isTrusted)void (window as unknown as {__buyerosKeyboardPointer:(type:string)=>Promise<void>}).__buyerosKeyboardPointer(type);
  16 |       },true);
  17 |     });
  18 |   }
  19 |   async function reach(target:Locator,kind:string){
  20 |     const page=target.page();await expect(target).toBeVisible();await expect(target).toBeEnabled();
  21 |     const visited:string[]=[];const end=Date.now()+10_000;let tabs=0;
  22 |     while(tabs<=250&&Date.now()<end){
  23 |       if(await target.evaluate(element=>element===document.activeElement)){
  24 |         const focus=await target.evaluate(element=>{const style=getComputedStyle(element);return {
  25 |           name:element.getAttribute('aria-label')??element.textContent?.trim().slice(0,120)??element.tagName,
  26 |           focusVisible:element.matches(':focus-visible'),outline:style.outlineStyle,outlineWidth:parseFloat(style.outlineWidth)};});
  27 |         expect(focus.focusVisible,`Keyboard focus must be visible on ${focus.name}`).toBe(true);
  28 |         expect(focus.outline!=='none'&&focus.outlineWidth>=2,`Visible outline on ${focus.name}`).toBe(true);
  29 |         actions.get(page)!.push({kind,name:focus.name,tabs,focusVisible:focus.focusVisible,outline:`${focus.outlineWidth}px ${focus.outline}`});return;
  30 |       }
  31 |       visited.push(await page.evaluate(()=>{const element=document.activeElement;return `${element?.tagName}:${element?.getAttribute('aria-label')??element?.textContent?.trim().slice(0,80)??''}`;}));
  32 |       await page.keyboard.press('Tab');tabs++;
  33 |     }
  34 |     throw new Error(`Control unreachable by Tab after ${tabs} steps: ${target}; last focus: ${visited.slice(-8).join(' | ')}`);
  35 |   }
  36 |   return {mode,install,
> 37 |     async activate(target:Locator){if(mode==='pointer')return target.click();await reach(target,'activate');await target.page().keyboard.press('Enter');},
     |                                                                      ^ Error: locator.click: Test timeout of 60000ms exceeded.
  38 |     async fill(target:Locator,value:string){if(mode==='pointer')return target.fill(value);await reach(target,'type');await target.page().keyboard.press('ControlOrMeta+A');await target.page().keyboard.insertText(value);await expect(target).toHaveValue(value);},
  39 |     async check(target:Locator,checked=true){if(mode==='pointer')return checked?target.check():target.uncheck();await reach(target,'checkbox');if(await target.isChecked()!==checked)await target.page().keyboard.press('Space');if(checked)await expect(target).toBeChecked();else await expect(target).not.toBeChecked();},
  40 |     async choose(target:Locator,value:string){
  41 |       if(mode==='pointer')return target.selectOption(value);await reach(target,'select');
  42 |       const options=await target.evaluate(element=>{if(!(element instanceof HTMLSelectElement))throw new Error('Keyboard choice requires a native select');return Array.from(element.options).map(option=>({value:option.value,disabled:option.disabled}));});
  43 |       const index=options.findIndex(option=>option.value===value&&!option.disabled);expect(index,`Enabled option ${value}`).toBeGreaterThanOrEqual(0);
  44 |       await target.page().keyboard.press('Space');await target.page().keyboard.press('Home');
  45 |       const enabled=options.slice(0,index).filter(option=>!option.disabled).length;
  46 |       for(let i=0;i<enabled;i++)await target.page().keyboard.press('ArrowDown');
  47 |       await target.page().keyboard.press('Enter');await expect(target).toHaveValue(value);
  48 |     },
  49 |     async verify(page:Page){
  50 |       if(mode==='pointer')return null;expect(pointers.get(page),'No trusted pointer input during keyboard journey').toEqual([]);
  51 |       const result=actions.get(page)!;expect(result.length).toBeGreaterThan(0);return {mode,actions:result,trustedPointerEvents:pointers.get(page)};
  52 |     },
  53 |   };
  54 | }
  55 | 
  56 | /** Await the real persisted preference before choosing a native select value.
  57 |  * A native unchanged selection does not emit change; initial English can precede
  58 |  * an existing zh-HK preference. This observes HTTP/DOM only, never writes storage.
  59 |  */
  60 | export function observeWorkspaceLocale(page:Page,workspace:string){
  61 |  const reads:Response[]=[];
  62 |  const record=(response:Response)=>{if(response.request().method()==='GET'&&response.status()===200&&new URL(response.url()).pathname===`/v1/workspaces/${workspace}/preferences`)reads.push(response);};
  63 |  page.on('response',record);
  64 |  return {
  65 |   async settle(){
  66 |    await expect.poll(()=>reads.length,{timeout:30_000,message:'Real fixture workspace preference read must complete before native language choice'}).toBeGreaterThan(0);
  67 |    const body=await reads.at(-1)!.json();expect(['en','zh-HK']).toContain(body.data.locale);
  68 |    const saved=await page.evaluate(()=>{try{return localStorage.getItem('buyeros.locale');}catch{return null;}});
  69 |    const expected=saved==='en'||saved==='zh-HK'?saved:body.data.locale;
  70 |    await expect(page.locator('header select')).toHaveValue(expected,{timeout:30_000});
  71 |   },
  72 |   dispose(){page.off('response',record);},
  73 |  };
  74 | }
  75 | 
```