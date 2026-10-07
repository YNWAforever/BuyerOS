'use client';
import {useEffect,useMemo,useRef,useState} from 'react';
import {liveZh} from './locale';
import type {components} from '@/services/generated/buyeros-api';
import {useWorkspaceSession,useSessionSnapshot} from '@/features/providers/workspace-session';
import {assignmentRecovery,freezeBulkAssignment,type FrozenBulkAssignment} from '@/services/live/bulk-confirmation';
import {startJobPoller} from '@/services/live/job-poller';
import {ActionIntent} from '@/services/live/action-intent';
import {downloadText} from '@/services/live/download-text';
import {readExportContent,type ExportJob} from '@/services/live/exports';
import {LiveCancelled,LiveError,describeLiveError} from '@/services/live/client';
import {buyerOperationContext} from '@/services/live/buyers';
import type {ReviewSelection} from '@/services/live/buyer-selection';
import {createOperationClient} from '@/services/live/operations';

type BulkResult=components['schemas']['BulkResult'];
type AsyncJob=components['schemas']['AsyncJob'];
type JobSummary=components['schemas']['AsyncJobSummary'];
type ResultPage=components['schemas']['AsyncJobResultPage'];
type Item=components['schemas']['BulkItemResult'];
type BulkOutcome=BulkResult|AsyncJob;
type Locale='en'|'zh-HK';
const zhCopy:Record<string,string>={
  'Assign buyer owners':'批量分派買家負責人','Assignment reason':'分派原因',
  'Confirm owner assignment':'確認負責人分派','Assign selected buyers':'分派已選買家',
  'Owner':'負責人','Me':'我','No owner':'沒有負責人','Search colleagues':'搜尋同事','Search':'搜尋','Previous colleagues':'上一頁同事','Next colleagues':'下一頁同事','Reload colleagues':'重新載入同事','Loading colleagues…':'正在載入同事…','Retry same assignment':'重試同一分派','Confirm this preview':'確認這份預覽','Scope':'工作區／專案','Reason':'原因',
  'The assignment result is unknown. Retry the same frozen assignment to reconcile; changes are locked until its result is known.':'分派結果未明。請重試同一份已凍結分派以核對結果；確認結果前暫停更改。',
  'Assigning...':'正在分派…','Bulk job progress':'批量工作進度','Close job':'關閉工作',
  'Loading job...':'正在載入工作…','Refresh job':'更新工作進度','Show job results':'顯示工作結果','Hide job results':'隱藏工作結果','Previous job results':'上一頁工作結果','Next job results':'下一頁工作結果',
  'Export failed IDs and reasons':'匯出失敗買家 ID 與原因',
  'Retry failed only with current versions':'只按目前版本重試失敗列','Preview failed rows with current versions':'按目前版本預覽失敗列',
  'Retrying...':'正在重試…','Cancel pending rows':'取消未處理列','Cancelling...':'正在取消…','queued':'排隊中','running':'處理中',
  'completed':'已完成','failed':'失敗','cancel_requested':'要求取消','cancelled':'已取消',
};
function copy(value:string,locale:Locale){return locale==='zh-HK'?(zhCopy[value]??liveZh[value]??value):value;}
export function isAsyncJob(value:BulkOutcome):value is AsyncJob{return 'kind' in value;}

