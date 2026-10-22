'use client';
import {useCallback,useEffect,useState} from 'react';
import {useWorkspaceSession,useSessionSnapshot} from '@/features/providers/workspace-session';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
import {loadPilotBudget,listPilotCostEvents,type PilotBudget} from '@/services/live/pilot-budgets';
import type {LeadIntentInput} from '@/services/live/lead-intents';
import {useLeadOperation,LeadRecovery} from './operation';
import {leadText,leadTime,hktInput,hktIso,safeLeadUrl,type LeadLocale} from './copy';
const actions=['pilot.policy','cost.record','credits.record','budget.reconcile'] as const;
type CostRecord=Awaited<ReturnType<typeof listPilotCostEvents>>['items'][number];
function micros(value:string){const [whole,fraction='']=value.split('.');return BigInt(whole)*BigInt(1_000_000)+BigInt(fraction.padEnd(6,'0'));}
export function PilotBudgetPanel({locale,isAdmin,summary=false}:{locale:LeadLocale;isAdmin:boolean;summary?:boolean}){
  const {client,session}=useWorkspaceSession(),snapshot=useSessionSnapshot();
  const [data,setData]=useState<PilotBudget|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(false);
  const [events,setEvents]=useState<CostRecord[]>([]),[offset,setOffset]=useState(0),[total,setTotal]=useState(0);
  const [limit,setLimit]=useState('10'),[policyReason,setPolicyReason]=useState('');
  const [title,setTitle]=useState(''),[url,setUrl]=useState(''),[reason,setReason]=useState(''),[shared,setShared]=useState(false);
  const [charge,setCharge]=useState(''),[state,setState]=useState<'committed'|'settled'|'unknown'|'corrected'>('unknown');
  const [amount,setAmount]=useState(''),[upper,setUpper]=useState(''),[period,setPeriod]=useState('');
  const [previous,setPrevious]=useState(''),[native,setNative]=useState(''),[fees,setFees]=useState(false),[minimum,setMinimum]=useState(false);
  const [currency,setCurrency]=useState('USD'),[original,setOriginal]=useState(''),[fx,setFx]=useState('');
  const [provider,setProvider]=useState(''),[unit,setUnit]=useState('credits'),[used,setUsed]=useState(''),[remaining,setRemaining]=useState('');
  const [creditStart,setCreditStart]=useState(''),[creditEnd,setCreditEnd]=useState(''),[observed,setObserved]=useState(hktInput());
  const t=(value:string)=>leadText(locale,value);
  const refresh=useCallback(async()=>{
    const identity=session.identity();
    try{
      setLoading(true);
      const value=await loadPilotBudget(client,session);
      const history=isAdmin&&!summary?await listPilotCostEvents(client,session,offset):null;
      if(!session.isCurrent(identity))return;
      setData(value);setError('');
      if(history){setEvents(history.items);setTotal(history.total);}
      return value;
    }finally{if(session.isCurrent(identity))setLoading(false);}
  },[client,session,isAdmin,summary,offset]);
  const readback=useCallback(async()=>{await refresh();setShared(false);},[refresh]);
  const operation=useLeadOperation(null,actions,readback,locale);
  useEffect(()=>{
    let active=true;
    void Promise.resolve().then(refresh).then(value=>{
      if(!active||!value)return;
      setLimit(value.limit);setPeriod(value.period_start.slice(0,10));
      setCreditStart(hktInput(value.period_start));setCreditEnd(hktInput(value.period_end));
    }).catch(cause=>{if(active&&!(cause instanceof LiveCancelled)){setData(null);setError(describeLiveError(cause));}});
    return()=>{active=false;};
  },[refresh,snapshot.identity]);
  const disabled=loading||operation.busy||operation.historyBlocked||operation.unknown||operation.pending.length>0;
  const hasProof=Boolean(title.trim()&&safeLeadUrl(url)&&reason.trim().length>=3);
  const source=[{title,url}];
  async function write(input:LeadIntentInput){await operation.run(input,'Budget record saved.');}
  async function policy(event:React.FormEvent){
    event.preventDefault();if(!data)return;
    await write({action:'pilot.policy',expected_version:data.version,payload:{monthly_limit:limit,reason:policyReason}});
  }
  async function cost(event:React.FormEvent){
    event.preventDefault();if(!data)return;
    await write({action:'cost.record',expected_version:data.version,payload:{
      economic_charge_key:charge,period_start:`${period}T00:00:00Z`,state,usd_amount:amount||null,usd_upper_bound:upper||null,
      original_currency:currency,original_amount:original||null,fx_basis:fx||null,fees_included:fees,minimum_purchase_included:minimum,
      source_refs:source,reason,previous_event_id:previous||null,native_operation_id:native||null,
    }});
  }
  async function credits(event:React.FormEvent){
    event.preventDefault();if(!data)return;
    await write({action:'credits.record',expected_version:data.version,payload:{
      provider,unit,period_start:hktIso(creditStart),period_end:hktIso(creditEnd),
      as_of:hktIso(observed),used:used||null,remaining:remaining||null,source_refs:source,
    }});
  }
  async function reconcile(){
    if(!data)return;
    await write({action:'budget.reconcile',expected_version:data.version,payload:{
      period_start:data.period_start,ledger_version:data.ledger_version,ledger_hash:data.ledger_hash,
      coverage_start:data.period_start,coverage_end:data.as_of,shared_usage_known:shared,reason,source_refs:source,
    }});
  }
  function selectPrevious(id:string){
    setPrevious(id);
    const row=events.find(item=>item.id===id),proof=row?.source as Record<string,unknown>|null;
    if(proof){setCharge(String(proof.economic_charge_key??''));setState('corrected');setPeriod(String(row?.period_start).slice(0,10));}
  }
  const warning=data&&data.external_unsettled!==null&&micros(data.recorded_settled)+micros(data.reserved_total)+micros(data.external_unsettled)>=micros(data.limit)*BigInt(8)/BigInt(10);
  return <section className="panel" aria-label={t('Pilot monthly budget')}>
    <h2>{t('Pilot monthly budget')}</h2>
    <p>{t('Paid research, all contact enrichment and sending remain disabled.')}</p>
    {loading&&<p role="status">{t('Loading budget…')}</p>}
    {error&&<p role="alert">{t('Budget unavailable.')} {t(error)}</p>}
    {data&&!error&&<>
      {!data.id&&<p>{t('Policy not saved')}</p>}
      <p>{t('Combined monthly USD limit')}: {data.limit}</p>
      <p>{t('Paid execution')}: {t(data.activation)}</p>
      {data.activation==='configuration_mismatch'&&<p role="alert">{t('Runtime configuration does not match the disabled pilot. Resolve it before any activation.')}</p>}
      <p>{t('Remaining USD')}: {data.remaining??t('unknown')}</p>
      <p>{t('Recorded settled USD')}: {data.recorded_settled}</p><p>{t('Confirmed settled USD')}: {data.settled_total??t('unknown')}</p>
      <p>{t('Reserved USD')}: {data.reserved_total} · {t('Carried reserved USD')}: {data.carried_reserved}</p>
      <p>{t('External unsettled USD')}: {data.external_unsettled??t('unknown')}</p>
      <p>{t('UTC billing period')}: {data.period_start} – {data.period_end}</p>
      <p>{t('Hong Kong display')}: {leadTime(data.period_start,locale)} – {leadTime(data.period_end,locale)}</p>
      <p>{t('Reconciliation')}: {t(data.reconciliation_status)} · {t('As of')}: {leadTime(data.as_of,locale)}</p>
      {warning&&<p role="alert">{t('At least 80% of the monthly cap is settled or committed.')}</p>}
      {data.budget_state==='over_limit'&&<p role="alert">{t('Recorded obligations exceed the monthly cap. Actual costs are preserved.')}</p>}
      {data.blockers.map(item=><p key={item}>{t(item)}</p>)}
      <p>{t('Credits are provider units, separate from USD purchase costs.')}</p>
      {data.credits.map((row,index)=><p key={index}>{String(row.provider)} · {String(row.unit)} · {t('Used')}: {String(row.used??t('unknown'))} · {t('Remaining')}: {String(row.remaining??t('unknown'))}
        {' · '}{String(row.period_start)} – {String(row.period_end)} · {t('Observed')}: {String(row.as_of)}</p>)}
      {isAdmin&&!summary&&<>
        <form onSubmit={event=>void policy(event)}>
          <label>{t('Monthly USD limit')}<input aria-label={t('Monthly USD limit')} inputMode="decimal" pattern="(0|[1-9][0-9]*)(\.[0-9]{1,6})?" required disabled={disabled} value={limit} onChange={e=>setLimit(e.target.value)}/></label>
          <label>{t('Budget change reason')}<input aria-label={t('Budget change reason')} required minLength={3} maxLength={4000} disabled={disabled} value={policyReason} onChange={e=>setPolicyReason(e.target.value)}/></label>
          <button type="submit" disabled={disabled}>{t('Save pilot policy')}</button>
        </form>
        <fieldset disabled={disabled}><legend>{t('Manual accounting evidence')}</legend>
          <label>{t('Budget evidence title')}<input aria-label={t('Budget evidence title')} maxLength={300} value={title} onChange={e=>setTitle(e.target.value)}/></label>
          <label>{t('Budget evidence URL')}<input aria-label={t('Budget evidence URL')} type="url" maxLength={2048} value={url} onChange={e=>setUrl(e.target.value)}/></label>
          <label>{t('Budget evidence reason')}<textarea aria-label={t('Budget evidence reason')} maxLength={4000} value={reason} onChange={e=>setReason(e.target.value)}/></label>
          <label><input type="checkbox" checked={shared} onChange={e=>setShared(e.target.checked)}/>{t('Shared provider usage is fully accounted for.')}</label>
          <p>{t('Reconciliation covers the UTC period start through the displayed observation time.')}</p>
          <button disabled={!data.id||!hasProof||!shared} onClick={()=>void reconcile()}>{t('Reconcile this period')}</button>
        </fieldset>
        <form onSubmit={event=>void cost(event)}>
          <h3>{t('Record external cost without purchasing')}</h3>
          <label>{t('Economic charge key')}<input aria-label={t('Economic charge key')} required maxLength={255} value={charge} disabled={disabled} onChange={e=>setCharge(e.target.value)}/></label>
          <label>{t('Cost state')}<select aria-label={t('Cost state')} value={state} disabled={disabled} onChange={e=>setState(e.target.value as typeof state)}>{['unknown','committed','settled','corrected'].map(value=><option key={value} value={value}>{t(value)}</option>)}</select></label>
          <label>{t('UTC cost month start')}<input aria-label={t('UTC cost month start')} type="date" required value={period} disabled={disabled} onChange={e=>setPeriod(e.target.value)}/></label>
          <label>{t('Settled USD amount')}<input aria-label={t('Settled USD amount')} inputMode="decimal" pattern="(0|[1-9][0-9]*)(\.[0-9]{1,6})?" required={state==='settled'} value={amount} disabled={disabled} onChange={e=>setAmount(e.target.value)}/></label>
          <label>{t('Verified USD upper bound')}<input aria-label={t('Verified USD upper bound')} inputMode="decimal" pattern="(0|[1-9][0-9]*)(\.[0-9]{1,6})?" required={state==='committed'} value={upper} disabled={disabled} onChange={e=>setUpper(e.target.value)}/></label>
          <label>{t('Original currency')}<input aria-label={t('Original currency')} pattern="[A-Z]{3}" required value={currency} disabled={disabled} onChange={e=>setCurrency(e.target.value)}/></label>
          <label>{t('Original amount')}<input aria-label={t('Original amount')} inputMode="decimal" value={original} disabled={disabled} onChange={e=>setOriginal(e.target.value)}/></label>
          <label>{t('FX evidence')}<textarea aria-label={t('FX evidence')} maxLength={2000} value={fx} disabled={disabled} onChange={e=>setFx(e.target.value)}/></label>
          <label>{t('Previous economic event')}<select aria-label={t('Previous economic event')} value={previous} disabled={disabled} onChange={e=>selectPrevious(e.target.value)}><option value="">—</option>{events.map(row=><option key={String(row.id)} value={String(row.id)}>{String(row.id)} · {String(row.state)}</option>)}</select></label>
          <label>{t('Native budget operation ID (optional)')}<input aria-label={t('Native budget operation ID (optional)')} value={native} disabled={disabled} onChange={e=>setNative(e.target.value)}/></label>
          <label><input type="checkbox" checked={fees} disabled={disabled} onChange={e=>setFees(e.target.checked)}/>{t('Taxes and fees are included.')}</label>
          <label><input type="checkbox" checked={minimum} disabled={disabled} onChange={e=>setMinimum(e.target.checked)}/>{t('Minimum purchase is included.')}</label>
          <button type="submit" disabled={disabled||!data.id||!hasProof}>{t('Record cost evidence')}</button>
        </form>
        <form onSubmit={event=>void credits(event)}>
          <h3>{t('Record observed credits without buying or consuming')}</h3>
          <label>{t('Credit provider')}<input aria-label={t('Credit provider')} required maxLength={100} value={provider} disabled={disabled} onChange={e=>setProvider(e.target.value)}/></label>
          <label>{t('Credit unit')}<input aria-label={t('Credit unit')} required maxLength={50} value={unit} disabled={disabled} onChange={e=>setUnit(e.target.value)}/></label>
          {([[t('Credit period start (Hong Kong)'),creditStart,setCreditStart],[t('Credit period end (Hong Kong)'),creditEnd,setCreditEnd],[t('Credit observed at (Hong Kong)'),observed,setObserved]] as const).map(([label,value,set])=><label key={label}>{label}<input aria-label={label} type="datetime-local" required value={value} disabled={disabled} onChange={e=>set(e.target.value)}/></label>)}
          <label>{t('Used credits')}<input aria-label={t('Used credits')} inputMode="decimal" value={used} disabled={disabled} onChange={e=>setUsed(e.target.value)}/></label>
          <label>{t('Remaining credits')}<input aria-label={t('Remaining credits')} inputMode="decimal" value={remaining} disabled={disabled} onChange={e=>setRemaining(e.target.value)}/></label>
          <button type="submit" disabled={disabled||!data.id||!hasProof}>{t('Record credit observation')}</button>
        </form>
        <h3>{t('Cost history')}</h3>
        {events.map(row=><article className="activity" key={String(row.id)}><p>{String(row.id)} · {t(String(row.state))} · USD {String(row.usd_amount??row.usd_upper_bound??t('unknown'))}</p>
          <p>{String(row.period_start)} · {String(row.recorded_by_user_id)}</p>
          {row.redacted?<p>{t('Source no longer available.')}</p>:<p>{String((row.source as Record<string,unknown>|null)?.reason??'')}</p>}
        </article>)}
        {total>20&&<div className="inline"><button disabled={offset===0||disabled} onClick={()=>setOffset(v=>Math.max(0,v-20))}>{t('Previous page')}</button><span>{offset+1}–{Math.min(offset+events.length,total)} / {total}</span><button disabled={offset+events.length>=total||disabled} onClick={()=>setOffset(v=>v+20)}>{t('Next page')}</button></div>}
      </>}
    </>}
    <button disabled={disabled} onClick={()=>void refresh().catch(cause=>{setData(null);setError(describeLiveError(cause));})}>{t('Refresh pilot budget')}</button>
    {!summary&&<LeadRecovery operation={operation} locale={locale}/>}
  </section>;
}
