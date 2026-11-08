import {useEffect,useSyncExternalStore} from 'react';
import {LiveCancelled,LiveError,describeLiveError,type LiveClient} from '@/services/live/client';
import type {SessionScope} from '@/services/live/session';
import {salesTasks} from '@/services/live/sales-tasks';

/** Entry state. Only a server-answered `disabled` may select the legacy #35 shell. */
export type SalesCapabilityStatus='idle'|'loading'|'enabled'|'disabled'|'unavailable';
export interface SalesCapabilityState {
  status:SalesCapabilityStatus;
  identity:string;
  /** Short, user-safe guidance for `unavailable`; never raw server detail. */
  reason:string;
  /** Automatic attempts consumed by the current bounded retry burst. */
  attempts:number;
  /** A background revalidation is in flight; the last settled state stays visible. */
  refreshing:boolean;
  /** Last settled read time (epoch ms); drives focus/location coalescing. */
  updatedAt:number;
  /** Manual retry. Bounded: ignored while loading, fresh, or in cooldown. */
  retry:()=>void;
}
export type SalesCapabilityShell='legacy'|'checking'|'conversation'|'unavailable';
/** Single source of truth for the shell decision shared by the picker and its panels. */
export function salesCapabilityShell(enabled:boolean,state:SalesCapabilityState):SalesCapabilityShell {
  if(!enabled)return 'legacy';
  if(state.status==='enabled')return 'conversation';
  if(state.status==='disabled')return 'legacy';
  if(state.status==='unavailable')return 'unavailable';
  return 'checking';
}
export const salesCapabilityCopy={
  en:{checking:'Checking conversation availability…',unavailable:'Conversation is unavailable',retry:'Check again'},
  'zh-HK':{checking:'正在確認討論功能…',unavailable:'討論功能暫時無法使用',retry:'重新檢查'},
} as const;
export type SalesCapabilityCopyKey=keyof typeof salesCapabilityCopy.en;
export function salesCapabilityText(locale:'en'|'zh-HK',key:SalesCapabilityCopyKey){return salesCapabilityCopy[locale][key];}

// Focus revalidates policy only when the last answer is older than a minute; location
// changes share a read that just ran; a manual retry cannot storm the API.
const FOCUS_REFRESH_MS=60_000,LOCATION_COALESCE_MS=1_500,RETRY_COOLDOWN_MS=5_000,MAX_ATTEMPTS=3;
const RETRY_DELAYS_MS=[400,1_200];
const IDLE:Readonly<SalesCapabilityState>=Object.freeze({status:'idle' as const,identity:'',reason:'',attempts:0,refreshing:false,updatedAt:0,retry:()=>{}});
const noopSubscribe=()=>()=>{};
const serverSnapshot=()=>IDLE;
const retryable=(error:unknown)=>error instanceof LiveCancelled?false:!(error instanceof LiveError)||error.status===0||error.status===408||error.status===429||error.status>=500||error.retryable;

export interface CapabilityReaderClock {
  now?:()=>number;
  schedule?:(run:()=>void,delayMs:number)=>unknown;
  cancel?:(handle:unknown)=>void;
}

/**
 * One capability read per session identity, shared by every mounted subscriber.
 * A read is single-flight, aborts when the scope changes, and never lets a stale
 * response overwrite a newer identity's state.
 */
