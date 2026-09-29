'use client';
import {useEffect,useRef,useState} from 'react';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
import {toBuyers,toEvidencePage,type LiveBuyer,type LiveEvidence} from '@/services/live/mapping';
import {ActionIntent} from '@/services/live/action-intent';
import {liveZh} from './locale';
import {ContactQuotePreview} from './contact-quote';
import {useRouter} from 'next/navigation';

type Tab='Overview'|'Evidence'|'Contacts'|'Activity';
function permittedUrl(value:string|null):string|null{
  if(!value)return null;
  try{const url=new URL(value);return ['http:','https:'].includes(url.protocol)?url.href:null;}catch{return null;}
}
export function LiveBuyerDetail({buyer,locale,canEdit,canQuote,canReview,ownMembershipId,onReviewAndNext,onChanged,onClose,onPrevious,onNext}:{
  buyer:LiveBuyer;locale:'en'|'zh-HK';canEdit:boolean;canQuote:boolean;canReview:boolean;ownMembershipId:string|null;
  onReviewAndNext:(status:'accepted'|'rejected'|'needs_information',reason:string)=>Promise<boolean>;
  onChanged:(buyer:LiveBuyer)=>void;onClose:()=>void;
  onPrevious?:()=>void;onNext?:()=>void;
}) {
  const {session,client}=useWorkspaceSession();
  const router=useRouter();
  const t=(value:string)=>locale==='zh-HK'?(liveZh[value]||value):value;
  const [full,setFull]=useState<LiveBuyer|null>(null);
  const [evidence,setEvidence]=useState<LiveEvidence[]|null>(null);
  const [note,setNote]=useState(buyer.note??'');
  const [tab,setTab]=useState<Tab>('Overview');
  const [reviewStatus,setReviewStatus]=useState<'accepted'|'rejected'|'needs_information'>('accepted');
  const [reviewReason,setReviewReason]=useState('');
  const [error,setError]=useState('');
  const [saveError,setSaveError]=useState('');
  const [saving,setSaving]=useState(false);
  const titleRef=useRef<HTMLHeadingElement>(null);
  const saveIntent=useRef(new ActionIntent<LiveBuyer>());
  useEffect(()=>{
    titleRef.current?.focus();
    const previous=document.body.style.overflow;document.body.style.overflow='hidden';
    const onKey=(event:KeyboardEvent)=>{if(event.key==='Escape')onClose();};
    window.addEventListener('keydown',onKey);
    return()=>{document.body.style.overflow=previous;window.removeEventListener('keydown',onKey);};
  },[onClose]);
  useEffect(()=>{
    let active=true;const own=new AbortController();
    const scope=session.current();
    if(!scope.workspace||!scope.project)return()=>{active=false;own.abort();};
    const identity=session.identity();
    const signal=AbortSignal.any([session.controller().signal,own.signal]);
    const path=`/v1/workspaces/${scope.workspace}/buyers/${buyer.id}`;
    void (async()=>{
      try{
        const fullBuyer=toBuyers({items:[await client.request<unknown>({path,token:session.token(),scope:identity,signal})]})[0];
        const found:LiveEvidence[]=[];
        for(let offset=0;;){
          const batch=toEvidencePage(await client.request<unknown>({path:`${path}/evidence?offset=${offset}&limit=100`,token:session.token(),scope:identity,signal}));
          found.push(...batch.items);
          if(found.length>=batch.total)break;
          if(!batch.items.length)throw new Error('Evidence page incomplete');
          offset+=batch.items.length;
        }
        if(!active||!session.isCurrent(identity))return;
        setFull(fullBuyer);setNote(fullBuyer.note??'');setEvidence(found);setError('');
      }catch(cause){if(active&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    })();
    return()=>{active=false;own.abort();};
  },[client,session,buyer.id]);
  async function savePatch(patch:{note?:string;owner_membership_id?:string|null},next=false){
    if(!canEdit||saving)return;
    const scope=session.current(),identity=session.identity();
    if(!scope.workspace||!full)return;
    setSaving(true);setSaveError('');
    try{
      const updated=await saveIntent.current.run(JSON.stringify({identity,buyer:buyer.id,version:full.version,patch}),async key=>
        toBuyers({items:[await client.request<unknown>({
          path:`/v1/workspaces/${scope.workspace}/buyers/${buyer.id}`,method:'PATCH',
          scope:identity,token:session.token(),signal:session.controller().signal,
          idempotencyKey:key,ifMatch:`"${full.version}"`,body:patch,
        })]})[0]);
      if(!session.isCurrent(identity))throw new LiveCancelled('scope changed');
      setFull(updated);setNote(updated.note??'');onChanged(updated);
      if(next)onNext?.();
    }catch(cause){if(!(cause instanceof LiveCancelled))setSaveError(describeLiveError(cause));}
    finally{setSaving(false);}
  }
  async function saveReviewAndNext(){
    if(!canReview||saving||reviewReason.trim().length<3)return;
    setSaving(true);setSaveError('');
    try{
      const applied=await onReviewAndNext(reviewStatus,reviewReason.trim());
      if(!applied){setSaveError('Review was blocked or conflicted. Refresh the buyer and inspect the assessment.');return;}
      setReviewReason('');
      if(onNext)onNext();else onClose();
    }finally{setSaving(false);}
  }
  const data=full??buyer;
  return <><div className="live-buyer-backdrop" onClick={onClose} aria-hidden="true" />
    <section className="panel live-buyer-drawer" role="dialog" aria-modal="true" aria-label={`Buyer details: ${buyer.name}`}>
    <div className="inline spread"><h3 ref={titleRef} tabIndex={-1}>{buyer.name}</h3><div className="inline">
      <button type="button" disabled={!onPrevious} onClick={onPrevious}>Previous buyer</button>
      <button type="button" disabled={!onNext} onClick={onNext}>Next buyer</button>
      <button type="button" onClick={onClose}>Close details</button>
    </div></div>
    <div role="tablist" aria-label="Buyer dossier tabs" className="inline">{(['Overview','Evidence','Contacts','Activity'] as const).map(name=>
      <button type="button" role="tab" aria-selected={tab===name} key={name} onClick={()=>setTab(name)}>{name}</button>)}</div>
    {error&&<p role="alert">{error}</p>}
    {!full||evidence===null?<p role="status">Loading buyer dossier...</p>:<div role="tabpanel">
      {tab==='Overview'&&<><p>Company: {data.name}</p><p>Domain: {data.domain??'Unknown'}</p><p>Fit: {data.fitVerdict??'Not assessed'}{data.fitFreshness==='stale'&&` · ${t('stale evidence')}`}</p>
        {data.fitRationale&&<p>Assessment: {data.fitRationale}</p>}{canEdit&&data.reviewStatus==='accepted'&&data.fitVerdict==='match'&&data.fitFreshness==='current'&&<button type="button" onClick={()=>{const scope=session.current();if(scope.workspace&&scope.project){onClose();router.push(`/app/outreach?${new URLSearchParams({workspace:scope.workspace,project:scope.project,buyer:data.id})}`);}}}>{t('Prepare grounded draft')}</button>}<p>Human review: {data.reviewStatus??'Not reviewed'}</p>
        <p>Owner membership: {data.ownerMembershipId??'Unassigned'}</p><p>Evidence records: {data.evidenceCount}</p>
        {canEdit&&<><div className="inline"><label>Buyer note <textarea aria-label="Buyer note" maxLength={20000} value={note} onChange={event=>setNote(event.target.value)}/></label>
          <button type="button" disabled={saving} onClick={()=>void savePatch({note})}>{saving?'Saving...':'Save note'}</button>
          <button type="button" disabled={saving||!onNext} onClick={()=>void savePatch({note},true)}>Save note and next</button></div>
          <div className="inline">{ownMembershipId&&data.ownerMembershipId!==ownMembershipId&&<button type="button" disabled={saving} onClick={()=>void savePatch({owner_membership_id:ownMembershipId})}>Assign to me</button>}
            {data.ownerMembershipId&&<button type="button" disabled={saving} onClick={()=>void savePatch({owner_membership_id:null})}>Clear owner</button>}</div></>}
        {canReview&&<div className="inline"><label>Individual review status <select aria-label="Individual review status" value={reviewStatus} onChange={event=>setReviewStatus(event.target.value as typeof reviewStatus)}><option value="accepted">Accepted</option><option value="rejected">Rejected</option><option value="needs_information">Needs information</option></select></label>
          <label>Individual review reason <input aria-label="Individual review reason" value={reviewReason} onChange={event=>setReviewReason(event.target.value)}/></label>
          <button type="button" disabled={saving||reviewReason.trim().length<3} onClick={()=>void saveReviewAndNext()}>{onNext?'Save review and next':'Save review'}</button></div>}
        {saveError&&<p role="alert">{saveError}</p>}</>}
      {tab==='Evidence'&&(evidence.length?evidence.map(row=><div className="activity" key={row.id}><div><b>{t(row.relationship)}</b>
        <p>{row.excerpt}</p>{row.translatedExcerpt&&<p>{t('Translation')}: {row.translatedExcerpt}</p>}
        <p>{t('Requirement')}: {row.requirementId??t('Unlinked')} · {t(row.kind)} · {t(row.status)}</p>
        {row.status==='available'&&permittedUrl(row.sourceUrl)&&<a href={permittedUrl(row.sourceUrl)!} target="_blank" rel="noopener noreferrer">{t('Source')}</a>}
        {row.retrievedAt&&<p>{t('Retrieved')}: {row.retrievedAt}</p>}
        {row.observedAt&&<p>{t('Observed')}: {row.observedAt}</p>}
        {row.retentionUntil&&<p>{t('Retention until')}: {row.retentionUntil}</p>}
        {row.originalLanguage&&<p>{t('Original language')}: {row.originalLanguage}</p>}
        {row.contentHash&&<p>{t('Content hash')}: {row.contentHash}</p>}
      </div></div>):<p>{t('No evidence recorded for this buyer.')}</p>)}
      {tab==='Contacts'&&<><p>Contact research: {data.contactResearchStatus??'Unknown'}</p>
        <p>No contact details are available in this read model.</p>
        <ContactQuotePreview key={`${data.id}:${data.version}`} buyerId={data.id} buyerVersion={data.version} canQuote={canQuote} t={t}/></>}
      {tab==='Activity'&&<><p>Review: {data.reviewStatus??'No human review recorded'}</p>
        {data.reviewReason&&<p>Reason: {data.reviewReason}</p>}{data.reviewAt&&<p>Reviewed at: {data.reviewAt}</p>}</>}
    </div>}
  </section></>;
}
