'use client';
import {useEffect,useRef,useState} from 'react';
import {ConversationThreads,threadNotice,type ServerThread,type ServerSummary,type ThreadShare,type Member} from '@/services/live/conversation-threads';
import type {LocalThread} from '@/services/live/discussions';

export function WorkspaceBadge({thread,t}:{thread:Pick<ServerSummary,'access'|'shareCount'>;t:(text:string)=>string}){
  return <span className="pill gray">{thread.access==='owner'?(thread.shareCount?<>{t('Shared with')} {thread.shareCount}</>:t('Workspace · Private')):<>{t('Shared with you')} · {t(thread.access==='viewer'?'Viewer':'Editor')}</>}</span>;
}
type Copy={t:(text:string)=>string};
export function SaveWorkspace({api,thread,t,onRemove,navigate,onSaved}:{api:ConversationThreads;thread:LocalThread;onRemove:()=>void;navigate:(path:string)=>void;onSaved?:(thread:ServerThread)=>void}&Copy){
  const dialog=useRef<HTMLDialogElement>(null),trigger=useRef<HTMLButtonElement>(null),pending=useRef(false);
  const [busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[saved,setSaved]=useState<ServerThread|null>(null);
  const importSnapshot=useRef<LocalThread|null>(null);
  const mounted=useRef(true);useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  async function save(){
    if(pending.current)return;pending.current=true;setBusy(true);setNotice('');
    try{importSnapshot.current??=thread;const result=await api.import(importSnapshot.current,true);if(mounted.current){setSaved(result);onSaved?.(result);dialog.current?.close();trigger.current?.focus();}}
    catch(error){if(mounted.current)setNotice(threadNotice(error));}
    finally{pending.current=false;if(mounted.current)setBusy(false);}
  }
  return <section className="live-thread-actions" aria-label={t('Workspace save')}>
    {saved?<><p role="status">{t('Saved to this workspace · visible to you and people you share with')}</p><button type="button" onClick={()=>navigate(`/app/discussions/s/${saved.id}`)}>{t('Open workspace discussion')}</button><button type="button" onClick={onRemove}>{t('Remove local copy')}</button></>:<button type="button" ref={trigger} onClick={()=>dialog.current?.showModal()}>{t('Save to workspace')}</button>}
    <dialog ref={dialog} className="live-thread-dialog" aria-labelledby="save-workspace-title" onCancel={event=>{if(busy)event.preventDefault();}}>
      <h2 id="save-workspace-title">{t('Save to workspace')}</h2><p>{t('Save a private copy to this workspace? Only you can see it until you share it. Your device copy stays here.')}</p>
      <p>{t('Only notes, titles, template and generic source/run references are saved. AI replies are excluded. Do not enter private buyer details, draft bodies or document text.')}</p>
      <p role="status">{notice&&t(notice)}</p><button type="button" disabled={busy} onClick={()=>{dialog.current?.close();trigger.current?.focus();}}>{t('Cancel')}</button><button type="button" disabled={busy} onClick={()=>void save()}>{t('Confirm workspace save')}</button>
    </dialog>
  </section>;
}
export function ShareThread({api,thread,t,onChange,onError}:{api:ConversationThreads;thread:ServerThread;onChange:(thread:ServerThread)=>void;onError:(error:unknown)=>void}&Copy){
  const dialog=useRef<HTMLDialogElement>(null),trigger=useRef<HTMLButtonElement>(null),pending=useRef(false);
  const [shares,setShares]=useState<ThreadShare[]>([]),[members,setMembers]=useState<Member[]>([]),[query,setQuery]=useState(''),[role,setRole]=useState<'viewer'|'editor'>('viewer'),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');
  const mounted=useRef(true);useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  async function perform(action:()=>Promise<void>){if(pending.current)return;pending.current=true;setBusy(true);setNotice('');try{await action();}catch(error){if(mounted.current){setNotice(threadNotice(error));onError(error);}}finally{pending.current=false;if(mounted.current)setBusy(false);}}
  async function read(){const result=await api.request<{items:ThreadShare[];version:number}>(`/${thread.id}/shares`);if(mounted.current)setShares(result.items);}
  function open(){dialog.current?.showModal();void perform(read);}
  function search(){void perform(async()=>{const result=await api.request<{items:Member[]}>(`/${thread.id}/share-recipients?q=${encodeURIComponent(query)}&limit=25`);if(mounted.current)setMembers(result.items);});}
  function change(memberId:string,role?:'viewer'|'editor'){void perform(async()=>{
    const result=await api.request<ServerThread>(`/${thread.id}/shares/${memberId}`,role?'PUT':'DELETE',role?{role}:undefined,thread.version);
    if(mounted.current)onChange(result);await read();
  });}
  return <><button ref={trigger} type="button" onClick={open}>{t('Share discussion')}</button>
    <dialog ref={dialog} className="live-thread-dialog" aria-labelledby="share-thread-title" onCancel={()=>trigger.current?.focus()}>
      <h2 id="share-thread-title">{t('Share discussion')}</h2><p>{t('Only active members of this workspace can be added. Viewers can read; editors can add notes and references. Only you can rename, share or delete.')}</p>
      <form onSubmit={event=>{event.preventDefault();search();}}><label>{t('Find workspace member')}<input maxLength={80} value={query} onChange={event=>setQuery(event.target.value)}/></label><button type="submit" disabled={busy}>{t('Search members')}</button></form>
      <label>{t('Share role')}<select aria-label={t('Share role')} value={role} onChange={event=>setRole(event.target.value as 'viewer'|'editor')}><option value="viewer">{t('Viewer')}</option><option value="editor">{t('Editor')}</option></select></label>
      <ul>{members.map(member=><li key={member.member_id}><span>{member.display_name}</span><button type="button" disabled={busy} onClick={()=>change(member.member_id,role)}>{t('Share with member')}</button></li>)}</ul>
      <h3>{t('People with access')}</h3><ul>{shares.map(share=><li key={share.member_id}><span>{share.display_name} · {!share.active?t('Inactive'):t(share.role==='viewer'?'Viewer':'Editor')}</span>
        <button type="button" disabled={busy||!share.active} onClick={()=>change(share.member_id,share.role==='viewer'?'editor':'viewer')}>{t(share.role==='viewer'?'Make editor':'Make viewer')}</button><button type="button" disabled={busy} onClick={()=>change(share.member_id)}>{t('Revoke access')}</button></li>)}</ul>
      <p role="status">{notice&&t(notice)}</p><button type="button" onClick={()=>{dialog.current?.close();trigger.current?.focus();}}>{t('Close')}</button>
    </dialog>
  </>;
}
