'use client';
import {useEffect,useMemo,useRef,useState,useSyncExternalStore} from 'react';
import type {LiveClient} from '@/services/live/client';
import type {SessionScope} from '@/services/live/session';
import {DiscussionStore} from '@/services/live/discussions';
import {loadDiscussionContext,type ContextSection} from '@/services/live/discussion-context';
import {conversationHomeEnabled,discussionForPath,templateForId} from './conversation-home';
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
  const focus=useRef<HTMLDivElement>(null),route=discussionForPath(pathname,true)!;
  const thread=snapshot.threads.find(item=>item.id===route.id)??null;
  const localRoute=route.id.startsWith('local-');
  const readKey=JSON.stringify([identity,canViewOffer,canViewResults]);
  // A permission reduction hides old records during this render, before effects run.
  const context=contextRead?.key===readKey?contextRead.sections:null;
  useEffect(()=>{focus.current?.focus();},[pathname]);
  useEffect(()=>{
    let active=true;
    let read=cache.reads.get(readKey);
    if(!read){read=loadDiscussionContext(client,session,{enabled:true,canViewOffer,canViewResults,signal:session.controller().signal});cache.reads.set(readKey,read);}
    void read.then(sections=>{if(active&&session.isCurrent(identity))setContext({key:readKey,sections});}).catch(()=>{if(active&&session.isCurrent(identity))setContext({key:readKey,sections:[{title:'Sources',items:[],notice:'Project context could not be loaded. Try refreshing.'}]});});
    return()=>{active=false;};
  },[cache.reads,readKey,client,session,identity,canViewOffer,canViewResults,refresh]);
  const current=()=>session.isCurrent(identity)&&session.getSnapshot().authenticated;
  function create(id:string){
    if(!current())return;
    const template=templateForId(id),created=store.create(template.id,t(template.prompt));
    if(created){setValue('');navigate(`/app/discussions/${created.id}`);}
  }
  function send(){
    if(!current()||!value.trim())return;
    if(thread){if(store.append(thread.id,value))setValue('');}
    else{const created=store.create('custom',value);if(created){setValue('');navigate(`/app/discussions/${created.id}`);}}
  }
  return <div ref={focus} tabIndex={-1} aria-label={t('Discussion workspace')}>
    {localRoute&&!thread?<>{snapshot.notice&&<p role="status">{t(snapshot.notice)}</p>}<LiveUnavailable state="not_found" reason={t('This discussion is not saved for this account and project on this device.')}/></>:<LiveDiscussion
      t={t} locale={locale} thread={thread} threads={snapshot.threads} entryTemplate={['prepare-follow-up','review-buyers'].includes(route.id)?route.id:undefined}
      value={value} onChange={setValue} onSend={send} onTemplate={create} navigate={navigate} notice={snapshot.notice} context={context}
      onSource={(source,selected)=>{if(thread&&current())store.select(thread.id,source,selected);}}
      onRefresh={()=>{if(current()){setContext(null);cache.reads.delete(readKey);setRefresh(value=>value+1);}}}/>}
  </div>;
}
