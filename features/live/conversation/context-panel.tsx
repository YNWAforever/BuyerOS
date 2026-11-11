'use client';
import {useEffect,useRef,useState,type KeyboardEvent,type ReactNode} from 'react';
import {ChartNoAxesCombined,FileText,Gauge,Link2,ShieldCheck,X} from 'lucide-react';
import {LiveCancelled} from '@/services/live/client';
import {loadTurnMetrics,MetricsLoadError} from '@/services/live/conversation-metrics';
import {METRICS_WINDOW_DAYS,formatLatency,formatMetricAmount,hasTurns,
  statusRows,type TurnStatusRow,type TurnMetrics} from './metrics';
import type {LiveClient} from '@/services/live/client';
import type {SessionScope} from '@/services/live/session';
import {loadDiscussionContext,type ContextSection} from '@/services/live/discussion-context';
import type {ChatRunReference,CitationItem,ProposalPart,SelectedSource,ThreadAccess,TurnStatus} from './types';
import {approvalNoticeKey,decisionGate,followUpNoticeKey,proposalUiState,type DecisionChoice,type LocalDecision} from './approval';
import type {OutputLinkPart} from './types';
import type {PanelProposal} from './parts';
import {latestToolActivity,type TerminalProposal} from './parts';
import type {TranscriptEntry} from './parts';
import {nextTabIndex,tabSequenceIndex} from './a11y';

