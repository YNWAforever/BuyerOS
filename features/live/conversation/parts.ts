/**
 * Pure transcript reduction. Thread messages plus turn responses become ordered
 * entries; persisted parts win over a replayed turn payload, and a turn that the
 * returned thread already contains is never rendered twice.
 */
import type {ChatThread,CitationItem,ConversationTurn,MessagePart,MessageRole,NoticePart,
  OutputLinkPart,ProposalPart,SelectedSource,ToolActivityPart} from './types';
import {isTerminalNoticeCode} from './approval';

export type EphemeralReply={id:string;text:string;citations:CitationItem[]};
export type TranscriptEntry={
  key:string;role:MessageRole;message:{id:string;text:string};
  parts:MessagePart[];turnId:string|null;seq:number|null;createdAt:number|null;ephemeral:boolean;
};
export type TranscriptDay={key:string;dayStart:number|null;entries:TranscriptEntry[]};

export function textPart(text:string):MessagePart{return {kind:'text',text};}
function digest(parts:MessagePart[]):string{
  return parts.map(part=>part.kind==='text'?part.text:part.kind).join('\u0000');
}
function noticePart(notice:{code:string;message:string;recovery?:{label:string;route?:string}}):NoticePart{
  return {kind:'notice',code:notice.code,message:notice.message,...(notice.recovery?{recovery:notice.recovery}:{})};
}
function turnParts(turn:ConversationTurn):MessagePart[]{
  const noticeParts=turn.notices.map(noticePart);
  const seen=new Set<string>(),parts:MessagePart[]=[];
  for(const part of [...turn.parts,...noticeParts]){
    if(part.kind==='notice'){
      const key=`${part.code}\u0000${part.message}`;
      if(seen.has(key))continue;
      seen.add(key);
    }
    parts.push(part);
  }
  return parts;
}
/** A persisted message keeps its own text/parts; legacy rows only have `text`. */
export function entryParts(message:ChatThread['messages'][number]):MessagePart[]{
  if(message.parts.length)return message.parts;
  if(message.role==='assistant'&&message.text.trim())return [textPart(message.text)];
  return [];
}
function represented(thread:ChatThread|null,turn:ConversationTurn):boolean{
  if(!thread)return false;
  const wanted=digest(turnParts(turn));
  return thread.messages.some(message=>message.turnId===turn.id||message.id===turn.id||
    (message.role==='assistant'&&wanted!==''&&digest(entryParts(message))===wanted));
}
export function buildTranscript(thread:ChatThread|null,turns:ReadonlyArray<ConversationTurn>=[],
  ephemeral:ReadonlyArray<EphemeralReply>=[]):TranscriptEntry[]{
  const entries:TranscriptEntry[]=[];
  for(const message of thread?.messages??[]){
    entries.push({key:`message:${message.id}`,role:message.role,message:{id:message.id,text:message.text},
      parts:entryParts(message),turnId:message.turnId,seq:message.seq,createdAt:message.createdAt,ephemeral:false});
  }
  for(const turn of turns){
    // A turn already persisted on the returned thread is represented there; adding
    // it again would double every reply after a refetch.
    if(represented(thread,turn))continue;
    const parts=turnParts(turn);
    entries.push({key:`turn:${turn.id}`,role:'assistant',message:{id:turn.id,text:''},parts,turnId:turn.id,
      seq:null,createdAt:null,ephemeral:false});
  }
  for(const reply of ephemeral){
    const parts:MessagePart[]=[textPart(reply.text)];
    if(reply.citations.length)parts.push({kind:'citations',items:reply.citations});
    entries.push({key:`ephemeral:${reply.id}`,role:'assistant',message:{id:reply.id,text:reply.text},parts,
      turnId:null,seq:null,createdAt:null,ephemeral:true});
  }
  return entries;
}
export function dayKey(createdAt:number,utcOffsetMinutes=0):string|null{
  if(!Number.isFinite(createdAt)||createdAt<0)return null;
  return new Date(createdAt-utcOffsetMinutes*60_000).toISOString().slice(0,10);
}
export function dayStart(createdAt:number,utcOffsetMinutes=0):number|null{
  const key=dayKey(createdAt,utcOffsetMinutes);
  if(!key)return null;
  return Date.parse(`${key}T00:00:00.000Z`)+utcOffsetMinutes*60_000;
}
/** Consecutive same-day entries form one group; undated entries form an unlabelled group. */
export function groupTranscript(entries:ReadonlyArray<TranscriptEntry>,utcOffsetMinutes=0):TranscriptDay[]{
  const groups:TranscriptDay[]=[];
  for(const entry of entries){
    const key=entry.createdAt===null?'unknown':dayKey(entry.createdAt,utcOffsetMinutes);
    const current=groups[groups.length-1];
    if(current&&current.key===key){current.entries.push(entry);continue;}
    groups.push({key:key??'unknown',dayStart:entry.createdAt===null?null:dayStart(entry.createdAt,utcOffsetMinutes),entries:[entry]});
  }
  return groups;
}
export type PanelProposal={part:ProposalPart;turnId:string|null;key:string};
export type PanelData={results:OutputLinkPart[];citations:CitationItem[];selectedSources:SelectedSource[];proposals:PanelProposal[]};
export function collectPanelData(thread:ChatThread|null,entries:ReadonlyArray<TranscriptEntry>):PanelData{
  const results:OutputLinkPart[]=[],citations:CitationItem[]=[],proposals:PanelProposal[]=[];
  const seenResults=new Set<string>(),seenCitations=new Set<string>(),seenProposals=new Set<string>();
  for(const entry of entries)for(const part of entry.parts){
    if(part.kind==='output_link'){
      const key=`${part.output_id}\u0000${part.revision}`;
      if(seenResults.has(key))continue;
      seenResults.add(key);results.push(part);
    }else if(part.kind==='citations'){
      for(const item of part.items){
        if(seenCitations.has(item.id))continue;
        seenCitations.add(item.id);citations.push(item);
      }
    }else if(part.kind==='proposal'){
      if(seenProposals.has(part.proposal_id))continue;
      seenProposals.add(part.proposal_id);proposals.push({part,turnId:entry.turnId,key:entry.key});
    }
  }
  return {results,citations,selectedSources:thread?.sources??[],proposals};
}
export function latestToolActivity(entries:ReadonlyArray<TranscriptEntry>,capability:string):ToolActivityPart|null{
  let latest:ToolActivityPart|null=null;
  for(const entry of entries)for(const part of entry.parts){
    if(part.kind==='tool_activity'&&part.capability===capability)latest=part;
  }
  return latest;
}
export function panelHasContent(panel:PanelData):boolean{
  return panel.results.length>0||panel.citations.length>0||panel.selectedSources.length>0||panel.proposals.length>0;
}
export type TerminalProposal={terminal:boolean;noticeMessage?:string};
/**
 * A proposal whose continuation already ended in a terminal configuration notice (or
 * a failed/skipped tool step for the same capability) must never be actionable again,
 * including after reload when the local decision record is gone.
 */
