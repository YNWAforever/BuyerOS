import type {components} from '@/services/generated/buyeros-api';
import {conversationHomeEnabled} from '@/features/live/conversation-home';
import {LiveCancelled,LiveError,type LiveClient} from './client';
import type {SessionScope} from './session';
import {startResearch,getRun,resetResearchIntent,type RunContext} from './runs';
import {loadPilotBudget} from './pilot-budgets';

export const researchNotices={
  CAPABILITY_DISABLED:'Paid research is disabled. No research was started.',
  PROVIDER_UNAVAILABLE:'The research provider is unavailable. No research was started.',
  POLICY_BLOCKED:'Research needs current policy approval. No research was started.',
  BUDGET_LIMIT:'The approved budget cannot cover this research. No research was started.',
  STALE_REVISION:'The approved profile changed. Refresh and review the proposal again.',
  forbidden:'You do not have permission to start research.',
  unknown:'Research acceptance is unconfirmed. Check Research runs before retrying; retry uses the same request key.',
  context:'A current approved profile and verified remaining budget are required.',
} as const;
export function researchNotice(error:unknown):string{
  if(error instanceof LiveError){
    if(error.status===403)return researchNotices.forbidden;
    if(Object.hasOwn(researchNotices,error.code))return researchNotices[error.code as keyof typeof researchNotices];
  }
  return researchNotices.unknown;
}
export const conversationLimits={query_rounds:1,max_queries_per_run:3,max_results:30,max_pages:20,
  max_page_bytes:1048576,max_duration_seconds:300,max_model_tokens:14000,provider_concurrency:1} as const;
