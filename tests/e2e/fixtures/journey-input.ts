import {expect,type Locator,type Page,type Response} from '@playwright/test';

export type JourneyInputMode='pointer'|'keyboard';
type Action={kind:string;name:string;tabs:number;focusVisible:boolean;outline:string};

/** Test driver: keyboard mode reaches controls through actual browser tab order. */
export function createJourneyInput(mode:JourneyInputMode='pointer'){
  const actions=new Map<Page,Action[]>(),pointers=new Map<Page,string[]>();
  async function install(page:Page){
    if(mode==='pointer'||pointers.has(page))return;
    pointers.set(page,[]);actions.set(page,[]);
    await page.exposeBinding('__buyerosKeyboardPointer',(_source,type:string)=>pointers.get(page)!.push(type));
    await page.addInitScript(()=>{
      for(const type of ['pointerdown','mousedown','touchstart'])document.addEventListener(type,event=>{
        if(event.isTrusted)void (window as unknown as {__buyerosKeyboardPointer:(type:string)=>Promise<void>}).__buyerosKeyboardPointer(type);
      },true);
    });
  }
  async function reach(target:Locator,kind:string){
    const page=target.page();await expect(target).toBeVisible();await expect(target).toBeEnabled();
    const visited:string[]=[];const end=Date.now()+10_000;let tabs=0;
    while(tabs<=250&&Date.now()<end){
      if(await target.evaluate(element=>element===document.activeElement)){
        const focus=await target.evaluate(element=>{const style=getComputedStyle(element);return {
          name:element.getAttribute('aria-label')??element.textContent?.trim().slice(0,120)??element.tagName,
          focusVisible:element.matches(':focus-visible'),outline:style.outlineStyle,outlineWidth:parseFloat(style.outlineWidth)};});
        expect(focus.focusVisible,`Keyboard focus must be visible on ${focus.name}`).toBe(true);
        expect(focus.outline!=='none'&&focus.outlineWidth>=2,`Visible outline on ${focus.name}`).toBe(true);
        actions.get(page)!.push({kind,name:focus.name,tabs,focusVisible:focus.focusVisible,outline:`${focus.outlineWidth}px ${focus.outline}`});return;
      }
      visited.push(await page.evaluate(()=>{const element=document.activeElement;return `${element?.tagName}:${element?.getAttribute('aria-label')??element?.textContent?.trim().slice(0,80)??''}`;}));
      await page.keyboard.press('Tab');tabs++;
    }
    throw new Error(`Control unreachable by Tab after ${tabs} steps: ${target}; last focus: ${visited.slice(-8).join(' | ')}`);
  }
  return {mode,install,
    async activate(target:Locator){if(mode==='pointer')return target.click();await reach(target,'activate');await target.page().keyboard.press('Enter');},
    async fill(target:Locator,value:string){if(mode==='pointer')return target.fill(value);await reach(target,'type');await target.page().keyboard.press('ControlOrMeta+A');await target.page().keyboard.insertText(value);await expect(target).toHaveValue(value);},
    async check(target:Locator,checked=true){if(mode==='pointer')return checked?target.check():target.uncheck();await reach(target,'checkbox');if(await target.isChecked()!==checked)await target.page().keyboard.press('Space');if(checked)await expect(target).toBeChecked();else await expect(target).not.toBeChecked();},
    async choose(target:Locator,value:string){
      if(mode==='pointer')return target.selectOption(value);await reach(target,'select');
      const options=await target.evaluate(element=>{if(!(element instanceof HTMLSelectElement))throw new Error('Keyboard choice requires a native select');return Array.from(element.options).map(option=>({value:option.value,disabled:option.disabled}));});
      const index=options.findIndex(option=>option.value===value&&!option.disabled);expect(index,`Enabled option ${value}`).toBeGreaterThanOrEqual(0);
      await target.page().keyboard.press('Space');await target.page().keyboard.press('Home');
      const enabled=options.slice(0,index).filter(option=>!option.disabled).length;
      for(let i=0;i<enabled;i++)await target.page().keyboard.press('ArrowDown');
      await target.page().keyboard.press('Enter');await expect(target).toHaveValue(value);
    },
    async verify(page:Page){
      if(mode==='pointer')return null;expect(pointers.get(page),'No trusted pointer input during keyboard journey').toEqual([]);
      const result=actions.get(page)!;expect(result.length).toBeGreaterThan(0);return {mode,actions:result,trustedPointerEvents:pointers.get(page)};
    },
  };
}

/** Await the real persisted preference before choosing a native select value.
 * A native unchanged selection does not emit change; initial English can precede
 * an existing zh-HK preference. This observes HTTP/DOM only, never writes storage.
 */
export function observeWorkspaceLocale(page:Page,workspace:string){
 const reads:Promise<{body:{data:{locale:string}}}|{error:unknown}>[]=[];
 const record=(response:Response)=>{
  if(response.request().method()==='GET'&&response.status()===200&&new URL(response.url()).pathname===`/v1/workspaces/${workspace}/preferences`){
   // Buffer while this document still owns the response. A callback navigation
   // can evict Chromium's response body before a later settle() call.
   reads.push(response.json().then(body=>({body}),error=>({error})));
  }
 };
 page.on('response',record);
 return {
  async settle(){
   await expect.poll(()=>reads.length,{timeout:30_000,message:'Real fixture workspace preference read must complete before native language choice'}).toBeGreaterThan(0);
   const read=await reads.at(-1)!;if('error' in read)throw read.error;
   const body=read.body;expect(['en','zh-HK']).toContain(body.data.locale);
   const saved=await page.evaluate(()=>{try{return localStorage.getItem('buyeros.locale');}catch{return null;}});
   const expected=saved==='en'||saved==='zh-HK'?saved:body.data.locale;
   await expect(page.locator('header select')).toHaveValue(expected,{timeout:30_000});
  },
  dispose(){page.off('response',record);},
 };
}
