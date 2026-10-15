import {LiveCancelled,LiveError,type LiveClient} from './client';
import type {SessionScope} from './session';
import {createOperationClient,type OperationInput} from './operations';
import type {components} from '@/services/generated/buyeros-api';
import {leadContext} from './lead-context';

export type LeadIntentInput=OperationInput<'prepareLeadIntent'>['body'];
export type LeadIntentView=components['schemas']['LeadIntentView'];
export type LeadIntentReceipt=components['schemas']['LeadIntentReceipt'];
type Pending={fingerprint:string;key:string;intentId?:string;promise?:Promise<LeadIntentView>};
const pending=new WeakMap<SessionScope,Map<string,Pending>>();
const observed=new WeakSet<SessionScope>();
function cache(session:SessionScope){
  let value=pending.get(session);if(!value){value=new Map();pending.set(session,value);}
  if(!observed.has(session)){
    observed.add(session);let identity=session.identity();
    session.subscribe(()=>{if(identity!==session.identity()){pending.get(session)?.clear();identity=session.identity();}});
    session.subscribeBeforeClear(()=>pending.get(session)?.clear());
  }
  return value;
}
function target(value:{action:string;buyer_id?:string|null;target_id?:string|null}){
  return JSON.stringify([value.action,value.buyer_id??null,value.target_id??null]);
}
function guardIntent(session:SessionScope,intent:LeadIntentView){
  const scope=session.current();
  if(intent.workspace_id!==scope.workspace||intent.project_id!==scope.project)throw new LiveCancelled('intent project scope changed');
}
export class LeadRecoveryRequired extends Error{
  constructor(){super('The original operation is pending. Read back or cancel it before creating a new edit.');}
}

export async function getLeadIntent(client:LiveClient,session:SessionScope,intentId:string,signal?:AbortSignal){
  const ctx=leadContext(session,signal);
  return createOperationClient(client).requestOperation('getLeadIntent',{
    path:{workspace_id:ctx.workspace,project_id:ctx.project,intent_id:intentId},
  },ctx);
}

export async function recoverLeadIntents(client:LiveClient,session:SessionScope,signal?:AbortSignal):Promise<LeadIntentView[]>{
  const ctx=leadContext(session,signal),items:LeadIntentView[]=[];
  for(let offset=0;;){
    const page=await createOperationClient(client).requestOperation('listLeadIntents',{
      path:{workspace_id:ctx.workspace,project_id:ctx.project},query:{offset,limit:100},
    },ctx);
    if(!Array.isArray(page.items)||!Number.isSafeInteger(page.total)||page.total<0)throw new Error('Invalid recovery page');
    for(const item of page.items){
      guardIntent(session,item);
      if(item.redacted)cache(session).delete(target(item));
      items.push(item);
    }
    if(items.length>=page.total)return items;
    if(!page.items.length)throw new Error('Recovery history is incomplete');
    offset+=page.items.length;
  }
}

export async function prepareLeadIntent(
  client:LiveClient,session:SessionScope,input:LeadIntentInput,
):Promise<LeadIntentView>{
  const ctx=leadContext(session),store=cache(session),frozen=structuredClone(input);
  const destination=target(frozen),fingerprint=JSON.stringify(frozen);
  const existing=store.get(destination);
  if(existing&&existing.fingerprint!==fingerprint)throw new LeadRecoveryRequired();
  if(existing?.promise)return existing.promise;
  const entry=existing??{fingerprint,key:crypto.randomUUID()};
  store.set(destination,entry);
  const work=(async()=>{
    const unresolved=await recoverLeadIntents(client,session);
    if(!ctx.isCurrent())throw new LiveCancelled('scope changed');
    const original=unresolved.find(item=>target(item)===destination);
    if(original){
      if(original.prepare_key!==entry.key&&original.id!==entry.intentId)throw new LeadRecoveryRequired();
      if(original.redacted)throw new Error('Original retained source is unavailable');
      entry.intentId=original.id;return original;
    }
    const value=await createOperationClient(client).requestOperation('prepareLeadIntent',{
      path:{workspace_id:ctx.workspace,project_id:ctx.project},
      header:{'Idempotency-Key':entry.key},body:frozen,
    },ctx);
    guardIntent(session,value);entry.intentId=value.id;return value;
  })();
  entry.promise=work;
  try{return await work;}
  catch(error){
    if(error instanceof LiveError&&error.status>=400&&error.status<500&&error.status!==409){
      if(error.status===401||error.status===403)store.clear();
      else if(store.get(destination)===entry)store.delete(destination);
    }
    throw error;
  }
  finally{if(store.get(destination)===entry)entry.promise=undefined;}
}

export async function applyLeadIntent(
  client:LiveClient,session:SessionScope,intent:LeadIntentView,
):Promise<LeadIntentReceipt>{
  guardIntent(session,intent);
  const ctx=leadContext(session);
  // Re-authorize every replay. A cached successful receipt is never authority.
  const current=await getLeadIntent(client,session,intent.id);
  if(!ctx.isCurrent())throw new LiveCancelled('scope changed');
  guardIntent(session,current);
  if(current.submission_key!==intent.submission_key||current.expected_version!==intent.expected_version
      ||current.action!==intent.action||current.buyer_id!==intent.buyer_id)throw new Error('Original intent identity changed');
  if(current.state==='applied'&&current.receipt)return current.receipt;
  if(current.redacted)throw new Error('Original retained source is unavailable');
  if(current.state!=='prepared')throw new Error('Original intent is not available for submission');
  return createOperationClient(client).requestOperation('applyLeadIntent',{
    path:{workspace_id:ctx.workspace,project_id:ctx.project,intent_id:current.id},
    header:{'Idempotency-Key':current.submission_key,
      ...(current.expected_version===null?{}:{'If-Match':`"${current.expected_version}"`})},
    body:{},
  },ctx);
}

export async function acknowledgeLeadIntent(client:LiveClient,session:SessionScope,intentId:string){
  const ctx=leadContext(session);
  const value=await createOperationClient(client).requestOperation('acknowledgeLeadIntent',{
    path:{workspace_id:ctx.workspace,project_id:ctx.project,intent_id:intentId},
    header:{'Idempotency-Key':`ack-${intentId}`},body:{},
  },ctx);
  for(const [key,entry]of cache(session))if(entry.intentId===intentId)cache(session).delete(key);
  return value;
}

export async function cancelLeadIntent(client:LiveClient,session:SessionScope,intentId:string){
  const ctx=leadContext(session);
  const value=await createOperationClient(client).requestOperation('cancelLeadIntent',{
    path:{workspace_id:ctx.workspace,project_id:ctx.project,intent_id:intentId},
    header:{'Idempotency-Key':`cancel-${intentId}`},body:{},
  },ctx);
  for(const [key,entry]of cache(session))if(entry.intentId===intentId)cache(session).delete(key);
  return value;
}