export type PanelTab='results'|'sources'|'decisions'|'metrics';
type Props={
  t:(value:string)=>string;
  locale:'en'|'zh-HK';
  tab:PanelTab;
  tabs:PanelTab[];
  onTab:(tab:PanelTab)=>void;
  results:OutputLinkPart[];
  runs:ChatRunReference[];
  citations:CitationItem[];
  selectedSources:SelectedSource[];
  proposals:PanelProposal[];
  entries:TranscriptEntry[];
  access:ThreadAccess;
  threadId:string|null;
  threadVersion:number;
  contextRevision:number;
  canEdit:boolean;
  canViewOffer:boolean;
  client:LiveClient;
  session:SessionScope;
  navigate:(path:string)=>void;
  onToggleSource:(source:SelectedSource,selected:boolean)=>void;
  sourcesBusy:boolean;
  onRemoveDrive:()=>void;
  onDecide:(part:ProposalPart,turnId:string|null,choice:DecisionChoice)=>void;
  deciding:boolean;
  decisionFor:(proposalId:string)=>LocalDecision|undefined;
  terminalFor:(proposalId:string)=>TerminalProposal|undefined;
  turnStatusFor:(turnId:string|null)=>TurnStatus|undefined;
  drive:ReactNode;
  onClose?:()=>void;
};
function tabIcon(tab:PanelTab){
  if(tab==='results')return <ChartNoAxesCombined size={14} aria-hidden="true"/>;
  if(tab==='sources')return <FileText size={14} aria-hidden="true"/>;
  if(tab==='metrics')return <Gauge size={14} aria-hidden="true"/>;
  return <ShieldCheck size={14} aria-hidden="true"/>;
}
function PanelLabel({tab,t}:{tab:PanelTab;t:(value:string)=>string}){
  return <>{tabIcon(tab)}{t(tab==='results'?'Results':tab==='sources'?'Sources':tab==='metrics'?'Turn metrics':'Decisions')}</>;
}
function SourcePicker({t,client,session,threadId,canViewOffer,selected,onToggleSource,busy,navigate,contextRevision}:{
  t:(value:string)=>string;client:LiveClient;session:SessionScope;threadId:string|null;canViewOffer:boolean;
  selected:SelectedSource[];onToggleSource:(source:SelectedSource,selected:boolean)=>void;busy:boolean;navigate:(path:string)=>void;
  contextRevision:number;
}){
  const [sections,setSections]=useState<ContextSection[]|null>(null),[notice,setNotice]=useState('');
  const read=useRef<string|null>(null);
  useEffect(()=>{
    if(!canViewOffer||!threadId)return;
    const key=`${session.identity()}:${threadId}:${contextRevision}`;
    if(read.current===key)return;
    read.current=key;let active=true;
    void loadDiscussionContext(client,session,{enabled:true,canViewOffer,canViewResults:false,signal:session.controller().signal})
      .then(rows=>{if(active)setSections(rows);}).catch(()=>{if(active)setNotice('Project context is unavailable. Try again later.');});
    return()=>{active=false;};
  },[client,session,canViewOffer,threadId,contextRevision]);
  if(!threadId)return <p>{t('Start a discussion before selecting sources.')}</p>;
  return <div className="conversation-sources-picker">
    <div className="conversation-panel-row"><b>{t('Project context')}</b><button type="button" onClick={()=>navigate('/app/discover/edit#offer-documents')}>{t('Open offer documents')}</button></div>
    {notice&&<p role="status">{t(notice)}</p>}
    {!sections?<p role="status">{t('Loading project context…')}</p>:sections.map((section,index)=><section key={index} aria-label={t(section.title)}>
      <h4>{t(section.title)}</h4>
      {section.notice&&<p className="conversation-panel-note">{t(section.notice)}</p>}
      {section.items.map(item=><label key={item.id} className="conversation-source-option">
        <input type="checkbox" disabled={busy} checked={selected.some(source=>source.id===item.id)} onChange={event=>onToggleSource({id:item.id,label:item.label},event.target.checked)}/>
        <span>{item.title!==item.label&&!item.id.startsWith('results:')?item.title:t(item.label)}</span>
        {item.id.startsWith('document:')&&item.status?<span className="pill gray">{t(item.status.replaceAll('_',' '))}</span>:null}
      </label>)}
    </section>)}
    <p className="conversation-panel-note">{t('A saved selection does not grant access. Current project permissions apply.')}</p>
  </div>;
}
function ResultsTab({t,results,runs,navigate}:{t:(value:string)=>string;results:OutputLinkPart[];runs:ChatRunReference[];navigate:(path:string)=>void}){
  if(!results.length&&!runs.length)return <p className="conversation-panel-empty">{t('No results in this discussion yet.')}</p>;
  return <div className="conversation-results">
    {results.map((part,index)=><article key={`${part.output_id}:${part.revision}:${index}`} className="conversation-result">
      <b>{part.title}</b><p><span className="pill gray">{t(part.status.replaceAll('_',' '))}</span> <span>{t('Revision')} {part.revision}</span></p>
      {part.href&&<button type="button" onClick={()=>navigate(part.href!)}>{t('Open saved output')}</button>}
    </article>)}
    {runs.map(run=><article key={run.id} className="conversation-result">
      <b>{t(run.label)}</b><p><span className="pill gray">{t(run.status.replaceAll('_',' '))}</span></p>
      <button type="button" onClick={()=>navigate(`/app/discover/${encodeURIComponent(run.id)}`)}>{t('Open research run')}</button>
    </article>)}
  </div>;
}
function SourcesTab({t,citations,selectedSources,canEdit,onToggleSource,sourcesBusy,onRemoveDrive,drive,threadId,canViewOffer,client,session,navigate,contextRevision}:{
  t:(value:string)=>string;citations:CitationItem[];selectedSources:SelectedSource[];canEdit:boolean;
  onToggleSource:(source:SelectedSource,selected:boolean)=>void;sourcesBusy:boolean;onRemoveDrive:()=>void;drive:ReactNode;threadId:string|null;
  canViewOffer:boolean;client:LiveClient;session:SessionScope;navigate:(path:string)=>void;contextRevision:number;
}){
  return <div className="conversation-sources">
    {citations.length>0&&<><h4>{t('Cited sources')}</h4><ul className="conversation-citations" aria-label={t('Cited sources')}>{citations.map(item=><li key={item.id}>{item.href?<button type="button" onClick={()=>navigate(item.href!)}><Link2 size={13} aria-hidden="true"/>{t(item.label)}</button>:<span className="pill gray">{t(item.label)}</span>}</li>)}</ul></>}
    <h4>{t('Selected sources')} ({selectedSources.length})</h4>
    {selectedSources.length?<ul className="conversation-selected-sources">{selectedSources.map(source=><li key={source.id}><span>{t(source.label)}</span>{canEdit&&<button type="button" disabled={sourcesBusy} onClick={()=>onToggleSource(source,false)}>{t('Remove')}</button>}</li>)}</ul>:<p className="conversation-panel-empty">{t('No sources selected.')}</p>}
    {canEdit&&selectedSources.some(source=>source.id.startsWith('drive:'))&&<button type="button" disabled={sourcesBusy} onClick={onRemoveDrive}>{t('Remove unavailable Google Drive selections')}</button>}
    <SourcePicker t={t} client={client} session={session} threadId={threadId} canViewOffer={canViewOffer} selected={selectedSources} onToggleSource={onToggleSource} busy={sourcesBusy} navigate={navigate} contextRevision={contextRevision}/>
    <details className="conversation-panel-details"><summary>{t('Google Drive')}</summary>{drive}</details>
  </div>;
}
function DecisionsTab({t,proposals,entries,access,onDecide,deciding,decisionFor,terminalFor,turnStatusFor}:{
  t:(value:string)=>string;proposals:PanelProposal[];entries:TranscriptEntry[];access:ThreadAccess;
  onDecide:(part:ProposalPart,turnId:string|null,choice:DecisionChoice)=>void;deciding:boolean;
  decisionFor:(proposalId:string)=>LocalDecision|undefined;terminalFor:(proposalId:string)=>TerminalProposal|undefined;
  turnStatusFor:(turnId:string|null)=>TurnStatus|undefined;
}){
  if(!proposals.length)return <p className="conversation-panel-empty">{t('No decisions in this discussion yet.')}</p>;
  return <ul className="conversation-decisions">{proposals.map(item=>{
    const terminal=terminalFor(item.part.proposal_id);
    const state=proposalUiState(item.part,turnStatusFor(item.turnId),decisionFor(item.part.proposal_id),access,terminal?.terminal??false);
    const gate=decisionGate(state),notice=approvalNoticeKey(state);
    const tool=latestToolActivity(entries,item.part.capability);
    return <li key={item.part.proposal_id}>
      <b>{item.part.title}</b>
      <p><span className={`pill ${state==='approved'?'green':state==='rejected'||state==='failed'||state==='inert'?'red':state==='unknown_outcome'?'amber':'gray'}`}>{t(state==='awaiting'?'Awaiting approval':state==='submitting'?'Sending…':state==='approved'?'Approved':state==='rejected'?'Rejected':state==='failed'?'Not confirmed':state==='unknown_outcome'?'Outcome unknown':state==='inert'?'Cannot run':'Unavailable')}</span></p>
      {gate.canDecide?<div className="conversation-proposal-actions"><button type="button" className="live-primary" disabled={deciding} onClick={()=>onDecide(item.part,item.turnId,'approve')}>{t('Approve')}</button><button type="button" disabled={deciding} onClick={()=>onDecide(item.part,item.turnId,'reject')}>{t('Reject')}</button></div>:notice&&<p className="conversation-panel-note" role="status">{t(notice)}</p>}
      {tool&&<p className="conversation-panel-note">{t(followUpNoticeKey(tool.state))}</p>}
    </li>;
  })}</ul>;
}
function statusLabel(status:TurnStatusRow):string{
  switch(status){
    case 'completed':return 'Completed';
    case 'needs_input':return 'Needs input';
    case 'needs_approval':return 'Needs approval';
    case 'failed':return 'Failed';
    case 'outcome_unknown':return 'Outcome unknown';
    default:return 'Cancelled';
  }
}
function MetricRows({t,rows}:{t:(value:string)=>string;rows:{label:string;value:string}[]}){
  return <dl className="conversation-metric-list">{rows.map(row=>
    <div key={row.label} className="conversation-metric-row"><dt>{t(row.label)}</dt><dd>{row.value}</dd></div>)}
  </dl>;
}
/**
 * Bounded dashboard for the current project: aggregates only, no user content.
 * A failed or unverified read renders an honest notice, never a guessed number.
 */
