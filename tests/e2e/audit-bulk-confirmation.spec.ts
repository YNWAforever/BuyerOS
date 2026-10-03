import {expect,test} from '@playwright/test';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {resolve} from 'node:path';
import {writeFileSync} from 'node:fs';
import {signInWorkbench,workspace,project} from './fixtures/workbench-auth';
async function fixture(command='seed',id?:string){
 const cwd=resolve('services/worker'),python=resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
 const result=await promisify(execFile)(python,['tests/fixtures/audit_bulk.py',command,...(id?[id]:[])],{cwd,timeout:30_000});
 return JSON.parse(result.stdout.trim().split(/\r?\n/).at(-1)!);
}
async function open(page:Parameters<typeof signInWorkbench>[0]){
 await signInWorkbench(page,true,'access');await page.getByRole('combobox',{name:/^(Language|語言)$/}).selectOption('en');
 await page.getByRole('button',{name:'Buyers',exact:true}).click();
 const buyers=page.getByRole('region',{name:'Buyer results',exact:true});await expect(buyers.getByRole('checkbox',{name:/^Select /})).toHaveCount(12);
 return buyers;
}
async function select(buyers:Awaited<ReturnType<typeof open>>,count:number){const rows=buyers.getByRole('checkbox',{name:/^Select /});for(let i=0;i<count;i++)await rows.nth(i).check();}
const assignments='**/v1/workspaces/*/projects/*/buyer-owner-assignments';
test.beforeEach(async()=>{await fixture();});
test.afterEach(async()=>{await fixture('cleanup');});
test('B02 adding a sixth buyer clears the previously confirmed five',async({page})=>{
 await signInWorkbench(page,true,'access');await page.getByRole('combobox',{name:/^(Language|語言)$/}).selectOption('en');
 await page.getByRole('button',{name:'Buyers',exact:true}).click();
 const buyers=page.getByRole('region',{name:'Buyer results',exact:true});
 const rows=buyers.getByRole('checkbox',{name:/^Select /});await expect(rows).toHaveCount(12);
 for(let i=0;i<5;i++)await rows.nth(i).check();
 const panel=buyers.getByRole('region',{name:'Assign buyer owners',exact:true});
 await panel.getByRole('textbox',{name:'Assignment reason'}).fill('Fixture duty rotation');
 const confirm=panel.getByRole('checkbox',{name:'Confirm owner assignment'});await confirm.check();await expect(confirm).toBeChecked();
 await rows.nth(5).check();await expect(confirm).not.toBeChecked();await expect(panel.getByRole('button',{name:'Assign selected buyers'})).toBeDisabled();
});

test('B02 reason, target and exclusions clear confirmation; unchanged selection survives paging',async({page})=>{
 const buyers=await open(page);await select(buyers,5);const panel=buyers.getByRole('region',{name:'Assign buyer owners',exact:true});
 const confirm=panel.getByRole('checkbox',{name:'Confirm owner assignment'}),reason=panel.getByRole('textbox',{name:'Assignment reason'});
 await reason.fill('Fixture bounded assignment');await confirm.check();await buyers.getByRole('button',{name:'Next page',exact:true}).click();await expect(confirm).toBeChecked();
 await reason.fill('Different reason');await expect(confirm).not.toBeChecked();await confirm.check();await panel.getByRole('combobox',{name:'Owner',exact:true}).selectOption('');await expect(confirm).not.toBeChecked();
 await confirm.check();await buyers.getByRole('button',{name:'Select all filtered'}).click();await expect(confirm).not.toBeChecked();await confirm.check();
 await buyers.getByRole('checkbox',{name:'Select Buyer Fixture 13',exact:true}).uncheck();await expect(confirm).not.toBeChecked();
 await confirm.check();await buyers.getByRole('button',{name:'Refresh results'}).click();await expect(confirm).not.toBeChecked();
});

