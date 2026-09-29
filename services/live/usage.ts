import type {components} from '@/services/generated/buyeros-api';
import type {LiveClient} from './client';
import type {SessionScope} from './session';
import {buyerOperationContext} from './buyers';
import {createOperationClient} from './operations';

export type Usage=components['schemas']['Usage'];
export function utcMonth(date=new Date()) {
  const from=new Date(Date.UTC(date.getUTCFullYear(),date.getUTCMonth(),1));
  const to=new Date(Date.UTC(date.getUTCFullYear(),date.getUTCMonth()+1,1));
  return {from:from.toISOString(),to:to.toISOString()};
}
export async function getUsage(client:LiveClient,session:SessionScope,from:string,to:string):Promise<Usage>{
  const ctx=buyerOperationContext(session);
  return createOperationClient(client).requestOperation('getUsage',{
    path:{workspace_id:ctx.workspace,project_id:ctx.project!},query:{from,to}},ctx);
}
