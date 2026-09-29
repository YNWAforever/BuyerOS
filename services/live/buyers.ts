import type {components} from '@/services/generated/buyeros-api';
import {createOperationClient} from './operations';
import type {LiveClient} from './client';
import type {SessionScope} from './session';
import {toBuyerPage, type LiveBuyerPage} from './mapping';

export type BuyerSort = 'name_asc'|'best_fit';
export type BuyerFit = ''|'match'|'needs_review'|'not_a_match';
export type BuyerReview = ''|'awaiting_review'|'accepted'|'rejected'|'needs_information';
export type BuyerQueue = ''|'unassigned'|'unknown';
export interface BuyerQuery {q:string; sort:BuyerSort; fit:BuyerFit; review:BuyerReview; queue:BuyerQueue; listId:string; size:8|12|24; offset:number;}
export interface BuyerSnapshot {id:string; total:number; expiresAt:string; clipped:boolean;}
const sizes=new Set([8,12,24]);
const fits=new Set<BuyerFit>(['','match','needs_review','not_a_match']);
const reviews=new Set<BuyerReview>(['','awaiting_review','accepted','rejected','needs_information']);
export function readBuyerQuery(search:string):BuyerQuery {
  const p=new URLSearchParams(search);
  const parsedSize=Number(p.get('size')||12),parsedOffset=Number(p.get('offset')||0);
  return {q:(p.get('q')||'').slice(0,200),sort:p.get('sort')==='best_fit'?'best_fit':'name_asc',
    fit:fits.has((p.get('fit')||'') as BuyerFit)?(p.get('fit')||'') as BuyerFit:'',
    review:reviews.has((p.get('review')||'') as BuyerReview)?(p.get('review')||'') as BuyerReview:'',
    queue:p.get('queue')==='unassigned'?'unassigned':p.get('queue')==='unknown'?'unknown':'',
    listId:/^[a-f0-9-]{36}$/i.test(p.get('list_id')||'')?p.get('list_id')!:'',
    size:sizes.has(parsedSize)?parsedSize as 8|12|24:12,
    offset:Number.isSafeInteger(parsedOffset)&&parsedOffset>=0?parsedOffset:0};
}
export function writeBuyerQuery(url:URL,query:BuyerQuery):string {
  for(const key of ['q','fit','review','queue','list_id','sort','size','offset'])url.searchParams.delete(key);
  if(query.q)url.searchParams.set('q',query.q);
  if(query.fit)url.searchParams.set('fit',query.fit);
  if(query.review)url.searchParams.set('review',query.review);
  if(query.queue)url.searchParams.set('queue',query.queue);
  if(query.listId)url.searchParams.set('list_id',query.listId);
  if(query.sort!=='name_asc')url.searchParams.set('sort',query.sort);
  if(query.size!==12)url.searchParams.set('size',String(query.size));
  if(query.offset)url.searchParams.set('offset',String(query.offset));
  return url.pathname+url.search+url.hash;
}
export function buyerOperationContext(session:SessionScope){
  const captured=session.captureWriteContext();
  if(!captured.project)throw new Error('Select a project');
  return {...captured,getToken:async()=>{
    const token=session.token();if(!token)throw new Error('Sign-in required');return token;
  },isCurrent:()=>session.isCurrent(captured.identity)};
}
export function buyerFiltersForQuery(query:BuyerQuery):components['schemas']['BuyerFilters']{
  return {q:query.q||undefined,fit:query.fit?[query.fit]:undefined,review:query.review?[query.review]:undefined,owner_unassigned:query.queue==='unassigned'?true:undefined,
    unknown_fit:query.queue==='unknown'?true:undefined,list_id:query.listId||undefined};
}
export async function createBuyerSnapshot(client:LiveClient,session:SessionScope,query:BuyerQuery):Promise<BuyerSnapshot>{
  const ctx=buyerOperationContext(session),raw=await createOperationClient(client).requestOperation('createBuyerSnapshot',{
    path:{workspace_id:ctx.workspace,project_id:ctx.project!},
    header:{'Idempotency-Key':crypto.randomUUID()},
    body:{filters:buyerFiltersForQuery(query),sort:query.sort,requested_limit:1000},
  },ctx);
  return {id:raw.id,total:raw.total,expiresAt:raw.expires_at,clipped:raw.result_limit_reached};
}
export async function loadBuyerPage(client:LiveClient,session:SessionScope,snapshotId:string,query:BuyerQuery):Promise<LiveBuyerPage>{
  const ctx=buyerOperationContext(session),raw=await createOperationClient(client).requestOperation('listBuyers',{
    path:{workspace_id:ctx.workspace,project_id:ctx.project!},
    query:{snapshot_id:snapshotId,offset:query.offset,limit:query.size},
  },ctx);
  return toBuyerPage(raw);
}
