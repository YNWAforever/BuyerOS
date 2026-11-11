'use client';
import {useCallback,useEffect,useLayoutEffect,useMemo,useRef,useState} from 'react';
import {Archive,Ellipsis,Menu,Pin,PanelRight} from 'lucide-react';
import type {LiveClient} from '@/services/live/client';
import {LiveCancelled,LiveError} from '@/services/live/client';
import type {UploadContext} from '@/services/live/document-upload';
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
import {type ChatThread,type ConversationTurn,type ProposalPart,type SelectedSource,type TurnCapability} from './types';import {buildTranscript,collectPanelData,companyFromEntries,latestToolActivity,mergeStreamedEntry,terminalProposals,type EphemeralReply} from './parts';
import {emptyTurnStream,reduceTurnEvent,streamIsLive,streamStep,type TurnStreamState} from './stream-events';
import {buildSkillCommands,type CatalogueSkill} from './skill-library';
import {fetchOutputPreview} from './output-preview';
import {attachmentBusy,attachmentPercent,classifyUploadFailure,createAttachmentGuard,nextAttachmentPercent,type AttachmentState,attachThreadSource} from './attachment';
import {useDataMode} from '@/features/providers/data-mode';
import {type DecisionChoice,type LocalDecision} from './approval';
import {ConversationThreadList,type ThreadListItem} from './thread-list';
import {applyStoredListPreference,persistThreadPreference,preferenceAllowed,shareControlVisible,visibleThreadRows} from './thread-management';
import {ConversationTranscript} from './transcript';
import {ConversationComposer,type ComposerAttachment,type ComposerChip} from './composer';
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
// A user's explicit "Guided setup" choice survives studio remounts and thread-route
// changes in the same scope. The secondary surface never opens on its own.
const guidedSetupChoice=new WeakMap<SessionScope,{identity:string;open:boolean}>();
// A thread-first response redirects immediately; the canonical studio resumes the
// live stream for that turn once the persisted thread has loaded.
const pendingStreams=new WeakMap<SessionScope,Map<string,string>>();
function stashPendingStream(session:SessionScope,threadId:string,turnId:string):void{
  let map=pendingStreams.get(session);
  if(!map){map=new Map();pendingStreams.set(session,map);}
  map.set(threadId,turnId);
}
function takePendingStream(session:SessionScope,threadId:string):string|null{
  const map=pendingStreams.get(session);
  if(!map)return null;
  const turnId=map.get(threadId)??null;
  map.delete(threadId);
  return turnId;
}
function guidedOpenFor(session:SessionScope):boolean{
  const row=guidedSetupChoice.get(session);
  return row?.identity===session.identity()?row.open:false;
}
function rememberGuidedOpen(session:SessionScope,open:boolean):void{
  guidedSetupChoice.set(session,{identity:session.identity(),open});
}
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
  const {apiBaseUrl}=useDataMode();
  const drafts=useMemo(()=>draftsFor(session,JSON.stringify([scope.actor,scope.workspace,scope.project]),{
    actor:scope.actor,workspace:scope.workspace??'',project:scope.project??''}),[session,scope.actor,scope.workspace,scope.project]);
  useLayoutEffect(()=>{if(!canViewOffer)api.forgetReply();},[api,canViewOffer]);

  const [list,setList]=useState<{items:ThreadListItem[];total:number;loading:boolean;notice:string}>({items:[],total:0,loading:true,notice:''});
  const [listRevision,setListRevision]=useState(0);
  const [preferenceBusy,setPreferenceBusy]=useState(false);
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
  const [catalogue,setCatalogue]=useState<ReadonlyArray<CatalogueSkill>>([]);
  const [projectName,setProjectName]=useState<string|null>(null);
  const [sending,setSending]=useState(false),sendRef=useRef(false);
  const [sendNotice,setSendNotice]=useState(''),[sendFailed,setSendFailed]=useState(false);
  const [stream,setStream]=useState<TurnStreamState|null>(null);
  const [reconnecting,setReconnecting]=useState(false);
  const [cancelling,setCancelling]=useState(false);
  const [reconciling,setReconciling]=useState(false);
  const [recoveredTurns,setRecoveredTurns]=useState<ReadonlySet<string>>(()=>new Set());
  const [attachment,setAttachment]=useState<AttachmentState>({phase:'idle'});
  const [contextRevision,setContextRevision]=useState(0);
  const streamAbort=useRef<AbortController|null>(null);
  const attachmentAbort=useRef<AbortController|null>(null);
  const attachGuard=useRef(createAttachmentGuard()).current;
  const threadIdRef=useRef<string|null>(null);
  const attachFileRef=useRef<File|null>(null);
  const attachDocumentRef=useRef<string|null>(null);
  threadIdRef.current=loaded?.chat.id??null;
  // The uploader is loaded lazily: the OFF discussion controller must never pull
  // ingest code (or its browser-only dependencies) into its module graph.
  const uploaderRef=useRef<ReturnType<typeof import('@/services/live/document-upload').createDocumentUpload>|null>(null);
  const [deciding,setDeciding]=useState(false),decidingRef=useRef(false);
  const [sourcesBusy,setSourcesBusy]=useState(false);
  const [panelPreference,setPanelPreference]=useState<boolean|null>(null);
  const [activeTab,setActiveTab]=useState<PanelTab|null>(null);
  const [mobileView,setMobileView]=useState<'conversation'|'threads'|'panel'>('conversation');
  const titleRef=useRef<HTMLHeadingElement>(null);
  const threadsTriggerRef=useRef<HTMLButtonElement>(null);
  const navThreadsRef=useRef<HTMLButtonElement>(null);
  const panelToggleRef=useRef<HTMLButtonElement>(null);
  const contextNavRef=useRef<HTMLButtonElement>(null);
  const threadsOpener=useRef<'header'|'nav'>('header');
  const panelOpener=useRef<'header'|'nav'>('header');
  const focusedThread=useRef<string|null>(null);
  const [title,setTitle]=useState('');
  const [guidedOpen,setGuidedOpen]=useState(()=>guidedOpenFor(session));
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
  },[api,archived,debouncedQuery,identity,session,listRevision]);
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
    // A route change or refetch owns the thread: stop any previous stream and drop
    // provisional entries so persisted data is the only source for the new view.
    streamAbort.current?.abort();streamAbort.current=null;
    setStream(null);setReconnecting(false);setRecoveredTurns(new Set());
    attachmentAbort.current?.abort();attachmentAbort.current=null;
    attachFileRef.current=null;attachDocumentRef.current=null;setAttachment({phase:'idle'});
    if(!targetId){setLoaded(null);setThreadState('new');setThreadNoticeText('');setTurns([]);setEphemeral([]);setDecisions({});return;}
    let active=true;
    setThreadState(previous=>previous==='ready'?'reloading':'loading');
    void api.get(targetId).then(row=>{
      if(!active||!session.isCurrent(identity))return;
      const chat=chatThread(row);
      if(!chat){setThreadState('unavailable');setThreadNoticeText(turnNotices.invalid);return;}
      setLoaded({raw:row,chat});setThreadState('ready');setThreadNoticeText('');
      setTurns([]);setEphemeral([]);setDecisions({});
      const pendingTurn=takePendingStream(session,row.id);
      if(pendingTurn)void beginStream({id:pendingTurn,status:'needs_input',parts:[],notices:[]},row.id);
    }).catch(error=>{
      if(!active||error instanceof LiveCancelled)return;
      const message=threadNotice(error);
      setThreadNoticeText(message);setThreadState(message===threadNotices.missing?'missing':'unavailable');
    });
    return()=>{active=false;};
    // eslint-disable-next-line react-hooks/exhaustive-deps -- beginStream resumes a one-shot stashed stream for the loaded thread.
  },[api,targetId,identity,session,reload]);
  useEffect(()=>{setTitle(loaded?.chat.title??'');},[loaded?.chat.id,loaded?.chat.title]);
  // Opening a discussion (row, deep link or linked company) moves focus to its
  // heading so the new context is announced once the thread is readable.
  useEffect(()=>{
    const id=loaded?.chat.id;
    if(!id||!targetId||id!==targetId||focusedThread.current===id)return;
    focusedThread.current=id;
    const frame=requestAnimationFrame(()=>titleRef.current?.focus({preventScroll:true}));
    return()=>cancelAnimationFrame(frame);
  },[loaded?.chat.id,targetId]);
  // Abort a live stream when the studio unmounts (route/scope change).
  useEffect(()=>()=>{
    streamAbort.current?.abort();streamAbort.current=null;
    attachmentAbort.current?.abort();attachmentAbort.current=null;
  },[]);

  useEffect(()=>{
    let active=true;
    void readProjectName(client,session).then(name=>{if(active&&session.isCurrent(identity))setProjectName(name);});
    return()=>{active=false;};
  },[client,session,identity]);
  useEffect(()=>{if(!canViewOffer)return;let active=true;
    void salesTasks(client,session).skills().then(page=>{
      if(active&&session.isCurrent(identity)&&Array.isArray(page.skills)){
        setSkillIds(new Set(page.skills.map(skill=>skill.id)));
        setCatalogue(page.skills.map(skill=>({id:skill.id,languages:skill.languages})));
      }
    }).catch(()=>{if(active){setSkillIds(null);setCatalogue([]);}});
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

  const persistedEntries=useMemo(()=>buildTranscript(loaded?.chat??null,turns,ephemeral),[loaded,turns,ephemeral]);
  // Live streamed parts render provisionally until the thread refetch supplies the
  // persisted parts for the same turn (persisted wins, no duplicate row).
  const entries=useMemo(()=>mergeStreamedEntry(persistedEntries,stream),[persistedEntries,stream]);
  const running=streamIsLive(stream);
  const latestTurn=turns.length?turns[turns.length-1]:null;
  // After reload the turn statuses are gone from the session; a persisted
  // outcome_unknown tool step still identifies the turn that can be checked.
  const persistedOutcomeTurnId=useMemo(()=>{
    for(let index=entries.length-1;index>=0;index-=1){
      const entry=entries[index];
      if(entry.role!=='assistant'||!entry.turnId)continue;
      return entry.parts.some(part=>part.kind==='tool_activity'&&part.state==='outcome_unknown')?entry.turnId:null;
    }
    return null;
  },[entries]);
  const recoverTurnId=(latestTurn?.status==='outcome_unknown'?latestTurn.id:persistedOutcomeTurnId)??null;
  const recoverableTurnId=recoverTurnId&&!recoveredTurns.has(recoverTurnId)?recoverTurnId:null;
  const outcomeTurn=!running&&recoverableTurnId?{id:recoverableTurnId}:null;
  const failedTurn=!running&&latestTurn?.status==='failed'?latestTurn:null;
  const panel=useMemo(()=>collectPanelData(loaded?.chat??null,entries),[loaded,entries]);
  const terminal=useMemo(()=>terminalProposals(entries),[entries]);
  const company=useMemo(()=>companyFromEntries(entries),[entries]);
  const companyLabel=loaded?.chat.buyerId?(company?.label??t('Linked company')):null;
  const chips=useMemo<ComposerChip[]>(()=>guidedTemplates.map(template=>{
    const candidate=chipSkills[template.id];
    return {key:template.id,label:t(template.title),prompt:t(template.prompt),skillId:candidate&&skillIds?.has(candidate)?candidate:null};
  }),[t,skillIds]);
  // Translation identity changes on every render; keep the command memo stable and
  // rebuild only when the catalogue, offered set or locale actually changes.
  const translateRef=useRef(t);
  translateRef.current=t;
  const commands=useMemo(()=>buildSkillCommands({skills:catalogue,offered:skillIds??new Set(),locale,
    translate:value=>translateRef.current(value)}),[catalogue,skillIds,locale]);
  const actions=useMemo<PartActions>(()=>({
    t,locale,navigate,access:loaded?.chat.access??'viewer',
    turnStatusFor:turnId=>turnId?turns.find(turn=>turn.id===turnId)?.status:undefined,
    decisionFor:proposalId=>decisions[proposalId],
    terminalFor:proposalId=>terminal.get(proposalId),
    toolFor:capabilityName=>latestToolActivity(entries,capabilityName),
    partsForTurn:turnId=>turnId?entries.filter(entry=>entry.turnId===turnId).flatMap(entry=>entry.parts):[],
    previewOutput:async(outputId,revision,signal)=>{
      const scope=session.current();
      if(!session.isCurrent(identity)||!scope.workspace||!scope.project||!session.token())
        return {kind:'error',error:'unavailable'};
      return fetchOutputPreview({baseUrl:apiBaseUrl,workspace:scope.workspace,project:scope.project,
        outputId,revision,token:session.token(),signal});
    },
    decide:(part,turnId,choice)=>{void decide(part,turnId,choice);},
    deciding,
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }),[t,locale,navigate,loaded?.chat.access,turns,decisions,terminal,entries,deciding,apiBaseUrl,identity,session]);

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
    const previousThreadId=loaded?.chat.id??null;
    if(response.thread.id!==previousThreadId){
      // Thread-first: canonicalise the route immediately so the persisted user row
      // is rendered from the saved thread; the canonical studio resumes the stream
      // for this turn after its thread read (see the thread-load effect).
      stashPendingStream(session,response.thread.id,response.turn.id);
      navigate(`/app/discussions/s/${response.thread.id}`);
      return true;
    }
    setLoaded({raw:rawOf(response.thread),chat:response.thread});
    setTurns(state=>state.some(turn=>turn.id===response.turn.id)?state:[...state,response.turn]);
    void beginStream(response.turn,response.thread.id);
    return true;
  }
  /**
   * Replay/live-tail the turn's events. On any unrecoverable failure the POST
   * response is already rendered and the thread is refetched: persisted data wins.
   */
  async function beginStream(turn:ConversationTurn,threadId:string):Promise<void>{
    const controller=new AbortController();
    streamAbort.current?.abort();streamAbort.current=controller;
    setReconnecting(false);setStream(emptyTurnStream(turn.id));
    const capabilityState=await turnsApi.streamCapability(false,apiBaseUrl);
    if(!current()||streamAbort.current!==controller)return;
    if(capabilityState!=='available'){setStream(null);return;}
    const outcome=await turnsApi.stream(turn.id,{signal:controller.signal,baseUrl:apiBaseUrl,
      onEvent:event=>{if(session.isCurrent(identity))setStream(prev=>prev?reduceTurnEvent(prev,event):prev);},
      onReconnect:()=>{if(session.isCurrent(identity))setReconnecting(true);},
    });
    if(!current()||streamAbort.current!==controller)return;
    streamAbort.current=null;setReconnecting(false);
    let persisted=false;
    try{
      const raw=await api.get(threadId);const chat=chatThread(raw);
      if(chat&&current()){
        setLoaded({raw,chat});
        persisted=chat.messages.some(message=>message.turnId===turn.id&&message.role==='assistant');
      }
    }catch{/* Keep streamed parts visible when the refetch also fails. */}
    if(!current()||streamAbort.current!==null)return;
    setStream(prev=>persisted?null:(prev?{...prev,final:true}:prev));
    if(outcome==='overflow')setSendNotice('The live update was too large and was stopped. The saved result is still shown.');
    else if(outcome==='unavailable'&&!persisted)setSendNotice('The live update was interrupted. Showing what was received.');
  }
  async function cancelTurn():Promise<void>{
    if(!loaded||!stream||stream.final||cancelling||loaded.chat.access==='viewer')return;
    setCancelling(true);setSendNotice('');
    try{
      const response=await turnsApi.cancel({threadId:loaded.chat.id,turnId:stream.turnId,expectedVersion:loaded.chat.version});
      if(!current())return;
      // The cancel response carries the terminal turn, so stop the live stream here.
      streamAbort.current?.abort();streamAbort.current=null;
      setReconnecting(false);
      setLoaded({raw:rawOf(response.thread),chat:response.thread});
      setTurns(state=>state.some(turn=>turn.id===response.turn.id)?state:[...state,response.turn]);
      setStream(prev=>prev?{...prev,status:response.turn.status,final:true}:prev);
    }catch(error){
      if(!(error instanceof LiveCancelled)&&current())setSendNotice(turnNotice(error));
    }finally{if(current())setCancelling(false);}
  }
  async function reconcileTurn():Promise<void>{
    if(!loaded||!outcomeTurn||reconciling||loaded.chat.access==='viewer')return;
    setReconciling(true);setSendNotice('');
    try{
      const response=await turnsApi.reconcile({threadId:loaded.chat.id,turnId:outcomeTurn.id,expectedVersion:loaded.chat.version});
      if(!current())return;
      setLoaded({raw:rawOf(response.thread),chat:response.thread});
      setTurns(state=>state.some(turn=>turn.id===response.turn.id)?state:[...state,response.turn]);
      setRecoveredTurns(state=>{const next=new Set(state);next.add(outcomeTurn.id);next.add(response.turn.id);return next;});
      setStream(null);setReconnecting(false);
      setSendNotice('The saved result was checked.');
    }catch(error){
      if(!(error instanceof LiveCancelled)&&current())setSendNotice(turnNotice(error));
    }finally{if(current())setReconciling(false);}
  }
  function startNewTurn():void{
    try{document.getElementById('conversation-message')?.focus();}catch{/* Focus is best-effort. */}
  }
  /** One attach attempt: reuse the existing uploader, then persist the source ref. */
  async function attachFile(file:File):Promise<void>{
    if(!loaded||loaded.chat.access==='viewer')return;
    if(!attachGuard.begin())return;
    try{
      if(!loaded||attachmentBusy(attachment))return;
      const scope=session.current();
      if(!scope.workspace||!scope.project||!scope.actor||!session.token()){
        setAttachment({phase:'failed',failure:'upload',message:'The attachment could not be uploaded. Try again.',retryable:true});
        return;
      }
      attachmentAbort.current?.abort();
      const controller=new AbortController();
      attachmentAbort.current=controller;
      const expectedThreadId=loaded.chat.id;
      attachFileRef.current=file;attachDocumentRef.current=null;
      setAttachment({phase:'uploading',percent:0});
      try{
        let workflow=uploaderRef.current;
        if(!workflow){
          const {createDocumentUpload}=await import('@/services/live/document-upload');
          let storage:Storage|undefined;
          try{if(typeof window!=='undefined')storage=window.sessionStorage;}catch{/* memory fallback stays available */}
          workflow=createDocumentUpload(client,storage);
          uploaderRef.current=workflow;
        }
        const signal=AbortSignal.any([controller.signal,session.controller().signal]);
        const uploadContext:UploadContext={actor:scope.actor,workspace:scope.workspace,project:scope.project,identity,
          token:session.token(),signal,isCurrent:()=>current()&&session.isCurrent(identity)};
        const document=await workflow.upload(file,uploadContext,
          progress=>{if(current()&&!controller.signal.aborted)setAttachment(state=>
            state.phase==='uploading'?{phase:'uploading',percent:nextAttachmentPercent(state.percent,progress.percent)}:state);});
        if(!current()||controller.signal.aborted)return;
        attachFileRef.current=null;attachDocumentRef.current=document.id;
        setAttachment({phase:'attaching'});
        await attachDocumentToThread(document.id,expectedThreadId,controller.signal);
      }catch(error){
        if(!current()||controller.signal.aborted||error instanceof LiveCancelled)return;
        attachmentAbort.current=null;
        const classification=classifyUploadFailure(error,t('The attachment could not be uploaded. Try again.'));
        setAttachment({phase:'failed',failure:classification.failure,message:classification.message,retryable:classification.retryable});
        attachFileRef.current=classification.retryable?file:null;
        attachDocumentRef.current=null;
      }
    }finally{
      attachGuard.end();
    }
  }
  /** Persist `document:<id>` on the thread, refetching once on a stale version. */
  async function attachDocumentToThread(documentId:string,expectedThreadId:string,signal:AbortSignal):Promise<void>{
    if(!loaded||threadIdRef.current!==expectedThreadId||signal.aborted)return;
    const thread=loaded.raw;
    const stillCurrent=()=>current()&&!signal.aborted&&threadIdRef.current===expectedThreadId;
    setAttachment({phase:'attaching'});
    try{
      if(!stillCurrent())throw new LiveCancelled('thread changed');
      const outcome=await attachThreadSource<ServerThread>({
        thread,documentId,
        save:(currentThread,sources)=>{if(!stillCurrent())throw new LiveCancelled('thread changed');return api.sources(currentThread,sources,signal);},
        refresh:async()=>{if(!stillCurrent())throw new LiveCancelled('thread changed');return api.get(expectedThreadId,signal);},
        isStale:error=>error instanceof LiveError&&(error.status===412||error.code==='STALE_REVISION'),
      });
      if(!current()||signal.aborted)return;
      if(threadIdRef.current!==expectedThreadId){setAttachment({phase:'idle'});return;}
      if(outcome.kind==='failed'){
        attachDocumentRef.current=documentId;
        setAttachment({phase:'failed',failure:'attach',message:'The attachment could not be added to this discussion. Try again.',retryable:true});
        return;
      }
      const chat=chatThread(outcome.thread);
      if(!chat){
        attachDocumentRef.current=documentId;
        setAttachment({phase:'failed',failure:'attach',message:'The attachment could not be added to this discussion. Try again.',retryable:true});
        return;
      }
      setLoaded({raw:outcome.thread,chat});
      attachFileRef.current=null;attachDocumentRef.current=null;
      setContextRevision(value=>value+1);
      setAttachment({phase:'attached'});
    }catch(error){
      if(error instanceof LiveCancelled||signal.aborted||!current()){
        if(current()&&threadIdRef.current===expectedThreadId)setAttachment({phase:'idle'});
        return;
      }
      if(threadIdRef.current!==expectedThreadId){setAttachment({phase:'idle'});return;}
      attachDocumentRef.current=documentId;
      setAttachment({phase:'failed',failure:'attach',message:'The attachment could not be added to this discussion. Try again.',retryable:true});
    }
  }
  function retryAttachment():void{
    if(attachment.phase!=='failed'||!attachment.retryable||attachGuard.locked)return;
    const documentId=attachDocumentRef.current;
    if(documentId&&loaded){
      if(!attachGuard.begin())return;
      attachmentAbort.current?.abort();
      const controller=new AbortController();
      attachmentAbort.current=controller;
      const expectedThreadId=loaded.chat.id;
      void attachDocumentToThread(documentId,expectedThreadId,controller.signal).finally(()=>attachGuard.end());
      return;
    }
    if(attachFileRef.current)void attachFile(attachFileRef.current);
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
  /**
   * Personal viewer preference: never optimistic. The row and menu update only
   * from the server's stored payload; a failure keeps state and shows the inline notice.
   */
  async function changePreference(change:'pin'|'archive'){
    if(!loaded||preferenceBusy||!preferenceAllowed(loaded.chat.access))return;
    const thread=loaded.chat;
    const currentPreferences={pinned:list.items.some(row=>row.id===thread.id&&row.pinned===true),
      archived:thread.archived===true};
    setPreferenceBusy(true);setThreadNoticeText('');
    try{
      const {stored}=await persistThreadPreference(api,thread.id,currentPreferences,change);
      if(!current())return;
      setLoaded(state=>state&&state.chat.id===thread.id?{raw:state.raw,
        chat:{...state.chat,archived:stored.archived}}:state);
      setList(state=>({...state,items:applyStoredListPreference(state.items,thread.id,stored),notice:''}));
      // Re-read the list so a later archived-view/search read agrees with the server.
      setListRevision(value=>value+1);
    }catch(error){
      if(!(error instanceof LiveCancelled)&&current())setThreadNoticeText(threadNotice(error));
    }finally{if(current())setPreferenceBusy(false);}
  }
  function focusOpenControl(kind:'threads'|'panel'){
    requestAnimationFrame(()=>{
      if(kind==='threads'){
        if(threadsOpener.current==='nav')navThreadsRef.current?.focus();
        else threadsTriggerRef.current?.focus();
      }else if(panelOpener.current==='nav')contextNavRef.current?.focus();
      else panelToggleRef.current?.focus();
    });
  }
  function closeMobileView(kind:'threads'|'panel'){
    setMobileView('conversation');
    focusOpenControl(kind);
  }
  useEffect(()=>{
    const onKey=(event:KeyboardEvent)=>{
      if(event.key!=='Escape')return;
      // A native modal dialog owns Escape and returns focus to its own trigger.
      if(document.querySelector('dialog[open]'))return;
      const menu=document.querySelector<HTMLDetailsElement>('details.conversation-menu[open]');
      if(menu){
        event.preventDefault();
        menu.open=false;
        menu.querySelector<HTMLElement>('summary')?.focus();
        return;
      }
      if(mobileView!=='conversation'){
        event.preventDefault();
        closeMobileView(mobileView);
      }
    };
    window.addEventListener('keydown',onKey);return()=>window.removeEventListener('keydown',onKey);
  });
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
  const step=running&&stream?streamStep(stream):'working';
  const statusLine=sending?t('Preparing a reply…'):sendNotice?t(sendNotice):threadNoticeText&&threadState==='ready'?t(threadNoticeText):'';
  // Archived comes from the loaded thread payload; the list row is a supplementary
  // fallback for the moment before the thread read resolves. Either hides attach.
  const archivedLoaded=loaded?.chat.archived===true||list.items.some(row=>row.id===loaded?.chat.id&&row.archived===true);
  const pinnedLoaded=loaded!==null&&list.items.some(row=>row.id===loaded.chat.id&&row.pinned===true);
  const shareAvailable=loaded!==null&&shareControlVisible(loaded.chat.access);
  const attachAvailable=!fresh&&loaded!==null&&loaded.chat.access!=='viewer'&&!archivedLoaded;
  const attachmentView:ComposerAttachment|null=attachAvailable?{
    visible:!attachmentBusy(attachment),
    busy:attachmentBusy(attachment),
    percent:attachmentPercent(attachment),
    label:attachment.phase==='attaching'?t('Adding attachment…'):t('Uploading attachment'),
    notice:attachment.phase==='failed'?attachment.message:'',
    retryable:attachment.phase==='failed'&&attachment.retryable,
    onFile:(file:File)=>void attachFile(file),
    onRetry:retryAttachment,
  }:null;
  return <div className="conversation-studio" data-mobile-view={mobileView} data-panel={panelOpen?'open':'closed'} aria-label={t('Discussion')} tabIndex={-1}>
    <button type="button" className="conversation-drawer-backdrop" aria-label={t('Close discussions')} tabIndex={mobileView==='threads'?0:-1} onClick={()=>closeMobileView('threads')}/>
    <ConversationThreadList t={t} locale={locale} items={visibleThreadRows(list.items,archived)} total={list.total} currentId={loaded?.chat.id??null} fresh={!targetId}
      notice={list.notice} loading={list.loading} query={query} archived={archived}
      onQuery={setQuery} onToggleArchived={()=>setArchived(value=>!value)} onNew={()=>navigate('/app/discussions/new')}
      onOpen={id=>navigate(`/app/discussions/s/${id}`)} onMore={list.items.length<list.total?()=>void moreThreads():undefined}
      onClose={mobileView==='threads'?()=>closeMobileView('threads'):undefined}/>
    <div className="conversation-main">
      <header className="conversation-head">
        <div className="conversation-head-title">
          <button type="button" ref={threadsTriggerRef} className="conversation-icon-button conversation-mobile-only" onClick={()=>{threadsOpener.current='header';setMobileView('threads');}} aria-label={t('Show discussions')}><Menu size={18} aria-hidden="true"/></button>
          <h2 ref={titleRef} tabIndex={-1}>{threadTitle}</h2>
          {loaded&&<WorkspaceBadge thread={loaded.raw} t={t}/>}
        </div>
        <div className="conversation-head-actions">
          {loaded&&<details className="conversation-menu"><summary aria-label={t('Discussion menu')}><Ellipsis size={18} aria-hidden="true"/><span className="conversation-sr">{t('Discussion menu')}</span></summary>
            <div className="conversation-menu-panel">
              <form onSubmit={event=>{event.preventDefault();void renameThread();}}><label>{t('Discussion title')}<input maxLength={80} value={title} onChange={event=>setTitle(event.target.value)}/></label><button type="submit" disabled={!title.trim()||title.trim()===loaded.chat.title}>{t('Rename discussion')}</button></form>
              <button type="button" aria-pressed={pinnedLoaded} disabled={preferenceBusy} onClick={()=>void changePreference('pin')}><Pin size={15} aria-hidden="true"/>{t(pinnedLoaded?'Unpin discussion':'Pin discussion')}</button>
              <button type="button" disabled={preferenceBusy} onClick={()=>void changePreference('archive')}><Archive size={15} aria-hidden="true"/>{t(archivedLoaded?'Restore discussion':'Archive discussion')}</button>
              {shareAvailable&&<ShareThread api={api} thread={loaded.raw} t={t} onChange={updated=>{void loadThread(updated,loaded.chat);}} onError={error=>setThreadNoticeText(threadNotice(error))}/>}
              <button type="button" onClick={()=>void removeThread()}>{t('Delete discussion')}</button>
            </div>
          </details>}
          <button type="button" ref={panelToggleRef} className="conversation-icon-button" onClick={()=>{panelOpener.current='header';setPanelPreference(!panelOpen);if(!panelOpen)setMobileView('panel');}} aria-label={t(panelOpen?'Hide context panel':'Show context panel')} aria-expanded={panelOpen} aria-controls="conversation-context-panel"><PanelRight size={18} aria-hidden="true"/></button>
        </div>
      </header>
      {threadNoticeText&&threadState==='ready'&&<p className="conversation-inline-notice" role="status">{t(threadNoticeText)}</p>}
      {threadState==='missing'
        ?<div className="conversation-load"><LiveUnavailable state="not_found" reason={t(threadNotices.missing)}/><button type="button" onClick={()=>navigate('/app/discussions/new')}>{t('New discussion')}</button></div>
        :threadState==='unavailable'
          ?<div className="conversation-load"><p role="alert">{t(threadNoticeText||threadNotices.unavailable)}</p><button type="button" onClick={()=>setReload(value=>value+1)}>{t('Retry')}</button></div>
          :<ConversationTranscript t={t} locale={locale} entries={entries} actions={actions} busy={sending} statusLine={statusLine} emptyTitle={t('What would you like to achieve for this project?')}/>}
      {running&&<div className="conversation-stream" role="status" aria-live="polite">
        <span className="conversation-stream-label">{reconnecting?t('Reconnecting…'):step==='approval'?t('Approval required'):step==='step'?t('Running a step…'):t('Working…')}</span>
        {loaded&&loaded.chat.access!=='viewer'&&<button type="button" className="conversation-cancel" disabled={cancelling} onClick={()=>void cancelTurn()}>{t(cancelling?'Cancelling…':'Cancel turn')}</button>}
      </div>}
      {outcomeTurn&&loaded&&loaded.chat.access!=='viewer'&&<div className="conversation-recovery" role="status">
        <p>{t('The outcome is unconfirmed. Check the saved result before trying again.')}</p>
        <button type="button" disabled={reconciling} onClick={()=>void reconcileTurn()}>{t(reconciling?'Checking result…':'Check result')}</button>
      </div>}      {failedTurn&&<div className="conversation-recovery" role="status">
        <p>{t('The turn failed. Nothing is retried automatically.')}</p>
        <button type="button" onClick={startNewTurn}>{t('Start a new turn')}</button>
      </div>}
      {awaitingHomeThread
        ?<div className="conversation-compose conversation-compose-pending" role="status" aria-busy="true">{t('Loading discussion…')}</div>
        :<ConversationComposer key={targetId??'new'} t={t} locale={locale} threadKey={targetId??'new'} drafts={drafts}
          // A saved thread stays read-only until its access is known: a viewer must never
          // get an enabled composer while the thread resolves, and a failed load stays inert.
          canWrite={threadId!==null?(loaded!==null&&loaded.chat.access!=='viewer'&&!running):(!loaded||loaded.chat.access!=='viewer')&&!running} sending={sending}
          projectName={projectName} companyName={companyLabel} chips={chips} commands={commands} capability={capability} capabilityNotice={capabilityNotice} onRetryCapability={()=>void probeCapability()}
          sendFailed={sendFailed} notice={sendNotice||urlNotice} attachment={attachmentView} onSend={send}/>}
      <details className="conversation-secondary" open={guidedOpen}
        onToggle={event=>{const open=event.currentTarget.open;setGuidedOpen(open);rememberGuidedOpen(session,open);}}><summary>{t('Guided setup')}</summary>
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
        threadId={loaded?.chat.id??null} threadVersion={loaded?.chat.version??0} contextRevision={contextRevision} canEdit={!!loaded&&loaded.chat.access!=='viewer'} canViewOffer={canViewOffer}
        client={client} session={session} navigate={navigate} onToggleSource={(source,selected)=>void toggleSource(source,selected)} sourcesBusy={sourcesBusy}
        onRemoveDrive={()=>void removeDriveSources()}
        onDecide={(part,turnId,choice)=>void decide(part,turnId,choice)} deciding={deciding} decisionFor={proposalId=>decisions[proposalId]} terminalFor={proposalId=>terminal.get(proposalId)}
        turnStatusFor={turnId=>turnId?turns.find(turn=>turn.id===turnId)?.status:undefined}
        drive={<DriveConnections key={`${identity}:${loaded?.chat.id??'none'}`} client={client} session={session} t={t} selected={loaded?.chat.sources??[]} readOnly={!loaded||loaded.chat.access==='viewer'} onSource={(source,selected)=>void toggleSource(source,selected)}/>}
        onClose={mobileView==='panel'?()=>closeMobileView('panel'):undefined}/>
    </div>}
    <nav className="conversation-mobile-views" aria-label={t('Views')}>
      <button type="button" aria-current={mobileView==='conversation'?'page':undefined} onClick={()=>setMobileView('conversation')}>{t('Conversation')}</button>
      <button type="button" ref={navThreadsRef} aria-current={mobileView==='threads'?'page':undefined} onClick={()=>{threadsOpener.current='nav';setMobileView('threads');}}>{t('Discussions')}</button>
      <button type="button" ref={contextNavRef} aria-current={mobileView==='panel'?'page':undefined} onClick={()=>{panelOpener.current='nav';setPanelPreference(true);setMobileView('panel');}}>{t('Context')}</button>
    </nav>
  </div>;
}
