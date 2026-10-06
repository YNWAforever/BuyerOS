"use client";
import {useEffect,useState} from 'react';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
import {buyerFiltersForQuery,buyerOperationContext,type BuyerQuery} from '@/services/live/buyers';
import {createOperationClient,type OperationOutput} from '@/services/live/operations';
import {executeManifest,previewManifest,readManifest,startNewManifest,manifestRecovery,type Manifest,type ManifestBody,type ManifestResult} from '@/services/live/bulk-manifests';
import type {components} from '@/services/generated/buyeros-api';
import {isAsyncJob} from './bulk-actions';
const zh:Record<string,string>={
 'Segmented maintenance':'分段批量維護','Preview segmented maintenance':'預覽分段批量維護','Operation':'操作','Assign owners':'指派負責人','Review buyers':'覆核買家','Change list membership':'更改清單成員',
 'Maintenance reason':'維護理由','Excluded buyer IDs (one per line)':'排除買家 ID（每行一個）','Owner':'負責人','Clear owner':'清除負責人','Me':'自己','Search colleagues':'搜尋同事','Search':'搜尋','Previous colleagues':'上一頁同事','Next colleagues':'下一頁同事',
 'Review status':'覆核狀態','List ID':'清單 ID','List change':'清單更改','add':'加入','remove':'移除','accepted':'接受','rejected':'拒絕','needs_information':'需要資料','Frozen manifest':'已凍結維護清單',
 'Confirm exact manifest':'確認精確維護清單','Execute confirmed manifest':'執行已確認維護清單','Recheck manifest':'重新查閱維護清單','Start a new preview':'開始新的預覽','Retry same preview':'重試同一預覽',
 'This preview freezes all matching IDs and versions, up to 10000. No buyer is changed until you confirm the exact digest.':'此預覽會凍結所有符合條件的 ID 及版本，上限 10000 筆。確認精確摘要前不會更改買家。',
 'The preview response is unknown. Retry uses the same frozen request and key.':'預覽結果未明；重試會使用相同凍結請求及 key。','Read the count, operation, target, reason and filters before confirming.':'確認前請核對筆數、操作、目標、理由及篩選條件。','Failed rows only; review a new digest before retrying.':'只包含失敗列；重試前須覆核新的摘要。',
 'The execution result is unknown. Retry the exact confirmation or recheck this manifest before starting another preview.':'執行結果未明；請重試精確確認或重新查閱此清單，確認後才開始另一份預覽。','updated':'已更新','blocked':'被阻止','conflicts':'版本衝突','count':'筆數','digest':'摘要','expires_at':'到期時間','target':'目標','filters':'篩選條件','reason':'理由','ready':'就緒','executed':'已執行',
};
export function BulkManifestMaintenance({query,canAssign,canReview,canManage,ownMembershipId,onJob,onCommitted,locale='en',sourceJob}:{query:BuyerQuery;canAssign:boolean;canReview:boolean;canManage:boolean;ownMembershipId:string|null;onJob:(id:string)=>void;onCommitted:()=>void;locale?:'en'|'zh-HK';sourceJob?:{id:string;manifest_id:string}}){
 const {client,session}=useWorkspaceSession(),t=(s:string)=>locale==='zh-HK'?(zh[s]??s):s;
 const [operation,setOperation]=useState<ManifestBody['operation']>(canAssign?'assignBuyerOwners':canReview?'reviewBuyers':'changeListMemberships');
 const [owner,setOwner]=useState(ownMembershipId??''),[review,setReview]=useState<'accepted'|'rejected'|'needs_information'>('accepted'),[list,setList]=useState(query.listId),[change,setChange]=useState<'add'|'remove'>('add');
 const [reason,setReason]=useState(''),[excluded,setExcluded]=useState(''),[search,setSearch]=useState(''),[q,setQ]=useState(''),[offset,setOffset]=useState(0);
 const [lists,setLists]=useState<OperationOutput<'listBuyerLists'>|null>(null),[listOffset,setListOffset]=useState(0),[listEpoch,setListEpoch]=useState(0);
 const [colleagues,setColleagues]=useState<components['schemas']['EligibleAssigneePage']|null>(null);
 const [manifest,setManifest]=useState<Manifest|null>(null),[busy,setBusy]=useState(false),[confirmed,setConfirmed]=useState(false),[error,setError]=useState(''),[result,setResult]=useState<ManifestResult|null>(null),[pending,setPending]=useState(()=>!!manifestRecovery(session).body),[epoch,setEpoch]=useState(0),[source,setSource]=useState<Manifest|null>(null),[executionPending,setExecutionPending]=useState(false);
 useEffect(()=>{let active=true;const identity=session.identity();if(!canAssign||sourceJob)return;
  const ctx=buyerOperationContext(session);void createOperationClient(client).requestOperation('listEligibleAssignees',{path:{workspace_id:ctx.workspace},query:{q,offset,limit:20}},ctx).then(value=>{if(active&&session.isCurrent(identity))setColleagues(value);}).catch(cause=>{if(active&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));});return()=>{active=false;};
 },[client,session,canAssign,q,offset,sourceJob]);
 useEffect(()=>{let active=true;const identity=session.identity();const id=sourceJob?.manifest_id??new URLSearchParams(window.location.search).get('bulk_manifest');if(!id)return;
  void readManifest(client,session,id).then(value=>{if(!active||!session.isCurrent(identity))return;
   if(sourceJob){setSource(value);setOperation(value.operation);if('owner_membership_id' in value.target)setOwner(value.target.owner_membership_id??'');if('status' in value.target)setReview(value.target.status);if('list_id' in value.target){setList(value.target.list_id);setChange(value.target.operation);}setReason(value.reason);}
   else {setManifest(value);setPending(false);setExecutionPending(false);setConfirmed(false);if(value.job_id)onJob(value.job_id);}
  }).catch(cause=>{if(active&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));});return()=>{active=false;};
 },[client,session,sourceJob,epoch,onJob]);
 useEffect(()=>{let active=true;const identity=session.identity();if(!canManage||sourceJob)return;
  const ctx=buyerOperationContext(session);void createOperationClient(client).requestOperation('listBuyerLists',{path:{workspace_id:ctx.workspace,project_id:ctx.project!},query:{offset:listOffset,limit:20}},ctx).then(value=>{if(active&&session.isCurrent(identity))setLists(value);}).catch(cause=>{if(active&&session.isCurrent(identity)&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));});return()=>{active=false;};
 },[client,session,canManage,sourceJob,listOffset,listEpoch]);
 const locked=busy||!!manifest||pending;
 function body():ManifestBody{
  const common={filters:sourceJob?{}:buyerFiltersForQuery(query),excluded_ids:excluded.split(/\s+/).filter(Boolean),reason:reason.trim(),...(sourceJob?{source_job_id:sourceJob.id}:{})};
  if(operation==='assignBuyerOwners')return {...common,operation,target:{owner_membership_id:owner||null}};
  if(operation==='reviewBuyers')return {...common,operation,target:{status:review}};
  return {...common,operation,target:{list_id:list,operation:change}};
 }
 async function prepare(){if(busy)return;const identity=session.identity();setBusy(true);setError('');setPending(true);
  try{const value=await previewManifest(client,session,body());if(!session.isCurrent(identity))return;setManifest(value);setPending(false);setConfirmed(false);const url=new URL(window.location.href);url.searchParams.set('bulk_manifest',value.id);window.history.replaceState(window.history.state,'',url.pathname+url.search+url.hash);}
  catch(cause){if(session.isCurrent(identity)&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
  finally{if(session.isCurrent(identity))setBusy(false);}
 }
 async function execute(){if(!manifest||busy||!confirmed)return;const identity=session.identity();setBusy(true);setExecutionPending(true);setError('');
  try{const value=await executeManifest(client,session,manifest);if(!session.isCurrent(identity))return;setResult(value);setExecutionPending(false);setConfirmed(false);if(isAsyncJob(value))onJob(value.id);else onCommitted();setEpoch(v=>v+1);}
  catch(cause){if(session.isCurrent(identity)&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
  finally{if(session.isCurrent(identity))setBusy(false);}
 }
 function newPreview(){if(busy)return;startNewManifest(session);setManifest(null);setResult(null);setPending(false);setConfirmed(false);setError('');setEpoch(v=>v+1);const url=new URL(window.location.href);url.searchParams.delete('bulk_manifest');window.history.replaceState(window.history.state,'',url.pathname+url.search+url.hash);}
 return <section className="panel bulk-action-panel bulk-manifest-panel" aria-label={t('Segmented maintenance')}>
  <h3>{t('Segmented maintenance')}</h3><p>{t('This preview freezes all matching IDs and versions, up to 10000. No buyer is changed until you confirm the exact digest.')}</p>
  {sourceJob&&<p>{t('Failed rows only; review a new digest before retrying.')}</p>}
  {error&&<p role="alert">{error}</p>}
  <fieldset disabled={locked||!!sourceJob}><legend>{t('Operation')}</legend><select aria-label={t('Operation')} value={operation} onChange={e=>setOperation(e.target.value as ManifestBody['operation'])}>
   {canAssign&&<option value="assignBuyerOwners">{t('Assign owners')}</option>}{canReview&&<option value="reviewBuyers">{t('Review buyers')}</option>}{canManage&&<option value="changeListMemberships">{t('Change list membership')}</option>}
  </select>
  {operation==='assignBuyerOwners'&&<><label>{t('Search colleagues')} <input aria-label={t('Search colleagues')} value={search} onChange={e=>setSearch(e.target.value)}/></label><button type="button" onClick={()=>{setQ(search.trim());setOffset(0);}}>{t('Search')}</button>
   <label>{t('Owner')} <select aria-label={t('Owner')} value={owner} onChange={e=>setOwner(e.target.value)}><option value="">{t('Clear owner')}</option>{owner&&!colleagues?.items.some(item=>item.membership_id===owner)&&<option value={owner}>{owner===ownMembershipId?t('Me'):owner}</option>}{colleagues?.items.map(item=><option key={item.membership_id} value={item.membership_id}>{item.display_name} · {item.membership_id}</option>)}</select></label>
   {colleagues&&<div>{offset+1}–{offset+colleagues.items.length} / {colleagues.total} <button disabled={offset===0} onClick={()=>setOffset(v=>Math.max(0,v-20))}>{t('Previous colleagues')}</button><button disabled={offset+20>=colleagues.total} onClick={()=>setOffset(v=>v+20)}>{t('Next colleagues')}</button></div>}</>}
  {operation==='reviewBuyers'&&<label>{t('Review status')} <select aria-label={t('Review status')} value={review} onChange={e=>setReview(e.target.value as typeof review)}>{(['accepted','rejected','needs_information'] as const).map(s=><option key={s} value={s}>{t(s)}</option>)}</select></label>}
  {operation==='changeListMemberships'&&<><label>{t('Target list')} <select aria-label={t('Target list')} value={list} onChange={e=>setList(e.target.value)}><option value="">{t('Choose list')}</option>{list&&!lists?.items.some(item=>item.id===list)&&<option value={list}>{list}</option>}{lists?.items.map(item=><option key={item.id} value={item.id}>{item.name} · {item.id}</option>)}</select></label><label>{t('List change')} <select aria-label={t('List change')} value={change} onChange={e=>setChange(e.target.value as typeof change)}>{(['add','remove'] as const).map(s=><option key={s} value={s}>{t(s)}</option>)}</select></label><button type="button" onClick={()=>setListEpoch(v=>v+1)}>{t('Reload lists')}</button>{lists&&<div>{lists.items.length?listOffset+1:0}–{listOffset+lists.items.length} / {lists.total}<button type="button" disabled={listOffset===0} onClick={()=>setListOffset(v=>Math.max(0,v-20))}>{t('Previous lists')}</button><button type="button" disabled={listOffset+20>=lists.total} onClick={()=>setListOffset(v=>v+20)}>{t('Next lists')}</button></div>}</>}
  </fieldset>
  <label>{t('Maintenance reason')} <input aria-label={t('Maintenance reason')} maxLength={2000} value={reason} disabled={locked} onChange={e=>setReason(e.target.value)}/></label>
  <label>{t('Excluded buyer IDs (one per line)')} <textarea aria-label={t('Excluded buyer IDs (one per line)')} value={excluded} disabled={locked} onChange={e=>setExcluded(e.target.value)}/></label>
  {!manifest&&<button type="button" disabled={busy||(!pending&&reason.trim().length<3)||(!!sourceJob&&!source)} onClick={()=>void prepare()}>{t(pending?'Retry same preview':'Preview segmented maintenance')}</button>}
  {pending&&!manifest&&<p role="status">{t('The preview response is unknown. Retry uses the same frozen request and key.')}</p>}
  {manifest&&<section className="panel" aria-label={t('Frozen manifest')}><h4>{t('Frozen manifest')}</h4><p style={{overflowWrap:'anywhere'}}>{manifest.id} · {t(manifest.status)} · {t('count')}: {manifest.count}</p><p style={{overflowWrap:'anywhere'}}>{t('digest')}: {manifest.digest}</p><p>{t('expires_at')}: {manifest.expires_at}</p><p>{t(manifest.operation==='assignBuyerOwners'?'Assign owners':manifest.operation==='reviewBuyers'?'Review buyers':'Change list membership')}</p><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{JSON.stringify({target:manifest.target,filters:manifest.filters,reason:manifest.reason,excluded_ids:manifest.excluded_ids},null,2)}</pre>
   <p>{t('Read the count, operation, target, reason and filters before confirming.')}</p><label><input type="checkbox" aria-label={t('Confirm exact manifest')} checked={confirmed} disabled={busy||manifest.status!=='ready'} onChange={e=>setConfirmed(e.target.checked)}/>{t('Confirm exact manifest')}</label><button type="button" disabled={busy||!confirmed||manifest.status!=='ready'} onClick={()=>void execute()}>{t('Execute confirmed manifest')}</button>
   <button type="button" disabled={busy} onClick={()=>{setConfirmed(false);setEpoch(v=>v+1);}}>{t('Recheck manifest')}</button></section>}
  {executionPending&&<p role="status">{t('The execution result is unknown. Retry the exact confirmation or recheck this manifest before starting another preview.')}</p>}
  {(manifest||pending)&&<button type="button" disabled={busy||executionPending} onClick={newPreview}>{t('Start a new preview')}</button>}
  {result&&!isAsyncJob(result)&&<p role="status">{result.updated} {t('updated')} · {result.blocked} {t('blocked')} · {result.conflicts} {t('conflicts')}</p>}
 </section>;
}
