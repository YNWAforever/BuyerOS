import {expect,test} from '@playwright/test';
import {signInWorkbench,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';
const requestId='b7aea690-a1a4-4c58-b85e-27dc02a7e7c8';
const url='http://localhost:5173/v1/workspaces?**';
test.beforeEach(async()=>{await resetWorkbenchFixtureRateWindows();});
async function outage(page: import('@playwright/test').Page) {
  await page.route(url,route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({
    code:'TEMPORARILY_UNAVAILABLE',message:'fixture outage',request_id:requestId,retryable:true})}));
  await signInWorkbench(page,false);
  await page.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');
}
test('N11-03 N11-14 clipboard success is confirmed after the write resolves',async({page})=>{
  await page.addInitScript(()=>Object.defineProperty(navigator,'clipboard',{value:{writeText:async(text:string)=>{
    (window as unknown as {supportText:string}).supportText=text;
  }}}));
  await outage(page);
  await page.getByRole('button',{name:'複製診斷資料'}).click();
  await expect(page.getByRole('status').filter({hasText:'診斷資料已複製'})).toBeVisible();
  const text=await page.evaluate(()=>(window as unknown as {supportText:string}).supportText);
  const data=JSON.parse(text);expect(data.request_id).toBe(requestId);
  expect(Object.keys(data).sort()).toEqual(['login_method','project_id','request_id','time','workspace_id']);
  expect(text).not.toMatch(/token|email|42P01|user_identities|fixture outage/);
  await expect(page.getByRole('button',{name:'複製診斷資料'})).toBeFocused();
});
for(const failure of ['missing','denied']) test(`N11-03 N11-14 ${failure} clipboard offers selectable diagnostics`,async({page})=>{
  await page.addInitScript(mode=>Object.defineProperty(navigator,'clipboard',{value:mode==='missing'?undefined:{
    writeText:async()=>{throw new DOMException('denied','NotAllowedError');}
  }}),failure);
  const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));
  await outage(page);await page.getByRole('button',{name:'複製診斷資料'}).click();
  await expect(page.getByRole('status').filter({hasText:'未能複製，請選取以下診斷資料。'})).toBeVisible();
  const details=page.getByRole('textbox',{name:'診斷資料',exact:true});
  await expect(details).toHaveValue(new RegExp(requestId));
  await details.focus();await details.press('ControlOrMeta+A');
  expect(await details.evaluate(el=>(el as HTMLTextAreaElement).selectionEnd)).toBeGreaterThan(0);
  expect(errors).toEqual([]);
});
test('N11-04 empty membership keeps retry disabled while one read is pending',async({page})=>{
  let reads=0;let release:()=>void=()=>{};const held=new Promise<void>(resolve=>{release=resolve;});
  await page.route(url,async route=>{
    reads++;if(reads>1)await held;
    return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({data_mode:'live',request_id:requestId,
      data:{items:[],offset:0,limit:100,total:0}})});
  });
  try {
    await signInWorkbench(page,false);
    const retry=page.getByRole('button',{name:'Check access again',exact:true});await retry.click();
    await expect(retry).toBeDisabled();await expect(page.getByRole('status').filter({hasText:'Checking access…'})).toBeVisible();
    await expect.poll(()=>reads).toBe(2);await retry.press('Enter');expect(reads).toBe(2);
  } finally {release();}
  await expect(page.getByRole('button',{name:'Check access again',exact:true})).toBeEnabled();
  await expect(page.getByText('No workspace membership. Ask an administrator for access.')).toBeVisible();
  await expect(page.getByText(/Last checked:/)).toBeVisible();
});
