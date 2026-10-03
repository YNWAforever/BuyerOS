import {expect,test} from '@playwright/test';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {resolve} from 'node:path';
import {readFile} from 'node:fs/promises';
import type {components} from '../../services/generated/buyeros-api';
import {createJourneyInput} from './fixtures/journey-input';
import {workspace,project,signInWorkbench,resetWorkbenchFixtureRateWindows} from './fixtures/workbench-auth';

type Seed={fixture_only:boolean;ids:string[]};
type State={fixture_only:boolean;buyers:{id:string;version:number;owner:string|null}[]};
type Jobs={fixture_only:boolean;own_ids:string[];other_ids:string[]};
async function fixture<T extends {fixture_only:boolean}>(script:string,...args:string[]):Promise<T>{
 const cwd=resolve('services/worker'),python=resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
 const {stdout}=await promisify(execFile)(python,[`tests/fixtures/${script}.py`,...args],{cwd,timeout:script==='audit_manifests'?45_000:30_000,maxBuffer:1024*1024});
 const value=JSON.parse(stdout.trim().split(/\r?\n/).at(-1)!) as T;expect(value.fixture_only).toBe(true);return value;
}
const zh:Record<string,string>={
 'Buyers':'買家','Buyer results':'買家結果','Search buyers':'搜尋買家','Next page':'下一頁',
 'Assign buyer owners':'批量分派買家負責人','Assignment reason':'分派原因','Confirm owner assignment':'確認負責人分派','Assign selected buyers':'分派已選買家',
 'Segmented maintenance':'分段批量維護','Maintenance reason':'維護理由','Preview segmented maintenance':'預覽分段批量維護','Frozen manifest':'已凍結維護清單',
 'Confirm exact manifest':'確認精確維護清單','Execute confirmed manifest':'執行已確認維護清單','Bulk job progress':'批量工作進度','Refresh job':'更新工作進度',
 'Show job results':'顯示工作結果','Next job results':'下一頁工作結果','Export failed IDs and reasons':'匯出失敗買家 ID 與原因','Preview failed rows with current versions':'按目前版本預覽失敗列',
 'Settings':'設定','Member management':'成員管理','Search members':'搜尋成員','Search':'搜尋','Member':'成員','operator':'操作員','Change reason':'變更原因','Save member':'儲存成員',
 'Project':'專案','Overview':'總覽','Failed jobs':'失敗工作','Open':'開啟','Bulk jobs':'批量工作','Next':'下一頁','Job details':'工作詳情',
};
const ownActor='e0000000-0000-4000-8000-000000000002',projectB='e1140000-0000-4000-8000-000000000002';
for(const [locale,layout] of [['en','desktop'],['zh-HK','mobile']] as const){
 const t=(text:string)=>locale==='zh-HK'?(zh[text]??text):text;
 const viewport=layout==='desktop'?{width:1280,height:800}:{width:390,height:844};
 test(`U09 U10 keyboard ${locale} ${layout} task3 cross-page assignment, persisted conflict and exact failed-only manifest`,async({page})=>{
  test.setTimeout(300_000);await page.setViewportSize(viewport);await resetWorkbenchFixtureRateWindows();
  const seeded=await fixture<Seed>('audit_manifests','seed','101'),input=createJourneyInput('keyboard');
  await signInWorkbench(page,true,'access',undefined,input);
  await input.choose(page.getByRole('combobox',{name:/^(Language|語言)$/,exact:true}),locale);
  await input.activate(page.getByRole('button',{name:t('Buyers'),exact:true}));
  const buyers=page.getByRole('region',{name:t('Buyer results'),exact:true});
  await input.fill(buyers.getByRole('textbox',{name:t('Search buyers'),exact:true}),'Q08 Manifest Fixture');await page.keyboard.press('Enter');
  const selected=buyers.getByRole('checkbox',{name:/^(Select |選取 )/});await expect(selected).toHaveCount(12);
  await input.check(selected.first());await input.activate(buyers.getByRole('button',{name:t('Next page'),exact:true}));
  await expect(selected.first()).toHaveAttribute('aria-label',locale==='en'?'Select Q08 Manifest Fixture 00012':'選取 Q08 Manifest Fixture 00012');await input.check(selected.first());
  const panel=buyers.getByRole('region',{name:t('Assign buyer owners'),exact:true});await expect(panel).toContainText(locale==='en'?'Preview: 2 selected buyers':'預覽：已選 2 位買家');
  await input.fill(panel.getByRole('textbox',{name:t('Assignment reason'),exact:true}),'Keyboard reviewed two pages');await input.check(panel.getByRole('checkbox',{name:t('Confirm owner assignment'),exact:true}));
  const assigned=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/buyer-owner-assignments'));
  await input.activate(panel.getByRole('button',{name:t('Assign selected buyers'),exact:true}));const response=await assigned;expect(response.status()).toBe(200);
  const first=(await response.json()).data;expect([first.updated,first.conflicts,first.blocked]).toEqual([2,0,0]);
  const initial=await fixture<State>('audit_manifests','inspect');expect(initial.buyers.filter(b=>b.owner===ownActor).map(b=>b.id)).toEqual([seeded.ids[0],seeded.ids[12]]);
  expect(initial.buyers.filter(b=>b.version===2)).toHaveLength(2);expect(initial.buyers.filter(b=>b.version===1&&b.owner===null)).toHaveLength(99);
  const maintenance=buyers.getByRole('region',{name:t('Segmented maintenance'),exact:true});
  await input.fill(maintenance.getByRole('textbox',{name:t('Maintenance reason'),exact:true}),'Keyboard reviewed exact101 manifest');
  async function preview(){
   const pending=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/bulk-manifests'));
   await input.activate(maintenance.getByRole('button',{name:t('Preview segmented maintenance'),exact:true}));const r=await pending;expect(r.status()).toBe(201);return (await r.json()).data as {id:string;count:number;digest:string};
  }
  async function execute(id:string){
   await input.check(maintenance.getByRole('checkbox',{name:t('Confirm exact manifest'),exact:true}));
   const pending=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith(`/bulk-manifests/${id}/execute`));
   await input.activate(maintenance.getByRole('button',{name:t('Execute confirmed manifest'),exact:true}));return await pending;
  }
  const manifest=await preview();expect(manifest.count).toBe(101);await fixture<Seed>('audit_manifests','stale',seeded.ids[1]);
  const executed=await execute(manifest.id);expect(executed.status()).toBe(202);const job=(await executed.json()).data;
  const drained=await fixture<{fixture_only:boolean;total:number}>('audit_manifests','drain',job.id);expect(drained.total).toBe(101);
  const progress=buyers.getByRole('region',{name:t('Bulk job progress'),exact:true});await input.activate(progress.getByRole('button',{name:t('Refresh job'),exact:true}));
  const summary=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/jobs/${job.id}/summary`,{headers:{Authorization:'Bearer fixture-access'}});expect(summary.status()).toBe(200);
  const result=(await summary.json()).data;expect([result.processed,result.updated,result.unchanged,result.conflicts,result.blocked]).toEqual([101,98,2,1,0]);
  await expect(progress).toContainText(locale==='en'?'1 conflicts':'衝突 1');
  const seen:string[]=[],resultReads:{offset:number;status:number;timing:ReturnType<import('@playwright/test').Request['timing']>}[]=[];
  for(let offset=0;offset<101;offset+=20){
   // Observe the actual read before the 5s rendering assertion. An incomplete
   // request is a failed HTTP check, never a synthetic page or ignored failure.
   const pending=page.waitForResponse(r=>{const url=new URL(r.url());return r.request().method()==='GET'&&url.pathname===`/v1/workspaces/${workspace}/jobs/${job.id}`&&url.searchParams.get('offset')===String(offset)&&url.searchParams.get('limit')==='20';});
   await input.activate(progress.getByRole('button',{name:t(offset===0?'Show job results':'Next job results'),exact:true}));
   const read=await pending;expect(read.status()).toBe(200);
   const value=(await read.json()).data as components['schemas']['AsyncJob'];
   expect(value.id).toBe(job.id);expect(value.result_page?.offset).toBe(offset);expect(value.result_page?.total).toBe(101);expect(value.result_page?.items).toHaveLength(Math.min(20,101-offset));
   resultReads.push({offset,status:read.status(),timing:read.request().timing()});
   await expect(progress.getByText(`${offset+1}–${Math.min(offset+20,101)} / 101`,{exact:true})).toBeVisible();
   const rendered=await progress.locator('code').allTextContents();expect(rendered).toEqual(value.result_page!.items.map(item=>item.id));seen.push(...rendered);
  }
  expect(seen.length).toBe(101);expect(new Set(seen)).toEqual(new Set(seeded.ids));
  const download=page.waitForEvent('download');await input.activate(progress.getByRole('button',{name:t('Export failed IDs and reasons'),exact:true}));
  const csv=await readFile((await (await download).path())!,'utf8');expect(csv.trim().split(/\r?\n/)).toHaveLength(2);expect(csv).toContain(seeded.ids[1]);expect(csv).not.toContain(seeded.ids[0]);
  const before=await fixture<State>('audit_manifests','inspect');
  await input.activate(progress.getByRole('button',{name:t('Preview failed rows with current versions'),exact:true}));
  const retry=await preview();expect(retry.count).toBe(1);expect(retry.digest).not.toBe(manifest.digest);const retried=await execute(retry.id);expect(retried.status()).toBe(200);expect((await retried.json()).data.updated).toBe(1);
  const after=await fixture<State>('audit_manifests','inspect');expect(after.buyers.filter(b=>b.owner===ownActor)).toHaveLength(101);
  expect(after.buyers.filter((b,i)=>b.version!==before.buyers[i].version).map(b=>b.id)).toEqual([seeded.ids[1]]);expect(after.buyers.find(b=>b.id===seeded.ids[1])?.version).toBe(3);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:`test-results/q09-keyboard-task3-${locale}-${layout}.png`,fullPage:true});
  await test.info().attach('keyboard-task3-proof',{body:JSON.stringify({fixture_only:true,manifest,retry,job:job.id,result,resultReads,csv,before,after,input:await input.verify(page)},null,2),contentType:'application/json'});
 });
 test(`U09 U10 keyboard ${locale} ${layout} task5 versioned member change, failed-job paging and scope recovery`,async({page,browser})=>{
  test.setTimeout(300_000);await page.setViewportSize(viewport);await resetWorkbenchFixtureRateWindows();
  await fixture<Seed>('audit_memberships');const jobs=await fixture<Jobs>('audit_job_scopes','21'),input=createJourneyInput('keyboard');
  await signInWorkbench(page,true,'admin',undefined,input);await input.choose(page.getByRole('combobox',{name:/^(Language|語言)$/,exact:true}),locale);
  await input.activate(page.getByRole('button',{name:t('Settings'),exact:true}));const directory=page.getByRole('region',{name:t('Member management'),exact:true});
  await input.fill(directory.getByRole('textbox',{name:t('Search members'),exact:true}),'Alex');await input.activate(directory.getByRole('button',{name:t('Search'),exact:true}));
  const members=directory.getByRole('group',{name:`${t('Member')} Alex Chen`,exact:true});await expect(members).toHaveCount(2);
  const first=members.filter({has:page.locator('code').filter({hasText:'71000001-0000-4000-8000-000000c011de'})});
  await input.activate(first.getByText(locale==='en'?'Technical details':'技術資料',{exact:true}));await expect(first.locator('code')).toBeVisible();
  await input.check(first.getByRole('checkbox',{name:t('operator'),exact:true}));await input.fill(directory.getByRole('textbox',{name:t('Change reason'),exact:true}),'Keyboard fixture duty rotation');
  const pending=page.waitForResponse(r=>r.request().method()==='PATCH'&&new URL(r.url()).pathname.includes('/memberships/'));
  await input.activate(first.getByRole('button',{name:t('Save member'),exact:true}));const changed=await pending;expect(changed.status()).toBe(200);expect(changed.request().headers()['if-match']).toBe('"1"');expect(changed.request().headers()['idempotency-key']).toBeTruthy();
  const member=(await changed.json()).data;expect(member.user_id).toBe('71000001-0000-4000-8000-000000c011de');expect(member.version).toBe(2);
  const read=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/memberships?q=Alex`,{headers:{Authorization:'Bearer fixture-admin'}});expect(read.status()).toBe(200);expect((await read.json()).data.items.map((m:{version:number})=>m.version)).toEqual([2,1]);
  await input.choose(page.getByRole('combobox',{name:t('Project'),exact:true}),projectB);await input.activate(page.getByRole('button',{name:t('Overview'),exact:true}));
  const card=page.locator('.activity').filter({has:page.getByText(t('Failed jobs'),{exact:true})});await expect(card.locator('p')).toHaveText('24');await input.activate(card.getByRole('button',{name:t('Open'),exact:true}));
  const list=page.getByRole('region',{name:t('Bulk jobs'),exact:true});await expect(list).toContainText(locale==='en'?'24 jobs in scope':'24 項範圍內工作');
  const seen=await list.getByRole('button').filter({hasText:/^[0-9a-f-]{36}$/}).allTextContents();expect(seen).toHaveLength(20);
  await input.activate(list.getByRole('button',{name:t('Next'),exact:true}));await expect(list.getByText('21–24 / 24',{exact:true})).toBeVisible();seen.push(...await list.getByRole('button').filter({hasText:/^[0-9a-f-]{36}$/}).allTextContents());
  expect(new Set(seen)).toEqual(new Set([...jobs.own_ids,...jobs.other_ids]));await input.activate(list.getByRole('button',{name:seen[20],exact:true}));
  const details=page.getByRole('region',{name:t('Job details'),exact:true});await expect(details).toBeVisible();
  const jobRead=await page.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/jobs/${seen[20]}`,{headers:{Authorization:'Bearer fixture-admin'}});expect(jobRead.status()).toBe(200);expect((await jobRead.json()).data.project_id).toBe(projectB);
  await input.choose(page.getByRole('combobox',{name:t('Project'),exact:true}),project);await expect(list).toContainText(locale==='en'?'0 jobs in scope':'0 項範圍內工作');await expect(details).toHaveCount(0);
  const viewerContext=await browser.newContext({viewport}),viewer=await viewerContext.newPage();
  try{await signInWorkbench(viewer,true,'viewer',undefined,input);await input.choose(viewer.getByRole('combobox',{name:/^(Language|語言)$/,exact:true}),locale);await input.activate(viewer.getByRole('button',{name:t('Settings'),exact:true}));await expect(viewer.getByRole('region',{name:t('Member management'),exact:true})).toHaveCount(0);
   expect((await viewer.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/memberships`,{headers:{Authorization:'Bearer fixture-viewer'}})).status()).toBe(403);
   expect((await viewer.request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/jobs/${jobs.own_ids[0]}`,{headers:{Authorization:'Bearer fixture-viewer'}})).status()).toBe(404);
   await test.info().attach('keyboard-task5-viewer',{body:JSON.stringify(await input.verify(viewer),null,2),contentType:'application/json'});
  }finally{await viewerContext.close();}
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.screenshot({path:`test-results/q09-keyboard-task5-${locale}-${layout}.png`,fullPage:true});
  await test.info().attach('keyboard-task5-proof',{body:JSON.stringify({fixture_only:true,member,jobs:seen,input:await input.verify(page)},null,2),contentType:'application/json'});
 });
}
