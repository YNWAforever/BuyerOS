// Q09 U09: same UI-created dataset through a real disposable Celery/Valkey transport.
// OIDC/provider/contact/policy inputs remain fictional; this is not live provider verification.
import {test,expect} from '@playwright/test';
import {createHash} from 'node:crypto';
import {registerWorkbenchStaffJourney as registerStaffJourney} from './fixtures/staff-journey';
test.describe('Q09 U09',()=>registerStaffJourney('celery','pointer',async context=>{
 const {request,workspace,project,runId,buyerId,contactId,draftJobId,draftId,exportId,approvedCopy}=context;
 const response=await request.get(`http://127.0.0.1:8000/v1/workspaces/${workspace}/drafts/${draftId}`,{
   headers:{Authorization:'Bearer fixture-reviewer'}});
 expect(response.ok()).toBe(true);
 const current=(await response.json()).data;
 expect(current.project_id).toBe(project);
 expect(current.approval_id).toBeTruthy();
 await test.info().attach('same-project-durable-chain',{
   body:JSON.stringify({fixture_only:true,normal_company_UAT:false,real_provider:false,real_messages:0,
     workspace,project,runId,buyerId,contactId,draftJobId,draftId,exportId,
     revision_id:current.revision_id,revision_number:current.revision_number,
     approval_id:current.approval_id,content_hash:current.content_hash,
     exported_copy_sha256:createHash('sha256').update(approvedCopy).digest('hex')},null,2),
   contentType:'application/json'});
}));