export type ResearchReview={profileId:string;profileNumber:number;remaining:string};
export type ResearchBody=components['schemas']['RunCreate'];
export type RunReference={id:string;label:'Research run';status:string};
const uuid=/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/;
const statuses=new Set(['draft','queued','running','partial','paused_budget','cancel_requested','cancelled','failed','completed','awaiting_reconciliation']);
export function validRunReference(value:unknown):value is RunReference{
  if(!value||typeof value!=='object')return false;
  const row=value as Record<string,unknown>;
  return Object.keys(row).length===3&&typeof row.id==='string'&&uuid.test(row.id)&&row.label==='Research run'&&typeof row.status==='string'&&statuses.has(row.status);
}
function context(client:LiveClient,session:SessionScope,enabled:boolean):RunContext{
  const scope=session.current();
  if(!conversationHomeEnabled(enabled?'true':undefined)||!session.token()||scope.mode!=='live'||!scope.actor||!scope.workspace||!scope.project)throw new LiveCancelled('scope changed');
  return {client,session,workspaceId:scope.workspace,projectId:scope.project,apiBaseUrl:''};
}
function fixed(value:unknown):value is string{return typeof value==='string'&&/^(?:0|[1-9]\d{0,13})\.\d{6}$/.test(value);}
/** Read only on explicit proposal. Never calls admission or stores profile/fact bodies. */
export async function reviewResearch(client:LiveClient,session:SessionScope,enabled:boolean,signal:AbortSignal):Promise<ResearchReview>{
  const ctx=context(client,session,enabled),identity=session.identity();
  const read=<T,>(path:string)=>client.request<T>({path,scope:identity,token:session.token(),signal:AbortSignal.any([signal,session.controller().signal])});
  const root=`/v1/workspaces/${ctx.workspaceId}/projects/${ctx.projectId}`;
  const project=await read<components['schemas']['Project']>(root);
  if(project.id!==ctx.projectId||project.workspace_id!==ctx.workspaceId||project.status!=='active'||!project.active_icp_version_id)throw new Error(researchNotices.context);
  const profiles=async()=>{
    for(let offset=0;offset<1000;offset+=100){
      const page=await read<components['schemas']['ICPVersionPage']>(`${root}/icp-versions?offset=${offset}&limit=100`);
      if(page.offset!==offset||page.limit!==100||!Array.isArray(page.items)||!Number.isSafeInteger(page.total)||page.total>1000)throw new Error(researchNotices.context);
      const found=page.items.find(row=>row.id===project.active_icp_version_id);if(found)return found;
      if(page.items.length<100)break;
    }
    throw new Error(researchNotices.context);
  };
  const [profile,pilot]=await Promise.all([profiles(),loadPilotBudget(client,session,signal)]);
  if(profile.id!==project.active_icp_version_id||profile.workspace_id!==ctx.workspaceId||profile.project_id!==ctx.projectId||
    profile.status!=='approved'||profile.is_current!==true||profile.basis_status!=='current'||profile.basis_offer_revision!==project.offer_revision||!profile.approved_by||!profile.approved_at)throw new Error(researchNotices.context);
  const accounts:components['schemas']['BudgetAccount'][]=[];
  // Workspace paging is bounded and must be complete before trusting remaining money.
  for(let offset=0;offset<1000;offset+=100){
    const page=await read<components['schemas']['BudgetAccountPage']>(`/v1/workspaces/${ctx.workspaceId}/budgets?offset=${offset}&limit=100`);
    if(page.offset!==offset||page.limit!==100||!Array.isArray(page.items)||!Number.isSafeInteger(page.total)||page.total>1000)throw new Error(researchNotices.context);
    accounts.push(...page.items);if(offset+page.items.length>=page.total)break;
    if(page.items.length!==100)throw new Error(researchNotices.context);
  }
  const now=Date.now(),current=accounts.filter(row=>row.workspace_id===ctx.workspaceId&&Date.parse(row.period_start)<=now&&now<Date.parse(row.period_end));
  const required=[['workspace',ctx.workspaceId,'all'],['project',ctx.projectId,'all'],['category',ctx.projectId,'discovery']];
  const remaining=required.map(([scope,id,category])=>{
    const rows=current.filter(row=>row.scope===scope&&row.scope_id===id&&row.category===category);
    if(rows.length!==1||!fixed(rows[0].remaining?.amount)||rows[0].remaining.currency!=='USD'||rows[0].effective_state!=='active')throw new Error(researchNotices.context);
    return Number(rows[0].remaining.amount);
  });
  if(pilot.workspace_id!==ctx.workspaceId||pilot.project_id!==ctx.projectId||pilot.currency!=='USD')throw new Error(researchNotices.context);
  if(pilot.id!==null){if(!fixed(pilot.remaining))throw new Error(researchNotices.context);remaining.push(Number(pilot.remaining));}
  if(signal.aborted||!session.isCurrent(identity))throw new LiveCancelled('scope changed');
  return {profileId:profile.id,profileNumber:profile.number,remaining:Math.min(...remaining).toFixed(6)};
}
/** Only the confirm handler supplies confirmed:true; no mount/template/AI callback calls this. */
export async function confirmResearch(client:LiveClient,session:SessionScope,options:{enabled:boolean;confirmed:boolean;review:ResearchReview;maxCost:string;target:number}):Promise<RunReference>{
  const ctx=context(client,session,options.enabled);
  if(!options.confirmed||!fixed(options.maxCost)||Number(options.maxCost)<=0||Number(options.maxCost)>Number(options.review.remaining)||!Number.isInteger(options.target)||options.target<1||options.target>100||!uuid.test(options.review.profileId))throw new Error(researchNotices.context);
  let run;
  try{run=await startResearch(ctx,{icp_version_id:options.review.profileId,target_companies:options.target,
    max_cost:{amount:options.maxCost,currency:'USD'},limits:{...conversationLimits}});
  }catch(error){
    if(error instanceof LiveError&&(error.status===403||['CAPABILITY_DISABLED','PROVIDER_UNAVAILABLE','POLICY_BLOCKED','BUDGET_LIMIT','STALE_REVISION'].includes(error.code)))resetResearchIntent(ctx);
    throw error;
  }
  const ref={id:run.id,label:'Research run' as const,status:run.status};
  if(run.workspace_id!==ctx.workspaceId||run.project_id!==ctx.projectId||!validRunReference(ref))throw new Error(researchNotices.unknown);
  return ref;
}
export async function refreshResearch(client:LiveClient,session:SessionScope,enabled:boolean,id:string):Promise<RunReference>{
  const ctx=context(client,session,enabled),run=await getRun(ctx,id),ref={id:run.id,label:'Research run' as const,status:run.status};
  if(run.id!==id||run.workspace_id!==ctx.workspaceId||run.project_id!==ctx.projectId||!validRunReference(ref))throw new Error(researchNotices.context);
  return ref;
}