function MetricsTab({t,locale,client,session}:{
  t:(value:string)=>string;locale:'en'|'zh-HK';client:LiveClient;session:SessionScope;
}){
  const [state,setState]=useState<{kind:'loading'}|{kind:'ready';metrics:TurnMetrics}|
    {kind:'failed';notice:string}>({kind:'loading'});
  useEffect(()=>{
    let active=true;
    void loadTurnMetrics(client,session,METRICS_WINDOW_DAYS)
      .then(metrics=>{if(active)setState({kind:'ready',metrics});})
      .catch((error:unknown)=>{
        if(!active||error instanceof LiveCancelled)return;
        setState({kind:'failed',notice:error instanceof MetricsLoadError?error.message:'Turn metrics are unavailable. Try again later.'});
      });
    return()=>{active=false;};
  },[client,session]);
  if(state.kind==='loading')return <p className="conversation-panel-empty" role="status">{t('Loading turn metrics…')}</p>;
  if(state.kind==='failed')return <p className="conversation-panel-empty" role="status">{t(state.notice)}</p>;
  const metrics=state.metrics;
  if(!hasTurns(metrics))return <div className="conversation-metrics">
    <p className="conversation-panel-note">{t('Last 7 days')}</p>
    <p className="conversation-panel-empty">{t('No turns in the last 7 days.')}</p>
  </div>;
  const latency=metrics.latency_ms,budget=metrics.budget;
  return <div className="conversation-metrics">
    <p className="conversation-panel-note">{t('Last 7 days')}</p>
    <section aria-label={t('Turn volume')}>
      <h4>{t('Turn volume')}</h4>
      <MetricRows t={t} rows={[{label:'Total turns',value:String(metrics.turns.total)},
        ...statusRows(metrics).filter(row=>row.count>0).map(row=>({label:statusLabel(row.status),value:String(row.count)}))]}/>
    </section>
    <section aria-label={t('Turn latency')}>
      <h4>{t('Turn latency')}</h4>
      <MetricRows t={t} rows={[
        {label:'Median',value:formatLatency(latency.p50,locale)},
        {label:'95th percentile',value:formatLatency(latency.p95,locale)},
        {label:'Slowest',value:formatLatency(latency.max,locale)},
        {label:'Turns measured',value:String(latency.samples)}]}/>
    </section>
    <section aria-label={t('Proposals')}>
      <h4>{t('Proposals')}</h4>
      <MetricRows t={t} rows={[
        {label:'Total proposals',value:String(metrics.proposals.total)},
        {label:'Approved',value:String(metrics.proposals.by_decision.approve??0)},
        {label:'Rejected',value:String(metrics.proposals.by_decision.reject??0)},
        {label:'Awaiting decision',value:String(metrics.proposals.awaiting_decision)},
        ...Object.entries(metrics.proposals.by_capability).map(([capability,count])=>
          ({label:capability,value:String(count)}))]}/>
    </section>
    <section aria-label={t('Budget')}>
      <h4>{t('Budget')}</h4>
      <MetricRows t={t} rows={[
        {label:'Priced proposals',value:String(budget.priced_proposals)},
        {label:'Price unavailable',value:String(budget.unknown_price_proposals)},
        {label:'No cost stated',value:String(budget.no_cost_proposals)},
        {label:'May incur provider charges',value:String(budget.may_incur_provider_charges)},
        ...budget.estimated.map(row=>({label:`${t('Estimated')} ${row.unit}`,
          value:formatMetricAmount(row.amount)}))]}/>
    </section>
    <section aria-label={t('Model availability')}>
      <h4>{t('Model availability')}</h4>
      <MetricRows t={t} rows={[{label:'Turns without a model answer',
        value:String(metrics.model.unavailable_turns)}]}/>
    </section>
    <section aria-label={t('Tool activity')}>
      <h4>{t('Tool activity')}</h4>
      <MetricRows t={t} rows={[{label:'Unknown outcomes',value:String(metrics.tool_activity.outcome_unknown)}]}/>
    </section>
  </div>;
}

