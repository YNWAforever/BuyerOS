import {expect,test} from '@playwright/test';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {resolve} from 'node:path';
import {signInWorkbench,workspace,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';
const action='Select a provider and complete bounded verification before activation.';
const disabled='Keep delivery disabled. Use authorized exports and manual outcomes.';
test.beforeEach(async()=>{await resetWorkbenchFixtureRateWindows();});

test('R05 provider responsibility and actionable status are available to a reviewer without admin reads',async({page})=>{
 const readiness:string[]=[];page.on('request',r=>{if(new URL(r.url()).pathname.endsWith('/readiness'))readiness.push(r.url());});
 await signInWorkbench(page);await page.getByRole('button',{name:'Operations',exact:true}).click();
 const integrations=page.getByRole('region',{name:'Integrations',exact:true});
 await expect(integrations.getByText('Responsible role: Release owner',{exact:true})).toHaveCount(5);
 for(const name of ['research','contact_enrichment','draft_generation'])await expect(integrations.getByRole('region',{name:`Capability: ${name}`,exact:true})).toContainText(action);
 for(const name of ['mailbox','crm'])await expect(integrations.getByRole('region',{name:`Capability: ${name}`,exact:true})).toContainText(disabled);
 await expect(integrations.locator('time')).toHaveCount(5);expect(readiness).toHaveLength(0);
 await expect(page.getByRole('region',{name:'Readiness',exact:true})).toHaveCount(0);
 await page.screenshot({path:'test-results/q11-capability-guidance/reviewer-en.png',fullPage:true});
});

test('R05 admin readiness guidance and malformed capability fail closed in zh-HK mobile',async({page})=>{
 await page.route('**/v1/workspaces/*/capabilities',async route=>{const response=await route.fetch();const body=await response.json();body.data.items[0]={...body.data.items[0],status:'ready',owner_role:null,next_action:null,checked_at:'invalid'};await route.fulfill({response,json:body});});
 await signInWorkbench(page,true,'admin');await page.getByRole('button',{name:'Operations',exact:true}).click();
 await page.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');await page.setViewportSize({width:390,height:844});
 const integrations=page.getByRole('region',{name:'整合服務',exact:true});
 await expect(integrations).toContainText('能力驗證資料無法確認。請保持停用並聯絡發佈負責人。');
 await expect(integrations.getByRole('region',{name:'能力：研究',exact:true})).not.toContainText('就緒');
 const readiness=page.getByRole('region',{name:'就緒狀態',exact:true});await expect(readiness).toContainText('責任角色：SRE');await expect(readiness).toContainText('檢查工作程序與佇列狀態，再重新整理。');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
 await page.screenshot({path:'test-results/q11-capability-guidance/admin-zh-mobile.png',fullPage:true});
 const saved=page.waitForResponse(r=>r.request().method()==='PATCH'&&new URL(r.url()).pathname.endsWith('/preferences'));await page.getByRole('combobox',{name:'語言',exact:true}).selectOption('en');expect((await saved).status()).toBe(200);
});

test('R05 new workspace hides old capability state while its read is pending and rejects A-B-A late advice',async({page})=>{
 const cwd=resolve('services/worker'),python=resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');await promisify(execFile)(python,['tests/fixtures/audit_jobs.py','0'],{cwd,timeout:30000});
 let release:()=>void=()=>{},received:()=>void=()=>{};const held=new Promise<void>(r=>release=r),started=new Promise<void>(r=>received=r);
 const other='e0000000-0000-4000-8000-000000000101';
 await page.route(`**/v1/workspaces/${other}/capabilities`,async route=>{const response=await route.fetch();const body=await response.json();body.data.items.forEach((item:{next_action:string})=>item.next_action='OLD WORKSPACE ADVICE');received();await held;await route.fulfill({response,json:body}).catch(()=>{});});
 await signInWorkbench(page);await page.getByRole('button',{name:'Operations',exact:true}).click();const integrations=page.getByRole('region',{name:'Integrations',exact:true});await expect(integrations).toContainText(action);
 await page.getByRole('combobox',{name:'Workspace',exact:true}).selectOption(other);await started;
 await expect(integrations).not.toContainText(action);await expect(integrations).toContainText('Loading capabilities…');
 await page.getByRole('combobox',{name:'Workspace',exact:true}).selectOption(workspace);await expect(integrations).toContainText(action);release();await page.waitForTimeout(300);await expect(integrations).not.toContainText('OLD WORKSPACE ADVICE');
});


test('R05 failed capability read remains unavailable and manual refresh recovers with reads only',async({page})=>{
 let reads=0;const writes:string[]=[];page.on('request',r=>{if(new URL(r.url()).pathname.endsWith('/capabilities')&&r.method()!=='GET')writes.push(r.method());});
 await page.route('**/v1/workspaces/*/capabilities',async route=>{reads++;if(reads===1)await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({code:'INTERNAL_ERROR',message:'fixture unavailable',request_id:'e0000000-0000-4000-8000-000000000011',retryable:true})});else await route.continue();});
 await signInWorkbench(page);await page.getByRole('button',{name:'Operations',exact:true}).click();const integrations=page.getByRole('region',{name:'Integrations',exact:true});
 await expect(integrations.getByRole('alert')).toContainText('Service temporarily unavailable');await expect(integrations).toContainText('Capability verification is unavailable.');
 await integrations.getByRole('button',{name:'Refresh service status',exact:true}).click();await expect(integrations.getByText('Responsible role: Release owner',{exact:true})).toHaveCount(5);await expect(integrations.getByRole('alert')).toHaveCount(0);expect(reads).toBe(2);expect(writes).toHaveLength(0);
});


test('R05 a ready label contradicting provider blockers remains unavailable',async({page})=>{
 await page.route('**/v1/workspaces/*/capabilities',async route=>{const response=await route.fetch();const body=await response.json();body.data.items[0].status='ready';await route.fulfill({response,json:body});});
 await signInWorkbench(page);await page.getByRole('button',{name:'Operations',exact:true}).click();const capability=page.getByRole('region',{name:'Capability: research',exact:true});
 await expect(capability).toContainText('Capability verification is unavailable.');await expect(capability.getByText('research: Ready',{exact:true})).toHaveCount(0);
});
