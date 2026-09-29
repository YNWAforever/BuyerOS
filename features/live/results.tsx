'use client';
import {useEffect,useRef,useState} from 'react';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
import {ActionIntent} from '@/services/live/action-intent';
import {utcMonth,getUsage,type Usage} from '@/services/live/usage';
import {listOutcomes,recordOutcome,correctOutcome,type Outcome,type OutcomePage} from '@/services/live/outcomes';
import {useWorkspaceSession,useSessionSnapshot} from '@/features/providers/workspace-session';
import {LiveBuyerResults} from './buyer-results';

function money(value:{amount:string;currency:string}|null|undefined){return value?`${value.amount} ${value.currency}`:'—';}
function utcDate(value:string){return `${value}T00:00:00.000Z`;}
function localInput(value:string){const date=new Date(value);return new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16);}
function localeDate(value:string,locale:'en'|'zh-HK'){return new Date(value).toLocaleString(locale==='zh-HK'?'zh-HK':'en-US');}

export function LiveUsage({t,locale}:{t:(value:string)=>string;locale:'en'|'zh-HK'}){
  const {client,session}=useWorkspaceSession(),scope=useSessionSnapshot().scope;
  const month=utcMonth();
  const [from,setFrom]=useState(month.from.slice(0,10)),[to,setTo]=useState(month.to.slice(0,10));
  const [applied,setApplied]=useState({from:month.from,to:month.to}),[refresh,setRefresh]=useState(0);
  const [usage,setUsage]=useState<Usage|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(true);
  useEffect(()=>{
    if(!scope.workspace||!scope.project)return;
    let active=true;
    void getUsage(client,session,applied.from,applied.to).then(value=>{if(active)setUsage(value);})
      .catch(cause=>{if(active&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));})
      .finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[client,session,scope.workspace,scope.project,applied,refresh]);
  function apply(){if(!from||!to||from>=to){setError(t('Choose an increasing UTC date range.'));return;}setUsage(null);setLoading(true);setError('');setApplied({from:utcDate(from),to:utcDate(to)});setRefresh(v=>v+1);}
  return <section className="panel" aria-label={t('Usage')}><h2>{t('Usage')}</h2>
    <p>{t('UTC half-open period; changing language does not change these dates.')}</p>
    <div className="inline live-usage-controls"><label>{t('From UTC')} <input type="date" aria-label={t('From UTC')} value={from} onChange={e=>setFrom(e.target.value)}/></label>
      <label>{t('To UTC')} <input type="date" aria-label={t('To UTC')} value={to} onChange={e=>setTo(e.target.value)}/></label>
      <button type="button" onClick={apply}>{t('Apply period')}</button><button type="button" onClick={()=>{setUsage(null);setLoading(true);setError('');setRefresh(v=>v+1);}}>{t('Refresh usage')}</button></div>
    {loading&&<p role="status">{t('Loading usage…')}</p>}{error&&<p role="alert">{error}</p>}
    {usage&&<><p>{t('Project')}: <code>{usage.project_id}</code> · {t('As of')}: {localeDate(usage.as_of,locale)}</p>
      <div className="grid two-col"><div className="activity"><b>{t('Settled metered cost')}</b><p>{money(usage.total_settled)}</p></div>
        <div className="activity"><b>{t('Active holds')}</b><p>{money(usage.total_reserved)}</p></div>
        <div className="activity"><b>{t('Remaining approved budget')}</b><p>{money(usage.remaining)}</p></div>
        <div className="activity"><b>{t('New accepted companies')}</b><p>{usage.accepted_company_count}</p></div>
        <div className="activity"><b>{t('Contactable accepted companies')}</b><p>{usage.eligible_contactable_company_count}</p></div>
        <div className="activity"><b>{t('Blended cost per accepted company')}</b><p>{money(usage.cost_per_accepted_company)}</p></div>
        <div className="activity"><b>{t('Blended cost per contactable company')}</b><p>{money(usage.cost_per_contactable_accepted_company)}</p></div></div>
      <p className="muted">{t('Actual recorded cost includes failed and partial work and signed refunds. Holds are separate. A zero denominator is shown as an em dash.')}</p>
      <details><summary>{t('Cost categories')}</summary>{usage.categories.map(row=><p key={row.category}>{t(row.category)}: {money(row.settled)} · {t('Held cost')}: {money(row.reserved)}</p>)}</details>
    </>}
  </section>;
}