export class CapabilityReader {
  private state:SalesCapabilityState;
  private readonly identity:string;
  private readonly listeners=new Set<()=>void>();
  private readonly controller=new AbortController();
  private readonly unsubscribe:()=>void;
  private readonly now:()=>number;
  private readonly schedule:(run:()=>void,delayMs:number)=>unknown;
  private readonly cancel:(handle:unknown)=>void;
  private inflight:Promise<void>|null=null;
  private attempts=0;
  private settledAt=0;
  private triggerAt=0;
  private retryNotBefore=0;
  private retryHandle:unknown;
  private disposed=false;
  constructor(private readonly client:LiveClient,private readonly session:SessionScope,clock:CapabilityReaderClock={}){
    this.identity=session.identity();
    this.now=clock.now??Date.now;
    this.schedule=clock.schedule??((run,delayMs)=>setTimeout(run,delayMs));
    this.cancel=clock.cancel??(handle=>clearTimeout(handle as ReturnType<typeof setTimeout>));
    this.state={...IDLE,identity:this.identity,retry:()=>this.trigger('retry')};
    this.unsubscribe=session.subscribe(()=>{if(!session.isCurrent(this.identity))this.dispose();});
  }
  getSnapshot=():SalesCapabilityState=>this.state;
  subscribe=(listener:()=>void)=>{this.listeners.add(listener);return()=>{this.listeners.delete(listener);};};
  start():void{this.trigger('initial');}
  refresh(kind:'focus'|'location'):void{this.trigger(kind);}
  dispose():void{if(this.disposed)return;this.disposed=true;if(this.retryHandle!==undefined){this.cancel(this.retryHandle);this.retryHandle=undefined;}this.unsubscribe();this.controller.abort();this.listeners.clear();}
  private ready(){const snapshot=this.session.getSnapshot();return this.session.isCurrent(this.identity)&&snapshot.authenticated&&!!snapshot.scope.workspace&&!!snapshot.scope.project;}
  private set(status:SalesCapabilityStatus,reason='',extra:{attempts?:number;refreshing?:boolean}={}){
    if(this.disposed)return;
    const next:SalesCapabilityState={status,identity:this.identity,reason,attempts:extra.attempts??0,refreshing:extra.refreshing??false,updatedAt:this.settledAt,retry:this.state.retry};
    if(next.status===this.state.status&&next.reason===this.state.reason&&next.attempts===this.state.attempts&&next.refreshing===this.state.refreshing&&next.updatedAt===this.state.updatedAt)return;
    this.state=next;
    for(const listener of [...this.listeners])listener();
  }
  private trigger(kind:'initial'|'focus'|'location'|'retry'){
    if(this.disposed||this.inflight||!this.ready())return;
    const now=this.now();
    if(kind==='focus'&&this.settledAt&&now-this.settledAt<FOCUS_REFRESH_MS)return;
    if(kind==='location'&&this.triggerAt&&now-this.triggerAt<LOCATION_COALESCE_MS)return;
    if(kind==='retry'&&now<this.retryNotBefore)return;
    this.inflight=this.read();
  }
  private async read():Promise<void>{
    this.triggerAt=this.now();
    const settled=this.state.status==='enabled'||this.state.status==='disabled';
    this.set(settled?this.state.status:'loading',settled?this.state.reason:'',{attempts:this.attempts,refreshing:true});
    try{
      const value=await salesTasks(this.client,this.session).capability(this.controller.signal);
      if(this.disposed||!this.session.isCurrent(this.identity))return;
      this.attempts=0;this.settledAt=this.now();this.retryNotBefore=0;
      this.set(value.admission_enabled?'enabled':'disabled');
    }catch(error){
      if(this.disposed||error instanceof LiveCancelled)return;
      if(retryable(error)&&this.attempts+1<MAX_ATTEMPTS){
        this.attempts++;
        const settled=this.state.status==='enabled'||this.state.status==='disabled';
        this.set(settled?this.state.status:'loading',describeLiveError(error),{attempts:this.attempts,refreshing:true});
        this.retryHandle=this.schedule(()=>{this.retryHandle=undefined;this.trigger('retry');},RETRY_DELAYS_MS[Math.min(this.attempts-1,RETRY_DELAYS_MS.length-1)]);
      }else{
        this.settledAt=this.now();this.retryNotBefore=this.settledAt+RETRY_COOLDOWN_MS;
        this.set('unavailable',describeLiveError(error),{attempts:this.attempts+1});
        this.attempts=0;
      }
    }finally{this.inflight=null;}
  }
}
const readers=new WeakMap<SessionScope,{identity:string;reader:CapabilityReader}>();
function capabilityReader(client:LiveClient,session:SessionScope){
  const identity=session.identity(),cached=readers.get(session);
  if(cached?.identity===identity)return cached.reader;
  cached?.reader.dispose();
  const reader=new CapabilityReader(client,session);
  readers.set(session,{identity,reader});
  return reader;
}
/**
 * Explicit conversation-entry capability. Reads are deduplicated across every
 * subscriber for one session identity; the legacy shell is only reachable through
 * a server-answered `disabled` (or the build-time flag being off).
 */
export function useSalesCapability(client:LiveClient,session:SessionScope,enabled=true):SalesCapabilityState {
  const snapshot=useSyncExternalStore(session.subscribe,session.getSnapshot,session.getSnapshot);
  const active=enabled&&snapshot.authenticated&&!!snapshot.scope.workspace&&!!snapshot.scope.project;
  const reader=active?capabilityReader(client,session):null;
  const state=useSyncExternalStore(reader?reader.subscribe:noopSubscribe,reader?reader.getSnapshot:serverSnapshot,serverSnapshot);
  useEffect(()=>{
    if(!reader)return;
    const focus=()=>reader.refresh('focus'),location=()=>reader.refresh('location');
    window.addEventListener('focus',focus);window.addEventListener('buyeros:location',location);
    reader.start();
    return()=>{window.removeEventListener('focus',focus);window.removeEventListener('buyeros:location',location);};
  },[reader]);
  return reader?state:IDLE;
}
