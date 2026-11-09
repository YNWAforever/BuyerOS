/**
 * Typed client for the conversation turn contract (draft v0 + Amendment A).
 *
 * Every mutation keeps one request key per exact payload, so an uncertain response
 * can be retried without repeating a possibly-billed step. The route is registered
 * only with the conversation-home flag; `capability()` probes it safely (OPTIONS)
 * and callers fall back to the older /conversation-reply flow instead of pretending
 * a turn engine exists.
 */
import {ActionIntent} from './action-intent';
import {LiveCancelled,LiveError,type LiveClient} from './client';
import type {SessionScope} from './session';
import {isUuid,readChatThread,readTurnResult,type ChatThread,type TurnCapability,type TurnDecision,type TurnResult} from '../../features/live/conversation/types';
import {MAX_STREAM_RECONNECTS,reconnectDelay,readTurnStreamEvent,SseParser,type TurnStreamEvent} from '../../features/live/conversation/stream-events';

export const turnNotices={
  stale:'This discussion changed. Copy any unsaved text, reload and send again.',
  unavailable:'The conversation did not respond. Your message is still here.',
  absent:'Continuous replies are not available here. Your message is still saved as a note.',
  forbidden:'You do not have permission to act in this discussion.',
  budget:'The approved budget cannot cover this step. Nothing was executed.',
  policy:'This step needs current policy approval. Nothing was executed.',
  admission:'Sales actions are disabled for this workspace. Your message was saved and no action ran.',
  conflict:'This message was already sent with different content. Reload the discussion before sending again.',
  unknown:'The result is unconfirmed. Retry the same message to check the saved result instead of running it twice.',
  invalid:'The conversation response could not be verified. Reload the discussion before retrying.',
  needsInput:'This step needs more information. See the notice in the discussion.',
  noRecovery:'This turn is no longer awaiting a result check.',
  rejected:'The request was rejected. Review the message and try again.',
  source:'A cited source is unavailable or is no longer approved.',
} as const;

export type TurnSubmitInput={
  threadId:string|null;clientMessageId:string;expectedVersion:number|null;
  text:string;skillId?:string|null;templateId?:string;buyerId?:string;language:'en'|'zh-HK';signal?:AbortSignal;
};
export type TurnDecisionInput={
  threadId:string;turnId:string;proposalId:string;decision:TurnDecision;
  expectedVersion:number;signal?:AbortSignal;
};
export type TurnCancelInput={threadId:string;turnId:string;expectedVersion:number;signal?:AbortSignal};
export type TurnReconcileInput={threadId:string;turnId:string;expectedVersion:number;signal?:AbortSignal};
export type TurnStreamOutcome='closed'|'absent'|'unavailable'|'overflow'|'aborted';
export type TurnStreamHandlers={
  signal:AbortSignal;baseUrl?:string;after?:number;
  onEvent:(event:TurnStreamEvent)=>void;
  onReconnect?:(attempt:number,delayMs:number)=>void;
  onStreamError?:(error:unknown)=>void;
};
function pause(ms:number,signal:AbortSignal):Promise<boolean>{
  if(signal.aborted)return Promise.resolve(false);
  return new Promise(resolve=>{
    const timer=setTimeout(()=>{signal.removeEventListener('abort',stop);resolve(true);},ms);
    const stop=()=>{clearTimeout(timer);resolve(false);};
    signal.addEventListener('abort',stop,{once:true});
  });
}

const MAX_TEXT=4_000;
const skillPattern=/^[a-z0-9][a-z0-9-]{0,80}$/;
export const turnTemplates=['first-project','understand-documents','research-market','review-buyers',
  'check-company','prepare-follow-up','custom'] as const;
function validText(value:unknown):value is string{
  return typeof value==='string'&&value.trim().length>0&&value.length<=MAX_TEXT;
}
export function turnNotice(error:unknown):string{
  if(error instanceof LiveCancelled)return '';
  if(error instanceof Error&&Object.values(turnNotices).includes(error.message as typeof turnNotices[keyof typeof turnNotices]))return error.message;
  if(error instanceof LiveError){
    if(error.code==='STALE_REVISION'||error.status===412)return turnNotices.stale;
    if(error.code==='IDEMPOTENCY_CONFLICT')return turnNotices.conflict;
    if(error.code==='BUDGET_LIMIT')return turnNotices.budget;
    if(error.code==='POLICY_BLOCKED')return turnNotices.policy;
    if(error.code==='SALES_ADMISSION_DISABLED')return turnNotices.admission;
    if(error.code==='NEEDS_INPUT')return turnNotices.needsInput;
    if(error.code==='INVALID_STATE')return turnNotices.noRecovery;
    if(error.code==='CONVERSATION_SOURCE_UNAVAILABLE'||error.code==='SOURCE_UNAVAILABLE')return turnNotices.source;
    if(error.status===403)return turnNotices.forbidden;
    if(error.status===404)return turnNotices.absent;
    if(error.status===409)return turnNotices.conflict;
    if(error.status===400||error.status===422)return turnNotices.rejected;
    return turnNotices.unknown;
  }
  return turnNotices.unknown;
}

