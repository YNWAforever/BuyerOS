# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-keyboard.spec.ts >> T30 keyboard en desktop UI-created offer through research, grounded addressed approval, export and outcome on one dataset
- Location: tests\e2e\fixtures\staff-journey.ts:105:1

# Error details

```
Error: expect(locator).toHaveValue(expected) failed

Locator: getByLabel('Must have', { exact: true })
Expected: "industrial sensors"
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toHaveValue" getByLabel('Must have', { exact: true }) with timeout 5000ms
  - waiting for getByLabel('Must have', { exact: true })

```

```yaml
- main:
  - text: FIMMICK BuyerOS Live workspace Language
  - combobox "Language":
    - option "English" [selected]
    - option "繁體中文"
  - button "Sign out"
  - navigation "BuyerOS sections":
    - button "Overview"
    - button "Offer"
    - button "Buyers"
    - button "Results"
    - button "Research runs"
    - button "Drafts"
    - button "Settings"
    - button "Operations"
  - region "Workspace selection":
    - heading "Workspaces" [level=2]
    - text: Workspace
    - combobox "Workspace":
      - option "Choose workspace"
      - option "E2E fixture workspace" [selected]
    - paragraph: "Role: operator"
  - region "Project selection":
    - heading "Projects" [level=2]
    - text: Project
    - combobox "Project":
      - option "Choose project"
      - option "Buyer Fixture Project"
      - option "Run Fixture Project" [selected]
    - button "New project"
    - button "Edit offer"
  - region "Create project":
    - heading "Create project" [level=2]
    - navigation "Offer steps":
      - button "1 Your offer"
      - button "2 Target buyers"
      - button "3 Buyer requirements"
      - button "4 Review and save" [disabled]
    - heading "Buyer requirements" [level=3]
    - text: Must have
    - textbox "Must have": industrial sensors
    - text: Nice to have
    - textbox "Nice to have"
    - text: Exclude
    - textbox "Exclude"
    - checkbox "I confirm these buyer requirements. Changes create a new profile version."
    - text: I confirm these buyer requirements. Changes create a new profile version.
    - button "Back"
    - button "Continue"
```

# Test source

```ts
  1  | import {expect,type Locator,type Page} from '@playwright/test';
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
  37 |     async activate(target:Locator){if(mode==='pointer')return target.click();await reach(target,'activate');await target.page().keyboard.press('Enter');},
> 38 |     async fill(target:Locator,value:string){if(mode==='pointer')return target.fill(value);await reach(target,'type');await target.page().keyboard.press('ControlOrMeta+A');await target.page().keyboard.insertText(value);await expect(target).toHaveValue(value);},
     |                                                                                                                                                                                                                                                ^ Error: expect(locator).toHaveValue(expected) failed
  39 |     async check(target:Locator,checked=true){if(mode==='pointer')return checked?target.check():target.uncheck();await reach(target,'checkbox');if(await target.isChecked()!==checked)await target.page().keyboard.press('Space');if(checked)await expect(target).toBeChecked();else await expect(target).not.toBeChecked();},
  40 |     async choose(target:Locator,value:string){
  41 |       if(mode==='pointer')return target.selectOption(value);await reach(target,'select');
  42 |       const options=await target.evaluate(element=>{if(!(element instanceof HTMLSelectElement))throw new Error('Keyboard choice requires a native select');return Array.from(element.options).map(option=>({value:option.value,disabled:option.disabled}));});
  43 |       const index=options.findIndex(option=>option.value===value&&!option.disabled);expect(index,`Enabled option ${value}`).toBeGreaterThanOrEqual(0);
  44 |       await target.page().keyboard.press('Home');
  45 |       const enabled=options.slice(0,index).filter(option=>!option.disabled).length;
  46 |       for(let i=0;i<enabled;i++)await target.page().keyboard.press('ArrowDown');
  47 |       await target.page().keyboard.press('Tab');await expect(target).toHaveValue(value);
  48 |     },
  49 |     async verify(page:Page){
  50 |       if(mode==='pointer')return null;expect(pointers.get(page),'No trusted pointer input during keyboard journey').toEqual([]);
  51 |       const result=actions.get(page)!;expect(result.length).toBeGreaterThan(0);return {mode,actions:result,trustedPointerEvents:pointers.get(page)};
  52 |     },
  53 |   };
  54 | }
  55 | 
```