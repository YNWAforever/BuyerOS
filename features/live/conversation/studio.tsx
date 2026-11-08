'use client';
import {useCallback,useEffect,useLayoutEffect,useMemo,useRef,useState} from 'react';
import {Ellipsis,Menu,PanelRight} from 'lucide-react';
import type {LiveClient} from '@/services/live/client';
import {LiveCancelled} from '@/services/live/client';
import type {SessionScope} from '@/services/live/session';
import {scopedThreadApi,threadNotice,threadNotices,type ServerThread} from '@/services/live/conversation-threads';
import {chatThread,scopedTurns,turnNotice,turnNotices} from '@/services/live/conversation-turn';
import {askBuyerOS,replyNotices} from '@/services/live/conversation-reply';
import {citationPath} from '@/services/live/discussion-citations';
import {salesTasks} from '@/services/live/sales-tasks';
import {DriveConnections} from '../conversation-connections';
import {GuidedSales} from '../sales-skills/workspace';
import {ShareThread,WorkspaceBadge} from '../discussion-sharing';
import {guidedTemplates} from '../conversation-home';
import {LiveUnavailable} from '../unavailable';
import {ConversationDrafts} from './draft';
import {type ChatThread,type ConversationTurn,type ProposalPart,type SelectedSource,type TurnCapability} from './types';import {buildTranscript,collectPanelData,companyFromEntries,latestToolActivity,terminalProposals,type EphemeralReply} from './parts';
import {type DecisionChoice,type LocalDecision} from './approval';
import {ConversationThreadList,type ThreadListItem} from './thread-list';
import {ConversationTranscript} from './transcript';
import {ConversationComposer,type ComposerChip} from './composer';
import {ConversationPanel,type PanelTab} from './context-panel';
import type {PartActions} from './inline-parts';

export type ConversationStudioProps={
  client:LiveClient;
  session:SessionScope;
  t:(value:string)=>string;
  locale:'en'|'zh-HK';
  navigate:(path:string)=>void;
  canViewOffer:boolean;
  canViewResults:boolean;
  /** Server thread id, or null for the project home / a new discussion. */
  threadId:string|null;
  /** True when the route explicitly asks for a new discussion. */
  fresh:boolean;
};
type LoadedThread={raw:ServerThread;chat:ChatThread};
type ThreadState='new'|'loading'|'ready'|'missing'|'unavailable'|'reloading';

const draftsBySession=new WeakMap<SessionScope,Map<string,ConversationDrafts>>();
const projectNames=new WeakMap<SessionScope,Map<string,Promise<string|null>>>();
function draftsFor(session:SessionScope,scopeKey:string,scope:{actor:string;workspace:string;project:string}){
  let map=draftsBySession.get(session);
  if(!map){map=new Map();draftsBySession.set(session,map);}
  let store=map.get(scopeKey);
  if(!store){let storage:Storage|undefined;try{storage=typeof window==='undefined'?undefined:window.localStorage;}catch{/* Tab-only drafts still work. */}
    store=new ConversationDrafts(scope,storage);map.set(scopeKey,store);}
  return store;
}
/** One membership-scoped project read names the composer identity; cached per scope. */
function readProjectName(client:LiveClient,session:SessionScope):Promise<string|null>{
  const scope=session.current(),key=JSON.stringify([scope.workspace,scope.project]);
  let map=projectNames.get(session);
  if(!map){map=new Map();projectNames.set(session,map);}
  const cached=map.get(key);
  if(cached)return cached;
  const read=client.request<unknown>({path:`/v1/workspaces/${encodeURIComponent(scope.workspace??'')}/projects/${encodeURIComponent(scope.project??'')}`,
    method:'GET',token:session.token(),scope:session.identity(),signal:session.controller().signal})
    .then(value=>{
      const name=typeof value==='object'&&value!==null&&'name' in value&&typeof (value as {name:unknown}).name==='string'?(value as {name:string}).name:null;
      return name&&name.length<=200?name:null;
    })
    .catch(()=>null);
  map.set(key,read);return read;
}
/** Only id/version and source references are consumed; guided surfaces never read messages. */
function rawOf(chat:ChatThread):ServerThread{
  const row={id:chat.id,version:chat.version,templateId:chat.templateId,title:chat.title,createdAt:chat.createdAt,
    updatedAt:chat.updatedAt,access:chat.access,shareCount:chat.shareCount,messages:[],sources:chat.sources,runs:chat.runs};
  return row as unknown as ServerThread;
}
function deriveTitle(text:string):string{
  return text.trim().replace(/\s+/g,' ').slice(0,80)||'New discussion';
}
function knownNotice(message:string):boolean{
  return [...Object.values(turnNotices),...Object.values(replyNotices)].some(value=>value===message);
}
/** Preset skills become chips only when the workspace registry actually offers them. */
const chipSkills:Record<string,string>={
  'first-project':'first-project','understand-documents':'understand-documents','research-market':'sales-research',
  'review-buyers':'review-buyers','check-company':'sales-qualify','prepare-follow-up':'sales-followup',
};
function useDebounced<T>(value:T,delay:number):T{
  const [debounced,setDebounced]=useState(value);
  useEffect(()=>{const timer=setTimeout(()=>setDebounced(value),delay);return()=>clearTimeout(timer);},[value,delay]);
  return debounced;
}

