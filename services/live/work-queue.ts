import type {components,operations} from '@/services/generated/buyeros-api';
import {buyerOperationContext} from './buyers';
import {createOperationClient} from './operations';
import {jobScopeLink} from './job-query';
import type {LiveClient} from './client';
import type {SessionScope} from './session';

export type WorkQueue=components['schemas']['WorkQueue'];
export type WorkQueueItem=components['schemas']['WorkQueueItem'];
export type ApprovalFilter=NonNullable<operations['listDrafts']['parameters']['query']>['approval'];
export type AcceptanceFilter=NonNullable<operations['listProviderOperations']['parameters']['query']>['acceptance'];
const filters:Record<WorkQueueItem['kind'],WorkQueueItem['filters']>={awaiting_review:{review:'awaiting_review'},pending_approval:{approval:'pending'},unassigned:{queue:'unassigned'},failed_job:{status:'failed'},unknown_fit:{queue:'unknown'},unknown_acceptance:{acceptance:'unknown'}};
export function readDraftApproval(value:string|null):ApprovalFilter{return value==='pending'?'pending':undefined;}
function exactFilters(item:WorkQueueItem):boolean{
 const expected=filters[item.kind];return Boolean(expected)&&Object.keys(item.filters).length===Object.keys(expected).length&&Object.entries(expected).every(([key,value])=>item.filters[key as keyof WorkQueueItem['filters']]===value);
}
export async function loadWorkQueue(client:LiveClient,session:SessionScope,signal?:AbortSignal):Promise<WorkQueue>{
 const basis=buyerOperationContext(session),ctx={...basis,signal:signal?AbortSignal.any([signal,basis.signal]):basis.signal};
 const value=await createOperationClient(client).requestOperation('getWorkQueue',{path:{workspace_id:ctx.workspace,project_id:ctx.project!}},ctx);
 if(!value||!Number.isFinite(Date.parse(value.as_of))||!/(Z|[+-]\d{2}:\d{2})$/.test(value.as_of)||!Array.isArray(value.items)||value.items.length!==6
  ||new Set(value.items.map(item=>item.kind)).size!==6||value.items.some(item=>!Number.isSafeInteger(item.count)||item.count<0||!exactFilters(item)))throw new Error('Work queue summary unavailable');
 return value;
}
export function workQueueLink(item:WorkQueueItem,scope:{workspaceId:string;projectId:string}):string{
 if(!scope.workspaceId||!scope.projectId||!exactFilters(item))throw new Error('Invalid work queue scope or filter');
 if(item.kind==='failed_job')return jobScopeLink({kind:'project',...scope},item.filters.status);
 const path=item.kind==='pending_approval'?'/app/outreach':item.kind==='unknown_acceptance'?'/app/operations':'/app/results';
 const query=new URLSearchParams({workspace:scope.workspaceId,project:scope.projectId});
 for(const [key,value] of Object.entries(item.filters))query.set(key,value);
 return path+'?'+query;
}
export async function listProviderOperations(client:LiveClient,session:SessionScope,acceptance:AcceptanceFilter,offset:number,limit:number,signal?:AbortSignal){
 const basis=buyerOperationContext(session),ctx={...basis,signal:signal?AbortSignal.any([signal,basis.signal]):basis.signal};
 return createOperationClient(client).requestOperation('listProviderOperations',{path:{workspace_id:ctx.workspace,project_id:ctx.project!},query:{acceptance,offset,limit}},ctx);
}
