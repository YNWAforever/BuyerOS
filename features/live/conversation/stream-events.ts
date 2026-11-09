/**
 * Increment C: streamed turn events.
 *
 * Dependency-free parsing/reduction so the browser client and node:test share the
 * exact event ordering, cursor, backoff and provisional-merge rules. Events are
 * derived data: persisted thread parts always win over a streamed part once the
 * thread refetches.
 */
import {readMessagePart,toolStates,turnStatuses,
  type MessagePart,type ToolState,type TurnNotice,type TurnStatus} from './types';

export type StreamStatus='running'|TurnStatus;
export type StreamTool={callId:string;capability:string;state:ToolState;summary?:string;errorCode?:string};
export type StreamedProposal={proposalId:string;capability:string;requiresApproval:boolean};
export type TurnStreamEvent=
  |{kind:'turn.started';seq:number;status:'running'}
  |{kind:'part';seq:number;index:number;part:MessagePart}
  |{kind:'tool';seq:number;callId:string;capability:string;state:ToolState;summary?:string;errorCode?:string}
  |{kind:'proposal';seq:number;proposalId:string;capability:string;requiresApproval:boolean}
  |{kind:'notice';seq:number;code:string;message:string}
  |{kind:'turn.final';seq:number;status:TurnStatus};
export type TurnStreamState={
  turnId:string;status:StreamStatus;parts:{index:number;part:MessagePart}[];tools:StreamTool[];
  proposals:StreamedProposal[];notices:TurnNotice[];cursor:number;final:boolean;
};
export const MAX_STREAM_RECONNECTS=5;
const BACKOFF_BASE_MS=400;
const BACKOFF_MAX_MS=8_000;
const MAX_PART_INDEX=64;

export function emptyTurnStream(turnId:string):TurnStreamState{
  return {turnId,status:'running',parts:[],tools:[],proposals:[],notices:[],cursor:0,final:false};
}
/** Events at or below the cursor are replays and never mutate state twice. */
export function reduceTurnEvent(state:TurnStreamState,event:TurnStreamEvent):TurnStreamState{
  if(state.final||!Number.isSafeInteger(event.seq)||event.seq<=state.cursor)return state;
  const next={...state,cursor:event.seq};
  switch(event.kind){
    case 'turn.started':return {...next,status:'running'};
    case 'part':{
      if(!Number.isSafeInteger(event.index)||event.index<0||event.index>MAX_PART_INDEX)return state;
      const parts=state.parts.filter(row=>row.index!==event.index);
      parts.push({index:event.index,part:event.part});
      return {...next,parts:parts.sort((a,b)=>a.index-b.index)};
    }
    case 'tool':{
      const tools=state.tools.filter(row=>row.callId!==event.callId);
      tools.push({callId:event.callId,capability:event.capability,state:event.state,
        ...(event.summary?{summary:event.summary}:{}),...(event.errorCode?{errorCode:event.errorCode}:{})});
      return {...next,tools};
    }
    case 'proposal':{
      const proposals=state.proposals.filter(row=>row.proposalId!==event.proposalId);
      proposals.push({proposalId:event.proposalId,capability:event.capability,requiresApproval:event.requiresApproval});
      return {...next,proposals};
    }
    case 'notice':{
      const notices=state.notices.some(row=>row.code===event.code&&row.message===event.message)?state.notices:
        [...state.notices,{code:event.code,message:event.message}];
      return {...next,notices};
    }
    case 'turn.final':return {...next,status:event.status,final:true};
    default:return state;
  }
}
export function reduceTurnEvents(state:TurnStreamState,events:ReadonlyArray<TurnStreamEvent>):TurnStreamState{
  return events.reduce(reduceTurnEvent,state);
}
/** Assistant parts for the provisional transcript entry, including honest notices. */
export function streamParts(state:TurnStreamState):MessagePart[]{
  const parts=state.parts.slice().sort((a,b)=>a.index-b.index).map(row=>row.part);
  return [...parts,...state.notices.map(notice=>({kind:'notice',code:notice.code,message:notice.message} as const))];
}
export type StreamStep='working'|'step'|'approval';
/** Coarse, honest progress label; capability ids stay out of ordinary copy. */
export function streamStep(state:TurnStreamState):StreamStep{
  const running=state.tools.find(tool=>tool.state==='running'||tool.state==='approved'||tool.state==='proposed');
  if(running)return 'step';
  if(state.proposals.some(proposal=>proposal.requiresApproval))return 'approval';
  return 'working';
}
export function streamIsLive(state:TurnStreamState|null):boolean{
  return state!==null&&!state.final;
}
/** Bounded exponential backoff; deterministic so tests never flake. */
export function reconnectDelay(attempt:number):number{
  if(!Number.isSafeInteger(attempt)||attempt<1)return BACKOFF_BASE_MS;
  return Math.min(BACKOFF_MAX_MS,BACKOFF_BASE_MS*2**(attempt-1));
}

