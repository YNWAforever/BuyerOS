import {expect,test} from '@playwright/test';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {resolve} from 'node:path';
import {writeFileSync} from 'node:fs';
import {signInWorkbench,workspace,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';
const other='e0000000-0000-4000-8000-000000000101';
async function fixture():Promise<{ids:string[];target:string;member:string}>{
 const cwd=resolve('services/worker');const python=resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
 return JSON.parse((await promisify(execFile)(python,['tests/fixtures/audit_memberships.py'],{cwd,timeout:30_000})).stdout);
}
async function open(page:Parameters<typeof signInWorkbench>[0]){
 await signInWorkbench(page,true,'admin');await page.getByRole('combobox',{name:/^(Language|語言)$/}).selectOption('en');
 await page.getByRole('button',{name:'Settings',exact:true}).click();return page.getByRole('region',{name:'Member management',exact:true});
}
test.beforeEach(async()=>{await resetWorkbenchFixtureRateWindows();});

test('U06 all 250 real members are readable in 13 pages and member 101 is searchable',async({page})=>{
 const seeded=await fixture();const region=await open(page);const seen:string[]=[];
 for(let offset=0;offset<250;offset+=20){
  await expect(region.locator('code')).toHaveCount(Math.min(20,250-offset));
  await expect(region.getByText(`${offset+1}–${Math.min(offset+20,250)} / 250`,{exact:true})).toBeVisible();
  seen.push(...await region.locator('code').allTextContents());
  if(offset+20<250)await region.getByRole('button',{name:'Next members',exact:true}).click();
 }
 expect(seen).toEqual(seeded.ids);expect(new Set(seen).size).toBe(250);
 await expect(region.getByRole('button',{name:'Next members'})).toBeDisabled();
 await region.getByRole('textbox',{name:'Search members'}).fill('Search target 101');await region.getByRole('button',{name:'Search',exact:true}).click();
 await expect(region.locator('code')).toHaveText([seeded.target]);await expect(region.getByText('1–1 / 1',{exact:true})).toBeVisible();
 await page.screenshot({path:'test-results/q02-members-en.png',fullPage:true});
 await region.getByRole('textbox',{name:'Search members'}).fill('absent');await region.getByRole('button',{name:'Search',exact:true}).click();
 await expect(region.getByText('0–0 / 0',{exact:true})).toBeVisible();await expect(region.locator('code')).toHaveCount(0);
});

test('U07 duplicate names and suffixes remain distinct during a versioned role change',async({page})=>{
 await fixture();const region=await open(page);
 await region.getByRole('textbox',{name:'Search members'}).fill('Alex');await region.getByRole('button',{name:'Search',exact:true}).click();
 await expect(region.locator('code')).toHaveText(['71000001-0000-4000-8000-000000c011de','71000002-0000-4000-8000-000000c011de']);
 const first=region.getByRole('group',{name:'Member 71000001-0000-4000-8000-000000c011de',exact:true});
 await first.getByRole('checkbox',{name:'operator',exact:true}).check();await region.getByRole('textbox',{name:'Change reason'}).fill('Fixture duty rotation');
 const changed=page.waitForResponse(r=>r.request().method()==='PATCH'&&r.url().includes('/memberships/'));
 await first.getByRole('button',{name:'Save member',exact:true}).click();const response=await changed;expect(response.status()).toBe(200);
 const payload=await response.json();expect(payload.data.user_id).toBe('71000001-0000-4000-8000-000000c011de');expect(payload.data.version).toBe(2);
 expect(response.request().headers()['if-match']).toBe('"1"');expect(response.request().headers()['idempotency-key']).toBeTruthy();
 const read=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/memberships?q=Alex`,{headers:{Authorization:'Bearer fixture-admin'}});
 expect((await read.json()).data.items.map((r:{version:number})=>r.version)).toEqual([2,1]);writeFileSync('test-results/q02-membership-role-change.json',JSON.stringify(payload,null,2));
});

test('U08 sole admin refusal is understandable and does not claim success',async({page})=>{
 await fixture();const region=await open(page);
 const own=region.getByRole('group',{name:'Member e0000000-0000-4000-8000-000000000008',exact:true});
 await own.getByRole('checkbox',{name:'viewer',exact:true}).check();await own.getByRole('checkbox',{name:'workspace_admin',exact:true}).uncheck();
 await region.getByRole('textbox',{name:'Change reason'}).fill('Fixture guard check');await own.getByRole('button',{name:'Save member'}).click();
 await expect(page.getByRole('alert').filter({hasText:'The last active administrator must remain.'})).toBeVisible();
 await expect(page.getByText('Membership updated.',{exact:true})).toHaveCount(0);
});

test('S06 viewer cannot read the admin directory or eligible assignees',async({page})=>{
 await fixture();await signInWorkbench(page,true,'viewer');await page.getByRole('combobox',{name:/^(Language|語言)$/}).selectOption('en');await page.getByRole('button',{name:'Settings',exact:true}).click();
 await expect(page.getByRole('region',{name:'Member management'})).toHaveCount(0);
 for(const path of ['memberships','eligible-assignees'])expect((await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/${path}`,{headers:{Authorization:'Bearer fixture-viewer'}})).status()).toBe(403);
});

