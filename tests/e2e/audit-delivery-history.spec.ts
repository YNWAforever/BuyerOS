import {expect,test} from '@playwright/test';
import {registerWorkbenchStaffJourney as registerStaffJourney} from './fixtures/staff-journey';

// Four locale/layout UI-created journeys. History states below are display-only
// browser metadata fixtures; real restricted PG history has a separate proof.
registerStaffJourney('celery','pointer',async ({page,reviewer,request,workspace,project,draftId,locale,layout})=>{
  const heading=locale==='en'?'Native delivery history':'站內寄送紀錄';
  await expect(reviewer.getByRole('region',{name:heading,exact:true})).toBeVisible();
  await expect(reviewer.getByRole('textbox',{name:locale==='en'?'Body':'內容',exact:true})).toBeDisabled();
  // The original operator retains edit authority; the reviewer remains read-only.
  await page.getByRole('button',{name:locale==='en'?'Drafts':'草稿',exact:true}).click();
  const list=page.getByRole('region',{name:locale==='en'?'Draft list':'草稿列表',exact:true});
  await expect(list.getByRole('button',{name:locale==='en'?'Open draft':'開啟草稿',exact:true})).toHaveCount(1);
  await list.getByRole('button',{name:locale==='en'?'Open draft':'開啟草稿',exact:true}).click();
  const history=page.getByRole('region',{name:heading,exact:true});
  await expect(history).toBeVisible();
  const original=await request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${draftId}`,{headers:{Authorization:'Bearer fixture-reviewer'}});
  expect(original.status()).toBe(200);const draft=(await original.json()).data;
  let error=false;const seen:string[]=[],submits:string[]=[];
  page.on('request',r=>{if(r.method()==='POST'&&new URL(r.url()).pathname.endsWith('/delivery-intents'))submits.push(r.url());});
  const ids=['90000001-1111-4000-8000-111111111111','90000001-1111-4000-8000-111111111112'];
  const items=['unknown','accepted'].map((state,i)=>({id:ids[i],workspace_id:workspace,project_id:project,draft_id:draftId,draft_revision_id:draft.revision_id,revision_number:draft.revision_number,approval_id:draft.approval_id,state,created_at:'2026-10-11T00:00:00Z',updated_at:'2026-10-11T00:00:00Z'}));
  await page.route(`**/v1/workspaces/${workspace}/projects/${project}/drafts/${draftId}/delivery-messages**`,async route=>{
    const req=route.request();expect(req.method()).toBe('GET');expect(req.postData()).toBeNull();seen.push(req.url());
    await route.fulfill({status:error?503:200,contentType:'application/json',body:JSON.stringify(error?
      {code:'READ_DISABLED',message:'fixture read paused',request_id:'90000001-1111-4000-8000-111111111113',retryable:true}:
      {data:{items,offset:0,limit:20,total:2},request_id:'90000001-1111-4000-8000-111111111113',data_mode:'live'})});
  });
  const body=page.getByRole('textbox',{name:locale==='en'?'Body':'內容',exact:true});const dirty=(await body.inputValue())+' Unsaved local note.';
  await expect(body).toBeEnabled();await body.fill(dirty);
  const editor=page.getByRole('region',{name:locale==='en'?'Open draft':'開啟草稿',exact:true});
  await expect(editor).toHaveAttribute('data-live-unsaved','true');
  const refresh=history.getByRole('button',{name:locale==='en'?'Refresh delivery history':'重新整理寄送紀錄',exact:true});
  await refresh.click();
  await expect(history.getByText(locale==='en'?'Outcome unknown':'結果未知',{exact:true})).toBeVisible();
  await expect(history.getByText(locale==='en'?'Accepted by provider':'供應商已受理',{exact:true})).toBeVisible();
  await expect(history.getByText(locale==='en'?'Delivered':'已送達',{exact:true})).toHaveCount(0);
  await expect(body).toHaveValue(dirty);
  await refresh.click();await expect(refresh).toBeEnabled();await expect(body).toHaveValue(dirty);expect(submits).toEqual([]);
  await page.screenshot({path:`test-results/history-${locale}-${layout}-metadata-fixture.png`,fullPage:true});
  error=true;await refresh.click();await expect(history.getByRole('alert')).toBeVisible();
  await expect(history.getByText(locale==='en'?'Accepted by provider':'供應商已受理',{exact:true})).toHaveCount(0);
  await expect(body).toHaveValue(dirty);expect(submits).toEqual([]);await expect(editor).toHaveAttribute('data-live-unsaved','true');expect(seen.length).toBeGreaterThanOrEqual(3);
  await test.info().attach('history-display-fixture-boundary',{body:JSON.stringify({locale,layout,metadata_source:'display-only browser route fixture',owned_ui_created_draft:draftId,history_GETs:seen.length,native_delivery_POSTs:submits.length,real_provider:false,human_UAT:false}),contentType:'application/json'});
});