/**
 * Conversation-first project surface: thread list, continuous transcript with inline
 * parts, and a composer whose text survives navigation and reload. Turn responses are
 * rendered once; reloads rebuild the same transcript from persisted parts.
 */
export function ConversationStudio({client,session,t,locale,navigate,canViewOffer,threadId,fresh}:ConversationStudioProps){
  const identity=session.identity(),scope=session.current();
  const api=useMemo(()=>scopedThreadApi(client,session,identity),[client,session,identity]);
  const turnsApi=useMemo(()=>scopedTurns(client,session,true),[client,session]);
  const drafts=useMemo(()=>draftsFor(session,JSON.stringify([scope.actor,scope.workspace,scope.project]),{
    actor:scope.actor,workspace:scope.workspace??'',project:scope.project??''}),[session,scope.actor,scope.workspace,scope.project]);
  useLayoutEffect(()=>{if(!canViewOffer)api.forgetReply();},[api,canViewOffer]);

  const [list,setList]=useState<{items:ThreadListItem[];total:number;loading:boolean;notice:string}>({items:[],total:0,loading:true,notice:''});
  const [query,setQuery]=useState(''),debouncedQuery=useDebounced(query,250);
  const [archived,setArchived]=useState(false);
  const [autoId,setAutoId]=useState<string|null>(null),autoTried=useRef(false);
  const [reload,setReload]=useState(0);
  const [loaded,setLoaded]=useState<LoadedThread|null>(null);
  const [threadState,setThreadState]=useState<ThreadState>('new');
  const [threadNoticeText,setThreadNoticeText]=useState('');
  const [turns,setTurns]=useState<ConversationTurn[]>([]);
  const [ephemeral,setEphemeral]=useState<EphemeralReply[]>([]);
  const [decisions,setDecisions]=useState<Record<string,LocalDecision>>({});
  const [capability,setCapability]=useState<TurnCapability>('checking');
  const [capabilityNotice,setCapabilityNotice]=useState('');
  const [skillIds,setSkillIds]=useState<ReadonlySet<string>|null>(null);
  const [projectName,setProjectName]=useState<string|null>(null);
  const [sending,setSending]=useState(false),sendRef=useRef(false);
  const [sendNotice,setSendNotice]=useState(''),[sendFailed,setSendFailed]=useState(false);
  const [deciding,setDeciding]=useState(false),decidingRef=useRef(false);
  const [sourcesBusy,setSourcesBusy]=useState(false);
  const [panelPreference,setPanelPreference]=useState<boolean|null>(null);
  const [activeTab,setActiveTab]=useState<PanelTab|null>(null);
  const [mobileView,setMobileView]=useState<'conversation'|'threads'|'panel'>('conversation');
  const [title,setTitle]=useState('');
  // A fallback conversation (turn route absent) cannot carry the company link; the
  // entry point says so on the canonical discussion route.
  const [urlNotice]=useState(()=>{
    try{return new URLSearchParams(window.location.search).get('company')==='unlinked'?'The company could not be attached to this conversation.':'';}
    catch{return '';}
  });

  const targetId=threadId??(fresh?null:autoId);
  const current=()=>session.isCurrent(identity)&&!!session.token();

  // Recent discussions: the list is the only thread read until one is opened.
  useEffect(()=>{
    let active=true;
    setList(state=>({...state,loading:true}));
    const read=archived||debouncedQuery.trim()?api.search(debouncedQuery.trim(),archived,0):api.list(0);
    void read.then(page=>{
      if(!active||!session.isCurrent(identity))return;
      autoTried.current=false;
      setList({items:page.items as ThreadListItem[],total:page.total,loading:false,notice:''});
    }).catch(error=>{
      if(!active||error instanceof LiveCancelled)return;
      setList(state=>({...state,loading:false,notice:threadNotice(error)}));
    });
    return()=>{active=false;};
  },[api,archived,debouncedQuery,identity,session]);
  useEffect(()=>{autoTried.current=false;setAutoId(null);},[threadId,fresh]);
  useEffect(()=>{
    if(threadId||fresh||autoTried.current||list.loading)return;
    autoTried.current=true;
    const first=list.items.find(row=>!row.archived);
    if(first)setAutoId(first.id);
  },[threadId,fresh,list.loading,list.items]);
  async function moreThreads(){
    if(list.loading)return;
    try{
      const page=archived||debouncedQuery.trim()?await api.search(debouncedQuery.trim(),archived,list.items.length):await api.list(list.items.length);
      if(!session.isCurrent(identity))return;
      setList(state=>({...state,items:[...state.items,...page.items as ThreadListItem[]],total:page.total}));
    }catch(error){if(!(error instanceof LiveCancelled)&&session.isCurrent(identity))setList(state=>({...state,notice:threadNotice(error)}));}
  }

  // One thread read per target; a turn response never triggers a second read.
  useEffect(()=>{
    if(!targetId){setLoaded(null);setThreadState('new');setThreadNoticeText('');setTurns([]);setEphemeral([]);setDecisions({});return;}
    let active=true;
    setThreadState(previous=>previous==='ready'?'reloading':'loading');
    void api.get(targetId).then(row=>{
      if(!active||!session.isCurrent(identity))return;
      const chat=chatThread(row);
      if(!chat){setThreadState('unavailable');setThreadNoticeText(turnNotices.invalid);return;}
      setLoaded({raw:row,chat});setThreadState('ready');setThreadNoticeText('');
      setTurns([]);setEphemeral([]);setDecisions({});
    }).catch(error=>{
      if(!active||error instanceof LiveCancelled)return;
      const message=threadNotice(error);
      setThreadNoticeText(message);setThreadState(message===threadNotices.missing?'missing':'unavailable');
    });
    return()=>{active=false;};
  },[api,targetId,identity,session,reload]);
  useEffect(()=>{setTitle(loaded?.chat.title??'');},[loaded?.chat.id,loaded?.chat.title]);

  useEffect(()=>{
    let active=true;
    void readProjectName(client,session).then(name=>{if(active&&session.isCurrent(identity))setProjectName(name);});
    return()=>{active=false;};
  },[client,session,identity]);
  useEffect(()=>{if(!canViewOffer)return;let active=true;
    void salesTasks(client,session).skills().then(page=>{
      if(active&&session.isCurrent(identity)&&Array.isArray(page.skills))setSkillIds(new Set(page.skills.map(skill=>skill.id)));
    }).catch(()=>{if(active)setSkillIds(null);});
    return()=>{active=false;};
  },[client,session,canViewOffer,identity]);

  const probeCapability=useCallback(async()=>{
    setCapability('checking');setCapabilityNotice('');
    const state=await turnsApi.capability(true);
    if(!session.isCurrent(identity))return;
    setCapability(state);
    if(state==='unavailable')setCapabilityNotice('Conversation replies are unavailable right now. Your text is kept and can be saved as a note.');
  },[turnsApi,identity,session]);
  useEffect(()=>{void probeCapability();},[probeCapability]);

  const entries=useMemo(()=>buildTranscript(loaded?.chat??null,turns,ephemeral),[loaded,turns,ephemeral]);
  const panel=useMemo(()=>collectPanelData(loaded?.chat??null,entries),[loaded,entries]);
  const terminal=useMemo(()=>terminalProposals(entries),[entries]);
  const company=useMemo(()=>companyFromEntries(entries),[entries]);
  const companyLabel=loaded?.chat.buyerId?(company?.label??t('Linked company')):null;
  const chips=useMemo<ComposerChip[]>(()=>guidedTemplates.map(template=>{
    const candidate=chipSkills[template.id];
    return {key:template.id,label:t(template.title),prompt:t(template.prompt),skillId:candidate&&skillIds?.has(candidate)?candidate:null};
  }),[t,skillIds]);
  const actions=useMemo<PartActions>(()=>({
    t,navigate,access:loaded?.chat.access??'viewer',
    turnStatusFor:turnId=>turnId?turns.find(turn=>turn.id===turnId)?.status:undefined,
    decisionFor:proposalId=>decisions[proposalId],
    terminalFor:proposalId=>terminal.get(proposalId),
    toolFor:capabilityName=>latestToolActivity(entries,capabilityName),
    decide:(part,turnId,choice)=>{void decide(part,turnId,choice);},
    deciding,
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }),[t,navigate,loaded?.chat.access,turns,decisions,terminal,entries,deciding]);

  async function loadThread(updated:ServerThread,fallback:ChatThread|null){
    const chat=chatThread(updated)??(fallback?{...fallback,version:updated.version,title:updated.title,updatedAt:updated.updatedAt}:null);
    if(chat&&current())setLoaded({raw:updated,chat});
  }
  async function send(text:string,clientMessageId:string,skillId:string|null):Promise<boolean>{
    if(sendRef.current)return false;
    sendRef.current=true;setSending(true);setSendNotice('');setSendFailed(false);
    try{
      const state=capability==='checking'?await turnsApi.capability():capability;
      if(current()&&state!==capability)setCapability(state);
      if(state==='available')return await sendTurn(text,clientMessageId,skillId);
      return await sendFallback(text,clientMessageId);
    }catch(error){
      if(error instanceof LiveCancelled||!current())return false;
      const message=error instanceof Error&&knownNotice(error.message)?error.message:
        capability==='available'?turnNotice(error):threadNotice(error);
      setSendNotice(message);setSendFailed(capability==='available');
      return false;
    }finally{sendRef.current=false;if(current())setSending(false);}
  }
  async function sendTurn(text:string,clientMessageId:string,skillId:string|null):Promise<boolean>{
    const response=await turnsApi.submit({threadId:loaded?.chat.id??null,clientMessageId,
      expectedVersion:loaded?.chat.version??null,text,skillId,language:locale});
    if(!current())return false;
    setLoaded({raw:rawOf(response.thread),chat:response.thread});
    setTurns(state=>state.some(turn=>turn.id===response.turn.id)?state:[...state,response.turn]);
    if(response.thread.id!==loaded?.chat.id)navigate(`/app/discussions/s/${response.thread.id}`);
    return true;
  }
  async function sendFallback(text:string,clientMessageId:string):Promise<boolean>{
    if(!loaded){
      const created=await api.create(deriveTitle(text),text);
      if(!current())return false;
      navigate(`/app/discussions/s/${created.id}`);
      return true;
    }
    const {chat,raw}=loaded;
    if(canViewOffer&&chat.sources.length>=1&&chat.sources.length<=20){
      const reply=await askBuyerOS(client,session,{enabled:true,question:text,sources:chat.sources,locale,signal:session.controller().signal});
      if(!current())return false;
      setEphemeral(state=>[...state,{id:clientMessageId,text:reply.text,
        citations:reply.citations.map(ref=>({id:ref.id,label:ref.label,kind:'citation',href:citationPath(ref)}))}]);
      try{
        const updated=await api.append(raw,text);
        if(current())await loadThread(updated,chat);
      }catch(error){
        if(error instanceof LiveCancelled||!current())return false;
        setSendNotice('The live reply is shown here, but the note was not saved. Copy your text and retry.');
        return false;
      }
      setSendNotice('Live reply shown in this tab only. The discussion note is saved.');
      return true;
    }
    const updated=await api.append(raw,text);
    if(!current())return false;
    await loadThread(updated,chat);
    setSendNotice('Saved as a note. Select sources to ask BuyerOS.');
    return true;
  }
  async function decide(part:ProposalPart,turnId:string|null,choice:DecisionChoice){
    if(decidingRef.current||!loaded||!turnId)return;
    decidingRef.current=true;setDeciding(true);
    setDecisions(state=>({...state,[part.proposal_id]:{choice,state:'submitting'}}));
    try{
      const response=await turnsApi.decide({threadId:loaded.chat.id,turnId,proposalId:part.proposal_id,
        decision:choice,expectedVersion:loaded.chat.version});
      if(!current())return;
      setLoaded({raw:rawOf(response.thread),chat:response.thread});
      setTurns(state=>state.some(turn=>turn.id===response.turn.id)?state:[...state,response.turn]);
      setDecisions(state=>({...state,[part.proposal_id]:{choice,state:'accepted'}}));
    }catch(error){
      if(error instanceof LiveCancelled||!current())return;
      setDecisions(state=>({...state,[part.proposal_id]:{choice,state:'failed',notice:turnNotice(error)}}));
    }finally{decidingRef.current=false;if(current())setDeciding(false);}
  }
  async function toggleSource(source:SelectedSource,selected:boolean){
    if(!loaded||loaded.chat.access==='viewer'||sourcesBusy)return;
    const sources=selected?[...loaded.chat.sources.filter(row=>row.id!==source.id),{id:source.id,label:source.label}]:
      loaded.chat.sources.filter(row=>row.id!==source.id);
    if(sources.length>100)return;
    setSourcesBusy(true);
    try{
      const updated=await api.sources(loaded.raw,sources);
      if(current())await loadThread(updated,loaded.chat);
    }catch(error){
      if(!(error instanceof LiveCancelled)&&current())setThreadNoticeText(threadNotice(error));
    }finally{if(current())setSourcesBusy(false);}
  }
  async function removeDriveSources(){
    if(!loaded||loaded.chat.access==='viewer'||sourcesBusy)return;
    const sources=loaded.chat.sources.filter(source=>!source.id.startsWith('drive:'));
    if(sources.length===loaded.chat.sources.length)return;
    setSourcesBusy(true);
    try{
      const updated=await api.sources(loaded.raw,sources);
      if(current())await loadThread(updated,loaded.chat);
    }catch(error){if(!(error instanceof LiveCancelled)&&current())setThreadNoticeText(threadNotice(error));}
    finally{if(current())setSourcesBusy(false);}
  }
  async function renameThread(){
    if(!loaded||!title.trim()||title.length>80)return;
    try{
      const updated=await api.request<ServerThread>(`/${loaded.chat.id}`,'PATCH',{title:title.trim()},loaded.chat.version);
      if(current())await loadThread(updated,{...loaded.chat,title:title.trim()});
    }catch(error){if(!(error instanceof LiveCancelled)&&current())setThreadNoticeText(threadNotice(error));}
  }
  async function removeThread(){
    if(!loaded)return;
    if(!window.confirm(t('Permanently delete this workspace discussion and its shares?')))return;
    try{
      await api.request(`/${loaded.chat.id}`,'DELETE',undefined,loaded.chat.version);
      if(current())navigate('/app/discussions/new');
    }catch(error){if(!(error instanceof LiveCancelled)&&current())setThreadNoticeText(threadNotice(error));}
  }
  useEffect(()=>{
    const onKey=(event:KeyboardEvent)=>{if(event.key==='Escape'&&mobileView!=='conversation')setMobileView('conversation');};
    window.addEventListener('keydown',onKey);return()=>window.removeEventListener('keydown',onKey);
  },[mobileView]);
  useEffect(()=>{if(mobileView==='panel')setPanelPreference(true);},[mobileView]);

  const contentTabs:PanelTab[]=[];
  if(panel.results.length||loaded?.chat.runs.length)contentTabs.push('results');
  if(panel.selectedSources.length||panel.citations.length)contentTabs.push('sources');
  if(panel.proposals.length)contentTabs.push('decisions');
  const panelTabs=contentTabs.length?contentTabs:(canViewOffer&&loaded?['sources' as PanelTab]:['results' as PanelTab]);
  const tab:PanelTab=activeTab&&panelTabs.includes(activeTab)?activeTab:panelTabs[0];
  const panelOpen=panelPreference??contentTabs.length>0;
  // On the project home the newest thread is resolved after the list read. Keep the
  // composer unmounted until it resolves so a reload can never present an empty
  // composer in place of the restored draft.
  const awaitingHomeThread=!fresh&&threadId===null&&(list.loading||(autoId!==null&&threadState!=='ready'));
  const threadTitle=loaded?.chat.title??t('New discussion');
  const statusLine=sending?t('Preparing a reply…'):sendNotice?t(sendNotice):threadNoticeText&&threadState==='ready'?t(threadNoticeText):'';
  return <div className="conversation-studio" data-mobile-view={mobileView} data-panel={panelOpen?'open':'closed'} aria-label={t('Discussion')}>
    <button type="button" className="conversation-drawer-backdrop" aria-label={t('Close discussions')} tabIndex={mobileView==='threads'?0:-1} onClick={()=>setMobileView('conversation')}/>
    <ConversationThreadList t={t} locale={locale} items={list.items.filter(row=>archived||!row.archived)} total={list.total} currentId={loaded?.chat.id??null} fresh={!targetId}
      notice={list.notice} loading={list.loading} query={query} archived={archived}
      onQuery={setQuery} onToggleArchived={()=>setArchived(value=>!value)} onNew={()=>navigate('/app/discussions/new')}
      onOpen={id=>navigate(`/app/discussions/s/${id}`)} onMore={list.items.length<list.total?()=>void moreThreads():undefined}
      onClose={mobileView==='threads'?()=>setMobileView('conversation'):undefined}/>
    <div className="conversation-main">
      <header className="conversation-head">
        <div className="conversation-head-title">
          <button type="button" className="conversation-icon-button conversation-mobile-only" onClick={()=>setMobileView('threads')} aria-label={t('Show discussions')}><Menu size={18} aria-hidden="true"/></button>
          <h2>{threadTitle}</h2>
          {loaded&&<WorkspaceBadge thread={loaded.raw} t={t}/>}
        </div>
        <div className="conversation-head-actions">
          {loaded&&<details className="conversation-menu"><summary aria-label={t('Discussion menu')}><Ellipsis size={18} aria-hidden="true"/><span className="conversation-sr">{t('Discussion menu')}</span></summary>
            <form onSubmit={event=>{event.preventDefault();void renameThread();}}><label>{t('Discussion title')}<input maxLength={80} value={title} onChange={event=>setTitle(event.target.value)}/></label><button type="submit" disabled={!title.trim()||title.trim()===loaded.chat.title}>{t('Rename discussion')}</button></form>
            <ShareThread api={api} thread={loaded.raw} t={t} onChange={updated=>{void loadThread(updated,loaded.chat);}} onError={error=>setThreadNoticeText(threadNotice(error))}/>
            <button type="button" onClick={()=>void removeThread()}>{t('Delete discussion')}</button>
          </details>}
          <button type="button" className="conversation-icon-button" onClick={()=>{setPanelPreference(!panelOpen);if(!panelOpen)setMobileView('panel');}} aria-label={t(panelOpen?'Hide context panel':'Show context panel')} aria-expanded={panelOpen} aria-controls="conversation-context-panel"><PanelRight size={18} aria-hidden="true"/></button>
        </div>
      </header>
      {threadNoticeText&&threadState==='ready'&&<p className="conversation-inline-notice" role="status">{t(threadNoticeText)}</p>}
      {threadState==='missing'
        ?<div className="conversation-load"><LiveUnavailable state="not_found" reason={t(threadNotices.missing)}/><button type="button" onClick={()=>navigate('/app/discussions/new')}>{t('New discussion')}</button></div>
        :threadState==='unavailable'
          ?<div className="conversation-load"><p role="alert">{t(threadNoticeText||threadNotices.unavailable)}</p><button type="button" onClick={()=>setReload(value=>value+1)}>{t('Retry')}</button></div>
          :<ConversationTranscript t={t} locale={locale} entries={entries} actions={actions} busy={sending} statusLine={statusLine} emptyTitle={t('What would you like to achieve for this project?')}/>}
      {awaitingHomeThread
        ?<div className="conversation-compose conversation-compose-pending" role="status" aria-busy="true">{t('Loading discussion…')}</div>
        :<ConversationComposer key={targetId??'new'} t={t} threadKey={targetId??'new'} drafts={drafts} canWrite={!loaded||loaded.chat.access!=='viewer'} sending={sending}
          projectName={projectName} companyName={companyLabel} chips={chips} capability={capability} capabilityNotice={capabilityNotice} onRetryCapability={()=>void probeCapability()}
          sendFailed={sendFailed} notice={sendNotice||urlNotice} onSend={send}/>}
      <details className="conversation-secondary"><summary>{t('Guided setup')}</summary>
        {loaded
          ?<GuidedSales key={loaded.chat.id} client={client} session={session} t={t} locale={locale} navigate={navigate} thread={loaded.raw} onThread={updated=>{void loadThread(updated,loaded.chat);}}/>
          :threadId!==null
            ?<p className="conversation-secondary-loading" role="status">{t('Loading discussion…')}</p>
            :<GuidedSales key="new" client={client} session={session} t={t} locale={locale} navigate={navigate} onThread={row=>navigate(`/app/discussions/s/${row.id}`)}/>}
      </details>
    </div>
    {panelOpen&&<div className="conversation-panel-slot" id="conversation-context-panel">
      <ConversationPanel t={t} locale={locale} tab={tab} tabs={panelTabs} onTab={setActiveTab} results={panel.results} runs={loaded?.chat.runs??[]}
        citations={panel.citations} selectedSources={panel.selectedSources} proposals={panel.proposals} entries={entries} access={loaded?.chat.access??'viewer'}
        threadId={loaded?.chat.id??null} threadVersion={loaded?.chat.version??0} canEdit={!!loaded&&loaded.chat.access!=='viewer'} canViewOffer={canViewOffer}
        client={client} session={session} navigate={navigate} onToggleSource={(source,selected)=>void toggleSource(source,selected)} sourcesBusy={sourcesBusy}
        onRemoveDrive={()=>void removeDriveSources()}
        onDecide={(part,turnId,choice)=>void decide(part,turnId,choice)} deciding={deciding} decisionFor={proposalId=>decisions[proposalId]} terminalFor={proposalId=>terminal.get(proposalId)}
        turnStatusFor={turnId=>turnId?turns.find(turn=>turn.id===turnId)?.status:undefined}
        drive={<DriveConnections key={`${identity}:${loaded?.chat.id??'none'}`} client={client} session={session} t={t} selected={loaded?.chat.sources??[]} readOnly={!loaded||loaded.chat.access==='viewer'} onSource={(source,selected)=>void toggleSource(source,selected)}/>}
        onClose={mobileView==='panel'?()=>setMobileView('conversation'):undefined}/>
    </div>}
    <nav className="conversation-mobile-views" aria-label={t('Views')}>
      <button type="button" aria-current={mobileView==='conversation'?'page':undefined} onClick={()=>setMobileView('conversation')}>{t('Conversation')}</button>
      <button type="button" aria-current={mobileView==='threads'?'page':undefined} onClick={()=>setMobileView('threads')}>{t('Discussions')}</button>
      <button type="button" aria-current={mobileView==='panel'?'page':undefined} onClick={()=>{setPanelPreference(true);setMobileView('panel');}}>{t('Context')}</button>
    </nav>
  </div>;
}
