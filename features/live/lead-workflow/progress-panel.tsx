'use client';
import {useCallback,useEffect,useState} from 'react';
import {LeadLink} from './link';
import {useSearchParams} from 'next/navigation';
import {useWorkspaceSession,useSessionSnapshot} from '@/features/providers/workspace-session';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
import {loadLeadProgress,type LeadFilters,type LeadProgressPage} from '@/services/live/lead-workflow';
import {LeadEvidencePanel} from './evidence-panel';
import {LeadCasePanel} from './case-panel';
import {leadText,leadTime,type LeadLocale} from './copy';
const stages=['find_person','verify_employment','verify_procurement','verify_channel','refresh_evidence','review_preparation','complete'] as const;
const criteria=['company_card','priority_company','qualified_person','direct_channel','reviewed_preparation'] as const;
const metrics=[
  ['company_card','company_cards','Company evidence',24],['priority_company','priority_companies','Priority companies',8],
  ['qualified_person','qualified_people_companies','Purchasing people',6],['direct_channel','direct_channel_companies','Direct channels',4],
  ['reviewed_preparation','reviewed_preparation_companies','Reviewed preparations',4],
] as const;
export function LeadProgressPanel({mode,locale,canEdit=false,onNavigate}:{
  mode:'overview'|'queue';locale:LeadLocale;canEdit?:boolean;onNavigate?:(path:string)=>void;
}){
  const {client,session}=useWorkspaceSession(),snapshot=useSessionSnapshot(),params=useSearchParams();
  const criterion=params.get('lead_qualifies')??'',stage=params.get('lead_stage')??'';
  const owner=params.get('lead_owner')??'',due=params.get('lead_due')??'';
  const [page,setPage]=useState<LeadProgressPage|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(false);
  const [offset,setOffset]=useState(0),[selected,setSelected]=useState(''),[reload,setReload]=useState(0);
  const t=(value:string)=>leadText(locale,value);
  const refresh=useCallback(async()=>{
    const identity=session.identity();
    const filters:LeadFilters={
      ...(criteria.includes(criterion as typeof criteria[number])?{qualifies_for:criterion as typeof criteria[number]}:{}),
      ...(stages.includes(stage as typeof stages[number])?{stage:stage as typeof stages[number]}:{}),
      ...(owner?{owner_user_id:owner}:{}),...(due?{due_before:due}:{}),
    };
    try{
      setLoading(true);
      const value=await loadLeadProgress(client,session,filters,undefined,offset,20);
      if(session.isCurrent(identity)){setPage(value);setError('');}
    }catch(cause){
      if(session.isCurrent(identity)&&!(cause instanceof LiveCancelled)){setPage(null);setError(describeLiveError(cause));}
    }finally{if(session.isCurrent(identity))setLoading(false);}
  },[client,session,criterion,stage,owner,due,offset]);
  useEffect(()=>{void Promise.resolve().then(refresh);},[refresh,snapshot.identity,reload]);
  function url(path:string,extra:Record<string,string>={}){
    const scope=session.current();return `${path}?${new URLSearchParams({workspace:scope.workspace!,project:scope.project!,...extra})}`;
  }
  function filter(value:Record<string,string>){
    setOffset(0);setSelected('');
    const next=url('/app/operations',{...(criterion?{lead_qualifies:criterion}:{}),...(stage?{lead_stage:stage}:{}),
      ...(owner?{lead_owner:owner}:{}),...(due?{lead_due:due}:{}),...value});
    if(onNavigate)onNavigate(next);
  }
  return <section className="panel" aria-label={t('Lead workflow')}>
    <h2>{t('Lead workflow')}</h2>
    <p>{t('Targets count different companies. Fixture data does not count as real leads.')}</p>
    {loading&&<p role="status">{t('Loading lead progress…')}</p>}
    {error&&<p role="alert">{t('Lead progress unavailable.')} {t(error)}</p>}
    {page&&!error&&<>
      <div className="grid two-col">{metrics.map(([key,metric,label,target])=><LeadLink key={key} onNavigate={onNavigate} href={url('/app/operations',{lead_qualifies:key})}>{t(label)}: {page.metrics[metric]} / {target}</LeadLink>)}</div>
      <p>{t('As of')}: <time dateTime={page.as_of}>{leadTime(page.as_of,locale)}</time></p>
      {mode==='queue'&&<>
        <p>{t('Follow-up dates are reminders; no automatic jobs are started.')}</p>
        <label>{t('Work stage')}<select aria-label={t('Work stage')} value={stage} onChange={e=>filter({lead_stage:e.target.value})}>
          <option value="">{t('All stages')}</option>{stages.map(value=><option key={value} value={value}>{t(value)}</option>)}
        </select></label>
        <label>{t('Owner user ID')}<input aria-label={t('Owner user ID')} defaultValue={owner} onBlur={e=>{if(e.target.value!==owner)filter({lead_owner:e.target.value});}}/></label>
        <label>{t('Due on or before')}<input aria-label={t('Due on or before')} type="date" value={due} onChange={e=>filter({lead_due:e.target.value})}/></label>
        <LeadLink onNavigate={onNavigate} href={url('/app/operations')}>{t('Clear lead filters')}</LeadLink>
        <p>{t('Matching companies')}: {page.total}</p>
        {page.items.length===0&&<p>{t('No matching companies.')}</p>}
        {page.items.map(row=><article className="activity" key={row.buyer_id} data-lead-buyer={row.buyer_id}>
          <h3>{row.company_name}</h3><p>{t(row.stage)}</p><p>{row.next_action||t('Next action not recorded.')}</p>
          <p>{t('Follow-up date')}: {row.due_on??t('Unknown')} · {t('Owner')}: {row.owner_user_id??t('Unassigned')}</p>
          {row.quality.blockers.map(value=><p key={value}>{t(value)}</p>)}
          <div className="inline"><button onClick={()=>setSelected(value=>value===row.buyer_id?'':row.buyer_id)}>{t('Review company evidence')}</button>
            <LeadLink onNavigate={onNavigate} href={url('/app/outreach',{buyer:row.buyer_id})}>{t('Prepare contact content')}</LeadLink>
            <LeadLink onNavigate={onNavigate} href={url('/app/discover',{q:row.company_name})}>{t('Company dossier')}</LeadLink></div>
          {selected===row.buyer_id&&<>
            <LeadEvidencePanel key={`e:${row.buyer_id}`} buyerId={row.buyer_id} locale={locale} canEdit={canEdit} onChanged={()=>setReload(v=>v+1)}/>
            <LeadCasePanel key={`c:${row.buyer_id}`} buyerId={row.buyer_id} locale={locale} canEdit={canEdit} contextVersion={row.version} onChanged={()=>setReload(v=>v+1)}/>
          </>}
        </article>)}
        <div className="inline"><button disabled={offset===0||loading} onClick={()=>setOffset(v=>Math.max(0,v-20))}>{t('Previous page')}</button>
          <span>{page.total?offset+1:0}–{Math.min(offset+page.items.length,page.total)} / {page.total}</span>
          <button disabled={offset+page.items.length>=page.total||loading} onClick={()=>setOffset(v=>v+20)}>{t('Next page')}</button></div>
      </>}
    </>}
    <button disabled={loading} onClick={()=>setReload(v=>v+1)}>{t('Refresh lead progress')}</button>
  </section>;
}