export type SseFrame={id:string;event:string;data:string};
/** Incremental `text/event-stream` frame parser; chunk boundaries never lose a field. */
export class SseParser{
  private buffer='';
  push(chunk:string):SseFrame[]{
    this.buffer+=chunk;
    return this.drain(false);
  }
  flush():SseFrame[]{
    const frames=this.drain(true);
    return frames;
  }
  private drain(final:boolean):SseFrame[]{
    const frames:SseFrame[]=[];
    while(true){
      const match=/\r?\n\r?\n/.exec(this.buffer);
      if(!match)break;
      const raw=this.buffer.slice(0,match.index);
      this.buffer=this.buffer.slice(match.index+match[0].length);
      const frame=parseFrame(raw);
      if(frame)frames.push(frame);
    }
    if(final&&this.buffer.trim()){
      const frame=parseFrame(this.buffer);
      this.buffer='';
      if(frame)frames.push(frame);
    }
    return frames;
  }
}
function parseFrame(raw:string):SseFrame|null{
  let id='',event='',data='';
  const payload:string[]=[];
  for(const line of raw.split(/\r?\n/)){
    if(!line||line.startsWith(':'))continue;
    const colon=line.indexOf(':');
    const field=colon===-1?line:line.slice(0,colon);
    let value=colon===-1?'':line.slice(colon+1);
    if(value.startsWith(' '))value=value.slice(1);
    if(field==='id')id=value;
    else if(field==='event')event=value;
    else if(field==='data')payload.push(value);
  }
  if(!payload.length)return null;
  data=payload.join('\n');
  return {id,event,data};
}
function integer(value:unknown):number|null{
  return typeof value==='number'&&Number.isSafeInteger(value)&&value>=0?value:null;
}
function text(value:unknown,max=2_000):string|null{
  return typeof value==='string'&&value.trim().length>0&&value.length<=max?value:null;
}
function record(value:unknown):value is Record<string,unknown>{
  return typeof value==='object'&&value!==null&&!Array.isArray(value);
}
/** Validate one SSE frame; unknown or malformed kinds degrade to null, never throw. */
export function readTurnStreamEvent(frame:SseFrame):TurnStreamEvent|null{
  let payload:unknown;
  try{payload=JSON.parse(frame.data);}catch{return null;}
  if(!record(payload))return null;
  const kind=frame.event||(typeof payload.kind==='string'?payload.kind:'')||(typeof payload.event==='string'?payload.event:'');
  const seq=integer(Number(frame.id))??integer(payload.seq);
  if(seq===null||seq<1)return null;
  if(kind==='turn.started')return {kind,seq,status:'running'};
  if(kind==='part'){
    const index=integer(payload.index);
    if(index===null||index>MAX_PART_INDEX)return null;
    return {kind,seq,index,part:readMessagePart(payload.part)};
  }
  if(kind==='tool'){
    const callId=text(payload.call_id??payload.callId,200),capability=text(payload.capability,120);
    const state=toolStates.includes((payload.state as ToolState))?payload.state as ToolState:null;
    if(!callId||!capability||!state)return null;
    const summary=text(payload.summary,500),errorCode=text(payload.error_code??payload.errorCode,120);
    return {kind,seq,callId,capability,state,...(summary?{summary}:{}),...(errorCode?{errorCode}:{})};
  }
  if(kind==='proposal'){
    const proposalId=text(payload.proposal_id??payload.proposalId,200),capability=text(payload.capability,120);
    if(!proposalId||!capability)return null;
    return {kind,seq,proposalId,capability,requiresApproval:payload.requires_approval!==false};
  }
  if(kind==='notice'){
    const code=text(payload.code,120),message=text(payload.message,500);
    if(!code||!message)return null;
    return {kind,seq,code,message};
  }
  if(kind==='turn.final'){
    const status=turnStatuses.includes(payload.status as TurnStatus)?payload.status as TurnStatus:null;
    return status?{kind,seq,status}:null;
  }
  return null;
}
export function parseTurnStreamChunks(chunks:ReadonlyArray<string>):TurnStreamEvent[]{
  const parser=new SseParser(),events:TurnStreamEvent[]=[];
  for(const chunk of chunks)for(const frame of parser.push(chunk)){
    const event=readTurnStreamEvent(frame);
    if(event)events.push(event);
  }
  for(const frame of parser.flush()){
    const event=readTurnStreamEvent(frame);
    if(event)events.push(event);
  }
  return events;
}
