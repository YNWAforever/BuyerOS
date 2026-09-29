import type {components} from '@/services/generated/buyeros-api';
import type {LiveClient} from './client';
import {LiveCancelled} from './client';
import type {SessionScope} from './session';
import {buyerOperationContext} from './buyers';
import {createOperationClient} from './operations';
import type {ReviewSelection} from './buyer-selection';
import type {Draft} from './drafts';

export type ExportJob=components['schemas']['ExportJob'];

function scope(client:LiveClient,session:SessionScope){
  return {api:createOperationClient(client),ctx:buyerOperationContext(session)};
}
export async function createBuyerExport(client:LiveClient,session:SessionScope,
  selection:ReviewSelection,includeContactData:boolean,key:string):Promise<ExportJob>{
  const {api,ctx}=scope(client,session);
  return api.requestOperation('exportBuyers',{path:{workspace_id:ctx.workspace,project_id:ctx.project!},
    header:{'Idempotency-Key':key},body:{selection,purpose:includeContactData?'export_contacts':'export_accounts',
      include_contact_data:includeContactData,format:'csv'}},ctx);
}
export async function createDraftExport(client:LiveClient,session:SessionScope,draft:Draft,
  format:'text'|'clipboard',key:string):Promise<ExportJob>{
  if(draft.status!=='approved'||!draft.approval_id)throw new Error('Current approved draft required');
  const {api,ctx}=scope(client,session);
  return api.requestOperation('exportDraft',{path:{workspace_id:ctx.workspace,draft_id:draft.id},
    header:{'Idempotency-Key':key,'If-Match':`"${draft.version}"`},
    body:{revision_id:draft.revision_id,approval_id:draft.approval_id,format}},ctx);
}
export async function getExport(client:LiveClient,session:SessionScope,id:string):Promise<ExportJob>{
  const {api,ctx}=scope(client,session);
  return api.requestOperation('getExport',{path:{workspace_id:ctx.workspace,export_id:id}},ctx);
}
export async function readExportContent(client:LiveClient,session:SessionScope,id:string){
  const ctx=buyerOperationContext(session),token=session.token();
  if(!token)throw new LiveCancelled('signed out');
  const result=await client.requestContent({path:`/v1/workspaces/${encodeURIComponent(ctx.workspace)}/exports/${encodeURIComponent(id)}/content`,
    token,scope:ctx.identity,signal:ctx.signal});
  if(!ctx.isCurrent())throw new LiveCancelled('scope changed');
  return result;
}
