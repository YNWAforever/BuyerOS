'use client';
import {useEffect,useMemo,useRef,useState} from 'react';
import {useSearchParams} from 'next/navigation';
import {readLatestProfile} from '@/services/live/profile-read';
import {buildJobQuery,jobQueryParams,readJobStatus,type JobScope} from '@/services/live/job-query';
import {useWorkspaceSession,useSessionSnapshot} from '@/features/providers/workspace-session';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
import type {components} from '@/services/generated/buyeros-api';
import {startJobPoller} from '@/services/live/job-poller';
import {createOperationClient} from '@/services/live/operations';

type Capability=components['schemas']['Capability'];
type Readiness=components['schemas']['Readiness'];
type Audit={id:string;action:string;entity_type:string;entity_id?:string;occurred_at:string;reason_code?:string;request_id?:string};
type Page<T>={items:T[];offset:number;limit:number;total:number};
type Job=components['schemas']['AsyncJob'];
type Result=components['schemas']['BulkItemResult'];

const capabilityNames=['research','contact_enrichment','draft_generation','mailbox','crm'];
const capabilityStatuses:Record<Capability['status'],string>={unconfigured:'Not configured',blocked:'Blocked',ready:'Ready',degraded:'Needs attention',disabled:'Disabled'};
const unknownAdvice='Capability verification is unavailable. Keep this capability disabled and contact the release owner.';
function capabilityView(item:Capability){
  const value=item&&typeof item==='object'?item:null;
  const name=value&&capabilityNames.includes(value.name)?value.name:'Unknown capability';
  const bounded=(text:unknown,max:number):text is string=>typeof text==='string'&&text.trim().length>0&&text.length<=max;
  const valid=value&&name!=='Unknown capability'&&typeof value.status==='string'&&Object.hasOwn(capabilityStatuses,value.status)
    &&bounded(value.owner_role,80)&&bounded(value.next_action,512)&&typeof value.billable==='boolean'
    &&bounded(value.checked_at,80)&&Number.isFinite(Date.parse(value.checked_at))
    &&Array.isArray(value.reason_codes)&&value.reason_codes.length<=20&&value.reason_codes.every(code=>bounded(code,120))
    &&(value.status!=='ready'||value.reason_codes.length===0);
  return {name,status:valid?capabilityStatuses[value.status]:'Unknown',owner:valid?value.owner_role:'Release owner',
    nextAction:valid?value.next_action:unknownAdvice,checkedAt:valid?value.checked_at:null,
    reason:valid?(value.reason_codes.includes('live_providers_not_activated')?'Live provider capabilities have not been verified.':'Review the current capability state before use.'):unknownAdvice,
    codes:valid?value.reason_codes:[]};
}

