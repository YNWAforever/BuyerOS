'use client';

import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {useRouter} from 'next/navigation';
import type {components} from '@/services/generated/buyeros-api';
import {useDataMode} from '@/features/providers/data-mode';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
import {cancelRun,getRun,listRuns,retryRun,startResearch,hasUncertainResearch,resetResearchIntent,uncertainResearchBody,subscribeRun,type Run,type RunContext,type RunPage} from '@/services/live/runs';

type Project=components['schemas']['Project'];
type Load={kind:'loading'}|{kind:'ready';page:RunPage}|{kind:'error';message:string};
const LIMITS={query_rounds:3,max_queries_per_run:12,max_results:300,max_pages:200,
  max_page_bytes:2097152,max_duration_seconds:1800,max_model_tokens:100000,provider_concurrency:4} as const;

function nextStep(status:Run['status']):string {
  if(status==='queued')return 'Waiting for the worker to start.';
  if(status==='running')return 'Research is in progress. Review committed buyers at any time.';
  if(status==='cancel_requested')return 'Wait for provider reconciliation; the hold remains.';
  if(status==='partial'||status==='failed')return 'Review committed buyers and resolve the reported issue before retrying.';
  if(status==='paused_budget')return 'Review the approved budget before retrying.';
  if(status==='completed')return 'Review committed buyers and decide the next manual step.';
  return 'No new research work will start.';
}

