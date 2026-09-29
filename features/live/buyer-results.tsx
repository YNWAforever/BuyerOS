'use client';
import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {useWorkspaceSession,useSessionSnapshot} from '@/features/providers/workspace-session';
import {LiveCancelled,LiveError,describeLiveError} from '@/services/live/client';
import {ActionIntent} from '@/services/live/action-intent';
import {createBuyerSnapshot,loadBuyerPage,readBuyerQuery,writeBuyerQuery,buyerOperationContext,type BuyerQuery,type BuyerSnapshot} from '@/services/live/buyers';
import {createOperationClient} from '@/services/live/operations';
import type {components} from '@/services/generated/buyeros-api';
import {explicitSelection,snapshotSelection,type ReviewSelection} from '@/services/live/buyer-selection';
import type {LiveBuyerPage} from '@/services/live/mapping';
import {LiveBuyerDetail} from './buyer-detail';
import {ExportDialog} from './export-dialog';
import {LiveBuyerManagementControls} from './buyer-management-controls';
import {BulkJobPanel,LiveBulkActions,isAsyncJob} from './bulk-actions';
import {liveZh} from './locale';

const reviewStatuses=['accepted','rejected','needs_information'] as const;
const initial=():BuyerQuery=>readBuyerQuery(typeof window==='undefined'?'':window.location.search);
export function LiveBuyerResults({canReview=false,canEdit=false,canQuote=false,canAssign=false,ownMembershipId=null,locale='en',onManualOutcome}:{canReview?:boolean;canEdit?:boolean;canQuote?:boolean;canAssign?:boolean;ownMembershipId?:string|null;locale?:'en'|'zh-HK';onManualOutcome?:(buyerId:string)=>void}){
  const {session,client}=useWorkspaceSession();
  const t=(value:string)=>locale==='zh-HK'?(liveZh[value]||value):value;
  const scope=useSessionSnapshot().scope;
  const [query,setQuery]=useState<BuyerQuery>(initial);
  const [search,setSearch]=useState(query.q);
  useEffect(()=>{
    // Vinext can mount the pathname before its query is committed to browser history.
    // Read the final URL after navigation so a work-queue deep link uses its server filter.
    const frame=window.requestAnimationFrame(()=>{
      const next=readBuyerQuery(window.location.search);
      setQuery(previous=>JSON.stringify(previous)===JSON.stringify(next)?previous:next);
      setSearch(next.q);
    });
    return()=>window.cancelAnimationFrame(frame);
  },[]);
  const [snapshot,setSnapshot]=useState<BuyerSnapshot|null>(null);
  const [page,setPage]=useState<LiveBuyerPage|null>(null);
  const [selected,setSelected]=useState<Record<string,number>>({});
  const [allFiltered,setAllFiltered]=useState(false);
  const [excluded,setExcluded]=useState<string[]>([]);
  const [detailId,setDetailId]=useState<string|null>(null);
  const [status,setStatus]=useState<(typeof reviewStatuses)[number]>('accepted');
  const [reason,setReason]=useState('');
  const [busy,setBusy]=useState(false);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState('');
  const [reload,setReload]=useState(0);
  const [reviewResult,setReviewResult]=useState<components['schemas']['BulkResult']|null>(null);
  const [jobId,setJobId]=useState(()=>typeof window==='undefined'?'':new URLSearchParams(window.location.search).get('bulk_job')??'');
  const reviewIntent=useRef(new ActionIntent<components['schemas']['BulkResult']|components['schemas']['AsyncJob']>());
  const onCommitted=useCallback(()=>setReload(value=>value+1),[]);
  const onJob=useCallback((id:string)=>{setJobId(id);const url=new URL(window.location.href);url.searchParams.set('bulk_job',id);window.history.replaceState(window.history.state,'',url.pathname+url.search+url.hash);},[]);
  const closeJob=useCallback(()=>{setJobId('');const url=new URL(window.location.href);url.searchParams.delete('bulk_job');window.history.replaceState(window.history.state,'',url.pathname+url.search+url.hash);},[]);
  const lastDetailTrigger=useRef<HTMLButtonElement|null>(null);
  const filterQuery=useMemo<BuyerQuery>(()=>({q:query.q,fit:query.fit,review:query.review,queue:query.queue,sort:query.sort,listId:query.listId,size:12,offset:0}),[query.q,query.fit,query.review,query.queue,query.sort,query.listId]);
  const workspace=scope.workspace,project=scope.project;
  function changeQuery(patch:Partial<BuyerQuery>,reset=false){
    const next={...query,...patch,offset:reset?0:(patch.offset??query.offset)};
    setQuery(next);setError('');
    if(typeof window!=='undefined')window.history.replaceState(window.history.state,'',writeBuyerQuery(new URL(window.location.href),next));
  }
  useEffect(()=>{
    if(!workspace||!project)return;
    let active=true;
    void (async()=>{
      setLoading(true);setPage(null);setSnapshot(null);setSelected({});setAllFiltered(false);setExcluded([]);setDetailId(null);setError('');
      try{
        const created=await createBuyerSnapshot(client,session,filterQuery);
        if(active){setSnapshot(created);setQuery(previous=>{if(previous.offset<created.total||previous.offset===0)return previous;const next={...previous,offset:0};window.history.replaceState(window.history.state,'',writeBuyerQuery(new URL(window.location.href),next));return next;});}
      }catch(cause){if(active&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
      finally{if(active)setLoading(false);}
    })();
    return()=>{active=false;};
  },[client,session,workspace,project,filterQuery,reload]);
  useEffect(()=>{
    if(!snapshot||!workspace||!project)return;
    let active=true;
    void (async()=>{
      setLoading(true);setError('');
      try{
        const result=await loadBuyerPage(client,session,snapshot.id,query);
        if(active){setPage(result);setDetailId(null);}
      }catch(cause){if(active&&!(cause instanceof LiveCancelled)){
        setPage(null);setError(cause instanceof LiveError&&cause.status===404?'Snapshot expired. Refresh results.':describeLiveError(cause));
      }}finally{if(active)setLoading(false);}
    })();
    return()=>{active=false;};
  },[client,session,snapshot,query,workspace,project]);
  function selectPage(){
    if(!page)return;
    setAllFiltered(false);setExcluded([]);
    setSelected(previous=>Object.assign({},previous,...page.items.map(buyer=>({[buyer.id]:buyer.version}))));
  }
  function toggle(id:string,version:number){
    if(allFiltered)setExcluded(previous=>previous.includes(id)?previous.filter(value=>value!==id):[...previous,id]);
    else setSelected(previous=>{const next={...previous};if(id in next)delete next[id];else next[id]=version;return next;});
  }
  const selectedCount=allFiltered?(snapshot?.total??0)-excluded.length:Object.keys(selected).length;
  function selection():ReviewSelection|null{
    if(!snapshot||selectedCount<=0)return null;
    return allFiltered?snapshotSelection(snapshot.id,excluded):explicitSelection(Object.entries(selected).map(([id,version])=>({id,version})));
  }
  async function submitReview(){
    const choice=selection();
    if(!choice||reason.trim().length<3){setError('Select buyers and enter a review reason.');return;}
    if(busy||!workspace||!project)return;
    setBusy(true);setError('');
    try{
      const ctx=buyerOperationContext(session),payload={selection:choice,status,reason:reason.trim()};
      const result=await reviewIntent.current.run(JSON.stringify({identity:ctx.identity,payload}),key=>
        createOperationClient(client).requestOperation('reviewBuyers',{
          path:{workspace_id:workspace,project_id:project},header:{'Idempotency-Key':key},body:payload,
        },ctx));
      if(isAsyncJob(result)){onJob(result.id);setReviewResult(null);}
      else{setReviewResult(result);if(result.updated){setReason('');setSelected({});setAllFiltered(false);setExcluded([]);setReload(value=>value+1);}}
    }catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    finally{setBusy(false);}
  }
  async function reviewOneAndNext(buyerId:string,buyerVersion:number,nextStatus:(typeof reviewStatuses)[number],nextReason:string):Promise<boolean>{
    if(!canReview||busy||!workspace||!project||nextReason.trim().length<3)return false;
    setBusy(true);setError('');
    try{
      const ctx=buyerOperationContext(session),payload={selection:explicitSelection([{id:buyerId,version:buyerVersion}]),status:nextStatus,reason:nextReason.trim()};
      const result=await reviewIntent.current.run(JSON.stringify({identity:ctx.identity,payload}),key=>
        createOperationClient(client).requestOperation('reviewBuyers',{
          path:{workspace_id:workspace,project_id:project},header:{'Idempotency-Key':key},body:payload,
        },ctx));
      if(isAsyncJob(result)){onJob(result.id);return false;}
      setReviewResult(result);
      if(result.updated!==1)return false;
      const version=result.results[0]?.version??buyerVersion+1;
      setPage(previous=>previous?{...previous,items:previous.items.map(row=>row.id===buyerId?{...row,version,reviewStatus:nextStatus,reviewReason:nextReason.trim()}:row)}:previous);
      setSelected({});setAllFiltered(false);setExcluded([]);
      return true;
    }catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));return false;}
    finally{setBusy(false);}
  }
  if(!workspace||!project)return <section className="panel" role="status">No project selected. Save a profile to create one.</section>;
  const index=page?.items.findIndex(buyer=>buyer.id===detailId)??-1;
  const current=index>=0?page?.items[index]:undefined;
  return <section className="panel live-buyer-results" aria-label="Buyer results">
    <div className="inline spread"><h2>Buyers</h2><span>{snapshot?`${snapshot.total} in snapshot`:'Loading snapshot...'}</span></div>
    <div className="inline" role="group" aria-label="Buyer filters">
      <label>Search buyers <input aria-label="Search buyers" value={search} onChange={event=>setSearch(event.target.value)} onKeyDown={event=>{if(event.key==='Enter')changeQuery({q:search.trim()},true);}}/></label>
      <button type="button" onClick={()=>changeQuery({q:search.trim()},true)}>Apply filters</button>
      <label>Fit <select aria-label="Fit filter" value={query.fit} onChange={event=>changeQuery({fit:event.target.value as BuyerQuery['fit']},true)}><option value="">Any</option><option value="match">Match</option><option value="needs_review">Needs review</option><option value="not_a_match">Not a match</option></select></label>
      <label>Review <select aria-label="Review filter" value={query.review} onChange={event=>changeQuery({review:event.target.value as BuyerQuery['review']},true)}><option value="">Any</option><option value="awaiting_review">Awaiting review</option><option value="accepted">Accepted</option><option value="rejected">Rejected</option><option value="needs_information">Needs information</option></select></label>
      <label>{t('Queue')} <select aria-label={t('Work queue filter')} value={query.queue} onChange={event=>changeQuery({queue:event.target.value as BuyerQuery['queue']},true)}><option value="">All</option><option value="unassigned">{t('Unassigned')}</option><option value="unknown">{t('Unknown fit')}</option></select></label>
      <label>Sort <select aria-label="Buyer sort" value={query.sort} onChange={event=>changeQuery({sort:event.target.value as BuyerQuery['sort']},true)}><option value="name_asc">Name</option><option value="best_fit">Best fit</option></select></label>
      <button type="button" onClick={()=>setReload(value=>value+1)}>Refresh results</button>
    </div>
    {snapshot?.clipped&&<p role="status">Showing the first 1000 matching buyers. Narrow filters to select all matching buyers.</p>}
    {error&&<p role="alert">{error}</p>}{loading&&<p role="status">Loading buyers...</p>}
    {page&&<>
      <div className="inline"><button type="button" disabled={!page.items.length} onClick={selectPage}>Select this page</button>
        <button type="button" disabled={!snapshot||snapshot.clipped||!snapshot.total} onClick={()=>{setAllFiltered(true);setSelected({});setExcluded([]);}}>Select all filtered</button>
        <button type="button" onClick={()=>{setAllFiltered(false);setSelected({});setExcluded([]);}}>Clear selection</button>
        <span aria-live="polite">{selectedCount} selected {allFiltered?'across this snapshot':'explicitly'}</span>
      </div>
      {page.items.length?page.items.map(buyer=><div className="activity" key={buyer.id}>
        <input type="checkbox" aria-label={`Select ${buyer.name}`} checked={allFiltered?!excluded.includes(buyer.id):buyer.id in selected} onChange={()=>toggle(buyer.id,buyer.version)}/>
        <div><b>{buyer.name}</b><p>{buyer.fitVerdict||'Fit not assessed'} · {buyer.reviewStatus||'Not reviewed'} · {buyer.note||'No note'}</p></div>
        <button type="button" onClick={event=>{lastDetailTrigger.current=event.currentTarget;setDetailId(buyer.id);}}>Details</button>
        {onManualOutcome&&<button type="button" onClick={()=>onManualOutcome(buyer.id)}>{t('Log outcome')}</button>}
      </div>):<p>No buyers in this snapshot.</p>}
      <div className="inline spread"><div className="inline"><button type="button" disabled={query.offset===0||loading} onClick={()=>changeQuery({offset:Math.max(0,query.offset-query.size)})}>Previous page</button>
        <span>Rows {page.total?query.offset+1:0}–{Math.min(query.offset+page.items.length,page.total)} of {page.total}</span>
        <button type="button" disabled={loading||query.offset+page.items.length>=page.total} onClick={()=>changeQuery({offset:query.offset+query.size})}>Next page</button></div>
        <label>Rows per page <select aria-label="Rows per page" value={query.size} onChange={event=>changeQuery({size:Number(event.target.value) as BuyerQuery['size'],offset:0})}><option value={8}>8</option><option value={12}>12</option><option value={24}>24</option></select></label>
      </div>
    </>}
    {canReview&&page&&<div className="inline"><label>Review status <select aria-label="Review status" value={status} onChange={event=>setStatus(event.target.value as typeof status)}>{reviewStatuses.map(value=><option key={value} value={value}>{value}</option>)}</select></label>
      <label>Review reason <input aria-label="Review reason" value={reason} onChange={event=>setReason(event.target.value)}/></label>
      <button type="button" disabled={busy||selectedCount<=0} onClick={()=>void submitReview()}>{busy?'Reviewing...':'Apply review'}</button></div>}
    {reviewResult&&<p role="status">Review: {reviewResult.updated} updated; {reviewResult.blocked} blocked; {reviewResult.conflicts} conflicts. {reviewResult.results.filter(row=>row.status==='blocked'||row.status==='conflict').map(row=>`${row.id}: ${row.reason_code??row.status}`).join('; ')}</p>}
    {canEdit&&<ExportDialog key={`export:${workspace}:${project}`} locale={locale} selection={selection()} canExport={canEdit}/>}
    <LiveBulkActions key={`bulk:${workspace}:${project}`} locale={locale} selection={selection()} count={selectedCount} canAssign={canAssign} ownMembershipId={ownMembershipId} onJob={onJob} onCommitted={onCommitted}/>
    {jobId&&<BulkJobPanel locale={locale} jobId={jobId} onJob={onJob} onCommitted={onCommitted} onClose={closeJob}/>}
    <LiveBuyerManagementControls key={`management:${workspace}:${project}`} onJob={onJob} query={query} onApplyQuery={patch=>{setSelected({});setAllFiltered(false);setExcluded([]);changeQuery(patch,true);setReload(value=>value+1);}} selection={selection()} canManage={canEdit}/>
    {current&&<LiveBuyerDetail key={current.id} buyer={current} locale={locale} canEdit={canEdit} canQuote={canQuote} canReview={canReview} ownMembershipId={ownMembershipId}
      onReviewAndNext={(nextStatus,nextReason)=>reviewOneAndNext(current.id,current.version,nextStatus,nextReason)}
      onChanged={updated=>{setPage(previous=>previous?{...previous,items:previous.items.map(row=>row.id===updated.id?updated:row)}:previous);setSelected({});setAllFiltered(false);setExcluded([]);}}
      onClose={()=>{setDetailId(null);setReload(value=>value+1);lastDetailTrigger.current?.focus();}}
      onPrevious={index>0?()=>setDetailId(page!.items[index-1].id):undefined}
      onNext={page&&index<page.items.length-1?()=>setDetailId(page.items[index+1].id):undefined}/>}
  </section>;
}
