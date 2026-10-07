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
import {BulkManifestMaintenance} from './bulk-manifest';
import {startNewManifest} from '@/services/live/bulk-manifests';

const reviewStatuses=['accepted','rejected','needs_information'] as const;
const initial=():BuyerQuery=>readBuyerQuery(typeof window==='undefined'?'':window.location.search);
export function LiveBuyerResults({canReview=false,canEdit=false,canQuote=false,canAssign=false,ownMembershipId=null,locale='en',onManualOutcome}:{canReview?:boolean;canEdit?:boolean;canQuote?:boolean;canAssign?:boolean;ownMembershipId?:string|null;locale?:'en'|'zh-HK';onManualOutcome?:(buyerId:string,buyerName:string)=>void}){
  const {session,client}=useWorkspaceSession();
  const t=(value:string)=>locale==='zh-HK'?(liveZh[value]||value):value;
  const sessionSnapshot=useSessionSnapshot(),scope=sessionSnapshot.scope;
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
  const [manifestSourceState,setManifestSource]=useState<{identity:string;value:{id:string;manifest_id:string}}|undefined>();
  const manifestSource=manifestSourceState?.identity===sessionSnapshot.identity?manifestSourceState.value:undefined;
  const [jobId,setJobId]=useState(()=>typeof window==='undefined'?'':new URLSearchParams(window.location.search).get('bulk_job')??'');
  const reviewIntent=useRef(new ActionIntent<components['schemas']['BulkResult']|components['schemas']['AsyncJob']>());
  const onCommitted=useCallback(()=>setReload(value=>value+1),[]);
  const onJob=useCallback((id:string)=>{setJobId(id);const url=new URL(window.location.href);url.searchParams.set('bulk_job',id);window.history.replaceState(window.history.state,'',url.pathname+url.search+url.hash);},[]);
  const closeJob=useCallback(()=>{setJobId('');const url=new URL(window.location.href);url.searchParams.delete('bulk_job');window.history.replaceState(window.history.state,'',url.pathname+url.search+url.hash);},[]);
  const previewFailedManifest=useCallback((source:{id:string;manifest_id:string})=>{
    startNewManifest(session);setManifestSource({identity:session.identity(),value:source});
    const url=new URL(window.location.href);url.searchParams.delete('bulk_manifest');
    window.history.replaceState(window.history.state,'',url.pathname+url.search+url.hash);
  },[session]);
  const lastDetailTrigger=useRef<HTMLButtonElement|null>(null),buyerRoot=useRef<HTMLElement|null>(null);
  const returnDetailFocus=useRef<{id:string;snapshot:string;identity:string}|null>(null);
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
  useEffect(()=>{
    const pending=returnDetailFocus.current;
    if(!pending)return;
    if(pending.identity!==sessionSnapshot.identity){returnDetailFocus.current=null;return;}
    if(detailId||!snapshot||!page||snapshot.id===pending.snapshot)return;
    const trigger=buyerRoot.current?.querySelector<HTMLButtonElement>(`button[data-buyer-id="${CSS.escape(pending.id)}"]`);
    (trigger??buyerRoot.current?.querySelector<HTMLButtonElement>('[data-refresh-buyers]'))?.focus();
    returnDetailFocus.current=null;
  },[page,snapshot,detailId,sessionSnapshot.identity]);
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
  if(!workspace||!project)return <section className="panel" role="status">{t('No project selected. Save a profile to create one.')}</section>;
  const index=page?.items.findIndex(buyer=>buyer.id===detailId)??-1;
  const current=index>=0?page?.items[index]:undefined;
  return <section ref={buyerRoot} className="panel live-buyer-results" aria-label={t('Buyer results')}>
    <div className="inline spread"><h2>{t('Buyers')}</h2><span>{snapshot?t('{count} in snapshot').replace('{count}',String(snapshot.total)):t('Loading snapshot...')}</span></div>
    <div className="inline" role="group" aria-label={t('Buyer filters')}>
      <label>{t('Search buyers')} <input aria-label={t('Search buyers')} value={search} onChange={event=>setSearch(event.target.value)} onKeyDown={event=>{if(event.key==='Enter')changeQuery({q:search.trim()},true);}}/></label>
      <button type="button" onClick={()=>changeQuery({q:search.trim()},true)}>{t('Apply filters')}</button>
      <label>{t('Fit')} <select aria-label={t('Fit filter')} value={query.fit} onChange={event=>changeQuery({fit:event.target.value as BuyerQuery['fit']},true)}><option value="">{t('Any')}</option><option value="match">{t('Match')}</option><option value="needs_review">{t('Needs review')}</option><option value="not_a_match">{t('Not a match')}</option></select></label>
      <label>{t('Review')} <select aria-label={t('Review filter')} value={query.review} onChange={event=>changeQuery({review:event.target.value as BuyerQuery['review']},true)}><option value="">{t('Any')}</option><option value="awaiting_review">{t('Awaiting review')}</option><option value="accepted">{t('Accepted')}</option><option value="rejected">{t('Rejected')}</option><option value="needs_information">{t('Needs information')}</option></select></label>
      <label>{t('Queue')} <select aria-label={t('Work queue filter')} value={query.queue} onChange={event=>changeQuery({queue:event.target.value as BuyerQuery['queue']},true)}><option value="">{t('All')}</option><option value="unassigned">{t('Unassigned')}</option><option value="unknown">{t('Unknown fit')}</option></select></label>
      <label>{t('Sort')} <select aria-label={t('Buyer sort')} value={query.sort} onChange={event=>changeQuery({sort:event.target.value as BuyerQuery['sort']},true)}><option value="name_asc">{t('Name')}</option><option value="best_fit">{t('Best fit')}</option></select></label>
      <button type="button" data-refresh-buyers onClick={()=>setReload(value=>value+1)}>{t('Refresh results')}</button>
    </div>
    {selectedCount>0&&<div className="live-selection-bar" role="group" aria-label={t('Selected buyer actions')}>
      <span role="status">{t('{count} selected').replace('{count}',String(selectedCount))}</span>
      <a href="#selected-buyer-tools">{t('Selected actions')}</a>
      <button type="button" onClick={()=>{setAllFiltered(false);setSelected({});setExcluded([]);}}>{t('Clear selection')}</button>
    </div>}
    {snapshot?.clipped&&<p role="status">{t('Showing the first 1000 matching buyers. Narrow filters to select all matching buyers.')}</p>}
    {error&&<p role="alert">{t(error)}</p>}{loading&&<p role="status">{t('Loading buyers...')}</p>}
    {page&&<>
      <div className="inline"><button type="button" disabled={!page.items.length} onClick={selectPage}>{t('Select this page')}</button>
        <button type="button" disabled={!snapshot||snapshot.clipped||!snapshot.total} onClick={()=>{setAllFiltered(true);setSelected({});setExcluded([]);}}>{t('Select all filtered')}</button>
        <button type="button" onClick={()=>{setAllFiltered(false);setSelected({});setExcluded([]);}}>{t('Clear selection')}</button>
        <span aria-live="polite">{t(allFiltered?'{count} selected across this snapshot':'{count} selected explicitly').replace('{count}',String(selectedCount))}</span>
      </div>
      {page.items.length?page.items.map(buyer=><div className="activity" key={buyer.id}>
        <input type="checkbox" aria-label={t('Select {buyer}').replace('{buyer}',buyer.name)} checked={allFiltered?!excluded.includes(buyer.id):buyer.id in selected} onChange={()=>toggle(buyer.id,buyer.version)}/>
        <div><b>{buyer.name}</b><p>{t(buyer.fitVerdict||'Fit not assessed')} · {t(buyer.reviewStatus||'Not reviewed')} · {buyer.note||t('No note')}</p></div>
        <button type="button" data-buyer-id={buyer.id} onClick={event=>{lastDetailTrigger.current=event.currentTarget;setDetailId(buyer.id);}}>{t('Details')}</button>
        {onManualOutcome&&<button type="button" onClick={()=>onManualOutcome(buyer.id,buyer.name)}>{t('Log outcome')}</button>}
      </div>):<p>{t('No buyers in this snapshot.')}</p>}
      <div className="inline spread"><div className="inline"><button type="button" disabled={query.offset===0||loading} onClick={()=>changeQuery({offset:Math.max(0,query.offset-query.size)})}>{t('Previous page')}</button>
        <span>{t('Rows {from}–{to} of {total}').replace('{from}',String(page.total?query.offset+1:0)).replace('{to}',String(Math.min(query.offset+page.items.length,page.total))).replace('{total}',String(page.total))}</span>
        <button type="button" disabled={loading||query.offset+page.items.length>=page.total} onClick={()=>changeQuery({offset:query.offset+query.size})}>{t('Next page')}</button></div>
        <label>{t('Rows per page')} <select aria-label={t('Rows per page')} value={query.size} onChange={event=>changeQuery({size:Number(event.target.value) as BuyerQuery['size'],offset:0})}><option value={8}>8</option><option value={12}>12</option><option value={24}>24</option></select></label>
      </div>
    </>}
    <div id="selected-buyer-tools">{canReview&&page&&selectedCount>0&&<div className="inline"><label>{t('Review status')} <select aria-label={t('Review status')} value={status} onChange={event=>setStatus(event.target.value as typeof status)}>{reviewStatuses.map(value=><option key={value} value={value}>{t(value)}</option>)}</select></label>
      <label>{t('Review reason')} <input aria-label={t('Review reason')} value={reason} onChange={event=>setReason(event.target.value)}/></label>
      <button type="button" disabled={busy||selectedCount<=0} onClick={()=>void submitReview()}>{t(busy?'Reviewing...':'Apply review')}</button></div>}
    {reviewResult&&<p role="status">{t('Review: {updated} updated; {blocked} blocked; {conflicts} conflicts.').replace('{updated}',String(reviewResult.updated)).replace('{blocked}',String(reviewResult.blocked)).replace('{conflicts}',String(reviewResult.conflicts))} {reviewResult.results.filter(row=>row.status==='blocked'||row.status==='conflict').map(row=>`${row.id}: ${row.reason_code??row.status}`).join('; ')}</p>}
    {canEdit&&selectedCount>0&&<ExportDialog key={`export:${workspace}:${project}`} locale={locale} selection={selection()} canExport={canEdit}/>}
    <LiveBulkActions key={`bulk:${sessionSnapshot.identity}`} locale={locale} selection={selection()} count={selectedCount} canAssign={canAssign} ownMembershipId={ownMembershipId} onJob={onJob} onCommitted={onCommitted}/>
    </div>
    {(canAssign||canReview||canEdit)&&<BulkManifestMaintenance key={`manifest:${sessionSnapshot.identity}:${manifestSource?.id??''}`} locale={locale} query={filterQuery} canAssign={canAssign} canReview={canReview} canManage={canEdit} ownMembershipId={ownMembershipId} onJob={onJob} onCommitted={onCommitted} sourceJob={manifestSource}/>}
    {jobId&&<BulkJobPanel key={`job:${sessionSnapshot.identity}:${jobId}`} locale={locale} jobId={jobId} onManifestRetry={previewFailedManifest} onJob={onJob} onCommitted={onCommitted} onClose={closeJob}/>}
    <LiveBuyerManagementControls key={`management:${workspace}:${project}`} locale={locale} onJob={onJob} query={query} onApplyQuery={patch=>{setSelected({});setAllFiltered(false);setExcluded([]);changeQuery(patch,true);setReload(value=>value+1);}} selection={selection()} canManage={canEdit}/>
    {current&&<LiveBuyerDetail key={current.id} buyer={current} locale={locale} canEdit={canEdit} canQuote={canQuote} canReview={canReview} ownMembershipId={ownMembershipId}
      onReviewAndNext={(nextStatus,nextReason)=>reviewOneAndNext(current.id,current.version,nextStatus,nextReason)}
      onChanged={updated=>{setPage(previous=>previous?{...previous,items:previous.items.map(row=>row.id===updated.id?updated:row)}:previous);setSelected({});setAllFiltered(false);setExcluded([]);}}
      onClose={()=>{if(snapshot)returnDetailFocus.current={id:lastDetailTrigger.current?.dataset.buyerId??current.id,snapshot:snapshot.id,identity:sessionSnapshot.identity};setDetailId(null);setReload(value=>value+1);}}
      onPrevious={index>0?()=>setDetailId(page!.items[index-1].id):undefined}
      onNext={page&&index<page.items.length-1?()=>setDetailId(page.items[index+1].id):undefined}/>}
  </section>;
}
