import type {components,operations} from '@/services/generated/buyeros-api';
import type {LiveClient} from './client';
import type {SessionScope} from './session';
import {createOperationClient} from './operations';
import {leadContext} from './lead-context';

export type LeadCaseView=components['schemas']['LeadCaseView'];
export type LeadObservationRecord=components['schemas']['LeadObservationRecord'];
export type LeadProgressPage=components['schemas']['LeadProgressPage'];
export type LeadFilters=Omit<NonNullable<operations['getLeadWorkflow']['parameters']['query']>,'offset'|'limit'>;

export async function loadLeadProgress(
  client:LiveClient,session:SessionScope,filters:LeadFilters={},signal?:AbortSignal,offset=0,limit=20,
){
  const ctx=leadContext(session,signal);
  const value=await createOperationClient(client).requestOperation('getLeadWorkflow',{
    path:{workspace_id:ctx.workspace,project_id:ctx.project},query:{...filters,offset,limit},
  },ctx);
  if(!Array.isArray(value.items)||!Number.isSafeInteger(value.total)||!value.metrics)throw new Error('Invalid workflow projection');
  return value;
}
export async function loadLeadCase(client:LiveClient,session:SessionScope,buyerId:string,signal?:AbortSignal){
  const ctx=leadContext(session,signal);
  return createOperationClient(client).requestOperation('getLeadCase',{
    path:{workspace_id:ctx.workspace,project_id:ctx.project,buyer_id:buyerId},
  },ctx);
}
export async function listLeadEvidence(
  client:LiveClient,session:SessionScope,buyerId:string,offset=0,limit=20,signal?:AbortSignal,
){
  const ctx=leadContext(session,signal);
  return createOperationClient(client).requestOperation('listLeadEvidence',{
    path:{workspace_id:ctx.workspace,project_id:ctx.project,buyer_id:buyerId},query:{offset,limit},
  },ctx);
}