export function terminalProposals(entries:ReadonlyArray<TranscriptEntry>):Map<string,TerminalProposal>{
  const result=new Map<string,TerminalProposal>();
  entries.forEach((entry,index)=>{
    const proposals=entry.parts.filter((part):part is ProposalPart=>part.kind==='proposal');
    if(!proposals.length)return;
    const later=entries.slice(index+1);
    for(const proposal of proposals){
      for(const row of later){
        for(const part of row.parts){
          if(part.kind==='notice'&&isTerminalNoticeCode(part.code)){
            result.set(proposal.proposal_id,{terminal:true,noticeMessage:part.message});
          }else if(part.kind==='tool_activity'&&part.capability===proposal.capability&&
            (part.state==='failed'||part.state==='outcome_unknown'||part.state==='skipped')){
            if(!result.has(proposal.proposal_id))result.set(proposal.proposal_id,{terminal:true});
          }
        }
      }
    }
  });
  return result;
}
/** Company identity linked to the thread, taken only from persisted/response citations. */
export function companyFromEntries(entries:ReadonlyArray<TranscriptEntry>):{id:string;label:string}|null{
  for(const entry of entries)for(const part of entry.parts){
    if(part.kind!=='citations')continue;
    const buyer=part.items.find(item=>item.kind==='buyer');
    if(buyer)return {id:buyer.id,label:buyer.label};
  }
  return null;
}