test('B03 searchable colleagues assign ten buyers through a real durable API; clear owner also works',async({page})=>{
 const seeded=await fixture('targets');const buyers=await open(page);await select(buyers,10);const panel=buyers.getByRole('region',{name:'Assign buyer owners',exact:true});
 await panel.getByRole('textbox',{name:'Search colleagues'}).fill('Q05 colleague');await panel.getByRole('button',{name:'Search',exact:true}).click();
 const picker=panel.getByRole('combobox',{name:'Owner',exact:true});await expect(picker.locator('option')).toHaveCount(12);
 await picker.selectOption(seeded.colleagues[9].membership_id);await panel.getByRole('textbox',{name:'Assignment reason'}).fill('  Fixture colleague rotation  ');
 await panel.getByRole('checkbox',{name:'Confirm owner assignment'}).check();
 const posted=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith('/buyer-owner-assignments'));
 await panel.getByRole('button',{name:'Assign selected buyers'}).click();const response=await posted;expect(response.status()).toBe(200);
 const result=await response.json();expect(result.data.updated).toBe(10);expect(response.request().postDataJSON().reason).toBe('Fixture colleague rotation');
 const state=await fixture('inspect');expect(state.buyers.slice(0,10).every((b:{owner:string;version:number})=>b.owner===seeded.colleagues[9].user_id&&b.version===2)).toBe(true);
 writeFileSync('test-results/q05-colleague-assignment.json',JSON.stringify({fixture_only:true,result,state},null,2));
 await expect(buyers.getByRole('checkbox',{name:/^Select /})).toHaveCount(12);await select(buyers,10);await picker.selectOption('');
 await panel.getByRole('textbox',{name:'Assignment reason'}).fill('Fixture clear assignment');await panel.getByRole('checkbox',{name:'Confirm owner assignment'}).check();
 const cleared=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith('/buyer-owner-assignments'));await panel.getByRole('button',{name:'Assign selected buyers'}).click();expect((await cleared).status()).toBe(200);
 expect((await fixture('inspect')).buyers.slice(0,10).every((b:{owner:string|null;version:number})=>b.owner===null&&b.version===3)).toBe(true);
 await page.screenshot({path:'test-results/q05-bulk-en.png',fullPage:true});
});

test('B04 inactive owner is rejected and a stale buyer reports conflict without overwriting',async({page})=>{
 const seeded=await fixture('targets');const buyers=await open(page);await select(buyers,2);const panel=buyers.getByRole('region',{name:'Assign buyer owners',exact:true});
 await panel.getByRole('combobox',{name:'Owner',exact:true}).selectOption(seeded.colleagues[0].membership_id);await panel.getByRole('textbox',{name:'Assignment reason'}).fill('Fixture revalidation');await panel.getByRole('checkbox',{name:'Confirm owner assignment'}).check();
 await fixture('deactivate',seeded.colleagues[0].membership_id);
 const rejected=page.waitForResponse(r=>r.url().endsWith('/buyer-owner-assignments')&&r.request().method()==='POST');await panel.getByRole('button',{name:'Assign selected buyers'}).click();expect((await rejected).status()).toBe(422);
 expect((await fixture('inspect')).buyers.slice(0,2).every((b:{owner:string|null;version:number})=>b.owner===null&&b.version===1)).toBe(true);
 await panel.getByRole('combobox',{name:'Owner',exact:true}).selectOption(seeded.colleagues[1].membership_id);await expect(panel.getByRole('checkbox',{name:'Confirm owner assignment'})).not.toBeChecked();
 await fixture('stale','e2000000-0000-4000-8000-000000000001');await panel.getByRole('checkbox',{name:'Confirm owner assignment'}).check();
 const posted=page.waitForResponse(r=>r.url().endsWith('/buyer-owner-assignments')&&r.request().method()==='POST');await panel.getByRole('button',{name:'Assign selected buyers'}).click();const result=(await (await posted).json()).data;
 expect([result.updated,result.conflicts,result.blocked]).toEqual([1,1,0]);await expect(panel.locator('code')).toHaveText('e2000000-0000-4000-8000-000000000001');const state=await fixture('inspect');expect(state.buyers[0].owner).toBeNull();expect(state.buyers[0].version).toBe(2);expect(state.buyers[1].owner).toBe(seeded.colleagues[1].user_id);
 writeFileSync('test-results/q05-owner-revalidation.json',JSON.stringify({fixture_only:true,result,state},null,2));
});

