import type {components} from '@/services/generated/buyeros-api';
import type {LiveClient} from './client';
import type {SessionScope} from './session';
import {createOperationClient} from './operations';
import {leadContext} from './lead-context';

export type LeadPreparation=components['schemas']['LeadPreparationView'];
export type LeadPreparationInput=components['schemas']['LeadPreparationInput'];
export async function loadLeadPreparations(
  client:LiveClient,session:SessionScope,buyerId:string,offset=0,limit=20,signal?:AbortSignal,
){
  const ctx=leadContext(session,signal);
  return createOperationClient(client).requestOperation('listLeadPreparations',{
    path:{workspace_id:ctx.workspace,project_id:ctx.project,buyer_id:buyerId},query:{offset,limit},
  },ctx);
}
export async function getLeadPreparation(client:LiveClient,session:SessionScope,preparationId:string,signal?:AbortSignal){
  const ctx=leadContext(session,signal);
  return createOperationClient(client).requestOperation('getLeadPreparation',{
    path:{workspace_id:ctx.workspace,project_id:ctx.project,preparation_id:preparationId},
  },ctx);
}
export async function listLeadPreparationRevisions(
  client:LiveClient,session:SessionScope,preparationId:string,offset=0,limit=20,signal?:AbortSignal,
){
  const ctx=leadContext(session,signal);
  return createOperationClient(client).requestOperation('listLeadPreparationRevisions',{
    path:{workspace_id:ctx.workspace,project_id:ctx.project,preparation_id:preparationId},query:{offset,limit},
  },ctx);
}
