/**
 * Conversation-turn contract v0 + Amendment A (2026-11-08), client-side shapes.
 *
 * This module is dependency-free and browser-free so the part reducer and approval
 * logic can be unit tested without React. Every value that crosses the network is
 * untrusted: readers below allowlist kinds, cap lengths and degrade unknown data
 * instead of throwing, so one additive server field can never crash a transcript.
 */
export type TurnStatus='completed'|'needs_input'|'needs_approval'|'failed'|'outcome_unknown'|'cancelled';
export const turnStatuses:readonly TurnStatus[]=['completed','needs_input','needs_approval','failed','outcome_unknown','cancelled'];
export type ToolState='proposed'|'approved'|'running'|'completed'|'failed'|'skipped'|'outcome_unknown';
export const toolStates:readonly ToolState[]=['proposed','approved','running','completed','failed','skipped','outcome_unknown'];
export type ThreadAccess='owner'|'editor'|'viewer';
export type MessageRole='user'|'assistant';
export type Recovery={label:string;route?:string};
export type CitationItem={id:string;label:string;kind:string;href:string};
export type TextPart={kind:'text';text:string;language?:string};
export type CitationsPart={kind:'citations';items:CitationItem[]};
export type ToolActivityPart={kind:'tool_activity';call_id:string;capability:string;title:string;state:ToolState;
  started_at?:string;finished_at?:string;summary?:string;error_code?:string};
export type ProposalCost={kind?:'nonbillable'|'provider_credits';amount?:number|string;unit?:string;
  may_incur_provider_charges?:boolean;known?:boolean;basis?:string};
export type ProposalPart={kind:'proposal';proposal_id:string;capability:string;title:string;rationale?:string;
  arguments_preview?:unknown;cost?:ProposalCost;requires_approval:boolean};
export type OutputLinkPart={kind:'output_link';output_id:string;outputKind:string;title:string;revision:number;status:string;href?:string};
export type NoticePart={kind:'notice';code:string;message:string;recovery?:Recovery};
/** A part kind this client version does not understand. Rendered as a quiet notice. */
export type UnsupportedPart={kind:'unsupported';source_kind:string};
export type MessagePart=TextPart|CitationsPart|ToolActivityPart|ProposalPart|OutputLinkPart|NoticePart|UnsupportedPart;
export type TurnNotice={code:string;message:string;recovery?:Recovery};
export type ConversationTurn={id:string;status:TurnStatus;parts:MessagePart[];notices:TurnNotice[]};
export type SelectedSource={id:string;label:string};
export type ChatRunReference={id:string;label:string;status:string};
export type ChatMessage={id:string;text:string;role:MessageRole;seq:number|null;clientMessageId:string|null;
  createdAt:number|null;parts:MessagePart[];turnId:string|null};
export type ChatThread={id:string;version:number;templateId:string;title:string;createdAt:number;updatedAt:number;
  access:ThreadAccess;shareCount:number;buyerId:string|null;messages:ChatMessage[];sources:SelectedSource[];runs:ChatRunReference[]};
export type TurnResult={thread:ChatThread;turn:ConversationTurn};
export type TurnCapability='checking'|'available'|'absent'|'unavailable';
export type TurnDecision='approve'|'reject';

