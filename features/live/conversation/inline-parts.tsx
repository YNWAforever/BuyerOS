'use client';
import {Check,CircleAlert,CircleDashed,CircleSlash,Clock,FileText,Link2,Loader} from 'lucide-react';
import type {CitationItem,MessagePart,NoticePart,OutputLinkPart,ProposalCost,ProposalPart,ThreadAccess,ToolActivityPart,ToolState,TurnStatus} from './types';
import {approvalNoticeKey,decisionGate,followUpNoticeKey,proposalUiState,toolStateAfterDecision,type DecisionChoice,type LocalDecision} from './approval';
import {type TerminalProposal,type TranscriptEntry} from './parts';
import {ProposalExplainer} from './proposal-explainer';

export type PartActions={
  t:(value:string)=>string;
  locale:'en'|'zh-HK';
  navigate:(path:string)=>void;
  access:ThreadAccess;
  turnStatusFor:(turnId:string|null)=>TurnStatus|undefined;
  decisionFor:(proposalId:string)=>LocalDecision|undefined;
  terminalFor:(proposalId:string)=>TerminalProposal|undefined;
  toolFor:(capability:string)=>ToolActivityPart|null;
  partsForTurn:(turnId:string|null)=>ReadonlyArray<MessagePart>;
  decide:(part:ProposalPart,turnId:string|null,choice:DecisionChoice)=>void;
  deciding:boolean;
};
const stateLabel:Record<ToolState,string>={
  proposed:'Proposed',approved:'Approved',running:'Running',completed:'Completed',
  failed:'Failed',skipped:'Skipped',outcome_unknown:'Outcome unknown',
};
function stateTone(state:ToolState):string{
  if(state==='completed')return 'green';
  if(state==='failed')return 'red';
  if(state==='outcome_unknown')return 'amber';
  if(state==='running'||state==='approved')return 'blue';
  return 'gray';
}
function StateIcon({state}:{state:ToolState}){
  if(state==='completed')return <Check size={15} aria-hidden="true"/>;
  if(state==='failed')return <CircleAlert size={15} aria-hidden="true"/>;
  if(state==='running'||state==='approved')return <Loader size={15} aria-hidden="true"/>;
  if(state==='skipped')return <CircleSlash size={15} aria-hidden="true"/>;
  if(state==='outcome_unknown')return <CircleDashed size={15} aria-hidden="true"/>;
  return <Clock size={15} aria-hidden="true"/>;
}
function shortTime(value:string|undefined):string{
  if(!value)return '';
  const parsed=Date.parse(value);
  return Number.isFinite(parsed)?new Date(parsed).toLocaleTimeString(undefined,{hour:'2-digit',minute:'2-digit'}):'';
}
/** Untrusted preview data now lives in the explainer projection (bounded/allowlisted). */
function Citations({part,actions}:{part:{items:CitationItem[]};actions:PartActions}){
  return <ul className="conversation-citations" aria-label={actions.t('Sources')}>{part.items.map(item=>
    <li key={item.id}>{item.href
      ?<button type="button" onClick={()=>actions.navigate(item.href)}><Link2 size={13} aria-hidden="true"/>{actions.t(item.label)}</button>
      :<span className="pill gray">{actions.t(item.label)}</span>}</li>)}
  </ul>;
}
function ToolActivity({part,actions}:{part:ToolActivityPart;actions:PartActions}){
  const t=actions.t,started=shortTime(part.started_at),finished=shortTime(part.finished_at);
  return <article className={`conversation-tool is-${part.state}`} aria-label={t('Tool activity')}>
    <span className="conversation-tool-icon" aria-hidden="true"><StateIcon state={part.state}/></span>
    <div className="conversation-tool-body">
      <div className="conversation-tool-head"><b>{part.title}</b><span className={`pill ${stateTone(part.state)}`}>{t(stateLabel[part.state])}</span></div>
      {part.summary&&<p>{part.summary}</p>}
      <details className="conversation-tool-details"><summary>{t('Details')}</summary>
        <dl><div><dt>{t('Capability')}</dt><dd>{part.capability}</dd></div>
          {started&&<div><dt>{t('Started')}</dt><dd>{started}</dd></div>}{finished&&<div><dt>{t('Finished')}</dt><dd>{finished}</dd></div>}
          {part.error_code&&<div><dt>{t('Error code')}</dt><dd><code>{part.error_code}</code></dd></div>}</dl>
      </details>
    </div>
  </article>;
}
function ProposalCostLine({cost,t}:{cost:ProposalCost;t:(value:string)=>string}){
  if(cost.kind==='provider_credits'&&cost.known===false)
    return <p className="conversation-proposal-cost">{t('Cost review required before any paid request.')}</p>;
  if(cost.known===false)return null;
  if(cost.amount===undefined)return null;
  return <p className="conversation-proposal-cost">{t('Cost')}: {String(cost.amount)}{cost.unit?` ${cost.unit}`:''}</p>;
}
function Proposal({part,entry,actions}:{part:ProposalPart;entry:TranscriptEntry;actions:PartActions}){
  const t=actions.t,turnStatus=actions.turnStatusFor(entry.turnId);
  const terminal=actions.terminalFor(part.proposal_id);
  const state=proposalUiState(part,turnStatus,actions.decisionFor(part.proposal_id),actions.access,terminal?.terminal??false);
  const gate=decisionGate(state),tool=actions.toolFor(part.capability),after=toolStateAfterDecision(tool);
  const notice=approvalNoticeKey(state);
  return <section className={`conversation-proposal is-${state}`} aria-label={t('Approval required')} aria-busy={state==='submitting'}>
    <div className="conversation-proposal-head"><b>{part.title}</b><span className="pill amber">{t('Approval required')}</span></div>
    {part.cost&&<ProposalCostLine cost={part.cost} t={t}/>}
    {gate.canDecide
      ?<div className="conversation-proposal-actions"><button type="button" className="live-primary" disabled={actions.deciding} onClick={()=>actions.decide(part,entry.turnId,'approve')}>{t('Approve')}</button><button type="button" disabled={actions.deciding} onClick={()=>actions.decide(part,entry.turnId,'reject')}>{t('Reject')}</button></div>
      :notice?<p className="conversation-proposal-state" role="status">{t(notice)}</p>:null}
    {after&&after!=='proposed'&&after!=='approved'&&<p className={`conversation-proposal-state ${after==='failed'?'error':''}`} role="status">{t(followUpNoticeKey(after))}</p>}
    <ProposalExplainer t={t} locale={actions.locale} navigate={actions.navigate} proposal={part}
      turnParts={actions.partsForTurn(entry.turnId)} approvalState={state}/>
  </section>;
}
function OutputLink({part,actions}:{part:OutputLinkPart;actions:PartActions}){
  const t=actions.t;
  return <article className="conversation-output">
    <FileText size={17} aria-hidden="true"/>
    <div><b>{part.title}</b><p><span className="pill gray">{t(part.status.replaceAll('_',' '))}</span> <span>{t('Revision')} {part.revision}</span></p></div>
    {part.href&&<button type="button" onClick={()=>actions.navigate(part.href!)}>{t('Open saved output')}</button>}
  </article>;
}
function Notice({part,actions}:{part:NoticePart;actions:PartActions}){
  const t=actions.t;
  return <div className="conversation-notice" role="status">
    <p>{part.message}</p>
    {part.recovery?.route&&<button type="button" onClick={()=>actions.navigate(part.recovery!.route!)}>{t(part.recovery.label)}</button>}
  </div>;
}
function Part({part,entry,actions}:{part:MessagePart;entry:TranscriptEntry;actions:PartActions}){
  switch(part.kind){
    case 'text':return <p className="conversation-part-text">{part.text}</p>;
    case 'citations':return <Citations part={part} actions={actions}/>;
    case 'tool_activity':return <ToolActivity part={part} actions={actions}/>;
    case 'proposal':return <Proposal part={part} entry={entry} actions={actions}/>;
    case 'output_link':return <OutputLink part={part} actions={actions}/>;
    case 'notice':return <Notice part={part} actions={actions}/>;
    default:return <p className="conversation-part-unsupported">{actions.t('This update is not supported by this interface.')}</p>;
  }
}
/** Inline parts for one assistant turn; unknown kinds degrade to a quiet notice. */
export function MessageParts({entry,actions}:{entry:TranscriptEntry;actions:PartActions}){
  if(!entry.parts.length)return null;
  return <>{entry.parts.map((part,index)=><Part key={`${part.kind}:${index}`} part={part} entry={entry} actions={actions}/>)}</>;
}
