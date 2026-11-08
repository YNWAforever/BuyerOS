'use client';
import {useEffect,useRef,useState,type ReactNode} from 'react';
import {ChartNoAxesCombined,FileText,Link2,ShieldCheck,X} from 'lucide-react';
import type {LiveClient} from '@/services/live/client';
import type {SessionScope} from '@/services/live/session';
import {loadDiscussionContext,type ContextSection} from '@/services/live/discussion-context';
import type {ChatRunReference,CitationItem,ProposalPart,SelectedSource,ThreadAccess,TurnStatus} from './types';
import {approvalNoticeKey,decisionGate,followUpNoticeKey,proposalUiState,type DecisionChoice,type LocalDecision} from './approval';
import type {OutputLinkPart} from './types';
import type {PanelProposal} from './parts';
import {latestToolActivity,type TerminalProposal} from './parts';
import type {TranscriptEntry} from './parts';

export type PanelTab='results'|'sources'|'decisions';
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
  return <ShieldCheck size={14} aria-hidden="true"/>;
}
function PanelLabel({tab,t}:{tab:PanelTab;t:(value:string)=>string}){
  return <>{tabIcon(tab)}{t(tab==='results'?'Results':tab==='sources'?'Sources':'Decisions')}</>;
}
function SourcePicker({t,client,session,threadId,canViewOffer,selected,onToggleSource,busy,navigate}:{
  t:(value:string)=>string;client:LiveClient;session:SessionScope;threadId:string|null;canViewOffer:boolean;
  selected:SelectedSource[];onToggleSource:(source:SelectedSource,selected:boolean)=>void;busy:boolean;navigate:(path:string)=>void;
}){
  const [sections,setSections]=useState<ContextSection[]|null>(null),[notice,setNotice]=useState('');
  const read=useRef<string|null>(null);
  useEffect(()=>{
    if(!canViewOffer||!threadId)return;
    const key=`${session.identity()}:${threadId}`;
    if(read.current===key)return;
    read.current=key;let active=true;
    void loadDiscussionContext(client,session,{enabled:true,canViewOffer,canViewResults:false,signal:session.controller().signal})
      .then(rows=>{if(active)setSections(rows);}).catch(()=>{if(active)setNotice('Project context is unavailable. Try again later.');});
    return()=>{active=false;};
  },[client,session,canViewOffer,threadId]);
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
function SourcesTab({t,citations,selectedSources,canEdit,onToggleSource,sourcesBusy,onRemoveDrive,drive,threadId,canViewOffer,client,session,navigate}:{
  t:(value:string)=>string;citations:CitationItem[];selectedSources:SelectedSource[];canEdit:boolean;
  onToggleSource:(source:SelectedSource,selected:boolean)=>void;sourcesBusy:boolean;onRemoveDrive:()=>void;drive:ReactNode;threadId:string|null;
  canViewOffer:boolean;client:LiveClient;session:SessionScope;navigate:(path:string)=>void;
}){
  return <div className="conversation-sources">
    {citations.length>0&&<><h4>{t('Cited sources')}</h4><ul className="conversation-citations" aria-label={t('Cited sources')}>{citations.map(item=><li key={item.id}>{item.href?<button type="button" onClick={()=>navigate(item.href!)}><Link2 size={13} aria-hidden="true"/>{t(item.label)}</button>:<span className="pill gray">{t(item.label)}</span>}</li>)}</ul></>}
    <h4>{t('Selected sources')} ({selectedSources.length})</h4>
    {selectedSources.length?<ul className="conversation-selected-sources">{selectedSources.map(source=><li key={source.id}><span>{t(source.label)}</span>{canEdit&&<button type="button" disabled={sourcesBusy} onClick={()=>onToggleSource(source,false)}>{t('Remove')}</button>}</li>)}</ul>:<p className="conversation-panel-empty">{t('No sources selected.')}</p>}
    {canEdit&&selectedSources.some(source=>source.id.startsWith('drive:'))&&<button type="button" disabled={sourcesBusy} onClick={onRemoveDrive}>{t('Remove unavailable Google Drive selections')}</button>}
    <SourcePicker t={t} client={client} session={session} threadId={threadId} canViewOffer={canViewOffer} selected={selectedSources} onToggleSource={onToggleSource} busy={sourcesBusy} navigate={navigate}/>
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
/** Right contextual panel. It only renders when the discussion has content for it. */
export function ConversationPanel(props:Props){
  const {t,tab,tabs,onTab,results,runs,citations,selectedSources,proposals,entries,access,threadId,canEdit,onDecide,deciding,decisionFor,turnStatusFor,drive,onClose}=props;
  return <aside className="conversation-panel" aria-label={t('Discussion context')}>
    <div className="conversation-panel-head">
      <div role="tablist" aria-label={t('Discussion context')} className="conversation-panel-tabs">
        {tabs.map(item=><button key={item} type="button" role="tab" id={`conversation-tab-${item}`} aria-selected={tab===item} aria-controls={`conversation-panel-${item}`} onClick={()=>onTab(item)}><PanelLabel tab={item} t={t}/></button>)}
      </div>
      {onClose&&<button type="button" className="conversation-icon-button" onClick={onClose} aria-label={t('Close context panel')}><X size={17} aria-hidden="true"/></button>}
    </div>
    <div className="conversation-panel-body" role="tabpanel" id={`conversation-panel-${tab}`} aria-labelledby={`conversation-tab-${tab}`}>
      {tab==='results'&&<ResultsTab t={t} results={results} runs={runs} navigate={props.navigate}/>}
      {tab==='sources'&&<SourcesTab t={t} citations={citations} selectedSources={selectedSources} canEdit={canEdit} onToggleSource={props.onToggleSource} sourcesBusy={props.sourcesBusy} onRemoveDrive={props.onRemoveDrive} drive={drive} threadId={threadId} canViewOffer={props.canViewOffer} client={props.client} session={props.session} navigate={props.navigate}/>}
      {tab==='decisions'&&<DecisionsTab t={t} proposals={proposals} entries={entries} access={access} onDecide={onDecide} deciding={deciding} decisionFor={decisionFor} terminalFor={props.terminalFor} turnStatusFor={turnStatusFor}/>}
    </div>
  </aside>;
}
