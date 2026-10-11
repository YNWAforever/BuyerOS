import type {components} from '@/services/generated/buyeros-api';
import type {LiveClient} from './client';
import type {SessionScope} from './session';
import {buyerOperationContext} from './buyers';
import {createOperationClient} from './operations';

type Page=components['schemas']['ICPVersionPage'];
/** The canonical history order is ascending. Read only a one-row head and tail. */
export async function readLatestProfile(client:LiveClient,session:SessionScope,projectId:string,signal:AbortSignal){
 const captured=buyerOperationContext(session),ctx={...captured,signal:AbortSignal.any([captured.signal,signal]),isCurrent:()=>captured.isCurrent()&&!signal.aborted};
 const api=createOperationClient(client),path={workspace_id:ctx.workspace,project_id:projectId};
 const read=async(offset:number)=>{
  const page:Page=await api.requestOperation('listICPVersions',{path,query:{offset,limit:1}},ctx);
  if(page.offset!==offset||page.limit!==1||!Number.isSafeInteger(page.total)||page.total<0||!Array.isArray(page.items)||page.items.length>1||page.items.some(row=>row.project_id!==projectId))throw new Error('Invalid profile metadata page');
  return page;
 };
 const first=await read(0);
 if(first.total===0){if(first.items.length)throw new Error('Invalid profile metadata page');return null;}
 const last=first.total===1?first:await read(first.total-1);
 if(last.total!==first.total||last.items.length!==1)throw new Error('Profile history changed. Refresh the offer before saving.');
 return last.items[0];
}
