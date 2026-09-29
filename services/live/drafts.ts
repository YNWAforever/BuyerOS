import type {components} from '@/services/generated/buyeros-api';
import {buyerOperationContext} from './buyers';
import {createOperationClient} from './operations';
import type {LiveClient} from './client';
import type {SessionScope} from './session';

export type Draft = components['schemas']['Draft'];
export type DraftJob = components['schemas']['AsyncJob'];
export type Project = components['schemas']['Project'];
export type Icp = components['schemas']['ICPVersion'];
export type Buyer = components['schemas']['Buyer'];
export type Evidence = components['schemas']['Evidence'];
export type DraftRequest = components['schemas']['DraftGenerateRequest'];
export type DraftChange = components['schemas']['DraftUpdate'];

function operation(client:LiveClient,session:SessionScope){
  return {api:createOperationClient(client),ctx:buyerOperationContext(session)};
}
export async function loadDraftContext(client:LiveClient,session:SessionScope,buyerId:string){
  const {api,ctx}=operation(client,session),workspace_id=ctx.workspace,project_id=ctx.project!;
  const [project,buyer]=await Promise.all([
    api.requestOperation('getProject',{path:{workspace_id,project_id}},ctx),
    api.requestOperation('getBuyer',{path:{workspace_id,buyer_id:buyerId}},ctx),
  ]);
  const icpVersions:Icp[]=[],evidence:Evidence[]=[];
  for(let offset=0;;){
    const page=await api.requestOperation('listICPVersions',{path:{workspace_id,project_id},query:{offset,limit:100}},ctx);
    if(page.offset!==offset||page.items.length>100)throw new Error('Invalid profile page');
    icpVersions.push(...page.items);
    if(icpVersions.length>=page.total)break;
    if(page.items.length!==100)throw new Error('Incomplete profile page');
    offset+=page.items.length;
  }
  for(let offset=0;;){
    const page=await api.requestOperation('listBuyerEvidence',{path:{workspace_id,buyer_id:buyerId},query:{offset,limit:100}},ctx);
    if(page.offset!==offset||page.items.length>100)throw new Error('Invalid evidence page');
    evidence.push(...page.items);
    if(evidence.length>=page.total)break;
    if(page.items.length!==100)throw new Error('Incomplete evidence page');
    offset+=page.items.length;
  }
  return {project,buyer,icp:icpVersions.find(row=>row.id===project.active_icp_version_id)||null,evidence};
}
export async function getProject(client:LiveClient,session:SessionScope):Promise<Project>{
  const {api,ctx}=operation(client,session);
  return api.requestOperation('getProject',{path:{workspace_id:ctx.workspace,project_id:ctx.project!}},ctx);
}
export async function saveSender(client:LiveClient,session:SessionScope,project:Project,
  sender:components['schemas']['SenderIdentityUpdate']):Promise<Project>{
  const {api,ctx}=operation(client,session);
  return api.requestOperation('updateProject',{path:{workspace_id:ctx.workspace,project_id:ctx.project!},
    header:{'If-Match':`"${project.version}"`,'Idempotency-Key':crypto.randomUUID()},
    body:{sender_identity:sender}},ctx);
}
export async function listDrafts(client:LiveClient,session:SessionScope,offset:number,limit:number){
  const {api,ctx}=operation(client,session);
  return api.requestOperation('listDrafts',{path:{workspace_id:ctx.workspace,project_id:ctx.project!},query:{offset,limit}},ctx);
}
export async function generateDraft(client:LiveClient,session:SessionScope,body:DraftRequest,key:string):Promise<DraftJob>{
  const {api,ctx}=operation(client,session);
  return api.requestOperation('generateDraft',{path:{workspace_id:ctx.workspace,project_id:ctx.project!},
    header:{'Idempotency-Key':key},body},ctx);
}
export async function getDraftJob(client:LiveClient,session:SessionScope,jobId:string):Promise<DraftJob>{
  const {api,ctx}=operation(client,session);
  return api.requestOperation('getAsyncJob',{path:{workspace_id:ctx.workspace,job_id:jobId}},ctx);
}
export async function getDraft(client:LiveClient,session:SessionScope,draftId:string):Promise<Draft>{
  const {api,ctx}=operation(client,session);
  const draft=await api.requestOperation('getDraft',{path:{workspace_id:ctx.workspace,draft_id:draftId}},ctx);
  if(draft.project_id!==ctx.project)throw new Error('Draft is outside selected project');
  return draft;
}
export async function editDraft(client:LiveClient,session:SessionScope,draft:Draft,
  body:DraftChange,key:string):Promise<Draft>{
  const {api,ctx}=operation(client,session);
  return api.requestOperation('editDraft',{path:{workspace_id:ctx.workspace,draft_id:draft.id},
    header:{'If-Match':`"${draft.version}"`,'Idempotency-Key':key},body},ctx);
}

export async function requestDraftReview(client:LiveClient,session:SessionScope,draft:Draft,key:string):Promise<Draft>{
  const {api,ctx}=operation(client,session);
  return api.requestOperation('requestDraftReview',{path:{workspace_id:ctx.workspace,draft_id:draft.id},
    header:{'If-Match':`"${draft.version}"`,'Idempotency-Key':key},
    body:{revision_id:draft.revision_id,content_hash:draft.content_hash,context_hash:draft.context_hash}},ctx);
}
export async function approveExactDraft(client:LiveClient,session:SessionScope,draft:Draft,key:string){
  const review=draft.approval_review;
  if(!review)throw new Error('Exact review context is unavailable');
  const {api,ctx}=operation(client,session);
  return api.requestOperation('approveDraft',{path:{workspace_id:ctx.workspace,draft_id:draft.id},
    header:{'If-Match':`"${draft.version}"`,'Idempotency-Key':key},
    body:{revision_id:draft.revision_id,content_hash:draft.content_hash,
      context_hash:draft.context_hash,recipient_contact_id:review.recipient.id,
      recipient_contact_version:review.recipient.version,evidence_set_hash:draft.evidence_set_hash,
      icp_version_id:draft.icp_version_id,policy_decision_ids:review.policy_decision_ids,
      sender_identity_version:review.sender.version_key,confirmation:true}},ctx);
}
