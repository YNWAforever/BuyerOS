import type {components} from '@/services/generated/buyeros-api';
import {createOperationClient, type WriteContext} from './operations';
import {LiveCancelled, LiveError, type LiveClient} from './client';
import {ActionIntent} from './action-intent';
import type {SessionScope} from './session';

export type Run = components['schemas']['SearchRun'];
export type RunEvent = components['schemas']['RunEvent'];
export type RunPage = components['schemas']['SearchRunPage'];
export type RunEventPage = components['schemas']['RunEventPage'];
export type RunUpdate = {kind:'event'; event:RunEvent} | {kind:'snapshot';run:Run} |
  {kind:'connection';transport:'sse'|'poll'} | {kind:'error';error:unknown};

export interface RunContext {
  client: LiveClient;
  session: SessionScope;
  apiBaseUrl: string;
  workspaceId: string;
  projectId: string;
}

function captured(ctx:RunContext, signal?:AbortSignal):WriteContext {
  const basis=ctx.session.captureWriteContext();
  if(basis.workspace!==ctx.workspaceId||basis.project!==ctx.projectId)throw new LiveCancelled('scope changed');
  return {...basis,signal:signal?AbortSignal.any([basis.signal,signal]):basis.signal,
    getToken:async()=>{const token=ctx.session.token();if(!token)throw new LiveCancelled('signed out');return token;},
    isCurrent:()=>ctx.session.isCurrent(basis.identity)};
}

export async function listRuns(ctx:RunContext, offset=0, limit=100):Promise<RunPage> {
  return createOperationClient(ctx.client).requestOperation('listRuns',
    {path:{workspace_id:ctx.workspaceId,project_id:ctx.projectId},query:{offset,limit}},captured(ctx));
}

export async function getRun(ctx:RunContext, runId:string):Promise<Run> {
  return createOperationClient(ctx.client).requestOperation('getRun',
    {path:{workspace_id:ctx.workspaceId,run_id:runId}},captured(ctx));
}

export async function startRun(ctx:RunContext, body:components['schemas']['RunCreate'],key:string):Promise<Run> {
  return createOperationClient(ctx.client).requestOperation('startRun',
    {path:{workspace_id:ctx.workspaceId,project_id:ctx.projectId},
      header:{'Idempotency-Key':key},body},captured(ctx));
}

type RunCreate=components['schemas']['RunCreate'];
export function normalizeResearchBody(body:RunCreate):RunCreate {
  const amount=body.max_cost.amount.trim();
  if(!/^(?:0|[1-9]\d{0,13})(?:\.\d{1,6})?$/.test(amount))throw new Error('Invalid fixed-point cap');
  const [whole,fraction='']=amount.split('.');
  return {...body,icp_version_id:body.icp_version_id.toLowerCase(),limits:{...body.limits},
    max_cost:{...body.max_cost,amount:`${whole}.${fraction.padEnd(6,'0')}`}};
}
function ordered(value:unknown):unknown {
  if(Array.isArray(value))return value.map(ordered);
  if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).sort(([a],[b])=>a.localeCompare(b)).map(([k,v])=>[k,ordered(v)]));
  return value;
}
function intentScope(ctx:RunContext){const scope=ctx.session.current();return JSON.stringify({mode:scope.mode,actor:scope.actor,workspace:ctx.workspaceId,project:ctx.projectId});}
export function researchFingerprint(ctx:RunContext,body:RunCreate){return JSON.stringify(ordered({scope:intentScope(ctx),body:normalizeResearchBody(body)}));}
type ResearchIntent={intent:ActionIntent<Run>;uncertain:boolean;pending:boolean;body:RunCreate;fingerprint:string};
// Session-owned memory survives route remounts. No token, cookie or credential is stored.
const researchIntents=new WeakMap<SessionScope,Map<string,ResearchIntent>>();
function intents(ctx:RunContext){let value=researchIntents.get(ctx.session);if(!value){value=new Map();researchIntents.set(ctx.session,value);}return value;}
export function hasUncertainResearch(ctx:RunContext){return intents(ctx).get(intentScope(ctx))?.uncertain??false;}
export function uncertainResearchBody(ctx:RunContext):RunCreate|null{const own=intents(ctx).get(intentScope(ctx));return own?.uncertain?normalizeResearchBody(own.body):null;}
export function resetResearchIntent(ctx:RunContext){const map=intents(ctx),scope=intentScope(ctx);if(map.get(scope)?.pending)throw new Error('Research is still pending');map.delete(scope);}
export function startResearch(ctx:RunContext,body:RunCreate):Promise<Run>{
  const map=intents(ctx),scope=intentScope(ctx),normalized=normalizeResearchBody(body),fingerprint=researchFingerprint(ctx,normalized);
  let record=map.get(scope);if(!record){record={intent:new ActionIntent<Run>(),uncertain:false,pending:false,body:normalized,fingerprint};map.set(scope,record);}
  const own=record;
  if(own.uncertain&&own.fingerprint!==fingerprint)throw new Error('Check existing runs and explicitly start a new intent before changing this request.');
  own.body=normalized;own.fingerprint=fingerprint;
  return own.intent.run(fingerprint,async key=>{
    own.pending=true;
    try{const value=await startRun(ctx,normalized,key);if(map.get(scope)===own)map.delete(scope);return value;}
    catch(error){own.uncertain=true;throw error;}
    finally{own.pending=false;}
  });
}

