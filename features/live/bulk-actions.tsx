'use client';
import {useEffect,useRef,useState} from 'react';
import type {components} from '@/services/generated/buyeros-api';
import {useWorkspaceSession,useSessionSnapshot} from '@/features/providers/workspace-session';
import {ActionIntent} from '@/services/live/action-intent';
import {downloadText} from '@/services/live/download-text';
import {readExportContent,type ExportJob} from '@/services/live/exports';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
import {buyerOperationContext} from '@/services/live/buyers';
import type {ReviewSelection} from '@/services/live/buyer-selection';
import {createOperationClient} from '@/services/live/operations';

type BulkResult=components['schemas']['BulkResult'];
type AsyncJob=components['schemas']['AsyncJob'];
type BulkOutcome=BulkResult|AsyncJob;
type Item=components['schemas']['BulkItemResult'];
type Locale='en'|'zh-HK';
const zhCopy:Record<string,string>={
  'Assign buyer owners':'批量分派買家負責人','Assignment reason':'分派原因',
  'Confirm owner assignment':'確認負責人分派','Assign selected buyers':'分派已選買家',
  'Assigning...':'正在分派…','Bulk job progress':'批量工作進度','Close job':'關閉工作',
  'Loading job...':'正在載入工作…','Refresh job':'更新工作進度',
  'Export failed IDs and reasons':'匯出失敗買家 ID 與原因',
  'Retry failed only with current versions':'只按目前版本重試失敗列',
  'Retrying...':'正在重試…','Cancel pending rows':'取消未處理列','Cancelling...':'正在取消…','queued':'排隊中','running':'處理中',
  'completed':'已完成','failed':'失敗','cancel_requested':'要求取消','cancelled':'已取消',
};
function copy(value:string,locale:Locale){return locale==='zh-HK'?(zhCopy[value]??value):value;}
export function isAsyncJob(value:BulkOutcome):value is AsyncJob{return 'kind' in value;}

export function LiveBulkActions({selection,count,canAssign,ownMembershipId,onJob,onCommitted,locale='en'}:{
  selection:ReviewSelection|null;count:number;canAssign:boolean;ownMembershipId:string|null;
  onJob:(id:string)=>void;onCommitted:()=>void;locale?:Locale;
}){
  const {session,client}=useWorkspaceSession(),{scope}=useSessionSnapshot();
  const [reason,setReason]=useState(''),[confirm,setConfirm]=useState(false),[busy,setBusy]=useState(false);
  const [message,setMessage]=useState(''),[error,setError]=useState('');
  const intent=useRef(new ActionIntent<BulkOutcome>());
  if(!canAssign)return null;
  async function assign(){
    if(!selection||!scope.workspace||!scope.project||!confirm||busy||reason.trim().length<3)return;
    setBusy(true);setError('');setMessage('');
    try{
      const ctx=buyerOperationContext(session),body={selection,owner_membership_id:ownMembershipId,reason:reason.trim()};
      const result=await intent.current.run(JSON.stringify({ctx:ctx.identity,body}),key=>
        createOperationClient(client).requestOperation('assignBuyerOwners',{
          path:{workspace_id:scope.workspace!,project_id:scope.project!},header:{'Idempotency-Key':key},body,
        },ctx));
      if(isAsyncJob(result)){onJob(result.id);setMessage(locale==='zh-HK'?`已將 ${result.requested} 列加入工作，請在下方查看進度。`:`${result.requested} buyer rows queued. Open the job below for progress.`);}
      else{setMessage(locale==='zh-HK'?`${result.updated} 列已更新；${result.unchanged} 列不變；${result.blocked} 列受阻；${result.conflicts} 列衝突。`:`${result.updated} updated; ${result.unchanged} unchanged; ${result.blocked} blocked; ${result.conflicts} conflicts.`);
        if(result.updated)onCommitted();}
      setConfirm(false);
    }catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    finally{setBusy(false);}
  }
  return <section className="panel bulk-action-panel" aria-label={copy('Assign buyer owners',locale)}>
    <h3>{copy('Assign buyer owners',locale)}</h3>
    <p>{locale==='zh-HK'?`預覽：已選 ${count} 位買家；提交前會重新檢查每列的版本和負責人資格。`:`Preview: ${count} selected buyer${count===1?'':'s'}; each current version and owner membership is checked again before commit.`}</p>
    <label className="bulk-action-field">{copy('Assignment reason',locale)} <input aria-label={copy('Assignment reason',locale)} value={reason} onChange={event=>setReason(event.target.value)}/></label>
    <div className="bulk-action-row"><label><input type="checkbox" aria-label={copy('Confirm owner assignment',locale)} checked={confirm} onChange={event=>setConfirm(event.target.checked)}/> {locale==='zh-HK'?`確認將已選買家${ownMembershipId?'分派給我':'設為沒有負責人'}`:`Confirm assignment ${ownMembershipId?'to me':'to no owner'} for this selection`}</label>
      <button type="button" disabled={!selection||count===0||!confirm||reason.trim().length<3||busy} onClick={()=>void assign()}>{copy(busy?'Assigning...':'Assign selected buyers',locale)}</button></div>
    {message&&<p role="status">{message}</p>}{error&&<p role="alert">{error}</p>}
  </section>;
}

