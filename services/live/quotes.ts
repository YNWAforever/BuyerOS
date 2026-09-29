import type {components} from '@/services/generated/buyeros-api';
import {createOperationClient, type WriteContext} from './operations';
import {LiveCancelled} from './client';
import type {RunContext} from './runs';

export type ContactQuote = components['schemas']['EnrichmentQuote'];
export type ContactJob = components['schemas']['EnrichmentJob'];

function captured(ctx:RunContext):WriteContext {
  const basis=ctx.session.captureWriteContext();
  if(basis.workspace!==ctx.workspaceId||basis.project!==ctx.projectId)throw new LiveCancelled('scope changed');
  return {...basis,getToken:async()=>{const token=ctx.session.token();if(!token)throw new LiveCancelled('signed out');return token;},
    isCurrent:()=>ctx.session.isCurrent(basis.identity)};
}

export function quoteContact(ctx:RunContext,buyerId:string,version:number,role:string,key:string):Promise<ContactQuote> {
  return createOperationClient(ctx.client).requestOperation('quoteLookup',
    {path:{workspace_id:ctx.workspaceId,project_id:ctx.projectId},header:{'Idempotency-Key':key},
      body:{selection:{kind:'explicit',buyers:[{id:buyerId,version}]},purpose:'contact_research',
        roles:[role],contact_type:'business_email'}},captured(ctx));
}

export function getContactQuote(ctx:RunContext,quoteId:string):Promise<ContactQuote> {
  return createOperationClient(ctx.client).requestOperation('getLookupQuote',
    {path:{workspace_id:ctx.workspaceId,quote_id:quoteId}},captured(ctx));
}

export function cancelContactQuote(ctx:RunContext,quote:ContactQuote,reason:string,key:string):Promise<ContactQuote> {
  return createOperationClient(ctx.client).requestOperation('cancelLookupQuote',
    {path:{workspace_id:ctx.workspaceId,quote_id:quote.id},header:{'Idempotency-Key':key,
      'If-Match':`"${quote.version}"`},body:{reason}},captured(ctx));
}


export function confirmContactQuote(ctx:RunContext,quote:ContactQuote,key:string):Promise<ContactJob> {
  return createOperationClient(ctx.client).requestOperation('confirmLookup',
    {path:{workspace_id:ctx.workspaceId,quote_id:quote.id},header:{'Idempotency-Key':key},
      body:{quote_hash:quote.quote_hash,confirm_eligible_only:true}},captured(ctx));
}


export function getContactJob(ctx:RunContext,jobId:string):Promise<ContactJob> {
  return createOperationClient(ctx.client).requestOperation('getEnrichmentJob',
    {path:{workspace_id:ctx.workspaceId,job_id:jobId}},captured(ctx));
}

export function cancelContactJob(ctx:RunContext,job:ContactJob,reason:string,key:string):Promise<ContactJob> {
  return createOperationClient(ctx.client).requestOperation('cancelEnrichmentJob',
    {path:{workspace_id:ctx.workspaceId,job_id:job.id},header:{'Idempotency-Key':key,
      'If-Match':`"${job.version}"`},body:{reason}},captured(ctx));
}