const uuidRe=/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;
const MAX_MESSAGES=500;
const MAX_PARTS=64;
const MAX_TEXT=20_000;
const MAX_USER_TEXT=4_000;
const MAX_CITATIONS=50;
const MAX_SOURCES=100;
const MAX_HREF=500;
export function isUuid(value:unknown):value is string{return typeof value==='string'&&uuidRe.test(value);}
function record(value:unknown):value is Record<string,unknown>{
  return typeof value==='object'&&value!==null&&!Array.isArray(value);
}
function str(value:unknown,max=MAX_TEXT):value is string{return typeof value==='string'&&value.length<=max;}
function nonBlank(value:unknown,max=MAX_TEXT):value is string{return str(value,max)&&value.trim().length>0;}
function int(value:unknown):value is number{return Number.isSafeInteger(value)&&(value as number)>=0;}
function dateString(value:unknown):value is string{
  return typeof value==='string'&&value.length<=64&&/^\d{4}-\d\d-\d\dT/.test(value)&&Number.isFinite(Date.parse(value));
}
function time(value:unknown):number|null{
  if(typeof value==='number'&&Number.isFinite(value)&&value>=0)return Math.floor(value);
  if(typeof value==='string'&&value.length<=64){const parsed=Date.parse(value);if(Number.isFinite(parsed)&&parsed>=0)return parsed;}
  return null;
}
/** Only internal application routes are navigable. Server-provided strings stay data. */
export function internalHref(value:unknown):string|undefined{
  if(!str(value,MAX_HREF)||!value.startsWith('/app')||value.startsWith('//'))return undefined;
  if(value!=='/app'&&!value.startsWith('/app/')&&!value.startsWith('/app?'))return undefined;
  if(/[\u0000-\u001f\\]/.test(value))return undefined;
  return value;
}
export function readRecovery(value:unknown):Recovery|undefined{
  if(!record(value)||!nonBlank(value.label,120))return undefined;
  const route=internalHref(value.route);
  return route?{label:value.label,route}:{label:value.label};
}
function readCost(value:unknown):ProposalCost|undefined{
  if(!record(value))return undefined;
  const cost:ProposalCost={};
  if(value.kind==='nonbillable'||value.kind==='provider_credits')cost.kind=value.kind;
  if(typeof value.amount==='number'&&Number.isFinite(value.amount))cost.amount=value.amount;
  else if(typeof value.amount==='string'&&/^\d{1,18}(?:\.\d{1,4})?$/.test(value.amount))cost.amount=value.amount;
  if(value.unit==='USD'||value.unit==='credits')cost.unit=value.unit;
  if(typeof value.may_incur_provider_charges==='boolean')cost.may_incur_provider_charges=value.may_incur_provider_charges;
  if(typeof value.known==='boolean')cost.known=value.known;
  if(str(value.basis,120))cost.basis=value.basis;
  return Object.keys(cost).length?cost:undefined;
}
const partKinds=['text','citations','tool_activity','proposal','output_link','notice'] as const;
function partDiscriminator(value:Record<string,unknown>):{kind:string;payloadKind:string|undefined}{
  for(const field of ['part_kind','part','type','kind'] as const){
    const candidate=value[field];
    if(typeof candidate==='string'&&(partKinds as readonly string[]).includes(candidate)){
      // `output_link` carries an output kind in its payload; a wire that puts that
      // value in `kind` still names the part via `part`/`part_kind`/`type`.
      return {kind:candidate,payloadKind:field==='kind'?undefined:candidate};
    }
  }
  return {kind:'unsupported',payloadKind:undefined};
}
/** Unknown or malformed part kinds become an `unsupported` marker, never an exception. */
export function readMessagePart(value:unknown):MessagePart{
  if(!record(value))return {kind:'unsupported',source_kind:'unknown'};
  const discriminator=partDiscriminator(value);
  const kind=discriminator.kind;
  switch(kind){
    case 'text':
      return nonBlank(value.text)?{kind:'text',text:value.text,...(str(value.language,16)?{language:value.language}:{})}:{kind:'unsupported',source_kind:'text'};
    case 'citations':{
      if(!Array.isArray(value.items))return {kind:'unsupported',source_kind:'citations'};
      const seen=new Set<string>(),items:CitationItem[]=[];
      for(const item of value.items.slice(0,MAX_CITATIONS)){
        if(!record(item)||!nonBlank(item.id,200)||seen.has(item.id)||!nonBlank(item.label,200)||!str(item.kind,80))continue;
        const href=internalHref(item.href)??'';
        seen.add(item.id);items.push({id:item.id,label:item.label,kind:item.kind,href});
      }
      return items.length?{kind:'citations',items}:{kind:'unsupported',source_kind:'citations'};
    }
    case 'tool_activity':{
      if(!nonBlank(value.call_id,200)||!nonBlank(value.capability,120)||!nonBlank(value.title,200))return {kind:'unsupported',source_kind:'tool_activity'};
      const state=toolStates.includes(value.state as ToolState)?value.state as ToolState:null;
      if(!state)return {kind:'unsupported',source_kind:'tool_activity'};
      return {kind:'tool_activity',call_id:value.call_id,capability:value.capability,title:value.title,state,
        ...(dateString(value.started_at)?{started_at:value.started_at}:{}),
        ...(dateString(value.finished_at)?{finished_at:value.finished_at}:{}),
        ...(str(value.summary,2_000)?{summary:value.summary}:{}),
        ...(str(value.error_code,120)?{error_code:value.error_code}:{})};
    }
    case 'proposal':{
      if(!nonBlank(value.proposal_id,200)||!nonBlank(value.capability,120)||!nonBlank(value.title,200))return {kind:'unsupported',source_kind:'proposal'};
      const cost=readCost(value.cost);
      return {kind:'proposal',proposal_id:value.proposal_id,capability:value.capability,title:value.title,
        ...(str(value.rationale,2_000)?{rationale:value.rationale}:{}),
        arguments_preview:value.arguments_preview,
        ...(cost?{cost}:{}),requires_approval:value.requires_approval!==false};
    }
    case 'output_link':{
      // The wire nests the output kind under `output` because `kind` is the part
      // discriminator; flat snake_case fields are tolerated during rollout.
      const nested=record(value.output)?value.output:value;
      const outputId=nested===value?(value.output_id??value.outputId):(nested.output_id??nested.outputId);
      const flatKind=typeof value.kind==='string'&&!(partKinds as readonly string[]).includes(value.kind)?value.kind:undefined;
      const outputKind=nested===value?(value.output_kind??value.outputKind??flatKind):
        (nested.output_kind??nested.outputKind??nested.kind);
      const revision=nested.revision??value.revision,status=nested.status??value.status,title=value.title;
      if(!nonBlank(outputId,200)||!nonBlank(outputKind,80)||!nonBlank(title,200)||!int(revision)||revision<1||!nonBlank(status,80))return {kind:'unsupported',source_kind:'output_link'};
      const href=internalHref(value.href);
      return {kind:'output_link',output_id:outputId,outputKind,title,revision,status,...(href?{href}:{})};
    }
    case 'notice':{
      if(!nonBlank(value.code,120)||!nonBlank(value.message,2_000))return {kind:'unsupported',source_kind:'notice'};
      const recovery=readRecovery(value.recovery);
      return {kind:'notice',code:value.code,message:value.message,...(recovery?{recovery}:{})};
    }
    default:return {kind:'unsupported',source_kind:typeof value.kind==='string'&&!(partKinds as readonly string[]).includes(value.kind)?value.kind.slice(0,40):'unknown'};
  }
}
export function readMessageParts(value:unknown):MessagePart[]{
  if(!Array.isArray(value))return [];
  const parts:MessagePart[]=[];
  for(const item of value.slice(0,MAX_PARTS))parts.push(readMessagePart(item));
  return parts;
}
export function readTurnNotice(value:unknown):TurnNotice|null{
  if(!record(value)||!nonBlank(value.code,120)||!nonBlank(value.message,2_000))return null;
  const recovery=readRecovery(value.recovery);
  return {code:value.code,message:value.message,...(recovery?{recovery}:{})};
}
export function readTurn(value:unknown):ConversationTurn|null{
  if(!record(value)||!isUuid(value.id))return null;
  if(!turnStatuses.includes(value.status as TurnStatus))return null;
  const notices=Array.isArray(value.notices)?value.notices.slice(0,MAX_PARTS).map(readTurnNotice).filter((row):row is TurnNotice=>row!==null):[];
  return {id:value.id,status:value.status as TurnStatus,parts:readMessageParts(value.parts),notices};
}
function readRole(value:unknown,parts:MessagePart[]):MessageRole{
  if(value==='assistant'||value==='user')return value;
  // Unknown role degrades to the safer reading: content-bearing rows are replies.
  return parts.length?'assistant':'user';
}
export function readChatMessage(value:unknown):ChatMessage|null{
  if(!record(value)||!nonBlank(value.id,200))return null;
  const parts=readMessageParts(value.parts);
  const role=readRole(value.role,parts);
  const textLength=role==='user'?MAX_USER_TEXT:MAX_TEXT;
  let text='';
  if(str(value.text,textLength))text=value.text;
  if(!text&&role==='assistant')text=parts.filter((part):part is TextPart=>part.kind==='text').map(part=>part.text).join('\n\n');
  const seq=int(value.seq)?value.seq as number:null;
  const createdAt=time(value.createdAt)??time(value.created_at);
  const clientMessageIdRaw=value.clientMessageId??value.client_message_id;
  const clientMessageId=typeof clientMessageIdRaw==='string'&&clientMessageIdRaw.length<=200?clientMessageIdRaw:null;
  const turnIdRaw=value.turnId??value.turn_id;
  const turnId=typeof turnIdRaw==='string'&&turnIdRaw.length<=200?turnIdRaw:null;
  return {id:value.id,text,role,seq,clientMessageId,createdAt,parts,turnId};
}
function readAccess(value:unknown):ThreadAccess|null{
  return value==='owner'||value==='editor'||value==='viewer'?value:null;
}
export function readChatThread(value:unknown):ChatThread|null{
  if(!record(value)||!nonBlank(value.id,200))return null;
  const access=readAccess(value.access);
  if(!access||!int(value.version)||!str(value.templateId,80)||!nonBlank(value.title,400)||!int(value.createdAt)||!int(value.updatedAt))return null;
  if(!Array.isArray(value.messages)||value.messages.length>MAX_MESSAGES)return null;
  const messages:ChatMessage[]=[];
  for(const row of value.messages){
    const message=readChatMessage(row);
    if(message)messages.push(message);
  }
  const sources:SelectedSource[]=[];
  if(Array.isArray(value.sources))for(const source of value.sources.slice(0,MAX_SOURCES)){
    if(record(source)&&nonBlank(source.id,200)&&nonBlank(source.label,80))sources.push({id:source.id,label:source.label});
  }
  const runs:ChatRunReference[]=[];
  if(Array.isArray(value.runs))for(const run of value.runs.slice(0,MAX_SOURCES)){
    if(record(run)&&nonBlank(run.id,200)&&nonBlank(run.label,80)&&nonBlank(run.status,80))runs.push({id:run.id,label:run.label,status:run.status});
  }
  const buyerIdRaw=value.buyerId??value.buyer_id;
  const buyerId=typeof buyerIdRaw==='string'&&buyerIdRaw.length>0&&buyerIdRaw.length<=200?buyerIdRaw:null;
  return {id:value.id,version:value.version,templateId:value.templateId,title:value.title,createdAt:value.createdAt,
    updatedAt:value.updatedAt,access,shareCount:int(value.shareCount)?value.shareCount as number:0,buyerId,messages,sources,runs};
}
export function readTurnResult(value:unknown):TurnResult|null{
  if(!record(value))return null;
  const thread=readChatThread(value.thread),turn=readTurn(value.turn);
  return thread&&turn?{thread,turn}:null;
}
