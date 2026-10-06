import {expect,test,type Page} from '@playwright/test';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {resolve} from 'node:path';
import {writeFileSync} from 'node:fs';
import {signInWorkbench,workspace,project,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';
async function fixture(...args:string[]){const cwd=resolve('services/worker');return JSON.parse((await promisify(execFile)(resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python'),['tests/fixtures/audit_drafts.py',...args],{cwd,timeout:30_000})).stdout);}
async function enter(page:Page){await resetWorkbenchFixtureRateWindows();const seeded=await fixture('create');await signInWorkbench(page,true,'access',`/app/outreach?workspace=${workspace}&project=${project}&draft=${seeded.draft}&draft_job=${seeded.job}`);const editor=page.getByRole('region',{name:'Open draft',exact:true});await expect(editor.getByRole('textbox',{name:'Subject',exact:true})).toHaveValue(seeded.subject);return {seeded,editor};}
async function otherDraftButton(page:Page,subject:string){
  const list=page.getByRole('region',{name:'Draft list'}),button=list.locator('div.inline').filter({hasText:subject}).getByRole('button',{name:'Open draft'});
  for(let i=0;i<100;i++){if(await button.count()){await expect(button).toBeVisible();return button;}const range=list.locator('p').first(),before=await range.innerText();await expect(list.getByRole('button',{name:'Next page',exact:true})).toBeEnabled();await list.getByRole('button',{name:'Next page',exact:true}).click();await expect(range).not.toHaveText(before);}
  throw new Error('Fictional target draft was not found through actual list pagination');
}
async function dirty(page:Page){const editor=page.getByRole('region',{name:'Open draft',exact:true});await editor.getByRole('textbox',{name:'Subject',exact:true}).fill('Local unsaved subject');await editor.getByRole('textbox',{name:'Body',exact:true}).fill('Local unsaved body');await editor.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');}
async function kept(page:Page){const editor=page.getByRole('region',{name:'Open draft',exact:true});await expect(editor.getByRole('textbox',{name:'Subject',exact:true})).toHaveValue('Local unsaved subject');await expect(editor.getByRole('textbox',{name:'Body',exact:true})).toHaveValue('Local unsaved body');await expect(editor.getByRole('combobox',{name:'Language',exact:true})).toHaveValue('zh-HK');await expect(editor).toHaveAttribute('data-live-unsaved','true');}
for(const action of ['Refresh draft','Open draft','Refresh job'])test(`D02 ${action} Cancel preserves all dirty fields; Discard is explicit`,async({page})=>{
  const {seeded,editor}=await enter(page);await dirty(page);if(action==='Refresh job')await fixture('complete',seeded.job);
  const trigger=action==='Open draft'?await otherDraftButton(page,seeded.other_subject):page.getByRole('button',{name:action,exact:true});
  await trigger.click();const dialog=page.getByRole('dialog',{name:'Unsaved draft changes'});await expect(dialog).toBeVisible();await dialog.getByRole('button',{name:'Cancel',exact:true}).click();await kept(page);await expect(trigger).toBeFocused();
  await trigger.click();await page.keyboard.press('Escape');await kept(page);
  await trigger.click();await dialog.getByRole('button',{name:'Discard',exact:true}).click();await expect(editor).not.toHaveAttribute('data-live-unsaved','true');
  await expect(editor.getByRole('textbox',{name:'Subject',exact:true})).toHaveValue(action==='Refresh draft'?seeded.subject:seeded.other_subject);
});
test('D02 Save is awaited before opening another draft and persists one revision',async({page})=>{
  const {seeded,editor}=await enter(page);await dirty(page);let release:()=>void=()=>{};const held=new Promise<void>(r=>release=r);let committed=false;
  await page.route(`**/v1/workspaces/${workspace}/drafts/${seeded.draft}`,async route=>{if(route.request().method()!=='PATCH')return route.continue();const response=await route.fetch();expect(response.status()).toBe(200);committed=true;await held;await route.fulfill({response});});
  await (await otherDraftButton(page,seeded.other_subject)).click();await page.getByRole('dialog').getByRole('button',{name:'Save',exact:true}).click();await expect.poll(()=>committed).toBe(true);await expect(editor.getByRole('textbox',{name:'Subject',exact:true})).toHaveValue('Local unsaved subject');release();
  await expect(editor.getByRole('textbox',{name:'Subject',exact:true})).toHaveValue(seeded.other_subject);
  const saved=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${seeded.draft}`,{headers:{Authorization:'Bearer fixture-access'}});expect(saved.status()).toBe(200);const data=(await saved.json()).data;expect(data.revision_number).toBe(2);expect(data.body).toBe('Local unsaved body');expect(data.language).toBe('zh-HK');
});
for(const status of [401,412,503])test(`D02 failed Save ${status} keeps buffer and dirty baseline`,async({page})=>{
  const {seeded,editor}=await enter(page);await dirty(page);const revision=await editor.getAttribute('data-baseline-revision'),version=await editor.getAttribute('data-baseline-version');
  if(status===412){const changed=await page.request.patch(`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${seeded.draft}`,{headers:{Authorization:'Bearer fixture-access','If-Match':'"1"','Idempotency-Key':`audit-other-${seeded.draft}`},data:{subject:'Remote changed subject',body:'Remote changed body'}});expect(changed.status()).toBe(200);}
  else await page.route(`**/v1/workspaces/${workspace}/drafts/${seeded.draft}`,route=>route.request().method()==='PATCH'?route.fulfill({status,contentType:'application/json',body:JSON.stringify({code:status===401?'UNAUTHORIZED':'SERVICE_UNAVAILABLE',request_id:'11111111-1111-4111-8111-111111111111',retryable:true})}):route.continue());
  await page.getByRole('button',{name:'Refresh draft',exact:true}).click();await page.getByRole('dialog').getByRole('button',{name:'Save',exact:true}).click();await expect(page.getByRole('alert').first()).toBeVisible();await kept(page);await expect(editor).toHaveAttribute('data-baseline-revision',revision!);await expect(editor).toHaveAttribute('data-baseline-version',version!);
  if(status===412){await expect(page.getByRole('region',{name:'Draft conflict comparison'})).toContainText('Remote changed subject');await expect(page.getByRole('button',{name:'Copy local content'})).toBeVisible();await page.context().grantPermissions(['clipboard-read','clipboard-write']);await page.getByRole('button',{name:'Copy local content'}).click();const copied=await page.evaluate(()=>navigator.clipboard.readText());writeFileSync('test-results/audit-draft-clipboard.json',JSON.stringify({platform:process.platform,raw:copied,normalized:copied.replace(/\r\n/g,'\n')},null,2));await expect.poll(async()=>(await page.evaluate(()=>navigator.clipboard.readText())).replace(/\r\n/g,'\n')).toBe('Local unsaved subject\nLocal unsaved body\nzh-HK');await kept(page);}
  await page.screenshot({path:`test-results/audit-draft-failure-${status}.png`,fullPage:true});
});

test('D02 Refresh does not overwrite the unsaved buffer before a decision',async({page})=>{
  const {seeded,editor}=await enter(page);await dirty(page);
  const response=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith(`/drafts/${seeded.draft}`)&&r.request().method()==='GET');
  await page.getByRole('button',{name:'Refresh draft',exact:true}).click();
  // A guarded refresh has not read/replaced content; an old unguarded refresh does.
  const outcome=await Promise.race([page.getByRole('dialog',{name:'Unsaved draft changes'}).waitFor().then(()=>true),response.then(async()=>{await page.waitForTimeout(200);return false;})]);
  if(outcome)await page.getByRole('dialog').getByRole('button',{name:'Cancel',exact:true}).click();
  await expect(editor.getByRole('textbox',{name:'Body',exact:true})).toHaveValue('Local unsaved body');await kept(page);
});

test('D02 delayed refresh cannot materialize a draft into a new project scope',async({page})=>{
  const {seeded}=await enter(page);await dirty(page);let release:()=>void=()=>{},received:()=>void=()=>{};const held=new Promise<void>(r=>release=r),started=new Promise<void>(r=>received=r);let first=true;
  await page.route(`**/v1/workspaces/${workspace}/drafts/${seeded.draft}`,async route=>{if(!first||route.request().method()!=='GET')return route.continue();first=false;const response=await route.fetch();received();await held;await route.fulfill({response}).catch(()=>{});});
  await page.getByRole('button',{name:'Refresh draft',exact:true}).click();await page.getByRole('dialog').getByRole('button',{name:'Discard',exact:true}).click();await started;
  page.once('dialog',d=>d.accept());await page.getByRole('combobox',{name:'Project',exact:true}).selectOption('e9100000-0000-4000-8000-000000000001');release();
  await expect(page.getByRole('region',{name:'Open draft',exact:true})).toHaveCount(0);await page.waitForTimeout(300);await expect(page.getByRole('region',{name:'Open draft',exact:true})).toHaveCount(0);
});
test('D02 zh-HK mobile dialog preserves content and keeps all choices visible',async({page})=>{
  await page.setViewportSize({width:390,height:844});await enter(page);await dirty(page);await page.getByRole('combobox',{name:'Language',exact:true}).first().selectOption('zh-HK');
  await page.getByRole('button',{name:'重新整理草稿',exact:true}).click();const dialog=page.getByRole('dialog',{name:'草稿有未儲存的更改'});await expect(dialog).toBeVisible();
  for(const name of ['儲存','捨棄','取消'])await expect(dialog.getByRole('button',{name,exact:true})).toBeVisible();
  const box=await dialog.boundingBox();expect(box).not.toBeNull();expect(box!.x).toBeGreaterThanOrEqual(0);expect(box!.x+box!.width).toBeLessThanOrEqual(390);
  await page.screenshot({path:'test-results/audit-draft-dialog-zh-mobile.png',fullPage:true});await dialog.getByRole('button',{name:'取消',exact:true}).click();
  const editor=page.getByRole('region',{name:'開啟草稿',exact:true});await expect(editor.getByRole('textbox',{name:'內容',exact:true})).toHaveValue('Local unsaved body');await expect(editor).toHaveAttribute('data-live-unsaved','true');
});