/** OPTIONS status classification for the event route (shared with tests). */
export function streamCapabilityFromStatus(status:number):TurnCapability{
  if(status===404)return 'absent';
  if(status===401||status===403)return 'unavailable';
  if(status>=200&&status<500)return 'available';
  return 'unavailable';
}
/** Turn routes are flag-gated; absence is a normal fallback, not a lost workspace. */
export class ConversationTurns{
  private intents=new Map<string,ActionIntent<unknown>>();
  private probe:Promise<TurnCapability>|null=null;
  private streamProbe:Promise<TurnCapability>|null=null;
  private identity:string;
  private root:string;
  constructor(private client:LiveClient,private session:SessionScope,private enabled:boolean){
    this.identity=session.identity();const scope=session.current();
    this.root=`/v1/workspaces/${encodeURIComponent(scope.workspace??'')}/projects/${encodeURIComponent(scope.project??'')}/conversation-turns`;
    const clear=()=>{this.intents.clear();this.probe=null;this.streamProbe=null;};
    const off=session.subscribeBeforeClear(clear);
    const unsubscribe=session.subscribe(()=>{if(!session.isCurrent(this.identity)){clear();off();unsubscribe();}});
  }
  private guard():void{
    const scope=this.session.current();
    if(!this.enabled||!this.session.isCurrent(this.identity)||!this.session.token()||scope.mode!=='live'||
      !scope.actor||!scope.workspace||!scope.project)throw new LiveCancelled('scope changed');
  }
  private intentFor(key:string):ActionIntent<unknown>{
    let intent=this.intents.get(key);
    if(!intent){intent=new ActionIntent<unknown>();this.intents.set(key,intent);}
    return intent;
  }
  /** OPTIONS never mutates. 2xx/4xx (except 404) prove the route exists; 404 means absent. */
  capability(force=false):Promise<TurnCapability>{
    if(!this.enabled)return Promise.resolve('absent');
    if(!force&&this.probe)return this.probe;
    const promise=this.probeOnce();
    this.probe=promise;
    return promise;
  }
  private async probeOnce():Promise<TurnCapability>{
    if(!this.session.isCurrent(this.identity)||!this.session.token())return 'unavailable';
    try{
      await this.client.request<unknown>({path:this.root,method:'OPTIONS',token:this.session.token(),scope:this.identity,
        signal:this.session.controller().signal,missingIsUnavailable:true});
      return 'available';
    }catch(error){
      if(error instanceof LiveCancelled)return 'unavailable';
      if(error instanceof LiveError){
        if(error.status===404)return 'absent';
        if(error.status>=400&&error.status<500)return 'available';
        return 'unavailable';
      }
      return 'unavailable';
    }
  }
  /**
   * OPTIONS probe for the event route (increment C). Uses fetch directly so a
   * missing optional route never trips the workspace access-denied listeners;
   * 405/2xx prove the path exists, the generic route-miss 404 means no stream.
   */
  streamCapability(force=false,baseUrl=''):Promise<TurnCapability>{
    if(!this.enabled)return Promise.resolve('absent');
    if(!force&&this.streamProbe)return this.streamProbe;
    const promise=this.probeStream(baseUrl);
    this.streamProbe=promise;
    return promise;
  }
  private async probeStream(baseUrl=''):Promise<TurnCapability>{
    if(!this.session.isCurrent(this.identity)||!this.session.token())return 'unavailable';
    const placeholder='00000000-0000-4000-8000-000000000000';
    const base=baseUrl.replace(/\/$/,'');
    const own=new AbortController(),timer=setTimeout(()=>own.abort(),5_000);
    try{
      const response=await fetch(`${base}${this.root}/${placeholder}/events?after=0`,{method:'OPTIONS',cache:'no-store',
        signal:AbortSignal.any([own.signal,this.session.controller().signal]),
        headers:{...(this.session.token()?{Authorization:`Bearer ${this.session.token()}`}:{})}});
      return streamCapabilityFromStatus(response.status);
    }catch{return 'unavailable';}
    finally{clearTimeout(timer);}
  }
  /**
   * SSE tail with bounded reconnect and the last seen cursor. Reconnects never
   * re-submit a turn; the server replays `seq > after` only.
   */
  async stream(turnId:string,handlers:TurnStreamHandlers):Promise<TurnStreamOutcome>{
    this.guard();
    if(!isUuid(turnId))throw new Error(turnNotices.rejected);
    const base=(handlers.baseUrl??'').replace(/\/$/,'');
    const parent=AbortSignal.any([handlers.signal,this.session.controller().signal]);
    let cursor=Number.isSafeInteger(handlers.after)&&(handlers.after as number)>0?handlers.after as number:0;
    let attempt=0;
    while(!parent.aborted){
      let response:Response;
      try{
        response=await fetch(`${base}${this.root}/${encodeURIComponent(turnId)}/events?after=${cursor}`,{
          method:'GET',signal:parent,cache:'no-store',
          headers:{Accept:'text/event-stream',...(this.session.token()?{Authorization:`Bearer ${this.session.token()}`}:{})},
        });
      }catch{
        if(parent.aborted)return 'aborted';
        attempt+=1;
        if(attempt>MAX_STREAM_RECONNECTS)return 'unavailable';
        handlers.onReconnect?.(attempt,reconnectDelay(attempt));
        if(!await pause(reconnectDelay(attempt),parent))return 'aborted';
        continue;
      }
      if(response.status===404||response.status===405)return 'absent';
      if(response.status===401||response.status===403)return 'unavailable';
      if(!response.ok){
        attempt+=1;
        if(attempt>MAX_STREAM_RECONNECTS)return 'unavailable';
        handlers.onReconnect?.(attempt,reconnectDelay(attempt));
        if(!await pause(reconnectDelay(attempt),parent))return 'aborted';
        continue;
      }
      if(!response.body)return 'unavailable';
      const parser=new SseParser(),reader=response.body.getReader(),decoder=new TextDecoder();
      let final=false;
      const apply=(frames:ReturnType<SseParser['push']>)=>{
        for(const frame of frames){
          const event=readTurnStreamEvent(frame);
          if(!event||event.seq<=cursor)continue;
          cursor=event.seq;handlers.onEvent(event);
          if(event.kind==='turn.final')final=true;
        }
      };
      try{
        while(!final){
          const {done,value}=await reader.read();
          if(parent.aborted){void reader.cancel().catch(()=>{});return 'aborted';}
          if(done)break;
          const cursorBefore=cursor;
          apply(parser.push(decoder.decode(value,{stream:true})));
          if(cursor>cursorBefore)attempt=0;
          if(parser.overflowed)return 'overflow';
        }
        if(!final)apply(parser.flush());
        if(parser.overflowed)return 'overflow';
      }catch(error){
        handlers.onStreamError?.(error);
        if(parent.aborted)return 'aborted';
      }finally{
        if(final)void reader.cancel().catch(()=>{});
        try{reader.releaseLock();}catch{/* already released */}
      }
      if(final)return 'closed';
      // The stream closed before turn.final (deadline, proxy): reconnect from the cursor.
      attempt+=1;
      if(attempt>MAX_STREAM_RECONNECTS)return 'unavailable';
      handlers.onReconnect?.(attempt,reconnectDelay(attempt));
      if(!await pause(reconnectDelay(attempt),parent))return 'aborted';
    }
    return 'aborted';
  }
  /** Recovery for outcome_unknown: read-only server probe; never dispatches work. */
  async reconcile(input:TurnReconcileInput):Promise<TurnResult>{
    this.guard();
    if(!isUuid(input.threadId)||!isUuid(input.turnId)||!Number.isSafeInteger(input.expectedVersion))throw new Error(turnNotices.rejected);
    const suffix=`/${encodeURIComponent(input.turnId)}/reconcile`;
    const key=JSON.stringify(['reconcile',this.identity,input.threadId,input.turnId,input.expectedVersion]);
    const raw=await this.intentFor(key).run(key,idempotencyKey=>this.send<unknown>(suffix,undefined,input.expectedVersion,idempotencyKey,input.signal));
    const result=readTurnResult(raw);
    if(!result)throw new Error(turnNotices.invalid);
    return result;
  }
  private async send<T>(suffix:string,body:unknown,expectedVersion:number|null,idempotencyKey:string,signal?:AbortSignal):Promise<T>{
    this.guard();
    const parent=signal?AbortSignal.any([signal,this.session.controller().signal]):this.session.controller().signal;
    const result=await this.client.request<T>({path:this.root+suffix,method:'POST',body,
      ifMatch:expectedVersion===null?undefined:`"${expectedVersion}"`,idempotencyKey,
      scope:this.identity,token:this.session.token(),signal:parent,missingIsUnavailable:true});
    if(!this.session.isCurrent(this.identity)||!this.session.token())throw new LiveCancelled('scope changed');
    return result;
  }
  /** `threadId:null` creates the thread and appends the first message atomically. */
  async submit(input:TurnSubmitInput):Promise<TurnResult>{
    this.guard();
    if(input.threadId!==null&&!isUuid(input.threadId))throw new Error(turnNotices.rejected);
    if(!isUuid(input.clientMessageId)||!validText(input.text))throw new Error(turnNotices.rejected);
    if(input.skillId!=null&&!skillPattern.test(input.skillId))throw new Error(turnNotices.rejected);
    if(input.language!=='en'&&input.language!=='zh-HK')throw new Error(turnNotices.rejected);
    if(input.expectedVersion!==null&&!Number.isSafeInteger(input.expectedVersion))throw new Error(turnNotices.rejected);
    if(input.threadId===null&&input.expectedVersion!==null)throw new Error(turnNotices.rejected);
    if(input.templateId!==undefined&&!(turnTemplates as readonly string[]).includes(input.templateId))throw new Error(turnNotices.rejected);
    if(input.buyerId!==undefined&&!isUuid(input.buyerId))throw new Error(turnNotices.rejected);
    const skillId=input.skillId??null;
    // Amendment A1: a first turn omits thread_id and expected_thread_version; the
    // server creates the thread, title and first user message in one transaction.
    // `buyer_id`/`template_id` are honoured only on that thread-first call.
    const body:Record<string,unknown>=input.threadId===null
      ?{client_message_id:input.clientMessageId,language:input.language,text:input.text,skill_id:skillId,
        ...(input.templateId?{template_id:input.templateId}:{}),...(input.buyerId?{buyer_id:input.buyerId}:{})}
      :{thread_id:input.threadId,client_message_id:input.clientMessageId,expected_thread_version:input.expectedVersion,
        language:input.language,text:input.text,skill_id:skillId};
    const key=JSON.stringify(['turn',this.identity,input.threadId,input.clientMessageId,input.expectedVersion,input.text,skillId,input.language,input.templateId??null,input.buyerId??null]);
    const raw=await this.intentFor(key).run(key,idempotencyKey=>this.send<unknown>('',body,input.expectedVersion,idempotencyKey,input.signal));
    const result=readTurnResult(raw);
    if(!result)throw new Error(turnNotices.invalid);
    return result;
  }
  async decide(input:TurnDecisionInput):Promise<TurnResult>{
    this.guard();
    if(!isUuid(input.threadId)||!isUuid(input.turnId)||!input.proposalId.trim()||
      (input.decision!=='approve'&&input.decision!=='reject')||!Number.isSafeInteger(input.expectedVersion))
      throw new Error(turnNotices.rejected);
    const body={proposal_id:input.proposalId,decision:input.decision,expected_thread_version:input.expectedVersion};
    const key=JSON.stringify(['decision',this.identity,input.threadId,input.turnId,input.proposalId,input.decision,input.expectedVersion]);
    const suffix=`/${encodeURIComponent(input.turnId)}/decisions`;
    const raw=await this.intentFor(key).run(key,idempotencyKey=>this.send<unknown>(suffix,body,input.expectedVersion,idempotencyKey,input.signal));
    const result=readTurnResult(raw);
    if(!result)throw new Error(turnNotices.invalid);
    return result;
  }
  async cancel(input:TurnCancelInput):Promise<TurnResult>{
    this.guard();
    if(!isUuid(input.threadId)||!isUuid(input.turnId)||!Number.isSafeInteger(input.expectedVersion))throw new Error(turnNotices.rejected);
    const key=JSON.stringify(['cancel',this.identity,input.threadId,input.turnId,input.expectedVersion]);
    const suffix=`/${encodeURIComponent(input.turnId)}/cancel`;
    // The cancel route takes no request body; the thread precondition is the strong
    // If-Match header (X-BuyerOS-If-Match over the wire).
    const raw=await this.intentFor(key).run(key,idempotencyKey=>this.send<unknown>(suffix,undefined,input.expectedVersion,idempotencyKey,input.signal));
    const result=readTurnResult(raw);
    if(!result)throw new Error(turnNotices.invalid);
    return result;
  }
}
const clients=new WeakMap<SessionScope,{identity:string;api:ConversationTurns}>();
export function scopedTurns(client:LiveClient,session:SessionScope,enabled:boolean){
  let cached=clients.get(session);
  if(!cached||cached.identity!==session.identity()){cached={identity:session.identity(),api:new ConversationTurns(client,session,enabled)};clients.set(session,cached);}
  return cached.api;
}
/** Normalise an existing thread response (legacy rows included) for the new surface. */
export function chatThread(value:unknown):ChatThread|null{
  return readChatThread(value);
}