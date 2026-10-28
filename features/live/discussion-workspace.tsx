'use client';
import {useEffect,useLayoutEffect,useMemo,useRef,useState,useSyncExternalStore} from 'react';
import type {LiveClient} from '@/services/live/client';
import type {SessionScope} from '@/services/live/session';
import {DiscussionStore} from '@/services/live/discussions';
import {loadDiscussionContext,type ContextSection} from '@/services/live/discussion-context';
import {askBuyerOS,replyNotices} from '@/services/live/conversation-reply';
import {LiveCancelled} from '@/services/live/client';
import {conversationHomeEnabled,discussionForPath,templateForId} from './conversation-home';
import type {GroundedReply} from '@/services/live/discussion-citations';
import {ConversationResearch} from './conversation-research';
import {LiveDiscussion} from './discussion';
import {LiveUnavailable} from './unavailable';

// Scope-owned resources survive route remounts. Thread actions never trigger context GETs.
const stores=new WeakMap<SessionScope,Map<string,DiscussionStore>>();
const reads=new WeakMap<SessionScope,Map<string,Promise<ContextSection[]>>>();
function resources(session:SessionScope){
  if(!stores.has(session)){
    stores.set(session,new Map());reads.set(session,new Map());
    session.subscribeBeforeClear(()=>{stores.get(session)?.clear();reads.get(session)?.clear();});
  }
  return {stores:stores.get(session)!,reads:reads.get(session)!};
}
type Props={enabled:boolean;session:SessionScope;client:LiveClient;pathname:string;locale:'en'|'zh-HK';t:(value:string)=>string;navigate:(path:string)=>void;canViewOffer:boolean;canViewResults:boolean};
export function LiveConversation(props:Props){
  if(!conversationHomeEnabled(props.enabled?'true':undefined)||!discussionForPath(props.pathname,true))return null;
  const snapshot=props.session.getSnapshot();
  if(!snapshot.authenticated||!snapshot.scope.workspace||!snapshot.scope.project)return null;
  return <ScopedConversation key={snapshot.identity} {...props}/>;
}
function ScopedConversation({session,client,pathname,locale,t,navigate,canViewOffer,canViewResults}:Props){
  const identity=session.identity(),scope=session.current();
  const cache=resources(session),scopeKey=JSON.stringify([scope.actor,scope.workspace,scope.project]);
  const store=useMemo(()=>{
    const cached=cache.stores.get(scopeKey);if(cached)return cached;
    let storage:Storage|undefined;try{storage=window.localStorage;}catch{/* Notice comes from the store. */}
    const created=new DiscussionStore(true,{actor:scope.actor,workspace:scope.workspace!,project:scope.project!},storage);
    cache.stores.set(scopeKey,created);return created;
  },[cache.stores,scopeKey,scope.actor,scope.workspace,scope.project]);
  const snapshot=useSyncExternalStore(store.subscribe,store.getSnapshot,store.getSnapshot);
  const [value,setValue]=useState(''),[contextRead,setContext]=useState<{key:string;sections:ContextSection[]}|null>(null),[refresh,setRefresh]=useState(0);
  const [liveReply,setLiveReply]=useState<{threadId:string;selection:string;reply:GroundedReply}|null>(null);
  const [asking,setAsking]=useState(false),[replyState,setReplyState]=useState({key:'',notice:''});
  const request=useRef<AbortController|null>(null),askingRef=useRef(false);
  const focus=useRef<HTMLDivElement>(null),writing=useRef(false),mounted=useRef(true),route=discussionForPath(pathname,true)!;
  const thread=snapshot.threads.find(item=>item.id===route.id)??null;
  const selection=JSON.stringify(thread?.sources.map(row=>row.id)??[]);
  const latest=useRef({pathname,selection,canViewOffer});
  const replyKey=JSON.stringify([pathname,selection,canViewOffer]);
  const replyNotice=replyState.key===replyKey?replyState.notice:'';
  const localRoute=route.id.startsWith('local-');
  const readKey=JSON.stringify([identity,canViewOffer,canViewResults]);
  // A permission reduction hides old records during this render, before effects run.
  const context=contextRead?.key===readKey?contextRead.sections:null;
  useEffect(()=>{focus.current?.focus();},[pathname]);
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  useLayoutEffect(()=>{
    latest.current={pathname,selection,canViewOffer};
    return()=>{request.current?.abort();};
  },[pathname,selection,canViewOffer]);
  useEffect(()=>{
    let active=true;
    let read=cache.reads.get(readKey);
    if(!read){read=loadDiscussionContext(client,session,{enabled:true,canViewOffer,canViewResults,signal:session.controller().signal});cache.reads.set(readKey,read);}
    void read.then(sections=>{if(active&&session.isCurrent(identity))setContext({key:readKey,sections});}).catch(()=>{if(active&&session.isCurrent(identity))setContext({key:readKey,sections:[{title:'Sources',items:[],notice:'Project context could not be loaded. Try refreshing.'}]});});
    return()=>{active=false;};
  },[cache.reads,readKey,client,session,identity,canViewOffer,canViewResults,refresh]);
  const current=()=>mounted.current&&session.isCurrent(identity)&&session.getSnapshot().authenticated;
  async function write(action:()=>void){
    if(writing.current||!current())return;
    writing.current=true;
    try{await store.withLocalWrite(current,action);}finally{writing.current=false;}
  }
  function create(id:string){
    const input=value,template=templateForId(id),prompt=t(template.prompt);
    void write(()=>{
      const created=store.create(template.id,prompt);
      if(created){setValue(current=>current===input?'':current);navigate(`/app/discussions/${created.id}`);}
    });
  }
  function send(){
    if(!current()||askingRef.current||!value.trim())return;
    const input=value,clear=()=>setValue(current=>current===input?'':current);
    void write(()=>{
      if(thread){if(store.append(thread.id,input))clear();}
      else{const created=store.create('custom',input);if(created){clear();navigate(`/app/discussions/${created.id}`);}}
    });
  }
  async function ask(){
    if(!current()||askingRef.current||writing.current||!canViewOffer||!thread||!thread.sources.length||!value.trim())return;
    const input=value,sourceIds=thread.sources.map(row=>row.id),controller=new AbortController();
    request.current=controller;askingRef.current=true;setAsking(true);setReplyState({key:replyKey,notice:''});
    const stillCurrent=()=>current()&&!controller.signal.aborted&&latest.current.pathname===pathname&&
      latest.current.selection===selection&&latest.current.canViewOffer;
    try{
      const reply=await askBuyerOS(client,session,{enabled:true,question:input,sources:thread.sources,locale,signal:controller.signal});
      if(!stillCurrent())return;
      await store.withLocalWrite(stillCurrent,()=>{
        const saved=reply.fixture?store.appendReply(thread.id,input,reply,sourceIds):store.append(thread.id,input);
        if(saved){if(!reply.fixture)setLiveReply({threadId:thread.id,selection,reply});setValue(value=>value===input?'':value);}
      });
    }catch(error){
      if(stillCurrent()&&!(error instanceof LiveCancelled))setReplyState({key:replyKey,notice:error instanceof Error?error.message:replyNotices.unavailable});
    }finally{
      askingRef.current=false;
      if(current())setAsking(false);
      if(request.current===controller)request.current=null;
    }
  }
  return <div ref={focus} tabIndex={-1} aria-label={t('Discussion workspace')}>
    {localRoute&&!thread?<>{snapshot.notice&&<p role="status">{t(snapshot.notice)}</p>}<LiveUnavailable state="not_found" reason={t('This discussion is not saved for this account and project on this device.')}/></>:<LiveDiscussion
      t={t} locale={locale} thread={thread} threads={snapshot.threads} entryTemplate={['prepare-follow-up','review-buyers'].includes(route.id)?route.id:undefined}
      value={value} onChange={setValue} onSend={send} onTemplate={create} navigate={navigate} notice={snapshot.notice} context={context}
      research={thread&&canViewOffer?<ConversationResearch key={thread.id} client={client} session={session} store={store} thread={thread} t={t} navigate={navigate}/>:null}
      liveReply={canViewOffer&&liveReply?.threadId===thread?.id&&liveReply?.selection===selection?liveReply?.reply:undefined}
      onAsk={()=>void ask()} asking={asking} replyNotice={replyNotice} canAsk={canViewOffer}
      onSource={(source,selected)=>{if(thread)void write(()=>{store.select(thread.id,source,selected);});}}
      onRefresh={()=>{if(current()){setContext(null);cache.reads.delete(readKey);setRefresh(value=>value+1);}}}/>}
  </div>;
}
