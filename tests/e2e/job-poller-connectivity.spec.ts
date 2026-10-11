import {test,expect} from '@playwright/test';
import {moduleUrl} from '../ts-loader.mjs';
const pollerModule=moduleUrl('services/live/job-poller.ts');

async function observe(page:import('@playwright/test').Page){
  return page.evaluate(()=>{
    const state=(window as unknown as {pollerState:{calls:number;values:number;errors:number;inFlight:number;max:number}}).pollerState;
    return {...state,online:navigator.onLine};
  });
}
async function start(page:import('@playwright/test').Page){
  await page.evaluate(async url=>{
    const {startJobPoller}=await import(url),controller=new AbortController();
    const state={calls:0,values:0,errors:0,inFlight:0,max:0};
    Object.assign(window,{pollerState:state,stopPoller:()=>controller.abort()});
    startJobPoller({signal:controller.signal,isVisible:()=>!document.hidden,
      fetchSummary:(signal:AbortSignal)=>new Promise((resolve,reject)=>{
        state.calls++;state.max=Math.max(state.max,++state.inFlight);
        const settle=()=>{state.inFlight--;signal.removeEventListener('abort',abort);};
        const timer=setTimeout(()=>{settle();resolve({status:'running'});},2500);
        const abort=()=>{clearTimeout(timer);settle();reject(signal.reason);};
        signal.addEventListener('abort',abort,{once:true});
      }),onValue:()=>state.values++,onError:()=>state.errors++,
    });
  },pollerModule);
}

test('C61-25 B13 native navigator offline starts no reads and online resumes once',async({page,context})=>{
  await context.setOffline(true);await start(page);
  await expect.poll(()=>observe(page)).toMatchObject({online:false,calls:0,inFlight:0});
  await page.waitForTimeout(2200);expect((await observe(page)).calls).toBe(0);
  await context.setOffline(false);await expect.poll(()=>observe(page)).toMatchObject({online:true,calls:1,inFlight:1,max:1});
  await page.evaluate(()=>{window.dispatchEvent(new Event('online'));window.dispatchEvent(new Event('online'));});
  expect((await observe(page)).calls).toBe(1);
});

test('C61-25 B13 native offline event aborts quietly and repeated resume stays single',async({page,context})=>{
  await start(page);await expect.poll(()=>observe(page)).toMatchObject({calls:1,inFlight:1});
  await context.setOffline(true);await expect.poll(()=>observe(page)).toMatchObject({online:false,calls:1,inFlight:0,values:0,errors:0});
  await page.waitForTimeout(2200);expect((await observe(page)).calls).toBe(1);
  await context.setOffline(false);await expect.poll(()=>observe(page)).toMatchObject({online:true,calls:2,inFlight:1,max:1,errors:0});
  await page.evaluate(()=>window.dispatchEvent(new Event('online')));expect((await observe(page)).calls).toBe(2);
});

test('C61-25 B16 stopped lifetime ignores native reconnect and has no late value',async({page,context})=>{
  await start(page);await expect.poll(()=>observe(page)).toMatchObject({calls:1,inFlight:1});
  await page.evaluate(()=>(window as unknown as {stopPoller:()=>void}).stopPoller());
  await context.setOffline(true);await context.setOffline(false);await page.waitForTimeout(2700);
  expect(await observe(page)).toMatchObject({online:true,calls:1,inFlight:0,values:0,errors:0,max:1});
});
