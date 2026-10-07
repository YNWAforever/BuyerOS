'use client';
import {useEffect,useState} from 'react';
import {useWorkspaceSession,useSessionSnapshot} from '@/features/providers/workspace-session';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
import {BudgetSettings} from './budgets';
import {MemberDirectory} from './member-directory';

type Preference={locale:'en'|'zh-HK';default_markets:string[];version:number};

export function LiveSettings({workspace,locale,isAdmin,onVersion,currentVersion,canViewBudget,t}:{workspace:string;locale:'en'|'zh-HK';isAdmin:boolean;onLocale:(value:'en'|'zh-HK')=>void;onVersion:(value:number)=>void;currentVersion:number;canViewBudget:boolean;t:(value:string)=>string}){
  const {session,client}=useWorkspaceSession();
  const scope=useSessionSnapshot();
  const [pref,setPref]=useState<Preference|null>(null),[markets,setMarkets]=useState('');
  const [error,setError]=useState(''),[status,setStatus]=useState('');
  const [pending,setPending]=useState(false);
  useEffect(()=>{
    const own=new AbortController(),identity=session.identity(),token=session.token();
    if(!token)return;
    const signal=AbortSignal.any([own.signal,session.controller().signal]);
    void client.request<Preference>({path:`/v1/workspaces/${workspace}/preferences`,token,scope:identity,signal}).then(value=>{
      if(!session.isCurrent(identity)||own.signal.aborted)return;
      setPref(value);setMarkets(value.default_markets.join(', '));
    }).catch(e=>{if(!(e instanceof LiveCancelled)&&!own.signal.aborted)setError(describeLiveError(e));});
    return()=>own.abort();
  },[client,session,workspace,scope.identity]);
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
  return <section className="panel" aria-label={t('Workspace settings')}>
    <h2>{t('Workspace settings')}</h2>
    <p>{t('Preferences are saved for this member and workspace. Research is unavailable until a verified provider is activated.')}</p>
    <label>{t('Language')} <output>{locale==='zh-HK'?'繁體中文':'English'}</output></label>
    <label>{t('Default markets')} <input aria-label={t('Default markets')} value={markets} onChange={e=>setMarkets(e.target.value)} placeholder="HK, US"/></label>
    <button disabled={!pref||pending} onClick={()=>void saveMarkets()}>{t('Save preferences')}</button>
    <p className="muted">{t('Research provider')} · {t('Not connected')}</p>
    <p className="muted">{t('Ask an administrator to select a research provider and confirm its price, budget and connection test.')}</p>
    {canViewBudget&&<BudgetSettings workspace={workspace} isAdmin={isAdmin} t={t}/>}
    {isAdmin&&<MemberDirectory key={`${workspace}-${scope.identity}`} workspace={workspace} t={t}/>}
    {error&&<p role="alert">{t(error)}</p>}{status&&<p role="status">{t(status)}</p>}
  </section>;
}
