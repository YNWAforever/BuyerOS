'use client';
import {useEffect,useMemo,useState} from 'react';
import {useWorkspaceSession,useSessionSnapshot} from '@/features/providers/workspace-session';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
import {createOperationClient} from '@/services/live/operations';
import {capabilityNames,validCapabilities,type CapabilityPage} from '@/services/live/capabilities';
import {BudgetSettings} from './budgets';
import {MemberDirectory} from './member-directory';

type Preference={locale:'en'|'zh-HK';default_markets:string[];version:number};

export function LiveSettings({workspace,locale,isAdmin,roles,onVersion,currentVersion,canViewBudget,t}:{workspace:string;locale:'en'|'zh-HK';isAdmin:boolean;roles:string[];onLocale:(value:'en'|'zh-HK')=>void;onVersion:(value:number)=>void;currentVersion:number;canViewBudget:boolean;t:(value:string)=>string}){
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
    <section aria-label={t('Role responsibilities')}><h3>{t('Role responsibilities')}</h3><p>{t('Current roles')}: <output>{roles.map(t).join(', ')}</output></p>
      <dl>{[
        ['viewer','Read workspace records and sources.'],
        ['operator','Prepare research, buyer maintenance and drafts; export approved revisions.'],
        ['reviewer','Review buyers, sources, sender details and draft approvals.'],
        ['workspace_admin','Manage verified memberships, provider setup and approved budgets.'],
      ].map(([role,description])=><div key={role}><dt>{t(role)}</dt><dd>{t(description)}</dd></div>)}</dl>
      <p>{t('Each action still requires current workspace membership, project access and server policy.')}</p>
    </section>
    <ProviderCapabilities workspace={workspace} t={t}/>
    {canViewBudget&&<BudgetSettings workspace={workspace} isAdmin={isAdmin} t={t}/>}
    {isAdmin&&<MemberDirectory key={`${workspace}-${scope.identity}`} workspace={workspace} t={t}/>}
    {error&&<p role="alert">{t(error)}</p>}{status&&<p role="status">{t(status)}</p>}
  </section>;
}

function ProviderCapabilities({workspace,t}:{workspace:string;t:(value:string)=>string}) {
  const {client,session}=useWorkspaceSession(),scope=useSessionSnapshot(),api=useMemo(()=>createOperationClient(client),[client]);
  const [refresh,setRefresh]=useState(0),[loaded,setLoaded]=useState<{key:string;page:CapabilityPage}|null>(null),[error,setError]=useState({key:'',message:''});
  const readKey=JSON.stringify([workspace,scope.identity,refresh]),page=loaded?.key===readKey?loaded.page:null,failure=error.key===readKey?error.message:'';
  useEffect(()=>{
    const own=new AbortController(),captured=session.captureWriteContext();
    const ctx={...captured,signal:AbortSignal.any([captured.signal,own.signal]),getToken:async()=>session.token()||'',isCurrent:()=>session.isCurrent(captured.identity)&&!own.signal.aborted};
    void api.requestOperation('getCapabilities',{path:{workspace_id:workspace}},ctx).then(value=>{
      if(!ctx.isCurrent())return;if(!validCapabilities(value))throw new Error('Incomplete capability response');setLoaded({key:readKey,page:value});
    }).catch(cause=>{if(ctx.isCurrent()&&!(cause instanceof LiveCancelled))setError({key:readKey,message:describeLiveError(cause)});});
    return()=>own.abort();
  },[api,session,workspace,scope.identity,readKey]);
  return <section aria-label={t('Provider capabilities')}><h3>{t('Provider capabilities')}</h3>
    <button type="button" onClick={()=>setRefresh(value=>value+1)}>{t('Refresh capabilities')}</button>
    {failure?<p role="alert">{t('Capabilities unavailable')}: {failure}</p>:!page&&<p role="status">{t('Loading capabilities…')}</p>}
    <p>{t('Confirm provider, price, approved budget and connection test with a workspace administrator.')}</p>
    {capabilityNames.map(name=>{const item=page?.items.find(row=>row.name===name);return <article className="panel" key={name} data-capability={name}>
      <h4>{t(name)}</h4><output>{item?t(item.status):'—'}</output>
      {item&&<><p>{t('Checked')}: <time dateTime={item.checked_at}>{item.checked_at}</time></p>
        {item.status!=='ready'&&<p>{t(item.reason_codes.includes('PAID_ADMISSION_DISABLED')?'Paid research is disabled. You can still review existing buyers and results.':name==='mailbox'||name==='crm'?'Native delivery requires its separate acceptance gate; use an approved export when available.':'Verify configuration and the account allowance, then run an authorized connection test before activation.')}</p>}
        <details><summary>{t('Technical details')}</summary><ul>{item.reason_codes.map(code=><li key={code} style={{overflowWrap:'anywhere'}}>{code}</li>)}</ul></details></>}
    </article>;})}
  </section>;
}
