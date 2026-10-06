'use client';
import {useEffect,useRef,useState} from 'react';
import {useWorkspaceSession,useSessionSnapshot} from '@/features/providers/workspace-session';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
import type {components} from '@/services/generated/buyeros-api';
import {startJobPoller} from '@/services/live/job-poller';
import {createOperationClient} from '@/services/live/operations';

type Capability={name:string;status:string;reason_codes:string[];checked_at:string;billable:boolean};
type Readiness={ready:boolean;database:string;queue:string;worker:string;checked_at:string};
type Audit={id:string;action:string;entity_type:string;entity_id?:string;occurred_at:string;reason_code?:string;request_id?:string};
type Page<T>={items:T[];offset:number;limit:number;total:number};
type Job=components['schemas']['AsyncJob'];
type Result=components['schemas']['BulkItemResult'];

export function LiveOperations({workspace,project,isAdmin,onOpenBuyers,t}:{workspace:string;project:string|null;isAdmin:boolean;onOpenBuyers:()=>void;t:(value:string)=>string}){
  const {client,session}=useWorkspaceSession();
  const scope=useSessionSnapshot();
  const [readiness,setReadiness]=useState<Readiness|null>(null),[capabilities,setCapabilities]=useState<Capability[]>([]);
  const [jobId,setJobId]=useState(()=>typeof window==='undefined'?'':new URLSearchParams(window.location.search).get('bulk_job')||'');
  const [job,setJob]=useState<Job|null>(null),[jobs,setJobs]=useState<Page<Job>|null>(null),[jobOffset,setJobOffset]=useState(0),[jobStatus,setJobStatus]=useState(()=>typeof window==='undefined'?'':new URLSearchParams(window.location.search).get('job_status')||'');
  const [audit,setAudit]=useState<Page<Audit>|null>(null),[auditOffset,setAuditOffset]=useState(0);
  const [pollError,setPollError]=useState('');
  const [error,setError]=useState(''),[resultLoading,setResultLoading]=useState(false);
  const jobRequest=useRef({sequence:0,controller:new AbortController()});
  const pageView=useRef(job);useEffect(()=>{pageView.current=job;},[job]);
  useEffect(()=>()=>{jobRequest.current.sequence++;jobRequest.current.controller.abort();},[scope.identity]);
  const [profileQueue,setProfileQueue]=useState<'loading'|'none'|'pending'|'current'|'stale'|'unavailable'>(project?'loading':'none');
  const [failedCount,setFailedCount]=useState<number|null|'unavailable'>(null);
  useEffect(()=>{
    const own=new AbortController(),identity=session.identity(),token=session.token();if(!token)return;
    const signal=AbortSignal.any([own.signal,session.controller().signal]);
    void client.request<Page<Capability>>({path:`/v1/workspaces/${workspace}/capabilities`,token,scope:identity,signal}).then(value=>{
      if(session.isCurrent(identity)&&!own.signal.aborted)setCapabilities(value.items);
    }).catch(e=>{if(!(e instanceof LiveCancelled)&&!own.signal.aborted)setError(describeLiveError(e));});
    if(isAdmin)void client.request<Readiness>({path:`/v1/workspaces/${workspace}/readiness`,token,scope:identity,signal}).then(value=>{
      if(session.isCurrent(identity)&&!own.signal.aborted)setReadiness(value);
    }).catch(e=>{if(!(e instanceof LiveCancelled)&&!own.signal.aborted)setError(describeLiveError(e));});
    return()=>own.abort();
  },[client,session,workspace,isAdmin,scope.identity]);
  useEffect(()=>{
    const own=new AbortController(),identity=session.identity(),token=session.token();if(!token)return;
    const query=new URLSearchParams({offset:String(jobOffset),limit:'20'});if(jobStatus)query.set('status',jobStatus);
    void client.request<Page<Job>>({path:`/v1/workspaces/${workspace}/jobs?${query}`,token,scope:identity,
      signal:AbortSignal.any([own.signal,session.controller().signal])}).then(value=>{
      if(session.isCurrent(identity)&&!own.signal.aborted)setJobs(value);
    }).catch(e=>{if(!(e instanceof LiveCancelled)&&!own.signal.aborted)setError(describeLiveError(e));});
    return()=>own.abort();
  },[client,session,workspace,jobOffset,jobStatus,scope.identity]);
  useEffect(()=>{
    const own=new AbortController(),identity=session.identity(),token=session.token();if(!token)return;
    const signal=AbortSignal.any([own.signal,session.controller().signal,AbortSignal.timeout(10_000)]);
    void client.request<Page<Job>>({path:`/v1/workspaces/${workspace}/jobs?status=failed&offset=0&limit=1`,token,scope:identity,signal}).then(value=>{
      if(session.isCurrent(identity)&&!own.signal.aborted)setFailedCount(value.total);
    }).catch(e=>{if(!(e instanceof LiveCancelled)&&!own.signal.aborted&&session.isCurrent(identity)){setFailedCount('unavailable');setError(describeLiveError(e));}});
    if(!project)return()=>own.abort();
    void (async()=>{
      const current=await client.request<{status:string;offer_revision:number}>({path:`/v1/workspaces/${workspace}/projects/${project}`,token,scope:identity,signal});
      const first=await client.request<Page<{approved_at:string|null;basis_offer_revision:number|null}>>({path:`/v1/workspaces/${workspace}/projects/${project}/icp-versions?offset=0&limit=1`,token,scope:identity,signal});
      if(!session.isCurrent(identity)||own.signal.aborted)return;
      if(first.total===0){setProfileQueue('none');return;}
      const latest=first.total===1?first.items[0]:(await client.request<Page<{approved_at:string|null;basis_offer_revision:number|null}>>({
        path:`/v1/workspaces/${workspace}/projects/${project}/icp-versions?offset=${first.total-1}&limit=1`,token,scope:identity,signal})).items[0];
      if(!session.isCurrent(identity)||own.signal.aborted||!latest)return;
      setProfileQueue(current.status!=='active'||latest.basis_offer_revision!==current.offer_revision?'stale':latest.approved_at?'current':'pending');
    })().catch(e=>{if(!(e instanceof LiveCancelled)&&!own.signal.aborted&&session.isCurrent(identity)){setProfileQueue('unavailable');setError(describeLiveError(e));}});
    return()=>own.abort();
  },[client,session,workspace,project,scope.identity]);
  useEffect(()=>{
    if(!isAdmin)return;
    const own=new AbortController(),identity=session.identity(),token=session.token();if(!token)return;
    void client.request<Page<Audit>>({path:`/v1/workspaces/${workspace}/audit-events?offset=${auditOffset}&limit=20`,token,scope:identity,
      signal:AbortSignal.any([own.signal,session.controller().signal])}).then(value=>{
      if(session.isCurrent(identity)&&!own.signal.aborted)setAudit(value);
    }).catch(e=>{if(!(e instanceof LiveCancelled)&&!own.signal.aborted)setError(describeLiveError(e));});
    return()=>own.abort();
  },[client,session,workspace,isAdmin,auditOffset,scope.identity]);
  async function loadJob(requestedId=jobId,resultOffset=0){
    if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(requestedId)){
      setError(t('Enter a valid job ID.'));return;
    }
    const basis=session.captureWriteContext();
    jobRequest.current.controller.abort();
    const own=new AbortController(),sequence=++jobRequest.current.sequence;jobRequest.current.controller=own;
    const isCurrent=()=>sequence===jobRequest.current.sequence&&session.isCurrent(basis.identity)&&!own.signal.aborted;
    setError('');setResultLoading(true);
    try{
      const value=await createOperationClient(client).requestOperation('getAsyncJob',
        {path:{workspace_id:workspace,job_id:requestedId},query:{offset:resultOffset,limit:20}},
        {...basis,signal:AbortSignal.any([basis.signal,own.signal]),isCurrent,getToken:async()=>session.token()||''});
      if(isCurrent())setJob(value);
    }catch(e){if(isCurrent()&&!(e instanceof LiveCancelled))setError(describeLiveError(e));}
    finally{if(isCurrent())setResultLoading(false);}
  }
  const loadJobRef=useRef(loadJob);useEffect(()=>{loadJobRef.current=loadJob;});
  const loadedJobId=job?.id;
  useEffect(()=>{
    if(!loadedJobId||!pageView.current||['completed','failed','cancelled'].includes(pageView.current.status))return;
    const basis=session.captureWriteContext(),own=new AbortController();let terminalSeen=false;
    const ctx={...basis,signal:AbortSignal.any([basis.signal,own.signal]),getToken:async()=>session.token()||'',isCurrent:()=>session.isCurrent(basis.identity)&&!own.signal.aborted};
    return startJobPoller({signal:ctx.signal,isVisible:()=>!document.hidden,
      fetchSummary:signal=>createOperationClient(client).requestOperation('getAsyncJobSummary',{path:{workspace_id:workspace,job_id:loadedJobId}}, {...ctx,signal:AbortSignal.any([ctx.signal,signal])}),
      onValue:summary=>{
        if(!ctx.isCurrent()||pageView.current?.id!==loadedJobId)return;
        setPollError('');setJob(current=>current?.id===summary.id?{...current,...summary}:current);
        if(!terminalSeen&&['completed','failed','cancelled'].includes(summary.status)){
          terminalSeen=true;
          const page=pageView.current?.result_page;
          if(page)void loadJobRef.current(loadedJobId,page.offset);
        }
      },onError:cause=>{if(ctx.isCurrent())setPollError(describeLiveError(cause));},
    });
  // Page changes do not create another poller; the current page is read via pageView.
  },[client,session,workspace,scope.identity,loadedJobId]);
  function changeJob(value:string){jobRequest.current.controller.abort();jobRequest.current.sequence++;setJobId(value);setJob(null);setPollError('');setResultLoading(false);}
  function resultRow(item:Result){return <p key={item.id}><code>{item.id}</code> · {t(item.status)} {item.reason_code||''} <button onClick={()=>void navigator.clipboard?.writeText(item.id)}>{t('Copy buyer ID')}</button></p>;}
  return <section className="panel" aria-label={t('Operations')}><h2>{t('Operations')}</h2>
    <p>{t('Live domain state only. Provider readiness remains blocked until verified.')}</p>
    <div role="region" aria-label={t('Work queue')}><h3>{t('Work queue')}</h3>
      <p>{t('Profile approval')}: {profileQueue==='pending'?'1':profileQueue==='loading'?t('Loading…'):profileQueue==='stale'?t('Profile needs refresh'):profileQueue==='unavailable'?t('Unavailable'):'0'}</p>
      <p>{t('Failed jobs')}: {failedCount===null?t('Loading…'):failedCount==='unavailable'?t('Unavailable'):failedCount}</p>
      <p>{t('Buyer review')}: {t('Open the live buyer list for current review status.')}</p>
      <button disabled={!project} onClick={onOpenBuyers}>{t('Open buyer list')}</button>
    </div>
    {isAdmin&&<div role="region" aria-label={t('Readiness')}><h3>{t('Readiness')}</h3>{readiness?<p>{t('Database')}: {readiness.database} · {t('Queue')}: {readiness.queue} · {t('Worker')}: {readiness.worker} · {readiness.ready?t('Ready'):t('Not ready')}</p>:<p role="status">{t('Loading readiness…')}</p>}</div>}
    <div role="region" aria-label={t('Integrations')}><h3>{t('Integrations')}</h3>{capabilities.map(item=><p key={item.name}>{t(item.name)}: {t(item.status)} · {item.reason_codes.map(t).join(', ')}</p>)}</div>
    <div role="region" aria-label={t('Bulk jobs')}><h3>{t('Bulk jobs')}</h3>
      <label>{t('Filter status')} <select aria-label={t('Filter status')} value={jobStatus} onChange={e=>{setJobOffset(0);setJobStatus(e.target.value);changeJob('');}}>
        <option value="">{t('All statuses')}</option>{['queued','running','cancel_requested','cancelled','completed','failed'].map(value=><option key={value} value={value}>{t(value)}</option>)}
      </select></label>
      {jobs&&<><p>{jobs.total} {t('jobs in scope')}</p>{jobs.items.length?jobs.items.map(item=><div key={item.id} className="inline" style={{flexWrap:'wrap'}}>
        <button onClick={()=>{changeJob(item.id);void loadJob(item.id);}}>{item.id}</button>
        <span>{t(item.status)} · {item.processed}/{item.requested}</span>
      </div>):<p>{t('No jobs in this scope.')}</p>}
        <div className="inline"><button disabled={jobOffset===0} onClick={()=>setJobOffset(Math.max(0,jobOffset-20))}>{t('Previous')}</button>
        <span>{jobs.total?jobOffset+1:0}–{Math.min(jobOffset+20,jobs.total)} / {jobs.total}</span>
        <button disabled={jobOffset+20>=jobs.total} onClick={()=>setJobOffset(jobOffset+20)}>{t('Next')}</button></div>
      </>}
    </div>
    <div role="region" aria-label={t('Job lookup')}><h3>{t('Job lookup')}</h3><label>{t('Job ID')} <input aria-label={t('Job ID')} value={jobId} onChange={e=>changeJob(e.target.value)}/></label>
      <button onClick={()=>void loadJob()}>{t('Load job')}</button>
      {job&&<div role="status"><p>{job.status}: {job.processed}/{job.requested} · {job.updated} {t('updated')} · {job.blocked} {t('blocked')} · {job.conflicts} {t('conflicts')}</p>
        <p>{t('Retry eligibility follows each row’s persisted reason and current version.')}</p>
        {job.result_page?.items.map(resultRow)}
        {job.result_page&&<div className="inline" aria-busy={resultLoading}>
          <button disabled={resultLoading||job.result_page.offset===0} onClick={()=>void loadJob(job.id,Math.max(0,job.result_page!.offset-20))}>{t('Previous results')}</button>
          <span>{job.result_page.total?job.result_page.offset+1:0}–{Math.min(job.result_page.offset+job.result_page.items.length,job.result_page.total)} / {job.result_page.total}</span>
          <button disabled={resultLoading||job.result_page.offset+20>=job.result_page.total} onClick={()=>void loadJob(job.id,job.result_page!.offset+20)}>{t('Next results')}</button>
        </div>}

      </div>}
    </div>
    {isAdmin&&<div role="region" aria-label={t('Audit trail')}><h3>{t('Audit trail')}</h3>{audit?.items.map(item=><p key={item.id}>{item.occurred_at} · {item.action} · {item.entity_type} {item.entity_id||''} · {item.reason_code||''} {item.request_id&&<code>{item.request_id}</code>}</p>)}
      {audit&&<div className="inline"><button disabled={auditOffset===0} onClick={()=>setAuditOffset(Math.max(0,auditOffset-20))}>{t('Previous')}</button><span>{audit.total?auditOffset+1:0}–{Math.min(auditOffset+20,audit.total)} / {audit.total}</span><button disabled={auditOffset+20>=audit.total} onClick={()=>setAuditOffset(auditOffset+20)}>{t('Next')}</button></div>}
    </div>}
    {error&&<p role="alert">{error}</p>}{pollError&&<p role="alert">{pollError}</p>}
  </section>;
}