export async function cancelRun(ctx:RunContext, run:Run, reason:string,key:string):Promise<Run> {
  return createOperationClient(ctx.client).requestOperation('cancelRun',
    {path:{workspace_id:ctx.workspaceId,run_id:run.id},
      header:{'Idempotency-Key':key,'If-Match':`"${run.version}"`},body:{reason}},captured(ctx));
}

export async function retryRun(ctx:RunContext, run:Run, reason:string,key:string):Promise<Run> {
  return createOperationClient(ctx.client).requestOperation('retryRun',
    {path:{workspace_id:ctx.workspaceId,run_id:run.id},
      header:{'Idempotency-Key':key,'If-Match':`"${run.version}"`},
      body:{reason,resume_from_last_committed_checkpoint:true}},captured(ctx));
}

export interface RunSubscription {
  runId:string;
  afterSequence:number;
  ctx:RunContext;
  onEvent:(update:RunUpdate)=>void;
}

/** Bearer fetch stream with cursor replay; JSON polling is the same authorized endpoint. */
export function subscribeRun({runId,afterSequence,ctx,onEvent}:RunSubscription):()=>void {
  const own=new AbortController();
  let basis:WriteContext;
  try {basis=captured(ctx,own.signal);} catch(error){onEvent({kind:'error',error});return()=>own.abort();}
  let cursor=afterSequence;
  const active=()=>!basis.signal.aborted&&basis.isCurrent();
  const path=`/v1/workspaces/${encodeURIComponent(ctx.workspaceId)}/runs/${encodeURIComponent(runId)}/events`;
  const emit=(update:RunUpdate)=>{if(active())onEvent(update);};
  const pause=(ms:number)=>new Promise<void>(resolve=>{const timer=setTimeout(resolve,ms);basis.signal.addEventListener('abort',()=>{clearTimeout(timer);resolve();},{once:true});});
  const accept=async(item:RunEvent)=>{
    if(!active()||item.run_id!==runId||item.workspace_id!==ctx.workspaceId||item.sequence<=cursor)return;
    if(item.sequence!==cursor+1){
      const latest=await getRun(ctx,runId);
      if(!active())return;
      cursor=latest.last_event_sequence;emit({kind:'snapshot',run:latest});return;
    }
    cursor=item.sequence;emit({kind:'event',event:item});
  };
  const poll=async()=>{
    emit({kind:'connection',transport:'poll'});
    while(active()){
      try{
        const token=await basis.getToken();
        const page=await ctx.client.request<RunEventPage>({path:`${path}?after_sequence=${cursor}&limit=200`,
          token,scope:basis.identity,signal:basis.signal});
        for(const item of page.items)await accept(item);
        if(page.has_more)continue;
      }catch(error){
        if(error instanceof LiveCancelled||!active())return;
        if(error instanceof LiveError&&error.status===401){ctx.session.setToken(undefined);return;}
        emit({kind:'error',error});
      }
      await pause(3000);
    }
  };
  const stream=async()=>{
    emit({kind:'connection',transport:'sse'});
    while(active()){
      try{
        const token=await basis.getToken();
        const response=await fetch(`${ctx.apiBaseUrl.replace(/\/$/,'')}${path}?after_sequence=${cursor}&limit=200`,{
          headers:{Authorization:`Bearer ${token}`,Accept:'text/event-stream','Last-Event-ID':String(cursor)},
          signal:basis.signal,cache:'no-store'});
        if(response.status===401){ctx.session.setToken(undefined);return;}
        if(!response.ok||!response.body||!response.headers.get('content-type')?.includes('text/event-stream')){
          await poll();return;
        }
        const reader=response.body.getReader(),decoder=new TextDecoder();let pending='';
        try{
          while(active()){
            const {value,done}=await reader.read();if(done)break;
            pending+=decoder.decode(value,{stream:true}).replaceAll('\r\n','\n');
            for(let boundary=pending.indexOf('\n\n');boundary>=0;boundary=pending.indexOf('\n\n')){
              const frame=pending.slice(0,boundary);pending=pending.slice(boundary+2);
              const data=frame.split('\n').filter(line=>line.startsWith('data:')).map(line=>line.slice(5).trimStart()).join('\n');
              if(data){const item=JSON.parse(data) as RunEvent;await accept(item);}
            }
          }
        }finally{reader.releaseLock();}
      }catch(error){
        if(!active()||error instanceof LiveCancelled)return;
        if(error instanceof LiveError&&error.status===401){ctx.session.setToken(undefined);return;}
        await poll();return;
      }
      await pause(3000);
    }
  };
  void stream();
  return()=>own.abort();
}
