import type {components} from '@/services/generated/buyeros-api';
import type {LiveClient} from './client';
import type {SessionScope} from './session';
import {createOperationClient} from './operations';
import {leadContext} from './lead-context';

export type PilotBudget=components['schemas']['PilotBudgetView'];
export async function loadPilotBudget(client:LiveClient,session:SessionScope,signal?:AbortSignal){
  const ctx=leadContext(session,signal);
  return createOperationClient(client).requestOperation('getPilotBudget',{
    path:{workspace_id:ctx.workspace,project_id:ctx.project},
  },ctx);
}
export async function listPilotCostEvents(client:LiveClient,session:SessionScope,offset=0,limit=20,signal?:AbortSignal){
  const ctx=leadContext(session,signal);
  return createOperationClient(client).requestOperation('listPilotCostEvents',{
    path:{workspace_id:ctx.workspace,project_id:ctx.project},query:{offset,limit},
  },ctx);
}
