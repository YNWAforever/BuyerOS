import {LiveCancelled, LiveError, type LiveClient} from './client';
import type {SessionScope} from './session';

interface Page<T> {items:T[];offset:number;limit:number;total:number;}
function page(raw:unknown):Page<unknown>{
  if(typeof raw!=='object'||raw===null)throw new Error('Invalid page');
  const p=raw as Record<string,unknown>;
  if(!Array.isArray(p.items)||!Number.isSafeInteger(p.offset)||!Number.isSafeInteger(p.limit)||!Number.isSafeInteger(p.total)||(p.limit as number)<1||(p.total as number)<0)throw new Error('Invalid page');
  return p as unknown as Page<unknown>;
}

export async function readAllPages<T>(client:LiveClient,session:SessionScope,path:string,map:(data:unknown)=>T[],signal:AbortSignal):Promise<T[]>{
  const identity=session.identity(),token=session.token();
  if(!token)throw new Error('Sign-in required');
  const items:T[]=[];
  for(let offset=0;;){
    const data=await client.request<unknown>({path:`${path}${path.includes('?')?'&':'?'}offset=${offset}&limit=100`,token,scope:identity,signal});
    if(!session.isCurrent(identity))throw new LiveCancelled('scope changed');
    const current=page(data);
    if(current.offset!==offset||current.total<items.length||current.items.length>100)throw new Error('Invalid pagination');
    items.push(...map(data));
    if(items.length>=current.total)return items;
    if(!current.items.length||current.items.length!==current.limit)throw new Error('Incomplete pagination');
    offset+=current.items.length;
  }
}

function guard(signal:AbortSignal){
  if(signal.aborted)throw new LiveCancelled('selection cancelled');
}

async function readAttempt<T>(read:(signal:AbortSignal)=>Promise<T>,parent:AbortSignal):Promise<T>{
  guard(parent);
  const own=new AbortController();
  const signal=AbortSignal.any([parent,own.signal]);
  let timer:ReturnType<typeof setTimeout>|undefined;
  let onAbort:()=>void=()=>{};
  const deadline=new Promise<never>((_resolve,reject)=>{
    onAbort=()=>reject(new LiveCancelled('selection cancelled'));
    parent.addEventListener('abort',onAbort,{once:true});
    timer=setTimeout(()=>{
      const error=new LiveError('selection deadline exceeded','REQUEST_TIMEOUT',0,'',true);
      reject(error);own.abort(error);
    },10_000);
  });
  try{
    const result=await Promise.race([read(signal),deadline]);
    guard(parent);return result;
  }catch(error){guard(parent);throw error;}
  finally{clearTimeout(timer);parent.removeEventListener('abort',onAbort);own.abort();}
}

function pause(signal:AbortSignal):Promise<void>{
  guard(signal);
  return new Promise((resolve,reject)=>{
    const cancel=()=>{clearTimeout(timer);reject(new LiveCancelled('selection cancelled'));};
    const timer=setTimeout(()=>{signal.removeEventListener('abort',cancel);resolve();},250);
    signal.addEventListener('abort',cancel,{once:true});
  });
}

/** Two bounded, read-only selection attempts. No mutation or general client replay. */
export async function loadSelection<T>(client:LiveClient,session:SessionScope,path:string,map:(data:unknown)=>T[],signal:AbortSignal):Promise<T[]>{
  for(let attempt=0;;attempt++){
    try{return await readAttempt(own=>readAllPages(client,session,path,map,own),signal);}
    catch(error){
      guard(signal);
      const retryable=error instanceof LiveError&&(error.status===0&&['NETWORK_ERROR','REQUEST_TIMEOUT'].includes(error.code)
        ||[502,503,504].includes(error.status)&&error.retryable&&!error.retryAfter);
      if(attempt!==0||!retryable)throw error;
      // Diagnostic fields intentionally exclude tokens, identity, paths and server messages.
      console.warn('BuyerOS selection read retry',{selection:path==='/v1/workspaces'?'workspaces':'projects',code:error.status===0?error.code:'TRANSIENT_SERVER_ERROR',status:error.status});
      await pause(signal);
    }
  }
}
