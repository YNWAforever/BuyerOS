'use client';
import {useCallback,useEffect,useState} from 'react';
import {useWorkspaceSession,useSessionSnapshot} from '@/features/providers/workspace-session';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
import {loadLeadCase,listLeadEvidence,type LeadObservationRecord} from '@/services/live/lead-workflow';
import type {LeadIntentInput} from '@/services/live/lead-intents';
import {useLeadOperation,LeadRecovery} from './operation';
import {leadText,leadTime,hktInput,hktIso,safeLeadUrl,type LeadLocale} from './copy';

const actions=['observation.append'] as const;
type Claim='employment'|'procurement_scope'|'channel_ownership';
export function LeadEvidencePanel({buyerId,locale,canEdit,onChanged=()=>{}}:{
  buyerId:string;locale:LeadLocale;canEdit:boolean;onChanged?:()=>void;
}){
  const {client,session}=useWorkspaceSession(),snapshot=useSessionSnapshot();
  const [rows,setRows]=useState<LeadObservationRecord[]|null>(null),[error,setError]=useState('');
  const [offset,setOffset]=useState(0),[total,setTotal]=useState(0);
  const [claim,setClaim]=useState<Claim>('employment'),[person,setPerson]=useState('new');
  const [name,setName]=useState(''),[role,setRole]=useState(''),[observed,setObserved]=useState(hktInput());
  const [title,setTitle]=useState(''),[url,setUrl]=useState(''),[excerpt,setExcerpt]=useState('');
  const [kind,setKind]=useState<'official'|'professional'|'other'>('official'),[published,setPublished]=useState('');
  const [rationale,setRationale]=useState(''),[limitations,setLimitations]=useState('');
  const [stance,setStance]=useState<'supports'|'refutes'|'uncertain'>('supports');
  const [channelType,setChannelType]=useState<'business_email'|'business_phone'|'procurement_form'|'referral'>('business_email');
  const [channel,setChannel]=useState('');
  const t=(value:string)=>leadText(locale,value);
  const refresh=useCallback(async()=>{
    const identity=session.identity();
    const [page,current]=await Promise.all([listLeadEvidence(client,session,buyerId,offset,20),loadLeadCase(client,session,buyerId)]);
    if(!session.isCurrent(identity))return;
    setRows(page.items);setTotal(page.total);setObserved(hktInput(current.as_of));setError('');
  },[client,session,buyerId,offset]);
  const readback=useCallback(async()=>{await refresh();onChanged();},[refresh,onChanged]);
  const operation=useLeadOperation(buyerId,actions,readback,locale);
  useEffect(()=>{let active=true;void Promise.resolve().then(refresh).catch(cause=>{if(active&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));});return()=>{active=false;};},[refresh,snapshot.identity]);
  const people=new Map((rows??[]).filter(row=>row.person_id&&row.person).map(row=>[row.person_id!,row.person!]));
  const disabled=operation.busy||operation.unknown||operation.pending.length>0;
  async function save(event:React.FormEvent){
    event.preventDefault();
    const selected=person==='new'?{full_name:name,role:role||null}:person?{person_id:person}:null;
    const input:LeadIntentInput={action:'observation.append',buyer_id:buyerId,payload:{
      claim,stance,person:selected,checked_at:hktIso(observed),
      channel:claim==='channel_ownership'?{type:channelType,value:channel,person_id:person&&person!=='new'?person:null}:null,
      sources:[{title,url,excerpt,source_kind:kind,published_on:published||null,published_precision:published?'date':null}],
      rationale,limitations:limitations||null,
    }};
    await operation.run(input,'Lead evidence saved.');
  }
  return <section className="panel" aria-label={t('Manual lead evidence')}>
    <h4>{t('Manual lead evidence')}</h4>
    <p>{t('Manual source verification does not verify delivery or grant sending permission.')}</p>
    {error&&<p role="alert">{t(error)}</p>}
    {rows===null&&!error&&<p role="status">{t('Loading lead evidence…')}</p>}
    {rows?.length===0&&<p>{t('No manual lead evidence yet.')}</p>}
    {rows?.map(row=><article className="activity" key={row.id}>
      <div><b>{row.person?.full_name as string||t('Department or referral')}</b>
        <p>{t(row.claim==='employment'?'Employment':row.claim==='procurement_scope'?'Purchasing responsibility':'Channel ownership')} · {t(row.stance==='supports'?'Supports':row.stance==='refutes'?'Refutes':'Uncertain')}</p>
        <p>{t('Observed')}: <time dateTime={row.checked_at}>{leadTime(row.checked_at,locale)}</time></p>
        {row.redacted?<p>{t('Source evidence is unavailable or expired.')}</p>:<>
          <p>{row.rationale}</p>{row.limitations&&<p>{row.limitations}</p>}
          {row.channel&&<p>{row.channel.value as string} · {t(row.channel.validity==='provider_marked_valid'?'Technical check: provider marked valid':'Technical check: not tested')}</p>}
          {row.sources.map((source,index)=><div key={`${row.id}:${index}`}>
            {safeLeadUrl(source.url)?<a href={safeLeadUrl(source.url)!} target="_blank" rel="noopener noreferrer">{source.title}</a>:<span>{source.title}</span>}
            <blockquote>{source.excerpt}</blockquote>
            <small>{source.published_on?`${t('Publication date')}: ${source.published_on}`:t('No publication date supplied')}</small>
          </div>)}
        </>}
      </div>
    </article>)}
    {rows&&total>20&&<div className="inline"><button disabled={offset===0} onClick={()=>setOffset(value=>Math.max(0,value-20))}>{t('Previous page')}</button>
      <span>{offset+1}–{Math.min(total,offset+rows.length)} / {total}</span>
      <button disabled={offset+rows.length>=total} onClick={()=>setOffset(value=>value+rows.length)}>{t('Next page')}</button></div>}
    {canEdit&&<form onSubmit={event=>void save(event)}>
      <div className="grid two-col">
        <label>{t('Evidence claim')}<select aria-label={t('Evidence claim')} value={claim} disabled={disabled} onChange={e=>setClaim(e.target.value as Claim)}>
          <option value="employment">{t('Employment')}</option><option value="procurement_scope">{t('Purchasing responsibility')}</option><option value="channel_ownership">{t('Channel ownership')}</option>
        </select></label>
        <label>{t('Evidence person')}<select aria-label={t('Evidence person')} value={person} disabled={disabled} onChange={e=>setPerson(e.target.value)}>
          <option value="new">{t('New person')}</option>{claim==='channel_ownership'&&<option value="">{t('Department or referral')}</option>}
          {[...people].map(([id,p])=><option key={id} value={id}>{p.full_name as string}</option>)}
        </select></label>
      </div>
      {person==='new'&&<div className="grid two-col"><label>{t('Person name')}<input aria-label={t('Person name')} required maxLength={200} disabled={disabled} value={name} onChange={e=>setName(e.target.value)}/></label>
        <label>{t('Person role')}<input aria-label={t('Person role')} maxLength={200} disabled={disabled} value={role} onChange={e=>setRole(e.target.value)}/></label></div>}
      {claim==='channel_ownership'&&<div className="grid two-col"><label>{t('Channel type')}<select aria-label={t('Channel type')} value={channelType} disabled={disabled} onChange={e=>setChannelType(e.target.value as typeof channelType)}>
        <option value="business_email">{t('Business email')}</option><option value="business_phone">{t('Business phone')}</option><option value="procurement_form">{t('Procurement form')}</option><option value="referral">{t('Referral link')}</option>
      </select></label><label>{t('New channel value')}<input aria-label={t('New channel value')} required maxLength={400} disabled={disabled} value={channel} onChange={e=>setChannel(e.target.value)}/></label></div>}
      <div className="grid two-col"><label>{t('Evidence observed at (Hong Kong)')}<input aria-label={t('Evidence observed at (Hong Kong)')} type="datetime-local" required disabled={disabled} value={observed} onChange={e=>setObserved(e.target.value)}/></label>
        <label>{t('Source stance')}<select aria-label={t('Source stance')} value={stance} disabled={disabled} onChange={e=>setStance(e.target.value as typeof stance)}><option value="supports">{t('Supports')}</option><option value="refutes">{t('Refutes')}</option><option value="uncertain">{t('Uncertain')}</option></select></label></div>
      <label>{t('Evidence source title')}<input aria-label={t('Evidence source title')} required maxLength={300} disabled={disabled} value={title} onChange={e=>setTitle(e.target.value)}/></label>
      <label>{t('Evidence source URL')}<input aria-label={t('Evidence source URL')} type="url" required maxLength={2048} disabled={disabled} value={url} onChange={e=>setUrl(e.target.value)}/></label>
      <label>{t('Evidence excerpt')}<textarea aria-label={t('Evidence excerpt')} required maxLength={4000} disabled={disabled} value={excerpt} onChange={e=>setExcerpt(e.target.value)}/></label>
      <div className="grid two-col"><label>{t('Source type')}<select aria-label={t('Source type')} value={kind} disabled={disabled} onChange={e=>setKind(e.target.value as typeof kind)}><option value="official">{t('Official')}</option><option value="professional">{t('Professional')}</option><option value="other">{t('Other')}</option></select></label>
        <label>{t('Publication date (optional)')}<input aria-label={t('Publication date (optional)')} type="date" disabled={disabled} value={published} onChange={e=>setPublished(e.target.value)}/></label></div>
      <label>{t('Evidence rationale')}<textarea aria-label={t('Evidence rationale')} required maxLength={4000} disabled={disabled} value={rationale} onChange={e=>setRationale(e.target.value)}/></label>
      <label>{t('Evidence limitations')}<textarea aria-label={t('Evidence limitations')} maxLength={4000} disabled={disabled} value={limitations} onChange={e=>setLimitations(e.target.value)}/></label>
      <button type="submit" disabled={disabled}>{t('Save lead evidence')}</button>
    </form>}
    <LeadRecovery operation={operation} locale={locale}/>
  </section>;
}
