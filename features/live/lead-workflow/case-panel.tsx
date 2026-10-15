'use client';
import {useCallback,useEffect,useRef,useState} from 'react';
import {useWorkspaceSession,useSessionSnapshot} from '@/features/providers/workspace-session';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
import {loadLeadCase,listLeadEvidence,listLeadReviews,type LeadCaseView,type LeadObservationRecord,type LeadReviewRecord} from '@/services/live/lead-workflow';
import {useLeadOperation,LeadRecovery} from './operation';
import {leadText,leadTime,type LeadLocale} from './copy';

const actions=['case.update','lead.review'] as const;
type Judgement='accepted'|'uncertain'|'rejected';
export function LeadCasePanel({buyerId,locale,canEdit,canAssign=false,onChanged=()=>{},contextVersion=0}:{
  buyerId:string;locale:LeadLocale;canEdit:boolean;canAssign?:boolean;onChanged?:()=>void;contextVersion?:number;
}){
  const {client,session}=useWorkspaceSession(),snapshot=useSessionSnapshot();
  const [data,setData]=useState<LeadCaseView|null>(null),[error,setError]=useState('');
  const [observations,setObservations]=useState<LeadObservationRecord[]>([]);
  const [priority,setPriority]=useState(false),[reason,setReason]=useState(''),[next,setNext]=useState(''),[due,setDue]=useState('');
  const [person,setPerson]=useState(''),[contact,setContact]=useState('');
  const [employment,setEmployment]=useState<Judgement>('uncertain'),[procurement,setProcurement]=useState<Judgement>('uncertain');
  const [ownership,setOwnership]=useState<Judgement>('uncertain'),[rationale,setRationale]=useState(''),[conflict,setConflict]=useState('');
  const [confirmed,setConfirmed]=useState(false),[cited,setCited]=useState<string[]>([]);
  const [history,setHistory]=useState<LeadReviewRecord[]|null>(null),[historyTotal,setHistoryTotal]=useState(0),[historyBusy,setHistoryBusy]=useState(false);
  const previousContext=useRef(contextVersion);
  const t=(value:string)=>leadText(locale,value);
  const refresh=useCallback(async()=>{
    const identity=session.identity(),all:LeadObservationRecord[]=[];
    const current=await loadLeadCase(client,session,buyerId);
    for(let offset=0;;){
      const page=await listLeadEvidence(client,session,buyerId,offset,100);all.push(...page.items);
      if(all.length>=page.total)break;
      if(!page.items.length)throw new Error('Incomplete evidence history');
      offset=all.length;
    }
    if(!session.isCurrent(identity))return;
    setData(current);setObservations(all);setError('');return current;
  },[client,session,buyerId]);
  const readback=useCallback(async()=>{await refresh();setHistory(null);onChanged();},[refresh,onChanged]);
  const operation=useLeadOperation(buyerId,actions,readback,locale);
  useEffect(()=>{
    let active=true;
    void Promise.resolve().then(refresh).then(current=>{
      if(!active||!current)return;
      setPriority(current.priority);setReason(current.priority_reason);setNext(current.next_action);setDue(current.due_on??'');
      setPerson(current.selected_person_id??'');setContact(current.selected_contact_id??'');
    }).catch(cause=>{if(active&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));});
    return()=>{active=false;};
  },[refresh,snapshot.identity]);
  useEffect(()=>{
    if(previousContext.current===contextVersion)return;
    previousContext.current=contextVersion;
    // A sibling evidence save updates the canonical status, never local edit text.
    void Promise.resolve().then(refresh).then(()=>setHistory(null)).catch(cause=>{
      if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));
    });
  },[contextVersion,refresh]);
  const disabled=operation.busy||operation.unknown||operation.pending.length>0;
  const people=new Map(observations.filter(row=>row.person_id&&row.person&&!row.redacted).map(row=>[row.person_id!,row.person!]));
  const channels=new Map(observations.filter(row=>row.contact_id&&row.channel&&!row.redacted).map(row=>[row.contact_id!,row.channel!]));
  const superseded=new Set(observations.map(row=>row.supersedes_id).filter(Boolean));
  const relevant=observations.filter(row=>!superseded.has(row.id)&&(
    (row.person_id===person&&['employment','procurement_scope'].includes(row.claim))||
    (contact&&row.contact_id===contact&&row.claim==='channel_ownership')));
  async function saveWork(event:React.FormEvent){
    event.preventDefault();if(!data)return;
    await operation.run({action:'case.update',buyer_id:buyerId,expected_version:data.version,
      payload:{priority,priority_reason:reason,next_action:next,due_on:due||null}},'Lead work state saved.');
    // Refresh the canonical version on conflicts without replacing unsaved form input.
    await refresh().catch(cause=>setError(describeLiveError(cause)));
  }
  async function saveReview(event:React.FormEvent){
    event.preventDefault();if(!data)return;
    await operation.run({action:'lead.review',buyer_id:buyerId,expected_version:data.version,
      payload:{person_id:person,contact_id:contact||null,employment,procurement_scope:procurement,
        channel_ownership:ownership,observation_ids:cited,rationale,conflict_resolution:conflict||null,
        previous_review_id:null}},'Purchasing review saved.');
    await refresh().catch(cause=>setError(describeLiveError(cause)));
  }
  async function loadHistory(){
    if(historyBusy)return;
    const identity=session.identity();setHistoryBusy(true);
    try{
      const page=await listLeadReviews(client,session,buyerId,history?.length??0);
      if(session.isCurrent(identity)){setHistory(rows=>[...(rows??[]),...page.items]);setHistoryTotal(page.total);}
    }catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    finally{if(session.isCurrent(identity))setHistoryBusy(false);}
  }
  return <section className="panel" aria-label={t('Lead contact preparation')}>
    <h4>{t('Lead contact preparation')}</h4>
    {error&&<p role="alert">{t(error)}</p>}
    {!data?<p role="status">{t('Loading lead work state…')}</p>:<>
      <p>{t(data.quality.qualified_person?'Purchasing role: confirmed':'Purchasing role: pending')}</p>
      <p>{t(data.quality.channel_ownership_current?'Channel ownership: confirmed':'Channel ownership: pending')}</p>
      <p>{t('Technical check: not tested')}</p><p>{t('Sending: disabled')}</p>
      <p>{t('Company source records')}: {data.source_check_ids.length}</p>
      <p>{t('Manual source verification does not verify delivery or grant sending permission.')}</p>
      {data.quality.expires_at&&<p>{t('Review deadline')}: {leadTime(data.quality.expires_at,locale)}</p>}
      <p>{t('Employment and purchasing: 30 days. Channel ownership: 7 days.')}</p>
      {data.quality.blockers.length>0&&<ul>{data.quality.blockers.map(item=><li key={item}>{t(item)}</li>)}</ul>}
      <p>{t('Previously stored next action')}: {data.next_action||'—'}</p>
      {canAssign&&<p>{t('Owner assignment remains in the buyer management controls.')}</p>}
      {canEdit&&<>
        <form onSubmit={event=>void saveWork(event)}>
          <label><input type="checkbox" checked={priority} disabled={disabled} onChange={e=>setPriority(e.target.checked)}/>{t('Priority company')}</label>
          <label>{t('Priority reason')}<textarea aria-label={t('Priority reason')} required={priority} maxLength={4000} value={reason} disabled={disabled} onChange={e=>setReason(e.target.value)}/></label>
          <label>{t('Next lead action')}<input aria-label={t('Next lead action')} maxLength={200} value={next} disabled={disabled} onChange={e=>setNext(e.target.value)}/></label>
          <label>{t('Follow-up date')}<input aria-label={t('Follow-up date')} type="date" value={due} disabled={disabled} onChange={e=>setDue(e.target.value)}/></label>
          <button type="submit" disabled={disabled}>{t('Save lead work state')}</button>
        </form>
        <form onSubmit={event=>void saveReview(event)}>
          <label>{t('Review person')}<select aria-label={t('Review person')} value={person} disabled={disabled} onChange={e=>{setPerson(e.target.value);setContact('');setOwnership('uncertain');setCited([]);setConfirmed(false);}}>
            <option value="">{t('No named person')}</option>{[...people].map(([id,row])=><option key={id} value={id}>{row.full_name as string||t('Unnamed candidate')}</option>)}
          </select></label>
          <label>{t('Review channel')}<select aria-label={t('Review channel')} value={contact} disabled={disabled} onChange={e=>{setContact(e.target.value);setCited([]);setConfirmed(false);}}>
            <option value="">{t('No direct channel')}</option>{[...channels].filter(([,row])=>!row.person_id||row.person_id===person).map(([id,row])=><option key={id} value={id}>{row.value as string}</option>)}
          </select></label>
          {([[t('Review employment'),employment,setEmployment],[t('Review procurement'),procurement,setProcurement],[t('Review ownership'),ownership,setOwnership]] as const).map(([label,value,set])=><label key={label}>{label}<select aria-label={label} value={value} disabled={disabled} onChange={e=>set(e.target.value as Judgement)}>
            <option value="uncertain">{t('Uncertain')}</option><option value="accepted">{t('Accepted')}</option><option value="rejected">{t('Rejected')}</option>
          </select></label>)}
          <p>{t('Select a person and cite every current source.')}</p>
          {relevant.map(row=><label key={row.id}><input type="checkbox" disabled={disabled||row.redacted} checked={cited.includes(row.id)} onChange={e=>setCited(values=>e.target.checked?[...values,row.id]:values.filter(id=>id!==row.id))}/>{t(row.claim)} · {row.sources[0]?.title??t('Source no longer available.')} · {leadTime(row.checked_at,locale)}</label>)}
          <label>{t('Review rationale')}<textarea aria-label={t('Review rationale')} required maxLength={4000} disabled={disabled} value={rationale} onChange={e=>setRationale(e.target.value)}/></label>
          <label>{t('Conflict resolution')}<textarea aria-label={t('Conflict resolution')} required={relevant.some(row=>row.stance==='refutes')} maxLength={4000} disabled={disabled} value={conflict} onChange={e=>setConflict(e.target.value)}/></label>
          <label><input type="checkbox" disabled={disabled} checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>{t('I checked these sources and purchasing responsibilities.')}</label>
          <button type="submit" disabled={disabled||!person||!confirmed||!relevant.length||cited.length!==relevant.length}>{t('Save purchasing review')}</button>
        </form>
      </>}
    </>}
    <section aria-label={t('Purchasing review history')}>
      <h5>{t('Purchasing review history')}</h5>
      <button disabled={historyBusy||history!==null&&history.length>=historyTotal} onClick={()=>void loadHistory()}>{t('Load purchasing review history')}</button>
      {history!==null&&<p>{history.length} / {historyTotal}</p>}
      {history?.map(row=><article className="activity" key={row.id}>
        <p>{t('Historical review')} · {row.case_version} · {leadTime(row.created_at,locale)}</p>
        <p>{t('Reviewed by')}: {row.recorded_by_user_id}</p>
        <p>{t('Review employment')}: {t(row.employment)} · {t('Review procurement')}: {t(row.procurement_scope)} · {t('Review ownership')}: {t(row.channel_ownership)}</p>
        {row.redacted?<p>{t('Source evidence is unavailable or expired.')}</p>:<><p>{row.rationale}</p>{row.conflict_resolution&&<p>{row.conflict_resolution}</p>}</>}
        <ul>{row.observation_ids.map(id=><li key={id}>{id} · {observations.find(value=>value.id===id)?.content_hash??t('Source no longer available.')}</li>)}</ul>
      </article>)}
    </section>
    <LeadRecovery operation={operation} locale={locale}/>
  </section>;
}
