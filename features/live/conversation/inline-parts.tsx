'use client';
import {useCallback,useEffect,useRef,useState} from 'react';
import {Check,CircleAlert,CircleDashed,CircleSlash,Clock,FileText,Link2,Loader} from 'lucide-react';
import type {CitationItem,MessagePart,NoticePart,OutputLinkPart,ProposalCost,ProposalPart,ThreadAccess,ToolActivityPart,ToolState,TurnStatus} from './types';
import {approvalNoticeKey,decisionGate,followUpNoticeKey,proposalUiState,toolStateAfterDecision,type DecisionChoice,type LocalDecision} from './approval';
import {type TerminalProposal,type TranscriptEntry} from './parts';
import {ProposalExplainer} from './proposal-explainer';
import {PREVIEW_SANDBOX,previewNoticeKey,sandboxedPreviewHtml,type PreviewOutcome} from './output-preview';

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
  previewOutput:(outputId:string,revision:number,signal?:AbortSignal)=>Promise<PreviewOutcome>;
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
        <dl>{started&&<div><dt>{t('Started')}</dt><dd>{started}</dd></div>}{finished&&<div><dt>{t('Finished')}</dt><dd>{finished}</dd></div>}
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
type PreviewState={kind:'idle'}|{kind:'loading'}|{kind:'ready';html:string;truncated:boolean}|{kind:'error';error:'denied'|'missing'|'unavailable'};
/**
 * Collapsed-by-default, lazy once-per-mount preview. The frame only ever receives
 * server-authored HTML via srcDoc after the status has been inspected, and it is
 * sandboxed with no tokens so the content cannot script or navigate the app.
 */
function OutputPreview({part,actions}:{part:OutputLinkPart;actions:PartActions}){
  const t=actions.t;
  const [state,setState]=useState<PreviewState>({kind:'idle'});
  const active=useRef(0);
  const controller=useRef<AbortController|null>(null);
  const load=useCallback(async()=>{
    const request=++active.current;
    controller.current?.abort();
    const local=new AbortController();
    controller.current=local;
    setState({kind:'loading'});
    let outcome:PreviewOutcome;
    try{
      outcome=await actions.previewOutput(part.output_id,part.revision,local.signal);
    }catch{
      outcome={kind:'error',error:'unavailable'};
    }
    if(request!==active.current||local.signal.aborted)return;
    setState(outcome.kind==='ready'?{kind:'ready',html:outcome.html,truncated:outcome.truncated}:{kind:'error',error:outcome.error});
  },[actions,part.output_id,part.revision]);
  useEffect(()=>()=>{
    active.current+=1;
    controller.current?.abort();
    controller.current=null;
  },[]);
  return <details className="conversation-output-preview"
    style={{flexBasis:'100%',fontSize:12,minWidth:0,borderTop:'1px solid var(--buyeros-border)',paddingTop:6}}
    onToggle={event=>{
      if(event.currentTarget.open&&state.kind==='idle')void load();
    }}>
    <summary style={{cursor:'pointer',fontWeight:600,color:'var(--buyeros-accent-hover)'}}>{t('Preview')}</summary>
    <div className="conversation-output-preview-body" style={{display:'flex',flexDirection:'column',gap:6,marginTop:6,minWidth:0}}
      aria-live="polite">
      {state.kind==='loading'&&<p style={{margin:0,overflowWrap:'anywhere'}}>{t('Loading preview…')}</p>}
      {state.kind==='error'&&<>
        <p style={{margin:0,overflowWrap:'anywhere'}} role="status">{t(previewNoticeKey(state.error))}</p>
        {state.error==='unavailable'&&<button type="button" style={{alignSelf:'flex-start'}} onClick={()=>void load()}>{t('Retry preview')}</button>}
      </>}
      {state.kind==='ready'&&<>
        <iframe className="conversation-output-preview-frame" sandbox={PREVIEW_SANDBOX} srcDoc={sandboxedPreviewHtml(state.html)}
          referrerPolicy="no-referrer" title={`${t('Preview')}: ${part.title}`}
          style={{width:'100%',height:'18rem',maxHeight:'18rem',border:'1px solid var(--buyeros-border)',
            borderRadius:'var(--buyeros-radius-small)',background:'var(--buyeros-surface)'}}/>
        {state.truncated&&<p style={{margin:0,overflowWrap:'anywhere'}}>{t(previewNoticeKey('truncated'))}</p>}
      </>}
    </div>
  </details>;
}
function OutputLink({part,actions}:{part:OutputLinkPart;actions:PartActions}){
  const t=actions.t;
  return <article className="conversation-output">
    <FileText size={17} aria-hidden="true"/>
    <div><b>{part.title}</b><p><span className="pill gray">{t(part.status.replaceAll('_',' '))}</span> <span>{t('Revision')} {part.revision}</span></p></div>
    {part.href&&<button type="button" onClick={()=>actions.navigate(part.href!)}>{t('Open saved output')}</button>}
    <OutputPreview key={`${part.output_id}:${part.revision}`} part={part} actions={actions}/>
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