export function LiveOperations({workspace,project,isAdmin,onOpenBuyers,t}:{workspace:string;project:string|null;isAdmin:boolean;onOpenBuyers:()=>void;t:(value:string)=>string}){
  const {client,session}=useWorkspaceSession();
  const scope=useSessionSnapshot(),searchParams=useSearchParams();
  const [readinessState,setReadiness]=useState<{key:string;value?:Readiness;error?:string}>();
  const [capabilityState,setCapabilities]=useState<{key:string;items?:Capability[];error?:string}>();
  const [statusReload,setStatusReload]=useState(0);
  const readiness=readinessState?.key===scope.identity?readinessState.value:undefined;
  const readinessError=readinessState?.key===scope.identity?readinessState.error:undefined;
  const capabilities=capabilityState?.key===scope.identity?capabilityState.items:undefined;
  const capabilityError=capabilityState?.key===scope.identity?capabilityState.error:undefined;
  const [jobId,setJobId]=useState(()=>typeof window==='undefined'?'':new URLSearchParams(window.location.search).get('bulk_job')||'');
  const [job,setJob]=useState<Job|null>(null);
  const [statusChoice,setStatusChoice]=useState<{value:ReturnType<typeof readJobStatus>}>();
  const jobStatus=statusChoice?statusChoice.value:readJobStatus(searchParams.get('job_status'));
  const [viewChoice,setViewChoice]=useState<'project'|'workspace'>();
  const jobView=viewChoice??(searchParams.get('job_scope')==='workspace'?'workspace':'project');
  const waitingForProject=jobView==='project'&&!project&&searchParams.has('project');
  const jobScope=useMemo<JobScope>(()=>jobView==='project'&&project?{kind:'project',workspaceId:workspace,projectId:project}:{kind:'workspace',workspaceId:workspace},[jobView,workspace,project]);
  const scopeKey=`${scope.identity}:${jobScope.kind}`,viewKey=`${scopeKey}:${jobStatus??''}`;
  const [offsetState,setOffset]=useState<{key:string;offset:number}>(),[listState,setList]=useState<{key:string;page?:Page<Job>;error?:string}>();
  const jobOffset=offsetState?.key===viewKey?offsetState.offset:0,listKey=`${viewKey}:${jobOffset}`;
  const jobs=listState?.key===listKey?listState.page:undefined,jobError=listState?.key===listKey?listState.error:undefined;
  const [listReload,setListReload]=useState(0);
  const setJobOffset=(offset:number)=>setOffset({key:viewKey,offset});
  const [audit,setAudit]=useState<Page<Audit>|null>(null),[auditOffset,setAuditOffset]=useState(0);
  const [pollError,setPollError]=useState('');
  const [error,setError]=useState(''),[resultLoading,setResultLoading]=useState(false);
  const jobRequest=useRef({sequence:0,controller:new AbortController()});
  const pageView=useRef(job);useEffect(()=>{pageView.current=job;},[job]);
  useEffect(()=>()=>{jobRequest.current.sequence++;jobRequest.current.controller.abort();},[scope.identity]);
  const [profileQueue,setProfileQueue]=useState<'loading'|'none'|'pending'|'current'|'stale'|'unavailable'>(project?'loading':'none');
  const [failedState,setFailed]=useState<{key:string;count:number|'unavailable'}>();
  const failedCount=failedState?.key===scopeKey?failedState.count:null;
  useEffect(()=>{
    if(!session.token()||session.current().workspace!==workspace)return;
    const own=new AbortController(),basis=session.captureWriteContext();
    const ctx={...basis,signal:AbortSignal.any([own.signal,basis.signal]),getToken:async()=>session.token()||'',isCurrent:()=>session.isCurrent(basis.identity)&&!own.signal.aborted};
    void createOperationClient(client).requestOperation('getCapabilities',{path:{workspace_id:workspace}},ctx).then(value=>{
      if(!Array.isArray(value.items))throw new Error('Invalid capability page');
      if(ctx.isCurrent())setCapabilities({key:basis.identity,items:value.items});
    }).catch(e=>{if(ctx.isCurrent()&&!(e instanceof LiveCancelled))setCapabilities({key:basis.identity,error:describeLiveError(e)});});
    if(isAdmin)void createOperationClient(client).requestOperation('getReadiness',{path:{workspace_id:workspace}},ctx).then(value=>{
      if(ctx.isCurrent())setReadiness({key:basis.identity,value});
    }).catch(e=>{if(ctx.isCurrent()&&!(e instanceof LiveCancelled))setReadiness({key:basis.identity,error:describeLiveError(e)});});
    return()=>own.abort();
  },[client,session,workspace,isAdmin,scope.identity,statusReload]);
  useEffect(()=>{
    if(waitingForProject)return;
    const own=new AbortController(),basis=session.captureWriteContext();
    const ctx={...basis,signal:AbortSignal.any([own.signal,basis.signal]),getToken:async()=>session.token()||'',isCurrent:()=>session.isCurrent(basis.identity)&&!own.signal.aborted};
    void createOperationClient(client).requestOperation('listAsyncJobs',{path:{workspace_id:workspace},query:jobQueryParams(jobScope,{offset:jobOffset,limit:20,status:jobStatus})},ctx)
      .then(page=>{if(ctx.isCurrent())setList({key:listKey,page});})
      .catch(cause=>{if(ctx.isCurrent()&&!(cause instanceof LiveCancelled))setList({key:listKey,error:describeLiveError(cause)});});
    return()=>own.abort();
  },[client,session,workspace,jobScope,jobOffset,jobStatus,scope.identity,listKey,listReload,waitingForProject]);
  // Router query state can settle before window.location during Vinext navigation.
  // Persist only deliberate choices; never overwrite an incoming deep link on mount.
  function updateJobUrl(kind:'project'|'workspace',status:ReturnType<typeof readJobStatus>){
    const url=new URL(window.location.href);url.searchParams.set('job_scope',kind);
    if(status)url.searchParams.set('job_status',status);else url.searchParams.delete('job_status');
    url.searchParams.delete('job_offset');url.searchParams.delete('bulk_job');
    window.history.replaceState(window.history.state,'',url.pathname+url.search+url.hash);
  }
  function setJobStatus(value:ReturnType<typeof readJobStatus>){setStatusChoice({value});updateJobUrl(jobScope.kind,value);}
  function setJobView(kind:'project'|'workspace'){setViewChoice(kind);updateJobUrl(kind,jobStatus);}
  useEffect(()=>{
    const own=new AbortController(),identity=session.identity(),token=session.token();if(!token)return;
    const signal=AbortSignal.any([own.signal,session.controller().signal,AbortSignal.timeout(10_000)]);
    if(waitingForProject)return()=>own.abort();
    void client.request<Page<Job>>({path:`/v1/workspaces/${workspace}/jobs?${buildJobQuery(jobScope,{status:'failed',offset:0,limit:1})}`,token,scope:identity,signal}).then(value=>{
      if(session.isCurrent(identity)&&!own.signal.aborted)setFailed({key:scopeKey,count:value.total});
    }).catch(e=>{if(!(e instanceof LiveCancelled)&&!own.signal.aborted&&session.isCurrent(identity)){setFailed({key:scopeKey,count:'unavailable'});setError(describeLiveError(e));}});
    if(!project)return()=>own.abort();
    void (async()=>{
      const current=await client.request<{status:string;offer_revision:number}>({path:`/v1/workspaces/${workspace}/projects/${project}`,token,scope:identity,signal});
      const latest=await readLatestProfile(client,session,project,signal);
      if(!session.isCurrent(identity)||own.signal.aborted)return;
      if(!latest){setProfileQueue('none');return;}
      setProfileQueue(current.status!=='active'||latest.basis_offer_revision!==current.offer_revision?'stale':latest.approved_at?'current':'pending');
    })().catch(e=>{if(!(e instanceof LiveCancelled)&&!own.signal.aborted&&session.isCurrent(identity)){setProfileQueue('unavailable');setError(describeLiveError(e));}});
    return()=>own.abort();
  },[client,session,workspace,project,scope.identity,jobScope,scopeKey,listReload,waitingForProject]);
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
    {isAdmin&&<div role="region" aria-label={t('Readiness')}><h3>{t('Readiness')}</h3>
      {readiness?<><p>{t('Database')}: {t(readiness.database)} · {t('Queue')}: {t(readiness.queue)} · {t('Worker')}: {t(readiness.worker)} · {readiness.ready===true&&readiness.database==='ready'&&readiness.queue==='ready'&&readiness.worker==='ready'&&Number.isFinite(Date.parse(readiness.checked_at))?t('Ready'):t('Not ready')}</p>
        <p>{t('Checked at')}: <time dateTime={readiness.checked_at}>{readiness.checked_at}</time></p></>:readinessError?<p role="alert">{t(readinessError)}</p>:<p role="status">{t('Loading readiness…')}</p>}
      <p>{t('Responsible role: {role}').replace('{role}','SRE')}</p><p>{t('Next action')}: {t(readiness?.database==='unavailable'?'Check the database connection and current workspace access, then refresh.':'Check worker and queue status, then refresh.')}</p>
    </div>}
    <div role="region" aria-label={t('Integrations')}><h3>{t('Integrations')}</h3>
      {capabilities?capabilities.length?capabilities.map((item,index)=>{const view=capabilityView(item);return <div role="region" aria-label={t('Capability: {name}').replace('{name}',t(view.name))} key={`${view.name}:${index}`}>
        <h4>{t(view.name)}: {t(view.status)}</h4><p>{t(view.reason)}</p>
        <p>{t('Responsible role: {role}').replace('{role}',t(view.owner))}</p>
        <p>{t('Next action')}: {t(view.nextAction)}</p>
        <p>{t('Checked at')}: {view.checkedAt?<time dateTime={view.checkedAt}>{view.checkedAt}</time>:t('Unknown')}</p>
        {view.codes.length>0&&<details><summary>{t('Technical details')}</summary><p>{view.codes.join(', ')}</p></details>}
      </div>;}):<p>{t(unknownAdvice)}</p>:capabilityError?<><p role="alert">{t(capabilityError)}</p><p>{t(unknownAdvice)}</p></>:<p role="status">{t('Loading capabilities…')}</p>}
      <button onClick={()=>{setCapabilities(undefined);setReadiness(undefined);setStatusReload(value=>value+1);}}>{t('Refresh service status')}</button>
    </div>
    <div role="region" aria-label={t('Bulk jobs')}><h3>{t('Bulk jobs')}</h3>
      <label>{t('Job scope')} <select aria-label={t('Job scope')} value={jobScope.kind} onChange={e=>{setJobView(e.target.value as 'project'|'workspace');changeJob('');}}>
        <option value="project" disabled={!project}>{t('Project jobs')}</option><option value="workspace">{t('Workspace jobs')}</option>
      </select></label>
      <p>{t(jobScope.kind==='project'?'Project jobs':'Workspace jobs')}</p><details><summary>{t('Technical details')}</summary><code>{jobScope.kind==='project'?jobScope.projectId:jobScope.workspaceId}</code></details>
      {!isAdmin&&<p>{t('Only jobs created by your account are included.')}</p>}
      <label>{t('Filter status')} <select aria-label={t('Filter status')} value={jobStatus??''} onChange={e=>{setJobStatus(readJobStatus(e.target.value));changeJob('');}}>
        <option value="">{t('All statuses')}</option>{['queued','running','cancel_requested','cancelled','completed','failed'].map(value=><option key={value} value={value}>{t(value)}</option>)}
      </select></label>
      {!jobs&&!jobError&&<p role="status">{t('Loading jobs…')}</p>}
      {jobError&&<><p role="alert">{jobError}</p><button onClick={()=>setListReload(v=>v+1)}>{t('Retry loading jobs')}</button></>}
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
      {job&&<div role="region" aria-label={t('Job details')}><p role="status" aria-atomic="true">{t(job.status)}</p><p>{job.processed}/{job.requested} · {job.updated} {t('updated')} · {job.blocked} {t('blocked')} · {job.conflicts} {t('conflicts')}</p>
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
