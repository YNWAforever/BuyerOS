import {expect,test,type Page,type Response} from '@playwright/test';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {resolve} from 'node:path';
import {writeFile} from 'node:fs/promises';
import {signIn,type StaffJourneyReadback} from './staff-journey';
type Receipt={path:string;method:string;status:number;request_id:string|null};
const paths=new WeakMap<Page,Set<string>>(),receipts=new WeakMap<Page,Receipt[]>(),pending=new WeakMap<Page,Promise<void>[]>();
export async function observeJoinedPages({page,browser}:{page:Page;browser:import('@playwright/test').Browser}){
 const observed=new Set<string>(),reads:Receipt[]=[],promises:Promise<void>[]=[];paths.set(page,observed);receipts.set(page,reads);pending.set(page,promises);
 const watch=(target:Page)=>{
  target.on('framenavigated',frame=>{if(frame===target.mainFrame())observed.add(new URL(frame.url()).pathname);});
  target.on('response',response=>{const path=new URL(response.url()).pathname;if(!path.startsWith('/v1/'))return;
   promises.push((async()=>{const body=response.headers()['content-type']?.includes('json')?await response.json().catch(()=>({})):{};
    reads.push({path,method:response.request().method(),status:response.status(),request_id:response.headers()['x-request-id']??body.request_id??null});})());});
 };watch(page);browser.on('context',context=>context.on('page',watch));
}
export async function joinedReadback(c:StaffJourneyReadback,unicodeGrounding?:Record<string,unknown>){
 const label=(en:string,zh:string)=>c.locale==='en'?en:zh;
 const activate=async(page:Page,en:string,zh:string)=>page.getByRole('button',{name:label(en,zh),exact:true}).click();
 const response=async(page:Page,suffix:string,action:()=>Promise<void>):Promise<Response>=>{const read=page.waitForResponse(r=>r.request().method()==='GET'&&new URL(r.url()).pathname.endsWith(suffix));await action();const result=await read;expect(result.status(),await result.text()).toBe(200);return result;};
 const settings=async(page:Page,role:'operator'|'reviewer'|'workspace_admin')=>{
  const read=await response(page,'/capabilities',()=>activate(page,'Settings','設定')),data=(await read.json()).data;
  const panel=page.getByRole('region',{name:label('Provider capabilities','供應商功能'),exact:true});
  expect(data.items).toHaveLength(5);await expect(panel.locator('[data-capability]')).toHaveCount(5);
  for(const item of data.items){await expect(panel.locator(`[data-capability="${item.name}"] time`)).toHaveAttribute('datetime',item.checked_at);}
  const names={operator:'操作員',reviewer:'審批員',workspace_admin:'工作區管理員'};
  await expect(page.getByRole('region',{name:label('Role responsibilities','角色責任'),exact:true}).locator('output')).toContainText(c.locale==='en'?role:names[role]);
  await expect(page.getByRole('region',{name:label('Member management','成員管理'),exact:true})).toHaveCount(role==='workspace_admin'?1:0);
  return {role,capabilities:data.items.map((item:{name:string;status:string})=>({name:item.name,status:item.status}))};
 };
 const queue=await response(c.page,'/work-queue',()=>activate(c.page,'Overview','總覽')),queueData=(await queue.json()).data;
 expect(queueData.items).toHaveLength(6);const panel=c.page.getByRole('region',{name:label('Daily work queue','每日工作佇列'),exact:true});
 await expect(panel).toBeVisible();for(const item of queueData.items)await expect(panel.locator(`[data-work-queue-kind="${item.kind}"] output`)).toHaveText(String(item.count));
 const operator=await settings(c.page,'operator'),reviewer=await settings(c.reviewer,'reviewer');
 const adminContext=await c.browser.newContext({viewport:c.layout==='mobile'?{width:390,height:844}:{width:1280,height:800}});
 try{
  const admin=await adminContext.newPage();await signIn(admin,'fixture-admin',`/app?workspace=${c.workspace}&project=${c.project}`,c.locale);
  const administrator=await settings(admin,'workspace_admin');
  await activate(c.page,'Operations','營運工作台');
  const lookup=c.page.getByRole('region',{name:label('Job lookup','工作查詢'),exact:true});
  await lookup.getByRole('textbox',{name:label('Job ID','工作識別碼'),exact:true}).fill(c.draftJobId);
  const jobRead=await response(c.page,`/jobs/${c.draftJobId}`,()=>lookup.getByRole('button',{name:label('Load job','載入工作'),exact:true}).click()),job=(await jobRead.json()).data;
  expect(job.id).toBe(c.draftJobId);expect(job.status).toBe('completed');
  await expect(lookup.getByRole('region',{name:label('Job details','工作詳情'),exact:true})).toBeVisible();
  const beforeLogout={locale:await c.page.locator('html').getAttribute('lang'),stored_locale:await c.page.evaluate(()=>localStorage.getItem('buyeros.locale'))};
  await activate(c.page,'Sign out','登出');await c.page.waitForURL('http://localhost:5173/app');
  const signedOut=c.page.getByRole('button',{name:/^(Sign in|登入)$/,exact:true});await expect(signedOut).toBeVisible();
  await expect(c.page.getByRole('combobox',{name:/^(Project|專案)$/,exact:true})).toHaveCount(0);
  const logout={before:beforeLogout,after_locale:await c.page.locator('html').getAttribute('lang'),sign_in_label:await signedOut.innerText(),scope_cleared:true};
  await signIn(c.page,'fixture-access',`/app/results?workspace=${c.workspace}&project=${c.project}`,c.locale);
  await expect(c.page.getByRole('region',{name:label('Manual outcomes','人手記錄成果'),exact:true})).toContainText('T30 continuous fixture outcome after approved copy');
  const cwd=resolve('services/worker'),py=resolve(cwd,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
  const child=await promisify(execFile)(py,[resolve('tests/e2e/fixtures/c61-owned-readback.py'),c.project,c.runId,c.buyerId,c.draftId,c.exportId],{cwd,timeout:60_000,maxBuffer:1024*1024});
  const persisted=JSON.parse(child.stdout);expect(persisted.workspace_id).toBe(c.workspace);expect(persisted.approval.recipient_contact_id).toBe(c.contactId);
  expect(persisted.draft.id).toBe(c.draftId);expect(persisted.run.id).toBe(c.runId);expect(persisted.export.id).toBe(c.exportId);
  if(unicodeGrounding){expect(persisted.approval.draft_revision_id).toBe(unicodeGrounding.approved_revision_id);expect(persisted.approval.content_hash).toBe(unicodeGrounding.approved_content_hash);expect(persisted.export.draft_revision_id).toBe(unicodeGrounding.approved_revision_id);}
  await Promise.all(pending.get(c.page)!);const reads=receipts.get(c.page)!,observed=[...paths.get(c.page)!];
  expect(observed).toEqual(expect.arrayContaining(['/app','/app/discover/edit','/app/discover','/app/results','/app/runs','/app/outreach','/app/settings','/app/operations']));
  expect(reads.filter(r=>r.path.endsWith('/capabilities')&&r.status===200).length).toBeGreaterThanOrEqual(3);
  expect(reads.some(r=>r.path.endsWith(`/jobs/${c.draftJobId}`)&&r.status===200)).toBe(true);
  expect(reads.every(r=>r.request_id!==null)).toBe(true);
  const ledger={version:1,environment:'built-owned-legacy-Celery-fixture',locale:c.locale,layout:c.layout,observed_paths:observed,scope:{workspace_id:c.workspace,project_id:c.project},chain:{run_id:c.runId,buyer_id:c.buyerId,contact_id:c.contactId,draft_id:c.draftId,job_id:c.draftJobId,export_id:c.exportId},roles:[operator,reviewer,administrator],logout,requests:reads,persisted,source_sha:process.env.C61_SOURCE_SHA,real_provider_accepted:false,Neon_preview_accepted:false,human_UAT:false,release_A_accepted:false,native_send_accepted:false,unicode_grounding:unicodeGrounding??null,remaining_local:unicodeGrounding?['other joined failure injections','failed-only bulk TTL in this dataset']:['joined failure injections','Unicode revision reground in this dataset','failed-only bulk TTL in this dataset'],remaining_external:['real provider/Neon same-artifact preview','human UAT']};
  await writeFile(`test-results/c61-26-${unicodeGrounding?'unicode-':''}${c.locale}-${c.layout}-journey-ledger.json`,JSON.stringify(ledger,null,2));await test.info().attach('eight-module-owned-fixture-ledger',{body:JSON.stringify(ledger,null,2),contentType:'application/json'});
 }finally{await adminContext.close();}
}
