# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: audit-keyboard.spec.ts >> T30 keyboard zh-HK desktop UI-created offer through research, grounded addressed approval, export and outcome on one dataset
- Location: tests\e2e\fixtures\staff-journey.ts:105:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('region', { name: '開啟草稿', exact: true }).getByRole('button', { name: '儲存版本', exact: true })
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('region', { name: '開啟草稿', exact: true }).getByRole('button', { name: '儲存版本', exact: true }) with timeout 5000ms
  - waiting for getByRole('region', { name: '開啟草稿', exact: true }).getByRole('button', { name: '儲存版本', exact: true })

```

```yaml
- main:
  - text: FIMMICK BuyerOS 正式工作區 語言
  - combobox "語言":
    - option "English"
    - option "繁體中文" [selected]
  - button "登出"
  - navigation "BuyerOS sections":
    - button "總覽"
    - button "產品資料"
    - button "買家"
    - button "結果"
    - button "研究進度"
    - button "草稿"
    - button "設定"
    - button "營運工作台"
  - region "工作區選擇":
    - heading "工作區" [level=2]
    - text: 工作區
    - combobox "工作區":
      - option "選擇工作區"
      - option "E2E fixture workspace" [selected]
      - option "Other audit fixture"
    - paragraph: "角色: 操作員"
  - region "專案選擇":
    - heading "專案" [level=2]
    - text: 專案
    - combobox "專案":
      - option "選擇專案"
      - option "Buyer Fixture Project"
      - option "Run Fixture Project"
      - option "T30 Fictional Seller"
      - option "T30 Fictional Seller"
      - option "T30 Fictional Seller"
      - option "T30 Fictional Seller"
      - option "Q14 project B"
      - option "T30 Fictional Seller"
      - option "T30 Fictional Seller"
      - option "T30 Fictional Seller" [selected]
    - button "新增專案"
    - button "編輯產品資料"
  - region "草稿":
    - heading "草稿" [level=2]
    - paragraph: 準備有證據草稿；發送功能已停用。
    - region "寄件人身份":
      - heading "寄件人身份" [level=3]
      - paragraph: "已審核寄件人: Fixture Alex · T30 Fictional Seller · alex@example.test · sender:8adf56f3-8ed2-4f90-9b47-0e0edb832cd6:1"
    - region "準備有證據草稿":
      - heading "準備有證據草稿" [level=3]
      - paragraph:
        - strong: 免費固定模板
      - paragraph: 模板語言只改變固定標題、開場及結尾；產品事實與來源引用保留原語言，不會自動翻譯。
      - paragraph: 產生後請人手修改草稿；更改須重新審核證據才可批准。
      - paragraph: T30 Fictional Industrial Buyer · 3 · 已接納
      - group "已批准的產品事實":
        - text: 已批准的產品事實
        - checkbox "Industrial sensor platform" [checked]
        - text: Industrial sensor platform
        - checkbox "Fictional monitoring lowers production downtime." [checked]
        - text: Fictional monitoring lowers production downtime.
      - group "支持買家的證據":
        - text: 支持買家的證據
        - checkbox "Fictional distributor lists industrial sensors in a public catalog. · v1" [checked]
        - text: Fictional distributor lists industrial sensors in a public catalog. · v1
      - paragraph: 首次聯絡
      - text: 收件人（可選）
      - combobox "收件人（可選）":
        - option "不指定收件人 — 未指定收件人的草稿"
        - option "recipient@fixture.example.test · v1" [selected]
      - text: 內部工作目的，不會改變模板正文
      - textbox "內部工作目的，不會改變模板正文": Introduce the approved offer
      - text: 模板語言
      - combobox "模板語言":
        - option "English"
        - option "繁體中文" [selected]
      - button "產生已指定收件人的草稿"
    - status:
      - heading "工作狀態" [level=3]
      - paragraph: bc00a90f-1182-4dc8-90f6-4c482c196f38 · completed
      - button "重新整理工作"
    - region "草稿列表":
      - heading "草稿列表" [level=3]
      - paragraph: 1–1 / 1
      - text: 業務簡介：Industrial sensor platform · 草稿 · v1
      - button "開啟草稿"
      - button "上一頁" [disabled]
      - button "下一頁" [disabled]
    - region "開啟草稿":
      - heading "業務簡介：Industrial sensor platform" [level=3]
      - paragraph: "版本: 1 · 草稿 · zh-HK"
      - paragraph: 寄送功能已停用。
      - text: 主旨
      - textbox "主旨": Keyboard invitation😀
      - text: 內容
      - textbox "內容": 你好， Industrial sensor platform Fictional distributor lists industrial sensors 謝謝！
      - text: 語言
      - combobox "語言":
        - option "English"
        - option "繁體中文" [selected]
      - button "儲存修訂"
      - button "準備跟進草稿"
      - heading "陳述及來源" [level=4]
      - paragraph: Industrial sensor platform · d0000000-0000-4000-8000-000000000001
      - paragraph: Fictional monitoring lowers production downtime. · d0000000-0000-4000-8000-000000000002
      - paragraph: Fictional distributor lists industrial sensors in a public catalog. · 6b93f010-1de7-5b23-9ef8-d5089103cb7c
      - region "精確版本審核":
        - heading "精確版本審核" [level=4]
        - paragraph: "版本: 1 · 2d451b7c18dbf4d196dd27da298bf14fbb74bf75e4a4434346dd9513962bef92"
        - paragraph: 審核前須有合資格收件人及現行政策。
        - button "重新整理草稿"
        - button "要求審核此版本" [disabled]
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
> 20 |     const page=target.page();await expect(target).toBeVisible();await expect(target).toBeEnabled();
     |                                                   ^ Error: expect(locator).toBeVisible() failed
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
```