export function BulkJobPanel({jobId,onJob,onCommitted,onClose,locale='en'}:{jobId:string;onJob:(id:string)=>void;onCommitted:()=>void;onClose:()=>void;locale?:Locale}){
  const {session,client}=useWorkspaceSession(),{scope}=useSessionSnapshot();
  const [job,setJob]=useState<AsyncJob|null>(null),[items,setItems]=useState<Item[]>([]);
  const [error,setError]=useState(''),[busy,setBusy]=useState(false),[retryResult,setRetryResult]=useState<BulkResult|null>(null);
  const [tick,setTick]=useState(0),settled=useRef('');
  const retryIntent=useRef(new ActionIntent<BulkOutcome>());
  const cancelIntent=useRef(new ActionIntent<AsyncJob>());
  const reportIntent=useRef(new ActionIntent<ExportJob>());
  useEffect(()=>{
    if(!jobId||!scope.workspace)return;
    let active=true;
    void(async()=>{
      try{
        const ctx=buyerOperationContext(session),op=createOperationClient(client);
        const first=await op.requestOperation('getAsyncJob',{path:{workspace_id:scope.workspace!,job_id:jobId},query:{offset:0,limit:100}},ctx);
        const collected:Item[]=[...(first.result_page?.items??[])];
        const total=first.result_page?.total??0;
        for(let offset=collected.length;offset<total;){
          const page=await op.requestOperation('getAsyncJob',{path:{workspace_id:scope.workspace!,job_id:jobId},query:{offset,limit:100}},ctx);
          const rows=page.result_page?.items??[];
          if(!rows.length)throw new Error('Incomplete job result page');
          collected.push(...rows);offset+=rows.length;
        }
        if(active){setJob(first);setItems(collected);setError('');
          if(first.status==='completed'&&first.updated&&settled.current!==jobId){settled.current=jobId;onCommitted();}}
      }catch(cause){if(active&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    })();
    return()=>{active=false;};
  },[client,session,scope.workspace,scope.project,jobId,tick,onCommitted]);
  const jobStatus=job?.status;
  useEffect(()=>{if(!jobStatus||!['queued','running','cancel_requested'].includes(jobStatus))return;
    const timer=window.setInterval(()=>setTick(value=>value+1),2000);return()=>window.clearInterval(timer);
  },[jobStatus]);
  const failures=items.filter(item=>item.status==='blocked'||item.status==='conflict');
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
      const result=await cancelIntent.current.run(JSON.stringify({ctx:ctx.identity,jobId}),key=>
        createOperationClient(client).requestOperation('cancelAsyncJob',{
          path:{workspace_id:scope.workspace!,job_id:jobId},header:{'Idempotency-Key':key},
        },ctx));
      setJob(result);setTick(value=>value+1);
    }catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    finally{setBusy(false);}
  }
  async function retry(){
    if(!scope.workspace||busy||!failures.length)return;
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
      <div className="bulk-action-row"><button type="button" onClick={()=>setTick(value=>value+1)}>{copy('Refresh job',locale)}</button>
      {['queued','running'].includes(job.status)&&<button type="button" disabled={busy} onClick={()=>void cancel()}>{copy(busy?'Cancelling...':'Cancel pending rows',locale)}</button>}
      {failures.length>0&&<><button type="button" disabled={busy||!['completed','failed'].includes(job.status)} onClick={()=>void downloadFailures()}>{copy('Export failed IDs and reasons',locale)}</button>
        <button type="button" disabled={busy||!['completed','failed'].includes(job.status)} onClick={()=>void retry()}>{copy(busy?'Retrying...':'Retry failed only with current versions',locale)}</button></>}</div>
      {failures.length>0&&<><p>{locale==='zh-HK'?`失敗列：${failures.length}。報告只包含買家 ID 和內部原因碼。`:`Failed rows: ${failures.length}. Reasons are limited to buyer IDs and internal codes.`}</p>
        <ul>{failures.slice(0,20).map(item=><li key={item.id}>{item.id}: {item.reason_code??item.status}</li>)}</ul></>}
      {retryResult&&<p role="status">{locale==='zh-HK'?`重試：更新 ${retryResult.updated}、受阻 ${retryResult.blocked}、衝突 ${retryResult.conflicts}。`:`Retry: ${retryResult.updated} updated; ${retryResult.blocked} blocked; ${retryResult.conflicts} conflicts.`}</p>}
    </>}
  </section>;
}
