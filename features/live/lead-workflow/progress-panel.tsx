'use client';
import {useCallback,useEffect,useRef,useState} from 'react';
import {LeadLink} from './link';
import {useOwnerDirectory} from './owner-directory';
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
export function LeadProgressPanel({mode,locale,canEdit=false,canAssign=false,onNavigate,ownMembershipId=null}:{
  mode:'overview'|'queue';locale:LeadLocale;canEdit?:boolean;canAssign?:boolean;onNavigate?:(path:string)=>void;ownMembershipId?:string|null;
}){
  const {client,session}=useWorkspaceSession(),snapshot=useSessionSnapshot(),params=useSearchParams();
  const criterion=params.get('lead_qualifies')??'',stage=params.get('lead_stage')??'';
  const owner=params.get('lead_owner')??'',due=params.get('lead_due')??'';
  const directory=useOwnerDirectory(ownMembershipId,mode==='queue'&&canAssign);
  const queryKey=JSON.stringify([criterion,stage,owner,due]);
  const [projection,setProjection]=useState<{query:string;offset:number;value:LeadProgressPage}|null>(null);
  const [error,setError]=useState(''),[loading,setLoading]=useState(false);
  const [paging,setPaging]=useState({query:queryKey,offset:0}),[selected,setSelected]=useState(''),[reload,setReload]=useState(0);
  const sequence=useRef(0);
  if(paging.query!==queryKey){setPaging({query:queryKey,offset:0});if(selected)setSelected('');}
  const offset=paging.query===queryKey?paging.offset:0;
  const page=projection?.query===queryKey&&projection.offset===offset?projection.value:null;
  function setOffset(update:number|((value:number)=>number)){
    setPaging(current=>({query:queryKey,offset:typeof update==='function'?update(current.query===queryKey?current.offset:0):update}));
  }
  const t=(value:string)=>leadText(locale,value);
  const refresh=useCallback(async(signal:AbortSignal)=>{
    const identity=session.identity(),serial=++sequence.current;
    const current=()=>!signal.aborted&&serial===sequence.current&&session.isCurrent(identity);
    const filters:LeadFilters={
      ...(criteria.includes(criterion as typeof criteria[number])?{qualifies_for:criterion as typeof criteria[number]}:{}),
      ...(stages.includes(stage as typeof stages[number])?{stage:stage as typeof stages[number]}:{}),
      ...(owner==='unassigned'?{owner_unassigned:true}:owner==='mine'?(directory.ownUserId?{owner_user_id:directory.ownUserId}:{}):owner?{owner_user_id:owner}:{}),...(due?{due_before:due}:{}),
    };
    try{
      if(signal.aborted)return;
      if(owner==='mine'&&!directory.ownUserId){
        setProjection(null);setLoading(false);
        setError(directory.loading?'':'Your current member identity is unavailable.');return;
      }
      setLoading(true);setError('');
      const value=await loadLeadProgress(client,session,filters,signal,offset,20);
      if(current()){setProjection({query:queryKey,offset,value});setError('');}
    }catch(cause){
      if(current()&&!(cause instanceof LiveCancelled)){setProjection(null);setError(describeLiveError(cause));}
    }finally{if(current())setLoading(false);}
  },[client,session,criterion,stage,owner,due,offset,queryKey,directory.ownUserId,directory.loading]);
  useEffect(()=>{
    const own=new AbortController();
    void Promise.resolve().then(()=>refresh(own.signal));
    return()=>own.abort();
  },[refresh,snapshot.identity,reload]);
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
      {mode==='queue'&&<>
        <p>{t('Follow-up dates are reminders; no automatic jobs are started.')}</p>
        <label>{t('Work stage')}<select aria-label={t('Work stage')} value={stage} onChange={e=>filter({lead_stage:e.target.value})}>
          <option value="">{t('All stages')}</option>{stages.map(value=><option key={value} value={value}>{t(value)}</option>)}
        </select></label>
        {canAssign&&<label>{t('Find owner')}<input type="search" aria-label={t('Find owner')} value={directory.search} maxLength={200} onChange={e=>directory.setSearch(e.target.value)}/></label>}
        {directory.loading&&<p role="status">{t('Loading members…')}</p>}
        {directory.error&&<p role="alert">{directory.error} <button onClick={directory.retry}>{t('Retry members')}</button></p>}
        <label>{t('Owner')}<select aria-label={t('Owner')} value={owner} onChange={e=>filter({lead_owner:e.target.value})}>
          <option value="">{t('All owners')}</option><option value="mine" disabled={!directory.ownUserId}>{t('Mine')}</option><option value="unassigned">{t('Unassigned')}</option>
          {owner&&!['mine','unassigned'].includes(owner)&&!directory.items.some(row=>row.user_id===owner)&&<option value={owner}>{directory.name(owner)||t('Unavailable member')}</option>}
          {directory.items.map(member=><option key={member.membership_id} value={member.user_id}>{member.display_name===member.user_id?t('Unavailable member'):member.display_name} · {member.membership_id.slice(-6)}</option>)}
        </select></label>
        {directory.offset+directory.items.length<directory.total&&<button disabled={directory.loading} onClick={directory.more}>{t('More members')}</button>}
        <label>{t('Due on or before')}<input aria-label={t('Due on or before')} type="date" value={due} onChange={e=>filter({lead_due:e.target.value})}/></label>
        <LeadLink onNavigate={onNavigate} href={url('/app/operations')}>{t('Clear lead filters')}</LeadLink>
      </>}
    {page&&!error&&<>
      <div className="grid two-col">{metrics.map(([key,metric,label,target])=><LeadLink key={key} onNavigate={onNavigate} href={url('/app/operations',{lead_qualifies:key})}>{t(label)}: {page.metrics[metric]} / {target}</LeadLink>)}</div>
      <p>{t('As of')}: <time dateTime={page.as_of}>{leadTime(page.as_of,locale)}</time></p>
      {mode==='queue'&&<>
        <p>{t('Matching companies')}: {page.total}</p>
        {page.items.length===0&&<p>{t('No matching companies.')}</p>}
        {page.items.map(row=><article className="activity lead-queue-item" key={row.buyer_id} data-lead-buyer={row.buyer_id}>
          <h3>{row.company_name}</h3><p>{t(row.stage)}</p><p>{row.next_action||t('Next action not recorded.')}</p>
          <p>{t('Follow-up date')}: {row.due_on??t('Unknown')} · {t('Owner')}: {row.owner_user_id?(directory.name(row.owner_user_id)||t('Unavailable member')):t('Unassigned')}</p>
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