test('B16 committed response loss locks changes and reconciles the same key after a route remount',async({page})=>{
 const seeded=await fixture('targets');const buyers=await open(page);await select(buyers,5);const panel=buyers.getByRole('region',{name:'Assign buyer owners',exact:true});await panel.getByRole('combobox',{name:'Owner',exact:true}).selectOption(seeded.colleagues[0].membership_id);await panel.getByRole('textbox',{name:'Assignment reason'}).fill('Fixture lost response');await panel.getByRole('checkbox',{name:'Confirm owner assignment'}).check();
 const requests:{key:string;body:unknown}[]=[];
 await page.route(assignments,async route=>{requests.push({key:route.request().headers()['idempotency-key'],body:route.request().postDataJSON()});const response=await route.fetch();expect(response.status()).toBe(200);if(requests.length===1)await route.abort('failed');else await route.fulfill({response});});
 await panel.getByRole('button',{name:'Assign selected buyers'}).click();await expect(panel.getByRole('button',{name:'Retry same assignment'})).toBeVisible();await expect(panel.getByRole('combobox',{name:'Owner',exact:true})).toBeDisabled();expect(requests).toHaveLength(1);
 await page.getByRole('button',{name:'Settings',exact:true}).click();await page.getByRole('button',{name:'Buyers',exact:true}).click();await expect(panel.getByRole('button',{name:'Retry same assignment'})).toBeVisible();await expect(panel.getByRole('combobox',{name:'Owner',exact:true})).toHaveValue(seeded.colleagues[0].membership_id);await expect(panel.getByText(/Preview: 5 selected buyers/)).toBeVisible();
 await panel.getByRole('button',{name:'Retry same assignment'}).click();await expect(panel.getByRole('button',{name:'Retry same assignment'})).toHaveCount(0);expect(requests).toHaveLength(2);expect(requests[1]).toEqual(requests[0]);
 const state=await fixture('inspect');expect(state.buyers.slice(0,5).every((b:{version:number})=>b.version===2)).toBe(true);writeFileSync('test-results/q05-lost-response.json',JSON.stringify({fixture_only:true,requests,state},null,2));
});