test('U06 stale page response cannot restore old A-B-A directory',async({page})=>{
 await fixture();const region=await open(page);await expect(region.locator('code')).toHaveCount(20);
 let release:()=>void=()=>{},received:()=>void=()=>{};const held=new Promise<void>(r=>release=r),started=new Promise<void>(r=>received=r);
 await page.route(`**/v1/workspaces/${workspace}/memberships?offset=20&limit=20**`,async route=>{const response=await route.fetch();received();await held;await route.fulfill({response}).catch(()=>{});});
 await region.getByRole('button',{name:'Next members'}).click();await started;
 await page.getByRole('combobox',{name:'Workspace',exact:true}).selectOption(other);await expect(region.locator('code')).toHaveCount(1);
 await page.getByRole('combobox',{name:'Workspace',exact:true}).selectOption(workspace);await expect(region.locator('code')).toHaveCount(20);release();
 await expect(region.locator('code').first()).toHaveText('e0000000-0000-4000-8000-000000000002');await page.waitForTimeout(300);
 await expect(region.getByText('1–20 / 250',{exact:true})).toBeVisible();
});

test('U06 zh-HK mobile search and failed page read recover without synthetic rows',async({page})=>{
 await fixture();await open(page);await page.setViewportSize({width:390,height:844});await page.getByRole('combobox',{name:'Language',exact:true}).selectOption('zh-HK');
 const region=page.getByRole('region',{name:'成員管理',exact:true});await expect(region.locator('code')).toHaveCount(20);
 let failed=false;await page.route(`**/v1/workspaces/${workspace}/memberships?offset=20&limit=20**`,async route=>{if(!failed){failed=true;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({code:'TEMPORARILY_UNAVAILABLE',message:'Fixture outage',request_id:'1d123054-2633-40b7-8e07-b6aed83dad98'})});}else await route.continue();});
 await region.getByRole('button',{name:'下一頁成員'}).click();await expect(region.locator('code')).toHaveCount(0);
 await expect(region.getByRole('button',{name:'重新載入成員'})).toBeVisible();await region.getByRole('button',{name:'重新載入成員'}).click();
 await expect(region.locator('code')).toHaveCount(20);await expect(region.getByText('21–40 / 250',{exact:true})).toBeVisible();
 await region.getByRole('textbox',{name:'搜尋成員'}).fill('Search target 101');await region.getByRole('button',{name:'搜尋',exact:true}).click();await expect(region.getByText('1–1 / 1',{exact:true})).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);await page.screenshot({path:'test-results/q02-members-zh-mobile.png',fullPage:true});
});


test('U07 lost committed role response requires a read before any further role write',async({page})=>{
 await fixture();const region=await open(page);
 await region.getByRole('textbox',{name:'Search members'}).fill('Alex');await region.getByRole('button',{name:'Search',exact:true}).click();
 const first=region.getByRole('group',{name:'Member 71000001-0000-4000-8000-000000c011de',exact:true});
 await first.getByRole('checkbox',{name:'operator',exact:true}).check();await region.getByRole('textbox',{name:'Change reason'}).fill('Fixture lost response');
 const keys:string[]=[];await page.route('**/v1/workspaces/*/memberships/*',async route=>{
  if(route.request().method()!=='PATCH'){await route.continue();return;}
  keys.push(route.request().headers()['idempotency-key']);const committed=await route.fetch();expect(committed.status()).toBe(200);await route.abort('failed');
 });
 await first.getByRole('button',{name:'Save member'}).click();
 await expect(first.getByRole('button',{name:'Save member'})).toBeDisabled();await expect(first.getByRole('checkbox',{name:'operator',exact:true})).toBeDisabled();
 await expect(region.getByRole('alert')).toContainText('The membership result is unknown. Reload members to check the current version before making another change.');
 expect(keys).toHaveLength(1);await region.getByRole('button',{name:'Reload members'}).click();
 await expect(region.getByRole('alert')).toHaveCount(0);await expect(first.getByRole('checkbox',{name:'operator',exact:true})).toBeEnabled();await expect(first.getByRole('checkbox',{name:'operator',exact:true})).toBeChecked();
 await expect(first.getByRole('button',{name:'Save member'})).toBeDisabled();expect(keys).toHaveLength(1);
 const read=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/memberships?q=Alex`,{headers:{Authorization:'Bearer fixture-admin'}});expect((await read.json()).data.items.map((r:{version:number})=>r.version)).toEqual([2,1]);
 writeFileSync('test-results/q02-membership-lost-response.json',JSON.stringify({fixture_only:true,patch_count:keys.length,idempotency_key:keys[0],read:await read.json()},null,2));
});
