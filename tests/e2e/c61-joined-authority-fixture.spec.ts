import {expect,test} from '@playwright/test';
import {registerStaffJourney} from './fixtures/staff-journey';

// Existing access/dirty-buffer repairs are exercised after one UI-created
// research -> exact review -> approved export -> manual outcome chain.
// Actual disposable API/PG/Celery; fictional identity/provider, no human UAT.
test.describe('C61-26 joined lost acknowledgement and authority faults',()=>{
registerStaffJourney('celery','keyboard',async ({page,reviewer,request,workspace,project,draftId,exportId,locale,layout,groundingReceipt})=>{
  const ui=(en:string,zh:string)=>locale==='en'?en:zh;
  expect(groundingReceipt?.requests).toHaveLength(2);
  expect(groundingReceipt?.requests[1]).toEqual(groundingReceipt?.requests[0]);
  expect(groundingReceipt?.committed_status).toBe(200);
  const base=`http://127.0.0.1:8000/v1/workspaces/${workspace}`;
  const admin={Authorization:'Bearer fixture-admin'};
  const operator={Authorization:'Bearer fixture-access'};
  const review={Authorization:'Bearer fixture-reviewer'};
  const members=await request.get(`${base}/memberships?limit=100`,{headers:admin});
  expect(members.status()).toBe(200);
  type Member={id:string;user_id:string;active:boolean;roles:string[];version:number};
  const original=((await members.json()).data.items as Member[]).find(m=>m.id==='e0000000-0000-4000-8000-000000000003');
  expect(original?.active).toBe(true);expect(original?.roles).toContain('operator');
  const draftResponse=await request.get(`${base}/drafts/${draftId}`,{headers:review});
  expect(draftResponse.status()).toBe(200);const before=(await draftResponse.json()).data;
  expect(before.approval_id).toBeTruthy();
  const exportBefore=await request.get(`${base}/exports/${exportId}/content`,{headers:review});
  expect(exportBefore.status()).toBe(200);const approvedBytes=await exportBefore.body();
  await page.getByRole('button',{name:ui('Drafts','草稿'),exact:true}).click();
  const list=page.getByRole('region',{name:ui('Draft list','草稿列表'),exact:true});
  await expect(list.getByRole('button',{name:ui('Open draft','開啟草稿'),exact:true})).toHaveCount(1);
  await list.getByRole('button',{name:ui('Open draft','開啟草稿'),exact:true}).click();
  const editor=page.getByRole('region',{name:ui('Open draft','開啟草稿'),exact:true});
  const body=editor.getByRole('textbox',{name:ui('Body','內容'),exact:true});
  await expect(body).toBeEnabled();const dirty=(await body.inputValue())+' 保留未保存內容🙂';
  await body.fill(dirty);await expect(editor).toHaveAttribute('data-live-unsaved','true');
  const writes:{method:string;url:string}[]=[];
  page.on('request',r=>{if(r.method()==='PATCH'&&new URL(r.url()).pathname===`/v1/workspaces/${workspace}/drafts/${draftId}`)writes.push({method:r.method(),url:r.url()});});
  let changed:Member|undefined;
  try{
    const withdrawal=await request.patch(`${base}/memberships/${original!.id}`,{headers:{...admin,'If-Match':`"${original!.version}"`,'Idempotency-Key':crypto.randomUUID()},data:{active:true,roles:['viewer'],reason:'C61-26 disposable joined authority regression'}});
    expect(withdrawal.status()).toBe(200);changed=(await withdrawal.json()).data;
    expect(changed?.user_id).toBe(original!.user_id);expect(changed?.version).toBe(original!.version+1);
    const denied=page.waitForResponse(r=>r.request().method()==='PATCH'&&new URL(r.url()).pathname===`/v1/workspaces/${workspace}/drafts/${draftId}`);
    const save=editor.getByRole('button',{name:ui('Save revision','儲存修訂'),exact:true});
    await save.click();const refusal=await denied;expect(refusal.status()).toBe(403);expect((await refusal.json()).code).toBe('PERMISSION_DENIED');
    await expect(save).toBeDisabled();await expect(body).toHaveValue(dirty);await expect(editor).toHaveAttribute('data-live-unsaved','true');
    const retained=await request.get(`${base}/drafts/${draftId}`,{headers:operator});
    expect(retained.status()).toBe(200);const after=(await retained.json()).data;
    expect(after.revision_id).toBe(before.revision_id);expect(after.version).toBe(before.version);expect(after.body).toBe(before.body);expect(after.approval_id).toBe(before.approval_id);
    const exportAfter=await request.get(`${base}/exports/${exportId}/content`,{headers:review});
    expect(exportAfter.status()).toBe(200);expect(await exportAfter.body()).toEqual(approvedBytes);
    expect(writes).toHaveLength(1);
    await test.info().attach('joined revoked write retained exact dirty and immutable approved data',{body:JSON.stringify({fixture_only:true,workspace,project,draftId,exportId,locale,layout,canonical_user_uuid:original!.user_id,membership_version_before:original!.version,membership_version_after:changed!.version,denied_write_status:403,native_draft_PATCH_count:writes.length,revision_unchanged:after.revision_id===before.revision_id,approval_unchanged:after.approval_id===before.approval_id,approved_export_bytes_unchanged:true,dirty_unicode_buffer_retained:true,real_provider:false,human_UAT:false}),contentType:'application/json'});
  }finally{
    if(changed){
      const restored=await request.patch(`${base}/memberships/${original!.id}`,{headers:{...admin,'If-Match':`"${changed.version}"`,'Idempotency-Key':crypto.randomUUID()},data:{active:original!.active,roles:original!.roles,reason:'Restore only this disposable joined fixture membership'}});
      expect(restored.status()).toBe(200);expect((await restored.json()).data.user_id).toBe(original!.user_id);
    }
  }
  // The reviewer is a different canonical user/context and has no dirty edit.
  const projects=await request.get(`${base}/projects?limit=100`,{headers:review});expect(projects.status()).toBe(200);
  const other=((await projects.json()).data.items as {id:string}[]).find(p=>p.id!==project);expect(other).toBeTruthy();
  let release:()=>void=()=>{},received:()=>void=()=>{},completed:()=>void=()=>{};
  const held=new Promise<void>(r=>release=r),started=new Promise<void>(r=>received=r),finished=new Promise<void>(r=>completed=r);
  const path=`**/v1/workspaces/${workspace}/drafts/${draftId}`;
  let oldResponses=0;
  await reviewer.route(path,async route=>{
    expect(route.request().method()).toBe('GET');const response=await route.fetch();expect(response.status()).toBe(200);
    expect((await response.json()).data.revision_id).toBe(before.revision_id);oldResponses++;received();await held;
    try{await route.fulfill({response});}catch{ /* A scope switch may cancel this already held read. */ }finally{completed();}
  });
  try{
    await reviewer.getByRole('button',{name:ui('Refresh draft','重新整理草稿'),exact:true}).click();await started;
    await reviewer.getByRole('combobox',{name:ui('Project','專案'),exact:true}).selectOption(other!.id);
    await expect(reviewer.getByRole('region',{name:ui('Open draft','開啟草稿'),exact:true})).toHaveCount(0);
    release();await finished;
    await expect(reviewer.getByRole('combobox',{name:ui('Project','專案'),exact:true})).toHaveValue(other!.id);
    await expect(reviewer.getByRole('region',{name:ui('Open draft','開啟草稿'),exact:true})).toHaveCount(0);
    expect(new URL(reviewer.url()).searchParams.get('draft')).toBeNull();expect(oldResponses).toBe(1);
    await expect(body).toHaveValue(dirty);
    await test.info().attach('joined actual delayed scoped read cannot revive prior draft',{body:JSON.stringify({fixture_only:true,workspace,source_project:project,current_project:other!.id,draftId,prior_revision:before.revision_id,old_owned_HTTP_status:200,old_owned_HTTP_response_count:oldResponses,old_draft_region_absent:true,original_operator_dirty_buffer_retained:true,grounding_commit_status:groundingReceipt!.committed_status,grounding_requests:groundingReceipt!.requests.length,same_grounding_intent_retry:true,real_provider:false,human_UAT:false}),contentType:'application/json'});
  }finally{release();await reviewer.unroute(path);}
  await page.screenshot({path:`test-results/joined-authority-${locale}-${layout}-dirty-fixture.png`,fullPage:true});
},{unicode:true,loseGroundingAck:true,delayedReviewAck:true});
});
