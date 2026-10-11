import type {components} from '@/services/generated/buyeros-api';
import {createOperationClient, type WriteContext} from './operations';
import {LiveCancelled} from './client';
import type {RunContext} from './runs';
import type {SessionScope} from './session';

export type CandidatePage=components['schemas']['ResearchCandidatePage'];
export type CandidateObservation=components['schemas']['ResearchCandidateObservation'];
export type CandidateReviewContext=components['schemas']['ResearchCandidateReviewContext'];
export type CandidateReviewResult=components['schemas']['ResearchCandidateReviewResult'];
type ReviewBody=components['schemas']['ResearchCandidateReviewRequest'];
export interface CandidateReviewDraft {
  companyId:string;context:CandidateReviewContext|null;excerpt:string;reason:string;
  phase:'editing'|'pending'|'unknown'|'accepted'|'expired';result:CandidateReviewResult|null;
  frozen:Readonly<ReviewBody>|null;key:string|null;pending:Promise<CandidateReviewResult>|null;
}

function captured(ctx:RunContext):WriteContext {
  const basis=ctx.session.captureWriteContext();
  if(basis.workspace!==ctx.workspaceId||basis.project!==ctx.projectId)throw new LiveCancelled('scope changed');
  return {...basis,getToken:async()=>{const token=ctx.session.token();if(!token)throw new LiveCancelled('signed out');return token;},
    isCurrent:()=>ctx.session.isCurrent(basis.identity)};
}
export async function loadResearchCandidates(ctx:RunContext,runId:string,offset=0,limit=20):Promise<CandidatePage>{
  return createOperationClient(ctx.client).requestOperation('listResearchCandidates',{
    path:{workspace_id:ctx.workspaceId,run_id:runId},query:{offset,limit}},captured(ctx));
}
export async function getCandidateReviewContext(ctx:RunContext,runId:string,rawId:string,companyId:string):Promise<CandidateReviewContext>{
  return createOperationClient(ctx.client).requestOperation('getResearchCandidateReviewContext',{
    path:{workspace_id:ctx.workspaceId,run_id:runId,raw_candidate_id:rawId},query:{company_id:companyId}},captured(ctx));
}
// In-memory session-owned review drafts survive route remounts; never persist credentials or source prose.
const drafts=new WeakMap<SessionScope,Map<string,CandidateReviewDraft>>();
export function candidateReviewDraft(ctx:RunContext,runId:string,rawId:string):CandidateReviewDraft {
  captured(ctx);const scope=ctx.session.current();
  const key=JSON.stringify([scope.mode,scope.actor,ctx.workspaceId,ctx.projectId,runId,rawId]);
  let own=drafts.get(ctx.session);if(!own){own=new Map();drafts.set(ctx.session,own);
    if(typeof window!=='undefined'){
      const records=own;
      window.addEventListener('beforeunload',event=>{
        if([...records.values()].some(d=>d.phase!=='accepted'&&(d.reason||d.excerpt||d.key))){event.preventDefault();event.returnValue='';}
      });
    }
  }
  let value=own.get(key);if(!value){value={companyId:'',context:null,excerpt:'',reason:'',phase:'editing',result:null,frozen:null,key:null,pending:null};own.set(key,value);}
  expireCandidateReviewDraft(value);
  return value;
}
// Component events use explicit ports; the session-owned buffer is not React state.
// Keep the earliest retained quote deadline even when a user changes company.
const retainedSourceDeadlines=new WeakMap<CandidateReviewDraft,number>();
export function updateCandidateReviewDraft(draft:CandidateReviewDraft,patch:Partial<Pick<CandidateReviewDraft,'companyId'|'excerpt'|'reason'>>):boolean {
  if(draft.phase!=='editing'||draft.frozen)return false;
  if(patch.companyId!==undefined&&patch.companyId!==draft.companyId)draft.context=null;
  Object.assign(draft,patch);
  return true;
}
export function bindCandidateReviewSource(draft:CandidateReviewDraft,context:CandidateReviewContext):boolean {
  if(draft.phase!=='editing'||draft.frozen||context.company.id!==draft.companyId)return false;
  draft.context=context;
  if(!draft.excerpt)draft.excerpt=context.page.excerpt;
  watchCandidateReviewSource(draft);
  return draft.phase==='editing';
}
const expiryTimers=new WeakMap<CandidateReviewDraft,ReturnType<typeof setTimeout>>();
export function watchCandidateReviewSource(draft:CandidateReviewDraft):void {
  const previous=expiryTimers.get(draft);if(previous)clearTimeout(previous);
  expiryTimers.delete(draft);
  if(draft.context){const deadline=Date.parse(draft.context.page.retention_until);retainedSourceDeadlines.set(draft,Math.min(retainedSourceDeadlines.get(draft)??Infinity,deadline));}
  if(expireCandidateReviewDraft(draft))return;
  const deadline=retainedSourceDeadlines.get(draft);if(deadline===undefined)return;
  const delay=Math.max(1,Math.min(deadline-Date.now(),2_147_483_647));
  const timer=setTimeout(()=>{expiryTimers.delete(draft);watchCandidateReviewSource(draft);},delay);
  if(typeof timer==='object')(timer as unknown as {unref?:()=>void}).unref?.();
  expiryTimers.set(draft,timer);
}
export function expireCandidateReviewDraft(draft:CandidateReviewDraft,now=Date.now()):boolean {
  if(draft.phase==='expired')return true;
  const deadline=Math.min(retainedSourceDeadlines.get(draft)??Infinity,draft.context?Date.parse(draft.context.page.retention_until):Infinity);
  if(!(deadline>now)){
    draft.context=null;draft.excerpt='';draft.frozen=null;draft.phase='expired';
    // Keep original key/result/reason for reconciliation; no new material can reuse this intent.
    return true;
  }
  return false;
}
export async function submitCandidateReview(ctx:RunContext,runId:string,rawId:string,draft:CandidateReviewDraft):Promise<CandidateReviewResult>{
  const write=captured(ctx);
  watchCandidateReviewSource(draft);
  if(draft.phase==='expired')throw new Error('Source expired; current reconciliation required');
  const context=draft.context;
  if(context?.entity_status==='reviewed'&&!draft.frozen)throw new Error('Existing entity review requires reconciliation; no new intent');
  if(!context||context.project_id!==ctx.projectId||context.run_id!==runId||context.raw_candidate_id!==rawId
    ||context.company.id!==draft.companyId)throw new Error('Current chosen-company review context required');
  if(!Number.isFinite(Date.parse(context.page.retention_until))||Date.parse(context.page.retention_until)<=Date.now())throw new Error('Review source expired; reload current context');
  if(draft.reason.trim().length<10||draft.reason.length>400||draft.excerpt.length<5||new TextEncoder().encode(draft.excerpt).length>4000
    ||!context.page.excerpt.includes(draft.excerpt))throw new Error('A bounded exact page quote and explicit review reason are required');
  const body:ReviewBody={company_id:context.company.id,page_source_id:context.page.id,expected_page_digest:context.page.digest,
    expected_company_hash:context.company.hash,excerpt:draft.excerpt,reason:draft.reason};
  if(draft.frozen&&JSON.stringify(body)!==JSON.stringify(draft.frozen))throw new Error('Review intent is frozen; retry the same material and key');
  if(draft.phase==='accepted'&&draft.result)return draft.result;
  if(draft.pending)return draft.pending;
  if(!draft.frozen){draft.frozen=Object.freeze({...body});draft.key=crypto.randomUUID();}
  draft.phase='pending';
  const pending=createOperationClient(ctx.client).requestOperation('reviewResearchCandidate',{
    path:{workspace_id:ctx.workspaceId,run_id:runId,raw_candidate_id:rawId},header:{'Idempotency-Key':draft.key!},body:{...draft.frozen}},write);
  draft.pending=pending;
  try{const result=await pending;draft.result=result;if(!expireCandidateReviewDraft(draft))draft.phase='accepted';return result;}
  catch(error){if(!expireCandidateReviewDraft(draft))draft.phase='unknown';throw error;}
  finally{draft.pending=null;}
}