export function LiveRunProgress({runId,canStart,t,onOpenBuyers}: {
  runId?:string;canStart:boolean;t:(text:string)=>string;onOpenBuyers:()=>void;
}) {
  const {session,client}=useWorkspaceSession(),{apiBaseUrl}=useDataMode(),router=useRouter();
  const scope=session.current(),workspace=scope.workspace,project=scope.project;
  const recovery=workspace&&project?uncertainResearchBody({client,session,apiBaseUrl,workspaceId:workspace,projectId:project}):null;
  const [list,setList]=useState<Load>({kind:'loading'}),[offset,setOffset]=useState(0);
  const [run,setRun]=useState<Run|null>(null),[detailError,setDetailError]=useState(''),[busy,setBusy]=useState(false);
  const [profile,setProfile]=useState<string|null>(null),[target,setTarget]=useState(()=>String(recovery?.target_companies??24));
  const [maxCost,setMaxCost]=useState(()=>recovery?.max_cost.amount??'2.000000'),[reason,setReason]=useState(''),[transport,setTransport]=useState('');
  const busyRef=useRef(false);
  const [uncertain,setUncertain]=useState(false);
  const ctx=useMemo<RunContext|null>(()=>workspace&&project?
    {client,session,apiBaseUrl,workspaceId:workspace,projectId:project}:null,
    [client,session,apiBaseUrl,workspace,project]);
  const current=()=>ctx&&session.current().workspace===ctx.workspaceId&&session.current().project===ctx.projectId;
  const loadPage=useCallback(async(next:number)=>{
    if(!ctx)return;
    try{const page=await listRuns(ctx,next,10);
      if(session.current().workspace===ctx.workspaceId&&session.current().project===ctx.projectId)setList({kind:'ready',page});}
    catch(error){if(session.current().workspace===ctx.workspaceId&&session.current().project===ctx.projectId&&!(error instanceof LiveCancelled))setList({kind:'error',message:describeLiveError(error)});}
  },[ctx,session]);
  useEffect(()=>{
    if(!ctx)return;
    const identity=session.identity(),token=session.token(),own=new AbortController();if(!token)return;
    void client.request<Project>({path:`/v1/workspaces/${encodeURIComponent(ctx.workspaceId)}/projects/${encodeURIComponent(ctx.projectId)}`,
      token,scope:identity,signal:AbortSignal.any([own.signal,session.controller().signal])})
      .then(value=>{if(!own.signal.aborted&&session.isCurrent(identity))setProfile(value.active_icp_version_id??null);})
      .catch(()=>{if(!own.signal.aborted&&session.isCurrent(identity))setProfile(null);});
    return()=>own.abort();
  },[client,session,ctx]);
  useEffect(()=>{
    if(runId||!ctx)return;
    let active=true;
    const identity=session.identity();
    void (async()=>{
      try{const page=await listRuns(ctx,offset,10);if(active&&session.isCurrent(identity))setList({kind:'ready',page});}
      catch(error){if(active&&session.isCurrent(identity)&&!(error instanceof LiveCancelled))setList({kind:'error',message:describeLiveError(error)});}
    })();
    return()=>{active=false;};
  },[ctx,session,runId,offset]);
  useEffect(()=>{
    if(!ctx||!runId)return;
    let active=true;let unsubscribe=()=>{};
    const identity=session.identity();
    void getRun(ctx,runId).then(value=>{
      if(!active||!session.isCurrent(identity))return;
      if(value.project_id!==ctx.projectId){setDetailError('Run not found (404)');return;}
      setRun(value);
      unsubscribe=subscribeRun({runId,afterSequence:value.last_event_sequence,ctx,onEvent:update=>{
        if(!active||!session.isCurrent(identity))return;
        if(update.kind==='connection')setTransport(update.transport);
        if(update.kind==='error')setDetailError(describeLiveError(update.error));
        if(update.kind==='snapshot'){setRun(update.run);setDetailError('');}
        if(update.kind==='event')void getRun(ctx,runId).then(fresh=>{
          if(active&&session.isCurrent(identity)&&fresh.project_id===ctx.projectId){setRun(fresh);setDetailError('');}
        }).catch(error=>{if(active&&session.isCurrent(identity)&&!(error instanceof LiveCancelled))setDetailError(describeLiveError(error));});
      }});
    }).catch(error=>{if(active&&session.isCurrent(identity)&&!(error instanceof LiveCancelled))setDetailError(describeLiveError(error));});
    return()=>{active=false;unsubscribe();};
  },[ctx,session,runId]);
  async function start(){
    if(!ctx||!profile||busyRef.current||!canStart)return;
    const targetCount=Number(target),amount=maxCost.trim();
    if(!Number.isInteger(targetCount)||targetCount<1||targetCount>100||!/^(?:0|[1-9]\d{0,13})(?:\.\d{1,6})?$/.test(amount)||!/[1-9]/.test(amount)){
      setDetailError(t('Enter a target from 1 to 100 and a positive USD cap.'));return;
    }
    const identity=session.identity();
    setMaxCost(`${amount.split('.')[0]}.${(amount.split('.')[1]??'').padEnd(6,'0')}`);
    busyRef.current=true;setBusy(true);setDetailError('');
    try{
      const value=await startResearch(ctx,uncertainResearchBody(ctx)??{icp_version_id:profile,target_companies:targetCount,
        max_cost:{amount:`${amount.split('.')[0]}.${(amount.split('.')[1]??'').padEnd(6,'0')}`,currency:'USD'},limits:{...LIMITS}});
      if(session.isCurrent(identity))router.push(`/app/discover/${encodeURIComponent(value.id)}?${new URLSearchParams({workspace:ctx.workspaceId,project:ctx.projectId})}`);
    }catch(error){if(session.isCurrent(identity)&&!(error instanceof LiveCancelled)){setUncertain(hasUncertainResearch(ctx));setDetailError(describeLiveError(error));}}
    finally{busyRef.current=false;if(session.isCurrent(identity))setBusy(false);}
  }
  async function act(kind:'cancel'|'retry'){
    if(!ctx||!run||busyRef.current||reason.trim().length<3)return;
    busyRef.current=true;setBusy(true);setDetailError('');
    try{const value=kind==='cancel'?await cancelRun(ctx,run,reason.trim(),crypto.randomUUID())
      :await retryRun(ctx,run,reason.trim(),crypto.randomUUID());
      if(current()){setRun(value);setReason('');}
    }catch(error){if(current()&&!(error instanceof LiveCancelled))setDetailError(describeLiveError(error));}
    finally{busyRef.current=false;setBusy(false);}
  }
  if(!ctx)return <section className="panel" role="status">{t('Choose a project to view runs.')}</section>;
  return <section className="panel live-runs" aria-label={t('Research runs')}>
    <div className="inline spread"><h2>{t('Research runs')}</h2>{runId&&<button type="button" onClick={()=>router.push(`/app/runs?${new URLSearchParams({workspace:ctx.workspaceId,project:ctx.projectId})}`)}>{t('All runs')}</button>}</div>
    {detailError&&<p role="alert">{t(detailError)}</p>}
    {!runId&&<>
      <p>{t('Check existing runs before starting new research.')}</p>
      {(uncertain||hasUncertainResearch(ctx))&&<p role="status">{t('The result is unknown. Query existing runs or retry the same research; its key is retained.')}</p>}
      {(uncertain||hasUncertainResearch(ctx))&&<button disabled={busy} onClick={()=>{if(window.confirm(t('The previous research may already exist. Start a new intent?'))){resetResearchIntent(ctx);setUncertain(false);setDetailError('');}}}>{t('Start new research intent')}</button>}
      <div className="run-grid"><label>{t('Target companies')} <input disabled={busy||uncertain||hasUncertainResearch(ctx)} type="number" min="1" max="100" value={target} onChange={event=>setTarget(event.target.value)}/></label>
        <label>{t('Maximum research cost (USD)')} <input disabled={busy||uncertain||hasUncertainResearch(ctx)} inputMode="decimal" value={maxCost} onChange={event=>setMaxCost(event.target.value)}/></label>
        <button type="button" disabled={!canStart||!profile||busy} onClick={()=>void start()}>{busy?t('Starting…'):t(uncertain||hasUncertainResearch(ctx)?'Retry same research':'Start research')}</button></div>
      {!profile&&<p role="status">{t('Approve the current buyer profile before research.')}</p>}
      {list.kind==='loading'&&<p role="status">{t('Loading runs…')}</p>}
      {list.kind==='error'&&<p role="alert">{list.message}<button type="button" onClick={()=>{setList({kind:'loading'});void loadPage(offset);}}>{t('Retry loading')}</button></p>}
      {list.kind==='ready'&&<><p>{t('Actual runs')}: {list.page.total}</p>
        {list.page.items.length===0?<p role="status">{t('No research runs yet.')}</p>:<ul className="run-list">{list.page.items.map(item=><li key={item.id}>
          <button type="button" onClick={()=>router.push(`/app/discover/${encodeURIComponent(item.id)}?${new URLSearchParams({workspace:ctx.workspaceId,project:ctx.projectId})}`)}>
            {t(item.status)} · {item.company_count}/{item.target_companies??'—'} {t('companies')} · {item.created_at}
          </button></li>)}</ul>}
        <div className="inline"><button type="button" disabled={offset===0} onClick={()=>{setList({kind:'loading'});setOffset(Math.max(0,offset-10));}}>{t('Previous')}</button>
          <span>{offset+1}–{Math.min(offset+list.page.items.length,list.page.total)} / {list.page.total}</span>
          <button type="button" disabled={offset+list.page.items.length>=list.page.total} onClick={()=>{setList({kind:'loading'});setOffset(offset+10);}}>{t('Next')}</button></div></>}
    </>}
    {runId&&!run&&!detailError&&<p role="status">{t('Loading run…')}</p>}
    {run&&<article className="run-detail" aria-live="polite">
      <p><strong>{t('Status')}:</strong> {t(run.status)} · <strong>{t('Stage')}:</strong> {t(run.stage)}</p>
      <p>{t('Actual yield')}: {run.company_count} / {run.target_companies??'—'} · {t('Raw candidates')}: {run.raw_count} · {t('Assessed')}: {run.assessed_count}</p>
      <p>{t('Research spend')}: USD {run.spent.amount} · {t('Pending hold')}: USD {run.reserved.amount} · {t('Maximum')}: USD {run.max_cost.amount}</p>
      <p>{t('Attempt')}: {run.attempt} · {t('Event')}: {run.last_event_sequence} · {t('Connection')}: {transport||t('Connecting')}</p>
      <p role="status">{t('Next step')}: {t(nextStep(run.status))}</p>
      {run.status==='cancel_requested'&&<p role="status">{t('New work is stopped. A submitted operation is awaiting reconciliation; its hold remains.')}</p>}
      {run.status==='completed'&&run.target_companies!==undefined&&run.company_count<run.target_companies&&<p role="status">{t('Research completed with fewer companies than the requested target.')}</p>}
      {['partial','paused_budget','failed'].includes(run.status)&&!['fit_review_required','fit'].includes(run.stage)&&<p role="status">{t('Discovery retry waits for authoritative reconciliation; committed results remain available.')}</p>}
      {run.failure_code&&<p role="alert">{t('Reason')}: {run.failure_code}</p>}
      <div className="run-grid">{canStart&&['queued','running','partial','paused_budget','failed'].includes(run.status)&&<label>{t('Reason for action')} <input value={reason} onChange={event=>setReason(event.target.value)} maxLength={2000}/></label>}
        {canStart&&['queued','running','partial','paused_budget','failed'].includes(run.status)&&<button type="button" disabled={busy||reason.trim().length<3} onClick={()=>void act('cancel')}>{t('Stop new work')}</button>}
        {canStart&&['partial','paused_budget','failed'].includes(run.status)&&['fit_review_required','fit'].includes(run.stage)&&<button type="button" disabled={busy||reason.trim().length<3} onClick={()=>void act('retry')}>{t('Retry safe work')}</button>}
        <button type="button" onClick={onOpenBuyers}>{t('Review committed buyers')}</button></div>
    </article>}
  </section>;
}