export function LiveBulkActions({selection,count,canAssign,ownMembershipId,onJob,onCommitted,locale='en'}:{
  selection:ReviewSelection|null;count:number;canAssign:boolean;ownMembershipId:string|null;
  onJob:(id:string)=>void;onCommitted:()=>void;locale?:Locale;
}){
 const {session,client}=useWorkspaceSession(),snapshot=useSessionSnapshot(),{scope}=snapshot;
 const api=useMemo(()=>createOperationClient(client),[client]);
 const record=assignmentRecovery(session);
 const [reason,setReason]=useState(''),[owner,setOwner]=useState<string|null>(ownMembershipId);
 const [ownerLabel,setOwnerLabel]=useState(ownMembershipId?copy('Me',locale):copy('No owner',locale));
 const [search,setSearch]=useState(''),[q,setQ]=useState(''),[offset,setOffset]=useState(0),[refresh,setRefresh]=useState(0);
 const [loaded,setLoaded]=useState<{key:string;page:components['schemas']['EligibleAssigneePage']}|null>(null);
 const [lookupError,setLookupError]=useState({key:'',message:''});
 const [busy,setBusy]=useState(false),[message,setMessage]=useState(''),[error,setError]=useState(''),[failures,setFailures]=useState<Item[]>([]);
 const writeBusy=useRef(false),lifetime=useRef(new AbortController());
 useEffect(()=>{const controller=new AbortController();lifetime.current=controller;return()=>controller.abort();},[]);
 const readKey=JSON.stringify([snapshot.identity,q,offset,refresh]);
 const page=loaded?.key===readKey?loaded.page:null;
 const failure=lookupError.key===readKey?lookupError.message:'';
 useEffect(()=>{
  if(!canAssign||!scope.workspace)return;
  const own=new AbortController(),captured=session.captureWriteContext();
  const ctx={...captured,signal:AbortSignal.any([captured.signal,own.signal]),getToken:async()=>session.token()||'',
   isCurrent:()=>session.isCurrent(captured.identity)&&!own.signal.aborted};
  void api.requestOperation('listEligibleAssignees',{path:{workspace_id:captured.workspace},query:{q,offset,limit:20}},ctx)
   .then(value=>{if(ctx.isCurrent())setLoaded({key:readKey,page:value});})
   .catch(cause=>{if(ctx.isCurrent()&&!(cause instanceof LiveCancelled))setLookupError({key:readKey,message:describeLiveError(cause)});});
  return()=>own.abort();
 },[api,session,canAssign,scope.workspace,snapshot.identity,q,offset,refresh,readKey]);
 const pending=record.pending;
 const frozen=selection&&scope.workspace&&scope.project?freezeBulkAssignment({actor:scope.actor,workspace:scope.workspace,project:scope.project,
  operation:'assignBuyerOwners',selection,ownerMembershipId:owner,reason},count):null;
 const locked=busy||!!pending;
 async function assign(preview:FrozenBulkAssignment){
  const current=session.current();
  if(writeBusy.current||!session.token()||preview.actor!==current.actor||preview.workspace!==current.workspace||preview.project!==current.project)return;
  writeBusy.current=true;record.begin(preview);setBusy(true);setError('');setMessage('');setFailures([]);
  const captured=buyerOperationContext(session);
  const ctx={...captured,signal:AbortSignal.any([captured.signal,lifetime.current.signal]),
   isCurrent:()=>captured.isCurrent()&&!lifetime.current.signal.aborted};
  try{
   const result=await record.intent.run(preview.fingerprint,key=>api.requestOperation('assignBuyerOwners',{
    path:{workspace_id:preview.workspace,project_id:preview.project},header:{'Idempotency-Key':key},body:preview.body,
   },ctx));
   record.clear();
   if(!ctx.isCurrent())return;
   if(isAsyncJob(result)){onJob(result.id);setMessage(locale==='zh-HK'?`已將 ${result.requested} 列加入工作，請在下方查看進度。`:`${result.requested} buyer rows queued. Open the job below for progress.`);}
   else{setFailures(result.results.filter(row=>row.status==='blocked'||row.status==='conflict'));setMessage(locale==='zh-HK'?`${result.updated} 列已更新；${result.unchanged} 列不變；${result.blocked} 列受阻；${result.conflicts} 列衝突。`:`${result.updated} updated; ${result.unchanged} unchanged; ${result.blocked} blocked; ${result.conflicts} conflicts.`);
    if(result.updated)onCommitted();}
  }catch(cause){
   if(cause instanceof LiveError&&cause.status>=400&&cause.status<500)record.clear();
   if(ctx.isCurrent()&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));
  }finally{writeBusy.current=false;if(ctx.isCurrent())setBusy(false);}
 }
 const resultView=(message||failures.length>0)&&<section aria-label={copy('Owner assignment results',locale)}>
  <h3>{copy('Owner assignment results',locale)}</h3>
  {message&&<p role="status" aria-atomic="true">{message}</p>}
  {failures.length>0&&<details><summary>{copy('Technical details',locale)}</summary><ul>{failures.map(row=><li key={row.id}><code>{row.id}</code>: {row.reason_code??row.status}{row.version?` (${row.version})`:''}</li>)}</ul></details>}
 </section>;
 if(!canAssign)return null;
 if(count===0&&!pending)return resultView?<div className="panel bulk-action-panel">{resultView}</div>:null;
 const preview=pending??frozen,selectedOwner=pending?pending.body.owner_membership_id:owner;
 const shownOwner=selectedOwner===null?copy('No owner',locale):selectedOwner===ownMembershipId?copy('Me',locale):
  page?.items.find(row=>row.membership_id===selectedOwner)?.display_name??(!pending||selectedOwner===owner?ownerLabel:copy('Selected colleague (name unavailable)',locale));
 return <section className="panel bulk-action-panel" aria-label={copy('Assign buyer owners',locale)}>
  <h3>{copy('Assign buyer owners',locale)}</h3>
  <p>{locale==='zh-HK'?`預覽：已選 ${preview?.count??count} 位買家；提交前會重新檢查每列的版本和負責人資格。`:`Preview: ${preview?.count??count} selected buyer${(preview?.count??count)===1?'':'s'}; each current version and owner membership is checked again before commit.`}</p>
  <details><summary>{copy('Technical details',locale)}</summary><p style={{overflowWrap:'anywhere'}}>{copy('Scope',locale)}: {scope.workspace} / {scope.project}</p><p>{preview?.body.owner_membership_id??''}</p></details>
  <p style={{overflowWrap:'anywhere'}}>{copy('Owner',locale)}: {shownOwner}</p>
  <label className="bulk-action-field">{copy('Owner',locale)} <select style={{display:'block',width:'100%',maxWidth:'100%'}} aria-label={copy('Owner',locale)} disabled={locked} value={selectedOwner??''} onChange={e=>{setOwner(e.target.value||null);setOwnerLabel(e.target.selectedOptions[0].text);}}>
   <option value="">{copy('No owner',locale)}</option>{ownMembershipId&&<option value={ownMembershipId}>{copy('Me',locale)}</option>}
   {selectedOwner&&selectedOwner!==ownMembershipId&&!page?.items.some(row=>row.membership_id===selectedOwner)&&<option value={selectedOwner}>{shownOwner}</option>}
   {page?.items.filter(row=>row.membership_id!==ownMembershipId).map(row=><option key={row.membership_id} value={row.membership_id}>{row.display_name} · {row.user_id}</option>)}
  </select></label>
  <form className="bulk-action-row" onSubmit={e=>{e.preventDefault();setQ(search.trim());setOffset(0);setRefresh(v=>v+1);}}>
   <label className="bulk-action-field">{copy('Search colleagues',locale)} <input aria-label={copy('Search colleagues',locale)} maxLength={200} disabled={locked} value={search} onChange={e=>setSearch(e.target.value)}/></label>
   <button disabled={locked}>{copy('Search',locale)}</button>
  </form>
  {!page&&!failure&&<p role="status">{copy('Loading colleagues…',locale)}</p>}
  {page&&<div className="bulk-action-row"><span>{page.items.length?offset+1:0}–{offset+page.items.length} / {page.total}</span>
   <button disabled={locked||offset===0} onClick={()=>setOffset(v=>Math.max(0,v-20))}>{copy('Previous colleagues',locale)}</button>
   <button disabled={locked||offset+20>=page.total} onClick={()=>setOffset(v=>v+20)}>{copy('Next colleagues',locale)}</button></div>}
  {failure&&<><p role="alert">{failure}</p><button disabled={locked} onClick={()=>setRefresh(v=>v+1)}>{copy('Reload colleagues',locale)}</button></>}
  <label className="bulk-action-field">{copy('Assignment reason',locale)} <input aria-label={copy('Assignment reason',locale)} maxLength={2000} disabled={locked} value={pending?.body.reason??reason} onChange={e=>setReason(e.target.value)}/></label>
  <p>{copy('Reason',locale)}: {preview?.body.reason??''}</p>
  {pending&&!busy?<><p role="alert">{copy('The assignment result is unknown. Retry the same frozen assignment to reconcile; changes are locked until its result is known.',locale)}</p>
   <button onClick={()=>void assign(pending)}>{copy('Retry same assignment',locale)}</button></>
   :<AssignmentConfirmation key={`${snapshot.identity}:${frozen?.fingerprint??''}:${message}`} preview={frozen} enabled={count>0&&reason.trim().length>=3&&!locked} busy={busy} locale={locale} onAssign={assign}/>}
  {resultView}{error&&<p role="alert">{error}</p>}
 </section>;
}
function AssignmentConfirmation({preview,enabled,busy,locale,onAssign}:{preview:FrozenBulkAssignment|null;enabled:boolean;busy:boolean;locale:Locale;onAssign:(preview:FrozenBulkAssignment)=>Promise<void>}){
 const [confirmed,setConfirmed]=useState(false);
 return <div className="bulk-action-row"><label><input type="checkbox" aria-label={copy('Confirm owner assignment',locale)} disabled={!enabled} checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>{copy('Confirm this preview',locale)}</label>
  <button type="button" disabled={!enabled||!confirmed||!preview} onClick={()=>{if(preview)void onAssign(preview);}}>{copy(busy?'Assigning...':'Assign selected buyers',locale)}</button></div>;
}

