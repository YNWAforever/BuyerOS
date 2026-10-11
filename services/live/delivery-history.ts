import type {components} from '@/services/generated/buyeros-api';
import type {Draft} from './drafts';
import {buyerOperationContext} from './buyers';
import {createOperationClient} from './operations';
import {LiveCancelled,type LiveClient} from './client';
import type {SessionScope} from './session';

export type DeliveryMessage=components['schemas']['DeliveryMessageMetadata'];
export type DeliveryMessagePage=components['schemas']['DeliveryMessagePage'];
export async function listDraftDeliveryMessages(client:LiveClient,session:SessionScope,
    draft:Pick<Draft,'id'|'workspace_id'|'project_id'>,offset:number):Promise<DeliveryMessagePage>{
  if(!Number.isSafeInteger(offset)||offset<0)throw new Error('Invalid history offset');
  const ctx=buyerOperationContext(session);
  if(draft.workspace_id!==ctx.workspace||draft.project_id!==ctx.project)throw new LiveCancelled('draft scope changed');
  const page=await createOperationClient(client).requestOperation('listDraftDeliveryMessages',{
    path:{workspace_id:ctx.workspace,project_id:ctx.project!,draft_id:draft.id},query:{offset,limit:20}},ctx);
  if(page.offset!==offset||page.limit!==20||!Number.isSafeInteger(page.total)||page.total<0||
     !Array.isArray(page.items)||page.items.length>20||
     (page.items.length>0&&page.total<offset+page.items.length)||
     new Set(page.items.map(row=>row.id)).size!==page.items.length||
     page.items.some(row=>row.workspace_id!==ctx.workspace||row.project_id!==ctx.project||row.draft_id!==draft.id)){
    throw new Error('Invalid scoped delivery history page');
  }
  return page;
}
