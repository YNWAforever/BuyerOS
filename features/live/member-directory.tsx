'use client';
import {useEffect,useMemo,useRef,useState} from 'react';
import {useWorkspaceSession,useSessionSnapshot} from '@/features/providers/workspace-session';
import type {components} from '@/services/generated/buyeros-api';
import {createOperationClient} from '@/services/live/operations';
import {LiveCancelled,LiveError,describeLiveError} from '@/services/live/client';
type Member=components['schemas']['Membership'];
type Role=Member['roles'][number];
const roles:Role[]=['viewer','operator','reviewer','workspace_admin'];
const pageSize=20;

/** Only the admin directory exposes roles; owner lookup is a separate restricted projection. */
export function MemberDirectory({workspace,t}:{workspace:string;t:(value:string)=>string}){
 const {client,session}=useWorkspaceSession();const scope=useSessionSnapshot();
 const api=useMemo(()=>createOperationClient(client),[client]);
 const [loaded,setLoaded]=useState<{key:string;page:components['schemas']['MembershipPage']|null}>({key:'',page:null});
 const [readFailure,setReadFailure]=useState({key:'',error:''});
 const [search,setSearch]=useState(''),[q,setQ]=useState(''),[offset,setOffset]=useState(0),[refresh,setRefresh]=useState(0);
 const [error,setError]=useState(''),[status,setStatus]=useState(''),[reason,setReason]=useState('');
 const [pending,setPending]=useState(false),[uncertain,setUncertain]=useState(false);
 const readKey=JSON.stringify([scope.identity,q,offset,refresh]);
 const page=loaded.key===readKey?loaded.page:null;
 const loading=loaded.key!==readKey&&readFailure.key!==readKey;
 const visibleError=error||(readFailure.key===readKey?readFailure.error:'');
 const busy=useRef(false),sequence=useRef(0),lifetime=useRef(new AbortController());
 useEffect(()=>{const controller=new AbortController();lifetime.current=controller;return()=>controller.abort();},[]);
 useEffect(()=>{
  const own=new AbortController(),number=++sequence.current;
  const captured=session.captureWriteContext();
  const ctx={...captured,signal:AbortSignal.any([captured.signal,own.signal,lifetime.current.signal]),
   getToken:async()=>session.token()||'',isCurrent:()=>session.isCurrent(captured.identity)&&!own.signal.aborted&&number===sequence.current};
  void api.requestOperation('listMemberships',{path:{workspace_id:workspace},query:{offset,limit:pageSize,q}},ctx)
   .then(value=>{if(ctx.isCurrent()){setLoaded({key:readKey,page:value});setUncertain(false);setError('');}})
   .catch(e=>{if(ctx.isCurrent()&&!(e instanceof LiveCancelled))setReadFailure({key:readKey,error:describeLiveError(e)});});
  return()=>own.abort();
 },[api,session,workspace,scope.identity,q,offset,refresh,readKey]);
 async function change(member:Member,selected:Role[],active:boolean){
  if(busy.current||uncertain)return;
  if(reason.trim().length<3){setError('Enter a reason of at least three characters.');return;}
  const captured=session.captureWriteContext();
  const ctx={...captured,signal:AbortSignal.any([captured.signal,lifetime.current.signal]),getToken:async()=>session.token()||'',
   isCurrent:()=>session.isCurrent(captured.identity)&&!lifetime.current.signal.aborted};
  busy.current=true;setPending(true);setError('');setStatus('');
  try{
   const value=await api.requestOperation('updateMembership',{path:{workspace_id:workspace,membership_id:member.id},
    header:{'If-Match':`"${member.version}"`,'Idempotency-Key':crypto.randomUUID()},body:{roles:selected,active,reason:reason.trim()}},ctx);
   if(!ctx.isCurrent())return;
   setLoaded(current=>current.page?{...current,page:{...current.page,items:current.page.items.map(row=>row.id===value.id?value:row)}}:current);
   setStatus('Membership updated.');setReason('');
  }catch(e){
   if(ctx.isCurrent()&&!(e instanceof LiveCancelled)){
    if(!(e instanceof LiveError)||e.status<400||e.status>=500){
     setUncertain(true);setError('The membership result is unknown. Reload members to check the current version before making another change.');
    }else setError(e.code==='LAST_ADMIN'?'The last active administrator must remain.':describeLiveError(e));
   }
  }finally{busy.current=false;if(ctx.isCurrent())setPending(false);}
 }
 function searchMembers(){setError('');setOffset(0);setQ(search.trim());setRefresh(x=>x+1);setStatus('');}
 return <section aria-label={t('Member management')} style={{minWidth:0}}>
  <h3>{t('Member management')}</h3><p>{t('Only existing verified members can be changed. The last administrator cannot be removed.')}</p>
  <form onSubmit={e=>{e.preventDefault();searchMembers();}}>
   <label>{t('Search members')} <input aria-label={t('Search members')} maxLength={200} value={search} disabled={pending||uncertain} onChange={e=>setSearch(e.target.value)}/></label>
   <button disabled={pending||uncertain}>{t('Search')}</button>
  </form>
  <label>{t('Change reason')} <input aria-label={t('Change reason')} maxLength={2000} value={reason} disabled={pending||uncertain} onChange={e=>setReason(e.target.value)}/></label>
  {loading&&<p role="status">{t('Loading members…')}</p>}
  {page&&<><p aria-live="polite">{page.items.length?offset+1:0}–{page.items.length?offset+page.items.length:0} / {page.total}</p>
   {page.items.map(member=><MemberRow key={`${member.id}-${member.version}`} member={member} pending={pending||uncertain} t={t} onSave={change}/>)}
   <nav aria-label={t('Member pages')} className="inline">
    <button disabled={pending||uncertain||loading||offset===0} onClick={()=>setOffset(value=>Math.max(0,value-pageSize))}>{t('Previous members')}</button>
    <button disabled={pending||uncertain||loading||offset+pageSize>=page.total} onClick={()=>setOffset(value=>value+pageSize)}>{t('Next members')}</button>
   </nav>
  </>}
  {visibleError&&<><p role="alert">{t(visibleError)}</p><button disabled={pending} onClick={()=>{setError('');setRefresh(x=>x+1);}}>{t('Reload members')}</button></>}
  {status&&<p role="status">{t(status)}</p>}
 </section>;
}
function MemberRow({member,pending,onSave,t}:{member:Member;pending:boolean;onSave:(m:Member,roles:Role[],active:boolean)=>Promise<void>;t:(value:string)=>string}){
 const [selected,setSelected]=useState<Role[]>(member.roles),[active,setActive]=useState(member.active);
 const name=member.display_name===member.user_id?t('Staff member (name unavailable)'):member.display_name;
 return <div role="group" aria-label={`${t('Member')} ${name}`} style={{borderTop:'1px solid var(--border)',paddingBlock:12,minWidth:0}}>
  <strong>{name}</strong><details><summary>{t('Technical details')}</summary><code style={{overflowWrap:'anywhere'}}>{member.user_id}</code> · {member.id}</details>
  <fieldset aria-label={`${t('Roles')} ${name}`} disabled={pending} style={{minWidth:0}}><legend>{t('Roles')}</legend>
   {roles.map(role=><label key={role}>{t(role)} <input type="checkbox" checked={selected.includes(role)} onChange={e=>setSelected(current=>e.target.checked?[...current,role]:current.filter(value=>value!==role))}/></label>)}
  </fieldset>
  <label>{t('Active')} <input type="checkbox" disabled={pending} checked={active} onChange={e=>setActive(e.target.checked)}/></label>
  <button disabled={pending||selected.length===0||selected.length===member.roles.length&&selected.every(role=>member.roles.includes(role))&&active===member.active} onClick={()=>void onSave(member,selected,active)}>{t('Save member')}</button>
 </div>;
}
