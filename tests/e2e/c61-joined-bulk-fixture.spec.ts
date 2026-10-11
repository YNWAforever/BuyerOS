import {expect,test} from '@playwright/test';
import {createHash} from 'node:crypto';
import {resolve} from 'node:path';
import {registerStaffJourney} from './fixtures/staff-journey';
import {runOwnedFixtureProcess} from './fixtures/owned-fixture-process';

type Row={id:string;version:number;owner:string|null};
type Native={fixture_only:boolean;project_id:string;count:number;ids:string[];prefix:string;buyers:Row[];total:number;native_process_pid:number;abrupt_worker_crash:boolean;owned_child_force_terminated:boolean;killed_native_exit:number;phase:string};
test.describe('C61-26 joined partial bulk and committed native process resumption',()=>{
registerStaffJourney('celery','keyboard',async({page,request,workspace,project,draftId,exportId,locale,layout})=>{
  const ui=(en:string,zh:string)=>locale==='en'?en:zh;
  const base=`http://127.0.0.1:8000/v1/workspaces/${workspace}`;
  const root=`${base}/projects/${project}/bulk-manifests`;
  const rootPath=new URL(root).pathname;
  const reviewer={Authorization:'Bearer fixture-reviewer'};
  const original=await request.get(`${base}/drafts/${draftId}`,{headers:reviewer});expect(original.status()).toBe(200);
  const draftBefore=(await original.json()).data;expect(draftBefore.approval_id).toBeTruthy();
  const exported=await request.get(`${base}/exports/${exportId}/content`,{headers:reviewer});expect(exported.status()).toBe(200);const originalBytes=await exported.body();
  async function fixture(command:string,...args:string[]):Promise<Native>{
    const cwd=resolve('services/worker'),python=resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
    const result=JSON.parse((await runOwnedFixtureProcess(python,['tests/fixtures/c61_joined_bulk_worker.py',project,command,...args],{cwd,timeout:45_000,maxBuffer:1024*1024})).stdout);
    expect(result.fixture_only).toBe(true);expect(result.project_id).toBe(project);expect(result.native_process_pid).toBeGreaterThan(0);return result;
  }
  const seeded=await fixture('seed');expect(seeded.count).toBe(120);
  // Results and Buyers both contain this control. Await the actual target
  // route and its real new snapshot before interacting with that module.
  const mountedSnapshot=page.waitForResponse(response=>{
    if(response.request().method()!=='POST'||new URL(response.url()).pathname!==`${new URL(base).pathname}/projects/${project}/buyer-snapshots`)return false;
    const current=new URL(page.url());return current.pathname==='/app/discover'&&current.searchParams.get('workspace')===workspace&&current.searchParams.get('project')===project;
  });
  await page.getByRole('button',{name:ui('Buyers','買家'),exact:true}).click();
  await expect(page).toHaveURL(url=>url.pathname==='/app/discover'&&url.searchParams.get('workspace')===workspace&&url.searchParams.get('project')===project);
  const actualSnapshot=await mountedSnapshot;expect(actualSnapshot.status()).toBe(201);

  const search=page.getByRole('textbox',{name:ui('Search buyers','搜尋買家'),exact:true});await search.fill(seeded.prefix);await search.press('Enter');
  await expect(search).toHaveValue(seeded.prefix);
  await expect(page).toHaveURL(url=>url.searchParams.get('q')===seeded.prefix);
  const panel=()=>page.getByRole('region',{name:ui('Segmented maintenance','分段批量維護'),exact:true});
  async function preview(){
    await panel().getByRole('textbox',{name:ui('Maintenance reason','維護理由'),exact:true}).fill('C61 same-project exact failed-only maintenance');
    const pending=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname===rootPath);
    await panel().getByRole('button',{name:ui('Preview segmented maintenance','預覽分段批量維護'),exact:true}).click();
    const response=await pending;expect(response.status()).toBe(201);return (await response.json()).data as {id:string;count:number;digest:string;version:number};
  }
  async function execute(id:string){
    await panel().getByRole('checkbox',{name:ui('Confirm exact manifest','確認精確維護清單'),exact:true}).check();
    const pending=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname===`${rootPath}/${id}/execute`);
    await panel().getByRole('button',{name:ui('Execute confirmed manifest','執行已確認維護清單'),exact:true}).click();return await pending;
  }
  const manifest=await preview();expect(manifest.count).toBe(120);
  await fixture('stale-many',...seeded.ids.slice(100));
  const admitted=await execute(manifest.id);expect(admitted.status()).toBe(202);const jobId=(await admitted.json()).data.id;
  const first=await fixture('crash-after-committed-chunk',jobId);expect(first.total).toBe(50);
  expect(first.phase).toBe('paused_after_committed_chunk');expect(first.abrupt_worker_crash).toBe(true);expect(first.owned_child_force_terminated).toBe(true);expect(first.killed_native_exit).not.toBe(0);
  const partial=await fixture('inspect');expect(partial.buyers.filter(row=>row.owner!==null).length).toBeGreaterThan(0);
  const committed=partial.buyers.filter(row=>row.owner!==null);
  const resumed=await fixture('drain',jobId);expect(resumed.total).toBe(70);expect(resumed.native_process_pid).not.toBe(first.native_process_pid);
  const after=await fixture('inspect');expect(after.buyers.filter(row=>row.owner!==null&&row.version===2)).toHaveLength(100);expect(after.buyers.filter(row=>row.owner===null&&row.version===2)).toHaveLength(20);
  for(const row of committed)expect(after.buyers.find(value=>value.id===row.id)).toEqual(row);
  const job=page.getByRole('region',{name:ui('Bulk job progress','批量工作進度'),exact:true});
  await job.getByRole('button',{name:ui('Refresh job','更新工作進度'),exact:true}).click();
  let directRetries=0;page.on('request',r=>{if(new URL(r.url()).pathname.endsWith('/retry-failed'))directRetries++;});
  await job.getByRole('button',{name:ui('Preview failed rows with current versions','按目前版本預覽失敗列'),exact:true}).click();
  const child=await preview();expect(child.count).toBe(20);expect(child.digest).not.toBe(manifest.digest);
  const childResult=await execute(child.id);expect(childResult.status()).toBe(200);
  const complete=await fixture('inspect');expect(complete.buyers.filter(row=>row.owner!==null&&row.version===3)).toHaveLength(20);
  const successful=after.buyers.filter(row=>row.owner!==null);
  for(const row of successful)expect(complete.buyers.find(value=>value.id===row.id)).toEqual(row);
  expect(directRetries).toBe(0);
  const readback=await request.get(`${base}/drafts/${draftId}`,{headers:reviewer});expect(readback.status()).toBe(200);const draftAfter=(await readback.json()).data;
  expect(draftAfter.revision_id).toBe(draftBefore.revision_id);expect(draftAfter.version).toBe(draftBefore.version);expect(draftAfter.approval_id).toBe(draftBefore.approval_id);expect(draftAfter.body).toBe(draftBefore.body);
  const exportAfter=await request.get(`${base}/exports/${exportId}/content`,{headers:reviewer});expect(exportAfter.status()).toBe(200);expect(await exportAfter.body()).toEqual(originalBytes);
  await test.info().attach('same-project partial bulk and abrupt native process restart',{body:JSON.stringify({fixture_only:true,workspace,project,draftId,exportId,locale,layout,parent_manifest:manifest,child_manifest:child,jobId,first_native_process_pid:first.native_process_pid,resumed_native_process_pid:resumed.native_process_pid,first_processed:50,resumed_processed:70,updated:100,conflicts:20,failed_only_new_preview_count:20,successful_rows_replayed:0,committed_first_chunk_successes:committed.length,direct_retry_requests:directRetries,approved_revision_unchanged:true,approved_export_sha256:createHash('sha256').update(originalBytes).digest('hex'),keyboard_standard_journey_verified_before_extension:true,extension_uses_ordinary_controls:true,abrupt_native_worker_process_killed_after_commit:first.owned_child_force_terminated,killed_native_exit:first.killed_native_exit,Celery_broker_ack_window_tested:false,unknown_provider_acceptance:false,real_provider:false,human_UAT:false}),contentType:'application/json'});
},{acceptedUnknownSearch:true});
});