test('B16 late committed B job cannot overwrite A; returning to B reconciles its exact job link',async({page})=>{
 const seeded=await fixture('targets');await open(page);await page.getByRole('combobox',{name:'Workspace',exact:true}).selectOption(seeded.other);
 await expect(page.getByRole('combobox',{name:'Project',exact:true})).toHaveValue(seeded.other_project);
 const buyers=page.getByRole('region',{name:'Buyer results',exact:true});await expect(buyers.getByRole('checkbox',{name:/^Select /})).toHaveCount(12);await buyers.getByRole('button',{name:'Select all filtered'}).click();
 const panel=buyers.getByRole('region',{name:'Assign buyer owners',exact:true});await panel.getByRole('textbox',{name:'Assignment reason'}).fill('Fixture scoped queued assignment');await panel.getByRole('checkbox',{name:'Confirm owner assignment'}).check();
 let release:()=>void=()=>{},received:()=>void=()=>{};const held=new Promise<void>(r=>release=r),started=new Promise<void>(r=>received=r);let job='';const keys:string[]=[];
 await page.route(assignments,async route=>{keys.push(route.request().headers()['idempotency-key']);const response=await route.fetch();expect(response.status()).toBe(202);job=(await response.json()).data.id;if(keys.length===1){received();await held;}await route.fulfill({response}).catch(()=>{});});
 await panel.getByRole('button',{name:'Assign selected buyers'}).click();await started;await page.getByRole('combobox',{name:'Workspace',exact:true}).selectOption(workspace);release();await page.getByRole('combobox',{name:'Project',exact:true}).selectOption(project);await expect(page.getByRole('combobox',{name:'Project',exact:true})).toHaveValue(project);
 await expect(buyers.getByRole('checkbox',{name:'Select Buyer Fixture 01',exact:true})).toBeVisible();await expect(panel.getByRole('checkbox',{name:'Confirm owner assignment'})).not.toBeChecked();expect(new URL(page.url()).searchParams.get('bulk_job')).toBeNull();
 await page.getByRole('combobox',{name:'Workspace',exact:true}).selectOption(seeded.other);await expect(panel.getByRole('button',{name:'Retry same assignment'})).toBeVisible();await panel.getByRole('button',{name:'Retry same assignment'}).click();
 await expect.poll(()=>new URL(page.url()).searchParams.get('bulk_job')).toBe(job);expect(keys).toHaveLength(2);expect(keys[1]).toBe(keys[0]);
 const read=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${seeded.other}/jobs/${job}`,{headers:{Authorization:'Bearer fixture-access'}});expect(read.status()).toBe(200);expect((await read.json()).data.requested).toBe(101);
 const foreign=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/jobs/${job}`,{headers:{Authorization:'Bearer fixture-access'}});expect(foreign.status()).toBe(404);
 writeFileSync('test-results/q05-scope-recovery.json',JSON.stringify({fixture_only:true,job,keys,read:await read.json()},null,2));
});

test('B03 zh-HK mobile colleague search recovers a failed read',async({page})=>{
 await open(page);await page.setViewportSize({width:390,height:844});await page.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');const panel=page.getByRole('region',{name:'批量分派買家負責人',exact:true});
 let failed=false;await page.route('**/eligible-assignees?**',async route=>{if(!failed){failed=true;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({code:'TEMPORARILY_UNAVAILABLE',message:'Fixture outage',request_id:'fixture-q05'})});}else await route.continue();});
 await panel.getByRole('textbox',{name:'搜尋同事'}).fill('Q05 colleague');await panel.getByRole('button',{name:'搜尋',exact:true}).click();await expect(panel.getByRole('button',{name:'重新載入同事'})).toBeVisible();await panel.getByRole('button',{name:'重新載入同事'}).click();await expect(panel.getByRole('combobox',{name:'負責人',exact:true}).locator('option')).toHaveCount(12);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);await page.screenshot({path:'test-results/q05-bulk-zh-mobile.png',fullPage:true});
 // This real fixture preference is shared with the following English D02 cases.
 const restored=page.waitForResponse(r=>r.request().method()==='PATCH'&&r.url().endsWith('/preferences'));
 await page.getByRole('combobox',{name:'語言',exact:true}).selectOption('en');expect((await restored).status()).toBe(200);
});

test('B03 viewer cannot assign through UI or direct API',async({page})=>{
 await signInWorkbench(page,true,'viewer');await page.getByRole('combobox',{name:/^(Language|語言)$/}).selectOption('en');await page.getByRole('button',{name:'Buyers',exact:true}).click();await expect(page.getByRole('region',{name:'Assign buyer owners',exact:true})).toHaveCount(0);
 const result=await page.request.post(`http://127.0.0.1:8000/v1/workspaces/${workspace}/projects/${project}/buyer-owner-assignments`,{headers:{Authorization:'Bearer fixture-viewer','Idempotency-Key':'q05-viewer-denied'},data:{selection:{kind:'explicit',buyers:[{id:'e2000000-0000-4000-8000-000000000001',version:1}]},owner_membership_id:null,reason:'Fixture denial'}});expect(result.status()).toBe(403);
});