/** Right contextual panel. It only renders when the discussion has content for it. */
export function ConversationPanel(props:Props){
  const {t,tab,tabs,onTab,results,runs,citations,selectedSources,proposals,entries,access,threadId,contextRevision,canEdit,onDecide,deciding,decisionFor,turnStatusFor,drive,onClose}=props;
  const activeIndex=Math.max(0,tabs.indexOf(tab));
  function onTabKeyDown(event:KeyboardEvent<HTMLDivElement>){
    const next=nextTabIndex(event.key,activeIndex,tabs.length);
    if(next===null)return;
    event.preventDefault();
    const nextTab=tabs[next];
    onTab(nextTab);
    // Focus follows selection; every tab button is already mounted.
    event.currentTarget.querySelector<HTMLButtonElement>(`#conversation-tab-${nextTab}`)?.focus();
  }
  return <aside className="conversation-panel" aria-label={t('Discussion context')}>
    <div className="conversation-panel-head">
      <div role="tablist" aria-label={t('Discussion context')} aria-orientation="horizontal" className="conversation-panel-tabs" onKeyDown={onTabKeyDown}>
        {tabs.map((item,index)=><button key={item} type="button" role="tab" id={`conversation-tab-${item}`} aria-selected={tab===item} aria-controls={`conversation-panel-${item}`} tabIndex={tabSequenceIndex(activeIndex,index)} onClick={()=>onTab(item)}><PanelLabel tab={item} t={t}/></button>)}
      </div>
      {onClose&&<button type="button" className="conversation-icon-button" onClick={onClose} aria-label={t('Close context panel')}><X size={17} aria-hidden="true"/></button>}
    </div>
    <div className="conversation-panel-body" role="tabpanel" id={`conversation-panel-${tab}`} aria-labelledby={`conversation-tab-${tab}`}>
      {tab==='results'&&<ResultsTab t={t} results={results} runs={runs} navigate={props.navigate}/>}
      {tab==='sources'&&<SourcesTab t={t} citations={citations} selectedSources={selectedSources} canEdit={canEdit} onToggleSource={props.onToggleSource} sourcesBusy={props.sourcesBusy} onRemoveDrive={props.onRemoveDrive} drive={drive} threadId={threadId} canViewOffer={props.canViewOffer} client={props.client} session={props.session} navigate={props.navigate} contextRevision={contextRevision}/>}
      {tab==='decisions'&&<DecisionsTab t={t} proposals={proposals} entries={entries} access={access} onDecide={onDecide} deciding={deciding} decisionFor={decisionFor} terminalFor={props.terminalFor} turnStatusFor={turnStatusFor}/>}
      {tab==='metrics'&&<MetricsTab t={t} locale={props.locale} client={props.client} session={props.session}/>}
    </div>
  </aside>;
}