export function LiveOutcomes({buyerId,canRecord,locale,t}:{buyerId:string|null;canRecord:boolean;locale:'en'|'zh-HK';t:(value:string)=>string}){
  const {client,session}=useWorkspaceSession(),scope=useSessionSnapshot().scope;
  const [page,setPage]=useState<OutcomePage|null>(null),[offset,setOffset]=useState(0),[refresh,setRefresh]=useState(0);
  const [error,setError]=useState(''),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false);
  const [stage,setStage]=useState<'reply'|'meeting'|'opportunity'|'disqualified'>('reply');
  const [occurred,setOccurred]=useState(localInput(new Date().toISOString()));
  const [notes,setNotes]=useState(''),[reason,setReason]=useState('');
  const [correcting,setCorrecting]=useState<Outcome|null>(null);
  const intent=useRef(new ActionIntent<Outcome>());
  useEffect(()=>{
    if(!scope.workspace||!scope.project)return;
    let active=true;
    void listOutcomes(client,session,offset).then(value=>{if(active)setPage(value);})
      .catch(cause=>{if(active&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));})
      .finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[client,session,scope.workspace,scope.project,offset,refresh]);
  async function submit(){
    const target=correcting?.buyer_id||buyerId;
    if(!target||notes.trim().length<3||!occurred||correcting&&reason.trim().length<3){setError(t('Choose a buyer, time and notes. Corrections need a reason.'));return;}
    if(busy)return;setBusy(true);setError('');
    const identity=session.identity();
    try{
      const at=new Date(occurred).toISOString();
      const key=JSON.stringify({scope:session.identity(),target,stage,at,notes,reason,correcting:correcting?.id});
      const result=await intent.current.run(key,id=>correcting
        ? correctOutcome(client,session,correcting.id,correcting.version,{stage,occurred_at:at,notes:notes.trim(),reason:reason.trim()},id)
        : recordOutcome(client,session,{buyer_id:target,stage,occurred_at:at,source:'manual',notes:notes.trim()},id));
      if(!session.isCurrent(identity))return;
      setCorrecting(null);setNotes('');setReason('');setPage(null);setLoading(true);setOffset(0);setRefresh(v=>v+1);
      void result;
    }catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    finally{setBusy(false);}
  }
  function startCorrection(row:Outcome){setCorrecting(row);setStage(row.stage);setOccurred(localInput(row.occurred_at));setNotes(row.notes);setReason('');}
  return <section className="panel" aria-label={t('Manual outcomes')}><h2>{t('Manual outcomes')}</h2>
    <p>{t('These stages are entered by staff. They do not verify mailbox activity or send a message.')}</p>
    {canRecord&&<div><p>{correcting?t('Correcting an earlier event'):buyerId?t('Selected buyer')+': '+buyerId:t('Select a buyer in Results to record an outcome.')}</p>
      <div className="inline live-outcome-fields"><label>{t('Stage')} <select aria-label={t('Outcome stage')} value={stage} onChange={e=>setStage(e.target.value as typeof stage)}>{(['reply','meeting','opportunity','disqualified'] as const).map(value=><option key={value} value={value}>{t(value)}</option>)}</select></label>
        <label>{t('Occurred at')} <input type="datetime-local" aria-label={t('Occurred at')} value={occurred} onChange={e=>setOccurred(e.target.value)}/></label></div>
      <label>{t('Notes')} <textarea aria-label={t('Outcome notes')} value={notes} onChange={e=>setNotes(e.target.value)} maxLength={2000}/></label>
      {correcting&&<label>{t('Correction reason')} <input aria-label={t('Correction reason')} value={reason} onChange={e=>setReason(e.target.value)} maxLength={1000}/></label>}
      <div className="inline"><button type="button" disabled={busy||!buyerId&&!correcting} onClick={()=>void submit()}>{busy?t('Saving…'):correcting?t('Append correction'):t('Record manual outcome')}</button>
        {correcting&&<button type="button" onClick={()=>setCorrecting(null)}>{t('Cancel correction')}</button>}</div></div>}
    {error&&<p role="alert">{error}</p>}{loading&&<p role="status">{t('Loading outcomes…')}</p>}
    {page&&<><p>{page.total} {t('outcome events')}</p>{page.items.length?page.items.map(row=><div className="activity" key={row.id}>
      <div><b>{t(row.stage)}</b><p>{t('Source')}: {t('manual')} · {t('Occurred at')}: {localeDate(row.occurred_at,locale)} · {t('Recorded at')}: {localeDate(row.recorded_at,locale)}</p>
        <p>{row.notes}{row.correction_reason&&<> · {t('Correction reason')}: {row.correction_reason}</>} · {t('Actor')}: <code>{row.actor_id}</code>{row.supersedes_id&&<> · {t('Corrects')}: <code>{row.supersedes_id}</code></>}</p></div>
      {canRecord&&<button type="button" onClick={()=>startCorrection(row)}>{t('Correct event')}</button>}</div>):<p>{t('No manual outcomes recorded.')}</p>}
      <div className="inline"><button disabled={offset===0} onClick={()=>{setPage(null);setLoading(true);setOffset(Math.max(0,offset-10));}}>{t('Previous')}</button>
        <span>{page.total?offset+1:0}–{Math.min(offset+page.items.length,page.total)} / {page.total}</span>
        <button disabled={offset+page.items.length>=page.total} onClick={()=>{setPage(null);setLoading(true);setOffset(offset+10);}}>{t('Next')}</button></div></>}
  </section>;
}

export function LiveResults({locale,canReview,canEdit,canQuote,canAssign,ownMembershipId,t}:{locale:'en'|'zh-HK';canReview:boolean;canEdit:boolean;canQuote:boolean;canAssign:boolean;ownMembershipId:string|null;t:(value:string)=>string}){
  const [buyerId,setBuyerId]=useState<string|null>(null);
  return <><LiveUsage locale={locale} t={t}/><LiveBuyerResults locale={locale} canReview={canReview} canEdit={canEdit} canQuote={canQuote} canAssign={canAssign} ownMembershipId={ownMembershipId} onManualOutcome={setBuyerId}/><LiveOutcomes buyerId={buyerId} canRecord={canEdit||canReview} locale={locale} t={t}/></>;
}