export function BulkJobPanel({jobId,onJob,onCommitted,onClose,locale='en',onManifestRetry}:{jobId:string;onJob:(id:string)=>void;onCommitted:()=>void;onClose:()=>void;locale?:Locale;onManifestRetry?:(source:{id:string;manifest_id:string})=>void}){
  const {session,client}=useWorkspaceSession(),snapshot=useSessionSnapshot(),{scope}=snapshot;
  const [job,setJob]=useState<JobSummary|null>(null),[resultPage,setResultPage]=useState<ResultPage|null>(null);
  const [error,setError]=useState(''),[busy,setBusy]=useState(false),[retryResult,setRetryResult]=useState<BulkResult|null>(null);
  const [tick,setTick]=useState(0),[resultsOpen,setResultsOpen]=useState(false),[resultOffset,setResultOffset]=useState(0),[resultTick,setResultTick]=useState(0),[resultBusy,setResultBusy]=useState(false);
  const settled=useRef(''),resultView=useRef({open:resultsOpen});
  useEffect(()=>{resultView.current={open:resultsOpen};},[resultsOpen]);
  const retryIntent=useRef(new ActionIntent<BulkOutcome>());
  const cancelIntent=useRef(new ActionIntent<AsyncJob>());
  const reportIntent=useRef(new ActionIntent<ExportJob>());
  useEffect(()=>{
    if(!jobId||!scope.workspace)return;
    const own=new AbortController(),basis=session.captureWriteContext(),op=createOperationClient(client);
    const signal=AbortSignal.any([basis.signal,own.signal]);
    return startJobPoller({signal,isVisible:()=>!document.hidden,
      fetchSummary:requestSignal=>op.requestOperation('getAsyncJobSummary',{path:{workspace_id:scope.workspace!,job_id:jobId}},
        {...basis,signal:AbortSignal.any([signal,requestSignal]),getToken:async()=>session.token()||'',isCurrent:()=>session.isCurrent(basis.identity)&&!own.signal.aborted}),
      onValue:value=>{
        if(!session.isCurrent(basis.identity)||own.signal.aborted)return;
        setJob(value);setError('');
        if(['completed','failed','cancelled'].includes(value.status)&&settled.current!==`${basis.identity}:${jobId}`){
          settled.current=`${basis.identity}:${jobId}`;
          if(resultView.current.open){setResultBusy(true);setResultTick(v=>v+1);}
          if(value.updated)onCommitted();
        }
      },onError:cause=>{if(session.isCurrent(basis.identity)&&!own.signal.aborted)setError(describeLiveError(cause));},
    });
  },[client,session,scope.workspace,scope.project,snapshot.identity,jobId,tick,onCommitted]);
  useEffect(()=>{
    if(!resultsOpen||!scope.workspace)return;
    const own=new AbortController(),basis=session.captureWriteContext();
    const current=()=>!own.signal.aborted&&session.isCurrent(basis.identity);
    void createOperationClient(client).requestOperation('getAsyncJob',{path:{workspace_id:scope.workspace,job_id:jobId},query:{offset:resultOffset,limit:20}},
      {...basis,signal:AbortSignal.any([own.signal,basis.signal]),getToken:async()=>session.token()||'',isCurrent:current})
      .then(value=>{if(current()){setResultPage(value.result_page??null);setError('');}})
      .catch(cause=>{if(current()&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));})
      .finally(()=>{if(current())setResultBusy(false);});
    return()=>own.abort();
  },[client,session,scope.workspace,snapshot.identity,jobId,resultsOpen,resultOffset,resultTick]);
  const failures=(resultPage?.items??[]).filter(item=>item.status==='blocked'||item.status==='conflict');
  const failureCount=(job?.blocked??0)+(job?.conflicts??0);
  async function downloadFailures(){
    if(!scope.workspace||!scope.project||!job||busy||!['completed','failed'].includes(job.status))return;
    setBusy(true);setError('');
    try{
      const ctx=buyerOperationContext(session);
      const report=await reportIntent.current.run(JSON.stringify({ctx:ctx.identity,jobId}),key=>
        createOperationClient(client).requestOperation('exportBulkFailures',{
          path:{workspace_id:scope.workspace!,job_id:jobId},header:{'Idempotency-Key':key},
        },ctx));
      if(report.kind!=='bulk_failure_csv'||report.project_id!==scope.project)
        throw new Error('Failure report scope changed');
      const content=await readExportContent(client,session,report.id);
      if(!ctx.isCurrent())throw new LiveCancelled('scope changed');
      downloadText(content.text,content.contentType,`buyer-job-${jobId}-failed.csv`);
    }catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    finally{setBusy(false);}
  }
  async function cancel(){
    if(!scope.workspace||busy)return;
    setBusy(true);setError('');
    try{
      const ctx=buyerOperationContext(session);
      await cancelIntent.current.run(JSON.stringify({ctx:ctx.identity,jobId}),key=>
        createOperationClient(client).requestOperation('cancelAsyncJob',{
          path:{workspace_id:scope.workspace!,job_id:jobId},header:{'Idempotency-Key':key},
        },ctx));
      setTick(value=>value+1);
    }catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    finally{setBusy(false);}
  }
  async function retry(){
    if(!scope.workspace||busy||!failureCount)return;
    if(job?.manifest_id){onManifestRetry?.({id:jobId,manifest_id:job.manifest_id});return;}
    setBusy(true);setError('');
    try{
      const ctx=buyerOperationContext(session);
      const result=await retryIntent.current.run(JSON.stringify({ctx:ctx.identity,jobId}),key=>
        createOperationClient(client).requestOperation('retryFailedAsyncJob',{
          path:{workspace_id:scope.workspace!,job_id:jobId},header:{'Idempotency-Key':key},
        },ctx));
      if(isAsyncJob(result))onJob(result.id);
      else{setRetryResult(result);if(result.updated)onCommitted();setTick(value=>value+1);}
    }catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    finally{setBusy(false);}
  }
  return <section className="panel bulk-action-panel" aria-label={copy('Bulk job progress',locale)}>
    <div className="bulk-action-row spread"><h3>{copy('Bulk job progress',locale)}</h3><button type="button" onClick={onClose}>{copy('Close job',locale)}</button></div>
    {error&&<p role="alert">{error}</p>}
    {!job&&!error&&<p role="status">{copy('Loading job...',locale)}</p>}
    {job&&<><p role="status">{locale==='zh-HK'?`${copy(job.status,locale)}：已處理 ${job.processed??0}／${job.requested??0} 列；更新 ${job.updated??0}、不變 ${job.unchanged??0}、受阻 ${job.blocked??0}、衝突 ${job.conflicts??0}、取消 ${job.cancelled??0}。`:`${job.status}: ${job.processed??0} of ${job.requested??0} processed; ${job.updated??0} updated; ${job.unchanged??0} unchanged; ${job.blocked??0} blocked; ${job.conflicts??0} conflicts; ${job.cancelled??0} cancelled.`}</p>
      <div className="bulk-action-row"><button type="button" onClick={()=>{setTick(value=>value+1);if(resultsOpen){setResultBusy(true);setResultTick(v=>v+1);}}}>{copy('Refresh job',locale)}</button>
      {['queued','running'].includes(job.status)&&<button type="button" disabled={busy} onClick={()=>void cancel()}>{copy(busy?'Cancelling...':'Cancel pending rows',locale)}</button>}
      {failureCount>0&&<><button type="button" disabled={busy||!['completed','failed'].includes(job.status)} onClick={()=>void downloadFailures()}>{copy('Export failed IDs and reasons',locale)}</button>
        <button type="button" disabled={busy||!['completed','failed','cancelled'].includes(job.status)||(!!job.manifest_id&&!onManifestRetry)} onClick={()=>void retry()}>{copy(busy?'Retrying...':job.manifest_id?'Preview failed rows with current versions':'Retry failed only with current versions',locale)}</button></>}</div>
      {failureCount>0&&<><p>{locale==='zh-HK'?`失敗列：${failureCount}。報告只包含買家 ID 和內部原因碼。`:`Failed rows: ${failureCount}. Reasons are limited to buyer IDs and internal codes.`}</p>
        <ul>{failures.map(item=><li key={item.id}>{item.id}: {item.reason_code??item.status}</li>)}</ul></>}
      <button type="button" onClick={()=>{setResultBusy(true);setResultsOpen(v=>!v);}}>{copy(resultsOpen?'Hide job results':'Show job results',locale)}</button>
      {resultsOpen&&<div aria-busy={resultBusy}>
        {resultPage?.items.map(item=><p key={item.id}><code>{item.id}</code>: {copy(item.status,locale)} {item.reason_code??''}</p>)}
        {resultPage&&<div className="bulk-action-row">
          <button type="button" disabled={resultBusy||resultOffset===0} onClick={()=>{setResultBusy(true);setResultOffset(v=>Math.max(0,v-20));}}>{copy('Previous job results',locale)}</button>
          <span>{resultPage.total?resultPage.offset+1:0}–{Math.min(resultPage.offset+resultPage.items.length,resultPage.total)} / {resultPage.total}</span>
          <button type="button" disabled={resultBusy||resultOffset+20>=resultPage.total} onClick={()=>{setResultBusy(true);setResultOffset(v=>v+20);}}>{copy('Next job results',locale)}</button>
        </div>}
      </div>}
      {retryResult&&<p role="status">{locale==='zh-HK'?`重試：更新 ${retryResult.updated}、受阻 ${retryResult.blocked}、衝突 ${retryResult.conflicts}。`:`Retry: ${retryResult.updated} updated; ${retryResult.blocked} blocked; ${retryResult.conflicts} conflicts.`}</p>}
    </>}
  </section>;
}
