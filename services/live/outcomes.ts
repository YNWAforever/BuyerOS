import type {components} from '@/services/generated/buyeros-api';
import type {LiveClient} from './client';
import type {SessionScope} from './session';
import {buyerOperationContext} from './buyers';
import {createOperationClient} from './operations';

export type Outcome=components['schemas']['OutcomeEvent'];
export type OutcomePage=components['schemas']['OutcomeEventPage'];
export type OutcomeCreate=components['schemas']['OutcomeCreate'];
export type OutcomeCorrection=components['schemas']['OutcomeCorrection'];
export async function listOutcomes(client:LiveClient,session:SessionScope,offset:number,limit=10):Promise<OutcomePage>{
  const ctx=buyerOperationContext(session);
  return createOperationClient(client).requestOperation('listOutcomes',{
    path:{workspace_id:ctx.workspace,project_id:ctx.project!},query:{offset,limit}},ctx);
}
export async function recordOutcome(client:LiveClient,session:SessionScope,body:OutcomeCreate,key:string):Promise<Outcome>{
  const ctx=buyerOperationContext(session);
  return createOperationClient(client).requestOperation('recordOutcome',{
    path:{workspace_id:ctx.workspace,project_id:ctx.project!},header:{'Idempotency-Key':key},body},ctx);
}
export async function correctOutcome(client:LiveClient,session:SessionScope,id:string,version:number,
    body:OutcomeCorrection,key:string):Promise<Outcome>{
  const ctx=buyerOperationContext(session);
  return createOperationClient(client).requestOperation('correctOutcome',{
    path:{workspace_id:ctx.workspace,outcome_id:id},header:{'Idempotency-Key':key,'If-Match':`"${version}"`},body},ctx);
}
