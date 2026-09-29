'use client';
import {useEffect,useState} from 'react';
import {useWorkspaceSession,useSessionSnapshot} from '@/features/providers/workspace-session';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
import {BudgetSettings} from './budgets';

type Preference={locale:'en'|'zh-HK';default_markets:string[];version:number};
type Membership={id:string;user_id:string;roles:string[];active:boolean;version:number};
type Page<T>={items:T[];offset:number;limit:number;total:number};
const roles=['viewer','operator','reviewer','workspace_admin'];

export function LiveSettings({workspace,locale,isAdmin,onLocale,onVersion,currentVersion,canViewBudget,t}:{workspace:string;locale:'en'|'zh-HK';isAdmin:boolean;onLocale:(value:'en'|'zh-HK')=>void;onVersion:(value:number)=>void;currentVersion:number;canViewBudget:boolean;t:(value:string)=>string}){
  const {session,client}=useWorkspaceSession();
  const scope=useSessionSnapshot();
  const [pref,setPref]=useState<Preference|null>(null),[markets,setMarkets]=useState('');
  const [members,setMembers]=useState<Membership[]>([]),[error,setError]=useState(''),[status,setStatus]=useState('');
  const [reason,setReason]=useState(''),[pending,setPending]=useState(false);
  useEffect(()=>{
    const own=new AbortController(),identity=session.identity(),token=session.token();
    if(!token)return;
    const signal=AbortSignal.any([own.signal,session.controller().signal]);
    void client.request<Preference>({path:`/v1/workspaces/${workspace}/preferences`,token,scope:identity,signal}).then(value=>{
      if(!session.isCurrent(identity)||own.signal.aborted)return;
      setPref(value);setMarkets(value.default_markets.join(', '));onLocale(value.locale);
    }).catch(e=>{if(!(e instanceof LiveCancelled)&&!own.signal.aborted)setError(describeLiveError(e));});
    if(isAdmin)void client.request<Page<Membership>>({path:`/v1/workspaces/${workspace}/memberships?offset=0&limit=100`,token,scope:identity,signal}).then(value=>{
      if(session.isCurrent(identity)&&!own.signal.aborted)setMembers(value.items);
    }).catch(e=>{if(!(e instanceof LiveCancelled)&&!own.signal.aborted)setError(describeLiveError(e));});
    return()=>own.abort();
  },[client,session,workspace,isAdmin,onLocale,scope.identity]);
  async function saveMarkets(){
    if(!pref||pending)return;
    const values=markets.split(',').map(x=>x.trim().toUpperCase()).filter(Boolean);
    if(values.length>20||values.some(x=>! /^[A-Z]{2}$/.test(x))||new Set(values).size!==values.length){setError('Use distinct two-letter market codes.');return;}
    const identity=session.identity(),token=session.token();if(!token)return;
    setPending(true);setError('');setStatus('');
    try{
      const value=await client.request<Preference>({path:`/v1/workspaces/${workspace}/preferences`,method:'PATCH',token,scope:identity,
        body:{default_markets:values},ifMatch:`"${Math.max(pref.version,currentVersion)}"`,idempotencyKey:crypto.randomUUID()});
      if(!session.isCurrent(identity))return;setPref(value);onVersion(value.version);setStatus('Preferences saved.');
    }catch(e){if(!(e instanceof LiveCancelled))setError(describeLiveError(e));}finally{setPending(false);}
  }
  async function changeMember(member:Membership,memberRoles:string[],active:boolean){
    if(pending||reason.trim().length<3){setError('Enter a reason of at least three characters.');return;}
    const identity=session.identity(),token=session.token();if(!token)return;
    setPending(true);setError('');setStatus('');
    try{
      const value=await client.request<Membership>({path:`/v1/workspaces/${workspace}/memberships/${member.id}`,method:'PATCH',token,scope:identity,
        body:{roles:memberRoles,active,reason:reason.trim()},ifMatch:`"${member.version}"`,idempotencyKey:crypto.randomUUID()});
      if(!session.isCurrent(identity))return;setMembers(items=>items.map(item=>item.id===value.id?value:item));setStatus('Membership updated.');setReason('');
    }catch(e){if(!(e instanceof LiveCancelled))setError(describeLiveError(e));}finally{setPending(false);}
  }
  return <section className="panel" aria-label={t('Workspace settings')}>
    <h2>{t('Workspace settings')}</h2>
    <p>{t('Preferences are saved for this member and workspace. Research is unavailable until a verified provider is activated.')}</p>
    <label>{t('Language')} <output>{locale==='zh-HK'?'繁體中文':'English'}</output></label>
    <label>{t('Default markets')} <input aria-label={t('Default markets')} value={markets} onChange={e=>setMarkets(e.target.value)} placeholder="HK, US"/></label>
    <button disabled={!pref||pending} onClick={()=>void saveMarkets()}>{t('Save preferences')}</button>
    <p className="muted">{t('Research provider')} · {t('Not connected')}</p>
    {canViewBudget&&<BudgetSettings workspace={workspace} isAdmin={isAdmin} t={t}/>}
    {isAdmin&&<section aria-label={t('Member management')}><h3>{t('Member management')}</h3>
      <p>{t('Only existing verified members can be changed. The last administrator cannot be removed.')}</p>
      <label>{t('Change reason')} <input aria-label={t('Change reason')} value={reason} onChange={e=>setReason(e.target.value)}/></label>
      {members.map(member=><MemberRow key={`${member.id}-${member.version}`} member={member} pending={pending} t={t} onSave={changeMember}/>)}
    </section>}
    {error&&<p role="alert">{t(error)}</p>}{status&&<p role="status">{t(status)}</p>}
  </section>;
}
function MemberRow({member,pending,onSave,t}:{member:Membership;pending:boolean;onSave:(m:Membership,roles:string[],active:boolean)=>Promise<void>;t:(value:string)=>string}){
  const [selectedRoles,setSelectedRoles]=useState<string[]>(member.roles),[active,setActive]=useState(member.active);
  return <div className="inline" style={{flexWrap:'wrap'}}><code>{member.user_id.slice(-8)}</code>
    <fieldset aria-label={`${t('Roles')} ${member.user_id.slice(-8)}`}><legend>{t('Roles')}</legend>{roles.map(item=><label key={item}>{t(item)} <input type="checkbox" checked={selectedRoles.includes(item)} onChange={e=>setSelectedRoles(current=>e.target.checked?[...current,item]:current.filter(value=>value!==item))}/></label>)}</fieldset>
    <label>{t('Active')} <input type="checkbox" checked={active} onChange={e=>setActive(e.target.checked)}/></label>
    <button disabled={pending||selectedRoles.length===0||selectedRoles.length===member.roles.length&&selectedRoles.every(value=>member.roles.includes(value))&&active===member.active} onClick={()=>void onSave(member,selectedRoles,active)}>{t('Save member')}</button>
  </div>;
}
