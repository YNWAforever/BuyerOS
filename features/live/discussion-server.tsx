'use client';
import {DriveConnections} from './conversation-connections';
import {useEffect,useLayoutEffect,useMemo,useRef,useState} from 'react';
import type {LiveClient} from '@/services/live/client';
import {LiveCancelled} from '@/services/live/client';
import type {SessionScope} from '@/services/live/session';
import {scopedThreadApi,threadNotice,threadNotices,type ServerThread} from '@/services/live/conversation-threads';
import {loadDiscussionContext,type ContextSection} from '@/services/live/discussion-context';
import {askBuyerOS,replyNotices} from '@/services/live/conversation-reply';
import type {GroundedReply} from '@/services/live/discussion-citations';
import type {RunReference} from '@/services/live/conversation-research';
import {LiveDiscussion} from './discussion';
import {ShareThread,WorkspaceBadge} from './discussion-sharing';
import {ConversationResearch} from './conversation-research';
import {LiveUnavailable} from './unavailable';

export function useThreadApi(client:LiveClient,session:SessionScope,canViewOffer:boolean){
  const identity=session.identity(),api=useMemo(()=>scopedThreadApi(client,session,identity),[client,session,identity]);
  useLayoutEffect(()=>{if(!canViewOffer)api.forgetReply();},[api,canViewOffer]);
  return api;
}
type Props={client:LiveClient;session:SessionScope;id:string;t:(text:string)=>string;locale:'en'|'zh-HK';navigate:(path:string)=>void;canViewOffer:boolean;canViewResults:boolean};
export function ServerConversation({client,session,id,t,locale,navigate,canViewOffer,canViewResults}:Props){
  const api=useThreadApi(client,session,canViewOffer),identity=session.identity();
  const [thread,setThread]=useState<ServerThread|null>(null),[notice,setNotice]=useState(''),[value,setValue]=useState(''),[contextRead,setContext]=useState<{key:string;sections:ContextSection[]}|null>(null),[busy,setBusy]=useState(false),[reply,setReply]=useState<GroundedReply|null>(null);
  const contextKey=JSON.stringify([identity,canViewOffer,canViewResults]);
  const context=contextRead?.key===contextKey?contextRead.sections:null;
  const [missing,setMissing]=useState(false),[stale,setStale]=useState(false),[title,setTitle]=useState(''),[unsavedRun,setUnsavedRun]=useState(false);
  const deleteDialog=useRef<HTMLDialogElement>(null),pending=useRef(false),mounted=useRef(true),focus=useRef<HTMLDivElement>(null),replyAbort=useRef<AbortController|null>(null);
  useEffect(()=>{mounted.current=true;focus.current?.focus();return()=>{mounted.current=false;replyAbort.current?.abort();};},[]);
  useLayoutEffect(()=>()=>{replyAbort.current?.abort();},[canViewOffer]);
  const current=()=>mounted.current&&session.isCurrent(identity)&&!!session.token();
  function failed(error:unknown){if(!current()||error instanceof LiveCancelled)return;const message=threadNotice(error);setNotice(message);if(message===threadNotices.stale)setStale(true);if(message===threadNotices.missing){api.forgetReply(id);setMissing(true);setThread(null);setReply(null);}}
  useEffect(()=>{
    let active=true;
    void api.get(id).then(row=>{if(active){if(row.access==='viewer')api.forgetReply(id);setThread(row);setTitle(row.title);}}).catch(error=>{if(active&&!(error instanceof LiveCancelled)){if(threadNotice(error)===threadNotices.missing)api.forgetReply(id);setNotice(threadNotice(error));setMissing(threadNotice(error)===threadNotices.missing);}});
    return()=>{active=false;};
  },[api,id]);
  async function refreshContext(){const sections=await loadDiscussionContext(client,session,{enabled:true,canViewOffer,canViewResults,signal:session.controller().signal});if(current())setContext({key:contextKey,sections});}
  useEffect(()=>{let active=true;void loadDiscussionContext(client,session,{enabled:true,canViewOffer,canViewResults,signal:session.controller().signal}).then(rows=>{if(active)setContext({key:contextKey,sections:rows});}).catch(()=>{if(active)setContext({key:contextKey,sections:[]});});return()=>{active=false;};},[client,session,contextKey,canViewOffer,canViewResults]);
  async function mutate(action:()=>Promise<ServerThread>){
    if(pending.current||stale||!current())return false;pending.current=true;setBusy(true);setNotice('');
    // Title/run writes do not consume an accepted answer whose note still needs saving.
    try{const result=await action();if(current()){setThread(result);setReply(null);}return current();}
    catch(error){failed(error);return false;}finally{pending.current=false;if(current())setBusy(false);}
  }
  async function send(){if(!thread||thread.access==='viewer'||!value.trim())return;const input=value;if(await mutate(()=>api.append(thread,input))){api.forgetReply(id,JSON.stringify([input,JSON.stringify(thread.sources),locale]));setValue(value=>value===input?'':value);}}
  async function saveRun(run:RunReference){
    if(!thread)return;
    // Admission has already succeeded. A reference-save failure must not reopen it.
    if(!await mutate(()=>api.run(thread,run))&&current())setUnsavedRun(true);
  }
  async function recheck(){const latest=await api.get(id);if(current())setThread(latest);if(latest.access==='viewer'){api.forgetReply(id);throw new Error(threadNotices.stale);}return latest;}
  async function ask(){
    if(!thread||thread.access==='viewer'||!canViewOffer||!value.trim()||pending.current||stale)return;
    const input=value,selection=JSON.stringify(thread.sources),fingerprint=JSON.stringify([input,selection,locale]),controller=new AbortController();replyAbort.current=controller;
    pending.current=true;setBusy(true);setNotice('');
    try{
      const latest=await recheck();if(latest.version!==thread.version)throw new Error(threadNotices.stale);
      const answer=api.acceptedReply(id,fingerprint)??await askBuyerOS(client,session,{enabled:true,question:input,sources:thread.sources,locale,signal:controller.signal});
      if(!current()||controller.signal.aborted)return;
      // A successful paid reply survives a failed note save. Retry only the note.
      api.retainReply(id,fingerprint,answer);
      const updated=await api.append(thread,input);if(!current()||controller.signal.aborted||selection!==JSON.stringify(updated.sources))return;
      api.forgetReply(id,fingerprint);setThread(updated);setReply(answer);setValue(value=>value===input?'':value);
    }catch(error){if(current()&&!(error instanceof LiveCancelled)){const message=error instanceof Error?error.message:'';if(message===threadNotices.stale){setStale(true);setNotice(message);}else if([...Object.values(threadNotices),...Object.values(replyNotices)].some(value=>value===message))setNotice(message);else failed(error);}}
    finally{pending.current=false;if(current())setBusy(false);}
  }
  const runSaveNotice=unsavedRun?<p role="status">{t('Research was accepted, but its reference could not be saved. Open Research runs.')}</p>:null;
  if(missing)return <>{runSaveNotice}<p role="status">{t(notice)}</p><LiveUnavailable state="not_found" reason={t(threadNotices.missing)}/></>;
  if(!thread)return <p role="status">{t(notice||'Loading workspace discussion…')}</p>;
  const editable=thread.access!=='viewer'&&!stale;
  return <div ref={focus} tabIndex={-1} aria-label={t('Discussion workspace')}>
    {runSaveNotice}
    <div className="live-thread-actions"><WorkspaceBadge thread={thread} t={t}/><button type="button" onClick={()=>window.location.reload()}>{t('Reload discussion')}</button>
      {thread.access==='owner'&&<><ShareThread api={api} thread={thread} t={t} onChange={setThread} onError={failed}/>
        <form onSubmit={event=>{event.preventDefault();void mutate(()=>api.request<ServerThread>(`/${thread.id}`,'PATCH',{title},thread.version));}}><label>{t('Discussion title')}<input maxLength={80} value={title} onChange={event=>setTitle(event.target.value)}/></label><button type="submit" disabled={busy||stale||!title.trim()}>{t('Rename discussion')}</button></form>
        <button type="button" disabled={busy||stale} onClick={()=>deleteDialog.current?.showModal()}>{t('Delete discussion')}</button>
        <dialog ref={deleteDialog} className="live-thread-dialog" aria-labelledby="delete-thread-title"><h2 id="delete-thread-title">{t('Delete discussion')}</h2><p>{t('Permanently delete this workspace discussion and its shares? Device copies are kept.')}</p><button type="button" onClick={()=>deleteDialog.current?.close()}>{t('Cancel')}</button><button type="button" disabled={busy||stale} onClick={()=>void (async()=>{if(await mutate(async()=>{await api.request(`/${thread.id}`,'DELETE',undefined,thread.version);return thread;}))navigate('/app');})()}>{t('Confirm delete')}</button></dialog>
      </>}
    </div>
    <LiveDiscussion thread={thread} threads={[]} t={t} locale={locale} value={value} onChange={setValue} onSend={()=>void send()} notice={notice} context={context} navigate={navigate} onTemplate={()=>{}} onRefresh={()=>void refreshContext()} onSource={(source,selected)=>{if(editable)void mutate(()=>api.sources(thread,selected?[...thread.sources.filter(row=>row.id!==source.id),source]:thread.sources.filter(row=>row.id!==source.id)));}}
      storageKind="workspace" readOnly={!editable} asking={busy} onAsk={()=>void ask()} canAsk={editable&&canViewOffer} liveReply={canViewOffer?reply??undefined:undefined}
      onClearDrive={()=>void mutate(()=>api.sources(thread,thread.sources.filter(source=>!source.id.startsWith('drive:'))))}
      connections={<DriveConnections key={identity+thread.id} client={client} session={session} t={t} selected={thread.sources} readOnly={!editable||busy} onSource={(source,selected)=>void mutate(()=>api.sources(thread,selected?[...thread.sources,source]:thread.sources.filter(row=>row.id!==source.id)))}/>}
      research={editable&&canViewOffer?<ConversationResearch key={thread.id} client={client} session={session} thread={thread} t={t} navigate={navigate} beforeResearch={async()=>{try{const latest=await recheck();if(latest.version!==thread.version)throw new Error(threadNotices.stale);}catch(error){failed(error);throw error;}}} saveRun={saveRun}/>:thread.runs?.length?<section aria-label={t('Research from this discussion')}>{thread.runs.map(run=><article key={run.id}><b>{t(run.label)}</b> <span>{t(run.status)}</span><button type="button" onClick={()=>navigate(`/app/discover/${encodeURIComponent(run.id)}`)}>{t('Open run · results, timeouts, cancel & retry')}</button></article>)}</section>:null}/>
  </div>;
}
