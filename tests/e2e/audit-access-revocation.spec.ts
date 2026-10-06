import {expect,test,type Page} from '@playwright/test';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {resolve} from 'node:path';
import {signInWorkbench,workspace,project,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';
const other='e0000000-0000-4000-8000-000000000101';
const member='e0000000-0000-4000-8000-000000000003';
async function fixture(action='inspect',script='audit_access_revocation.py'){
 const cwd=resolve('services/worker');return JSON.parse((await promisify(execFile)(resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python'),[`tests/fixtures/${script}`,action],{cwd,timeout:30_000})).stdout);
}
async function changeAccess(page:Page,active=false,roles=['operator']){
 const response=await page.request.patch(`http://127.0.0.1:8000/v1/workspaces/${workspace}/memberships/${member}`,{headers:{Authorization:'Bearer fixture-admin','If-Match':'"1"','Idempotency-Key':crypto.randomUUID()},data:{active,roles,reason:'U05 fictional access change'}});
 expect(response.status()).toBe(200);return (await response.json()).data;
}
async function denied(page:Page){
 const headers={Authorization:'Bearer fixture-access'};
 const read=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/projects`,{headers});
 expect(read.status()).toBe(404);expect((await read.json()).code).toBe('NOT_FOUND');
 const write=await page.request.patch(`http://127.0.0.1:8000/v1/workspaces/${workspace}/preferences`,{headers:{...headers,'If-Match':'"1"','Idempotency-Key':crypto.randomUUID()},data:{locale:'zh-HK'}});
 expect(write.status()).toBe(404);return {read:read.status(),write:write.status()};
}
async function cleared(page:Page){
 await expect(page.getByRole('combobox',{name:/^(Project|專案)$/})).toHaveCount(0);
 await expect(page.getByRole('combobox',{name:/^(Workspace|工作區)$/})).toHaveValue('');
 await expect(page.getByRole('region',{name:/^(Buyer results|買家結果)$/})).toHaveCount(0);
 const url=new URL(page.url());for(const key of ['workspace','project','profile','bulk_job','bulk_manifest','draft','draft_job'])expect(url.searchParams.has(key)).toBe(false);
 await expect(page.getByRole('button',{name:/^(Sign out|登出)$/})).toBeVisible();
}
async function proof(name:string,value:unknown){await test.info().attach(name,{body:JSON.stringify(value,null,2),contentType:'application/json'});}
test.beforeEach(async({page})=>{await page.addInitScript(()=>localStorage.setItem('buyeros.locale','en'));await resetWorkbenchFixtureRateWindows();await fixture('reset');});
test.afterEach(async()=>{await fixture('cleanup');});

for(const locale of ['en','zh-HK'] as const)test(`U05 revoked open-page read clears private scope ${locale}`,async({page})=>{
 if(locale==='zh-HK')await page.setViewportSize({width:390,height:844});
 await signInWorkbench(page,true,'access',`/app/discover?workspace=${workspace}&project=${project}`);
 await page.getByRole('combobox',{name:/^(Language|語言)$/}).first().selectOption(locale);
 const buyers=page.getByRole('region',{name:/^(Buyer results|買家結果)$/});await expect(buyers.getByRole('checkbox',{name:/^(Select |選取 )/}).first()).toBeVisible();
 const before=await fixture();const changed=await changeAccess(page);const statuses=await denied(page);
 const failed=page.waitForResponse(r=>r.url().includes(`/workspaces/${workspace}/`)&&r.status()===404);
 await buyers.getByRole('button',{name:/^(Refresh results|更新結果)$/}).click();await failed;await cleared(page);
 await page.getByRole('combobox',{name:/^(Language|語言)$/}).first().selectOption(locale==='en'?'zh-HK':'en');
 await page.getByRole('button',{name:/^(Check access again|重新檢查存取)$/}).click();await cleared(page);
 const after=await fixture();expect(after.active).toBe(false);expect(after.version).toBe(2);expect(after.users).toBe(before.users);expect(after.memberships).toBe(before.memberships);
 await page.getByRole('combobox',{name:/^(Language|語言)$/}).first().selectOption(locale);await expect(page.locator('html')).toHaveAttribute('lang',locale);
 await proof(`U05 revoked read ${locale}`,{before,changed,statuses,after});await page.screenshot({path:`test-results/u05-revoked-${locale}.png`,fullPage:true});
});

test('U05 explicit recheck cancels held pre-withdrawal buyer rows',async({page})=>{
 await signInWorkbench(page,true,'access',`/app/discover?workspace=${workspace}&project=${project}`);
 const buyers=page.getByRole('region',{name:'Buyer results',exact:true});await expect(buyers.getByRole('checkbox',{name:/^Select /}).first()).toBeVisible();
 let release=()=>{},started=()=>{},completed=()=>{};const finished=new Promise<void>(r=>completed=r),held=new Promise<void>(r=>release=r),received=new Promise<void>(r=>started=r);
 await page.route(`**/v1/workspaces/${workspace}/projects/${project}/buyers?**`,async route=>{const response=await route.fetch();expect(response.status()).toBe(200);started();await held;await route.fulfill({response}).catch(()=>{});completed();});
 try{await buyers.getByRole('button',{name:'Refresh results',exact:true}).click();await received;await changeAccess(page);
 await page.getByRole('button',{name:'Check access again',exact:true}).click();await cleared(page);release();await finished;await cleared(page);
 await expect(page.getByText('Fixture company',{exact:false})).toHaveCount(0);
 await proof('U05 held rows',{active:(await fixture()).active,old_response_status:200,scope_cleared:true});
 }finally{release();}
});

test('U05 older access check cannot restore withdrawn A after another recheck',async({page})=>{
 await signInWorkbench(page,true,'access');let release=()=>{},started=()=>{},completed=()=>{},hold=true;
 const finished=new Promise<void>(r=>completed=r),held=new Promise<void>(r=>release=r),received=new Promise<void>(r=>started=r);
 await page.route('**/v1/workspaces?**',async route=>{if(!hold)return route.continue();hold=false;const response=await route.fetch();expect(response.status()).toBe(200);started();await held;await route.fulfill({response}).catch(()=>{});completed();});
 try{await page.getByRole('button',{name:'Check access again',exact:true}).click();await received;await changeAccess(page);
 await page.getByRole('button',{name:'Check access again',exact:true}).click();await cleared(page);release();await finished;await cleared(page);
 await expect(page.getByRole('combobox',{name:'Workspace',exact:true}).getByRole('option',{name:'E2E fixture workspace',exact:true})).toHaveCount(0);
 }finally{release();}
});

test('U05 delayed A access result cannot clear current B',async({page})=>{
 await signInWorkbench(page,true,'access');let release=()=>{},started=()=>{},completed=()=>{},hold=true;
 const finished=new Promise<void>(r=>completed=r),held=new Promise<void>(r=>release=r),received=new Promise<void>(r=>started=r);
 await changeAccess(page);
 await page.route('**/v1/workspaces?**',async route=>{if(!hold)return route.continue();hold=false;const response=await route.fetch();started();await held;await route.fulfill({response}).catch(()=>{});completed();});
 try{await page.getByRole('button',{name:'Check access again',exact:true}).click();await received;
 await page.getByRole('combobox',{name:'Workspace',exact:true}).selectOption(other);
 await expect(page.getByRole('combobox',{name:'Workspace',exact:true})).toHaveValue(other);release();await finished;
 await expect(page.getByRole('combobox',{name:'Workspace',exact:true})).toHaveValue(other);
 expect(new URL(page.url()).searchParams.get('workspace')).toBe(other);
 }finally{release();}
});

test('U05 denial during a held access check schedules a fresh membership read',async({page})=>{
 await signInWorkbench(page,true,'access',`/app/discover?workspace=${workspace}&project=${project}`);
 const buyers=page.getByRole('region',{name:'Buyer results',exact:true});await expect(buyers.getByRole('checkbox',{name:/^Select /}).first()).toBeVisible();
 let release=()=>{},started=()=>{},completed=()=>{},hold=true;
 const held=new Promise<void>(r=>release=r),received=new Promise<void>(r=>started=r),finished=new Promise<void>(r=>completed=r);
 await page.route('**/v1/workspaces?**',async route=>{if(!hold)return route.continue();hold=false;const response=await route.fetch();expect(response.status()).toBe(200);started();await held;await route.fulfill({response}).catch(()=>{});completed();});
 try{await page.getByRole('button',{name:'Check access again',exact:true}).click();await received;await changeAccess(page);
 const denied=page.waitForResponse(r=>r.url().includes(`/workspaces/${workspace}/`)&&r.status()===404);
 await buyers.getByRole('button',{name:'Refresh results',exact:true}).click();await denied;
 release();await finished;await cleared(page);
 await proof('U05 denial while checking',{active:(await fixture()).active,pre_withdrawal_directory:200,scope_cleared:true});
 }finally{release();}
});

test('U05 forbidden save rechecks downgraded role while retaining dirty Unicode draft',async({page})=>{
 const seeded=await fixture('create','audit_drafts.py');await signInWorkbench(page,true,'access',`/app/outreach?workspace=${workspace}&project=${project}&draft=${seeded.draft}&draft_job=${seeded.job}`);
 const editor=page.getByRole('region',{name:'Open draft',exact:true});await expect(editor.getByRole('textbox',{name:'Subject',exact:true})).toHaveValue(seeded.subject);
 await editor.getByRole('textbox',{name:'Subject',exact:true}).fill('未保存主旨🙂');await editor.getByRole('textbox',{name:'Body',exact:true}).fill('保留本地內容🙂');await editor.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');
 await changeAccess(page,true,['viewer']);const fail=page.waitForResponse(r=>r.request().method()==='PATCH'&&r.url().includes('/drafts/')&&r.status()===403);
 await editor.getByRole('button',{name:'Save revision',exact:true}).click();await fail;
 await expect(page.getByText('Role: viewer',{exact:true})).toBeVisible();await expect(page.getByRole('combobox',{name:'Workspace',exact:true})).toHaveValue(workspace);
 await expect(editor.getByRole('textbox',{name:'Subject',exact:true})).toHaveValue('未保存主旨🙂');await expect(editor.getByRole('textbox',{name:'Body',exact:true})).toHaveValue('保留本地內容🙂');await expect(editor.getByRole('combobox',{name:'Language',exact:true})).toHaveValue('zh-HK');await expect(editor).toHaveAttribute('data-live-unsaved','true');
 const stored=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${seeded.draft}`,{headers:{Authorization:'Bearer fixture-admin'}});expect(stored.status()).toBe(200);expect((await stored.json()).data.subject).toBe(seeded.subject);
 await proof('U05 denied write unchanged',{membership:await fixture(),stored:(await stored.json()).data});
});

test('U05 revoked save is denied without creating a revision or replaying',async({page})=>{
 const seeded=await fixture('create','audit_drafts.py');await signInWorkbench(page,true,'access',`/app/outreach?workspace=${workspace}&project=${project}&draft=${seeded.draft}&draft_job=${seeded.job}`);
 const editor=page.getByRole('region',{name:'Open draft',exact:true});await expect(editor.getByRole('textbox',{name:'Subject',exact:true})).toHaveValue(seeded.subject);
 await editor.getByRole('textbox',{name:'Subject',exact:true}).fill('未保存主旨🙂');await editor.getByRole('textbox',{name:'Body',exact:true}).fill('保留本地內容🙂');await editor.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');
 let writes=0;page.on('request',r=>{if(r.method()==='PATCH'&&r.url().includes('/drafts/'))writes++;});
 await changeAccess(page);const fail=page.waitForResponse(r=>r.request().method()==='PATCH'&&r.url().includes('/drafts/')&&r.status()===404);
 await editor.getByRole('button',{name:'Save revision',exact:true}).click();await fail;
 await cleared(page);expect(writes).toBe(1);
 const stored=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${seeded.draft}`,{headers:{Authorization:'Bearer fixture-admin'}});expect(stored.status()).toBe(200);expect((await stored.json()).data.subject).toBe(seeded.subject);expect((await stored.json()).data.revision_number).toBe(1);
 await proof('U05 revoked write unchanged',{membership:await fixture(),stored:(await stored.json()).data});
});

test('U05 missing job does not revoke an active membership',async({page})=>{
 let checks=0;page.on('request',r=>{if(new URL(r.url()).pathname==='/v1/workspaces')checks++;});
 await signInWorkbench(page,true,'access');const before=checks;
 await page.getByRole('button',{name:'Operations',exact:true}).click();
 const input=page.getByRole('textbox',{name:'Job ID',exact:true});await input.fill('f9999999-0000-4000-8000-000000000000');
 await page.getByRole('button',{name:'Load job',exact:true}).click();await expect.poll(()=>checks).toBeGreaterThan(before);
 await expect(page.getByRole('combobox',{name:'Workspace',exact:true})).toHaveValue(workspace);expect((await fixture()).active).toBe(true);
});

test('U05 failed access recheck preserves scope and supports explicit recovery',async({page})=>{
 await signInWorkbench(page,true,'access');let fail=true;
 await page.route('**/v1/workspaces?**',async route=>{if(!fail)return route.continue();await route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({code:'INTERNAL_ERROR',message:'fixture failure',request_id:'12345678-1234-4123-8123-123456789012',retryable:true})});});
 await page.getByRole('button',{name:'Check access again',exact:true}).click();await expect(page.getByRole('alert').filter({hasText:'Service temporarily unavailable.'})).toBeVisible();
 await expect(page.getByRole('combobox',{name:'Workspace',exact:true})).toHaveValue(workspace);fail=false;
 await page.getByRole('button',{name:'Check access again',exact:true}).click();await expect(page.getByRole('alert').filter({hasText:'Service temporarily unavailable.'})).toHaveCount(0);
 expect((await fixture()).active).toBe(true);
});
