'use client';
import {useEffect,useRef,useState} from 'react';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {LiveCancelled,LiveError,describeLiveError} from '@/services/live/client';
import {toBuyers,toEvidencePage,type LiveBuyer,type LiveEvidence} from '@/services/live/mapping';
import {ActionIntent} from '@/services/live/action-intent';
import {createBuyerSourceCheck,listBuyerSourceChecks,type LiveBuyerSourceCheck,type LiveBuyerSourceCheckInput,type LiveBuyerSourceCheckGrade} from '@/services/live/buyer-source-checks';
import {liveZh} from './locale';
import {ContactQuotePreview} from './contact-quote';
import {BuyerImportSourcePanel} from './buyer-import-source';
import {useRouter} from 'next/navigation';

type Tab='Overview'|'Evidence'|'Contacts'|'Activity';
type SourceCheckForm={checkedOn:string;grade:LiveBuyerSourceCheckGrade|'';rationale:string;limitations:string;references:{title:string;url:string}[]};
function localDateInput():string{const date=new Date();date.setMinutes(date.getMinutes()-date.getTimezoneOffset());return date.toISOString().slice(0,10);}
function newSourceCheckForm():SourceCheckForm{return {checkedOn:localDateInput(),grade:'',rationale:'',limitations:'',references:[{title:'',url:''}]};}
function isPublicSourceUrl(value:string):boolean{try{const url=new URL(value);return ['http:','https:'].includes(url.protocol)&&!url.username&&!url.password&&!/\s/.test(value);}catch{return false;}}
function permittedUrl(value:string|null):string|null{
  if(!value)return null;
  try{const url=new URL(value);return ['http:','https:'].includes(url.protocol)&&!url.username&&!url.password&&!/\s/.test(value)?url.href:null;}catch{return null;}
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
  const [sourceCheckData,setSourceCheckData]=useState<{buyerId:string;checks:LiveBuyerSourceCheck[]|null;error:string}>(()=>({buyerId:buyer.id,checks:null,error:''}));
  const sourceCheckDataForBuyer=sourceCheckData.buyerId===buyer.id?sourceCheckData:{buyerId:buyer.id,checks:null,error:''};
  const sourceChecks=sourceCheckDataForBuyer.checks,sourceCheckLoadError=sourceCheckDataForBuyer.error;
  const [sourceFormState,setSourceFormState]=useState<{buyerId:string;form:SourceCheckForm}>(()=>({buyerId:buyer.id,form:newSourceCheckForm()}));
  const sourceForm=sourceFormState.buyerId===buyer.id?sourceFormState.form:newSourceCheckForm();
  const [sourceSaving,setSourceSaving]=useState(false);
  const [sourceCheckError,setSourceCheckError]=useState('');
  const [sourceCheckSaved,setSourceCheckSaved]=useState(false);
  const [pendingSourceCheckState,setPendingSourceCheckState]=useState<{buyerId:string;identity:string;input:LiveBuyerSourceCheckInput}|null>(null);
  const pendingSourceCheck=pendingSourceCheckState?.buyerId===buyer.id?pendingSourceCheckState:null;
  const sourceCheckIntent=useRef(new ActionIntent<LiveBuyerSourceCheck>());
  const [sourceNavigationBlocked,setSourceNavigationBlocked]=useState(false);
  const sourceNavigationBlockedRef=useRef(false);
  const updateSourceForm=(patch:Partial<SourceCheckForm>)=>{
    const current=sourceFormState.buyerId===buyer.id?sourceFormState.form:newSourceCheckForm();
    setSourceFormState({buyerId:buyer.id,form:{...current,...patch}});setSourceCheckError('');setSourceCheckSaved(false);
  };
  useEffect(()=>{
    titleRef.current?.focus();
    const previous=document.body.style.overflow;document.body.style.overflow='hidden';
    const onKey=(event:KeyboardEvent)=>{if(event.key==='Escape'&&!sourceNavigationBlockedRef.current)onClose();};
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
  useEffect(()=>{
    let active=true;const own=new AbortController();
    const scope=session.current();
    if(!scope.workspace)return()=>{active=false;own.abort();};
    const identity=session.identity();
    const signal=AbortSignal.any([session.controller().signal,own.signal]);
    void listBuyerSourceChecks(client,session,buyer.id,signal).then(checks=>{
      if(!active||!session.isCurrent(identity))return;
      setSourceCheckData({buyerId:buyer.id,checks,error:''});
    }).catch(cause=>{
      if(!active||cause instanceof LiveCancelled||!session.isCurrent(identity))return;
      setSourceCheckData({buyerId:buyer.id,checks:[],error:describeLiveError(cause)});
    });
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
  async function saveSourceCheck(retry=false){
    if(!canEdit||sourceSaving)return;
    const identity=session.identity(),pending=pendingSourceCheck;
    const input=retry&&pending?pending.input:{
      checkedOn:sourceForm.checkedOn,grade:sourceForm.grade as LiveBuyerSourceCheckGrade,
      rationale:sourceForm.rationale.trim(),limitations:sourceForm.limitations.trim()||null,
      references:sourceForm.references.map(reference=>({title:reference.title.trim(),url:reference.url.trim()})),
    };
    if(pending&&pending.identity!==identity){setSourceCheckError(t('This source check belongs to another workspace session. Reload and inspect saved checks before retrying.'));return;}
    if(!retry&&!sourceFormValid){setSourceCheckError(t('Enter a valid date, grade, rationale and 1–10 valid HTTP(S) source references.'));return;}
    if(retry&&!pending)return;
    if(pending&&!retry)return;
    const scope=session.current();if(!scope.workspace)return;
    let retainNavigation=false;
    sourceNavigationBlockedRef.current=true;setSourceNavigationBlocked(true);setSourceSaving(true);setSourceCheckError('');setSourceCheckSaved(false);
    try{
      const saved=await sourceCheckIntent.current.run(JSON.stringify({identity,buyer:buyer.id,input}),key=>
        createBuyerSourceCheck(client,session,buyer.id,input,key,session.controller().signal));
      if(!session.isCurrent(identity))throw new LiveCancelled('scope changed');
      setSourceCheckData(current=>{
        const existing=current.buyerId===buyer.id?current.checks??[]:[];
        return {buyerId:buyer.id,checks:existing.some(check=>check.id===saved.id)?existing:[...existing,saved],error:''};
      });
      setPendingSourceCheckState(null);setSourceFormState({buyerId:buyer.id,form:newSourceCheckForm()});setSourceCheckSaved(true);
    }catch(cause){
      if((cause instanceof LiveError&&cause.retryable)||cause instanceof LiveCancelled){
        retainNavigation=true;sourceNavigationBlockedRef.current=true;setSourceNavigationBlocked(true);
        setPendingSourceCheckState(pending??{buyerId:buyer.id,identity,input});
        setSourceCheckError(t('The source check result is unknown. Retry the same source check; its original details and key are retained.'));
      }else setSourceCheckError(describeLiveError(cause));
    }finally{setSourceSaving(false);if(!retainNavigation){sourceNavigationBlockedRef.current=false;setSourceNavigationBlocked(false);}}
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
  const sourceFormValid=!!sourceForm.checkedOn&&!!sourceForm.grade&&!!sourceForm.rationale.trim()&&sourceForm.references.length>=1&&sourceForm.references.length<=10&&sourceForm.references.every(reference=>!!reference.title.trim()&&reference.title.trim().length<=300&&isPublicSourceUrl(reference.url.trim())&&reference.url.trim().length<=2048);
  return <><div className="live-buyer-backdrop" onClick={()=>{if(!sourceNavigationBlocked)onClose();}} aria-hidden="true" />
    <section className="panel live-buyer-drawer" role="dialog" aria-modal="true" aria-label={t('Buyer details: {buyer}').replace('{buyer}',buyer.name)}>
    <div className="inline spread"><h3 ref={titleRef} tabIndex={-1}>{buyer.name}</h3><div className="inline">
      <button type="button" disabled={!onPrevious||sourceNavigationBlocked} onClick={onPrevious}>{t('Previous buyer')}</button>
      <button type="button" disabled={!onNext||sourceNavigationBlocked} onClick={onNext}>{t('Next buyer')}</button>
      <button type="button" disabled={sourceNavigationBlocked} onClick={onClose}>{t('Close details')}</button>
    </div></div>
    <div role="tablist" aria-label={t('Buyer dossier tabs')} className="inline">{(['Overview','Evidence','Contacts','Activity'] as const).map(name=>
      <button type="button" role="tab" aria-selected={tab===name} key={name} onClick={()=>setTab(name)}>{t(name)}</button>)}</div>
    {error&&<p role="alert">{error}</p>}
    {!full||evidence===null?<p role="status">{t('Loading buyer dossier...')}</p>:<div role="tabpanel">
      {tab==='Overview'&&<><p>{t('Company')}: {data.name}</p><p>{t('Domain')}: {data.domain??t('Unknown')}</p><p>{t('Fit')}: {t(data.fitVerdict??'Not assessed')}{data.fitFreshness==='stale'&&` · ${t('stale evidence')}`}</p>
        {data.fitRationale&&<p>{t('Assessment')}: {data.fitRationale}</p>}{canEdit&&data.reviewStatus==='accepted'&&data.fitVerdict==='match'&&data.fitFreshness==='current'&&<button type="button" onClick={()=>{const scope=session.current();if(scope.workspace&&scope.project){onClose();router.push(`/app/outreach?${new URLSearchParams({workspace:scope.workspace,project:scope.project,buyer:data.id})}`);}}}>{t('Prepare grounded draft')}</button>}<p>{t('Human review')}: {t(data.reviewStatus??'Not reviewed')}</p>
        <p>{t('Owner membership')}: {data.ownerMembershipId??t('Unassigned')}</p><p>{t('Evidence records')}: {data.evidenceCount}</p>
        <BuyerImportSourcePanel key={`${session.identity()}:${buyer.id}`} buyerId={buyer.id} t={t}/>
        {canEdit&&<><div className="inline"><label>{t('Buyer note')} <textarea aria-label={t('Buyer note')} maxLength={20000} value={note} onChange={event=>setNote(event.target.value)}/></label>
          <button type="button" disabled={saving} onClick={()=>void savePatch({note})}>{saving?t('Saving...'):t('Save note')}</button>
          <button type="button" disabled={saving||!onNext} onClick={()=>void savePatch({note},true)}>{t('Save note and next')}</button></div>
          <div className="inline">{ownMembershipId&&data.ownerMembershipId!==ownMembershipId&&<button type="button" disabled={saving} onClick={()=>void savePatch({owner_membership_id:ownMembershipId})}>{t('Assign to me')}</button>}
            {data.ownerMembershipId&&<button type="button" disabled={saving} onClick={()=>void savePatch({owner_membership_id:null})}>{t('Clear owner')}</button>}</div></>}
        {canReview&&<div className="inline"><label>{t('Individual review status')} <select aria-label={t('Individual review status')} value={reviewStatus} onChange={event=>setReviewStatus(event.target.value as typeof reviewStatus)}><option value="accepted">{t('Accepted')}</option><option value="rejected">{t('Rejected')}</option><option value="needs_information">{t('Needs information')}</option></select></label>
          <label>{t('Individual review reason')} <input aria-label={t('Individual review reason')} value={reviewReason} onChange={event=>setReviewReason(event.target.value)}/></label>
          <button type="button" disabled={saving||reviewReason.trim().length<3} onClick={()=>void saveReviewAndNext()}>{t(onNext?'Save review and next':'Save review')}</button></div>}
        {saveError&&<p role="alert">{saveError}</p>}</>}
      {tab==='Evidence'&&<>
        {evidence.length?evidence.map(row=><div className="activity" key={row.id}><div><b>{t(row.relationship)}</b>
          <p>{row.excerpt}</p>{row.translatedExcerpt&&<p>{t('Translation')}: {row.translatedExcerpt}</p>}
          <p>{t('Requirement')}: {row.requirementId??t('Unlinked')} · {t(row.kind)} · {t(row.status)}</p>
          {row.status==='available'&&permittedUrl(row.sourceUrl)&&<a href={permittedUrl(row.sourceUrl)!} target="_blank" rel="noopener noreferrer">{t('Source')}</a>}
          {row.retrievedAt&&<p>{t('Retrieved')}: {row.retrievedAt}</p>}
          {row.observedAt&&<p>{t('Observed')}: {row.observedAt}</p>}
          {row.retentionUntil&&<p>{t('Retention until')}: {row.retentionUntil}</p>}
          {row.originalLanguage&&<p>{t('Original language')}: {row.originalLanguage}</p>}
          {row.contentHash&&<p>{t('Content hash')}: {row.contentHash}</p>}
        </div></div>):<p>{t('No evidence recorded for this buyer.')}</p>}
        <section className="activity" role="region" aria-labelledby={`source-checks-${buyer.id}`}>
          <h4 id={`source-checks-${buyer.id}`}>{t('Public source checks')}</h4>
          <p>{t('Manual public-source checks are separate from research evidence. BuyerOS stores the links as references and does not fetch them.')}</p>
          {sourceCheckLoadError&&<p role="alert">{t('Could not load public source checks.')}</p>}
          {sourceChecks===null?<p role="status">{t('Loading public source checks...')}</p>:sourceCheckLoadError?null:sourceChecks.length?sourceChecks.map(check=><article className="activity" key={check.id}>
            <h5>{t('Source check')} · {check.grade}</h5>
            <p>{t('Checked on')}: {check.checkedOn} · {t('Evidence grade')}: {check.grade}</p>
            <p>{t('Match rationale')}: {check.rationale}</p>
            {check.limitations&&<p>{t('Limitations')}: {check.limitations}</p>}
            <ul>{check.references.map((reference,index)=>{const href=permittedUrl(reference.url);return <li key={`${check.id}:${index}`}>
              {href?<a href={href} target="_blank" rel="noopener noreferrer">{reference.title}</a>:<span>{reference.title} · {t('Source link unavailable')}</span>}
            </li>;})}</ul>
            <p>{t('Recorded by')}: {check.recordedBy} · {t('Recorded at')}: {check.createdAt}</p>
          </article>):<p>{t('No public source checks recorded.')}</p>}
          {canEdit&&<form onSubmit={event=>{event.preventDefault();void saveSourceCheck();}}>
            <div className="inline">
              <label>{t('Checked on')} <input aria-label={t('Checked on')} type="date" required value={sourceForm.checkedOn} disabled={sourceSaving||!!pendingSourceCheck} onChange={event=>updateSourceForm({checkedOn:event.target.value})}/></label>
              <label>{t('Evidence grade')} <select aria-label={t('Evidence grade')} required value={sourceForm.grade} disabled={sourceSaving||!!pendingSourceCheck} onChange={event=>updateSourceForm({grade:event.target.value as SourceCheckForm['grade']})}>
                <option value="">{t('Select a grade')}</option><option value="A">A</option><option value="B">B</option><option value="C">C</option>
              </select></label>
            </div>
            <label>{t('Match rationale')} <textarea aria-label={t('Match rationale')} required maxLength={4000} value={sourceForm.rationale} disabled={sourceSaving||!!pendingSourceCheck} onChange={event=>updateSourceForm({rationale:event.target.value})}/></label>
            <label>{t('Limitations (optional)')} <textarea aria-label={t('Limitations (optional)')} maxLength={4000} value={sourceForm.limitations} disabled={sourceSaving||!!pendingSourceCheck} onChange={event=>updateSourceForm({limitations:event.target.value})}/></label>
            {sourceForm.references.map((reference,index)=><div className="inline" key={index}>
              <label>{t('Source title {number}').replace('{number}',String(index+1))} <input aria-label={`Source title ${index+1}`} required maxLength={300} value={reference.title} disabled={sourceSaving||!!pendingSourceCheck} onChange={event=>updateSourceForm({references:sourceForm.references.map((item,i)=>i===index?{...item,title:event.target.value}:item)})}/></label>
              <label>{t('Source URL {number}').replace('{number}',String(index+1))} <input aria-label={`Source URL ${index+1}`} type="url" required maxLength={2048} value={reference.url} disabled={sourceSaving||!!pendingSourceCheck} onChange={event=>updateSourceForm({references:sourceForm.references.map((item,i)=>i===index?{...item,url:event.target.value}:item)})}/></label>
              {sourceForm.references.length>1&&<button type="button" disabled={sourceSaving||!!pendingSourceCheck} onClick={()=>updateSourceForm({references:sourceForm.references.filter((_,i)=>i!==index)})}>{t('Remove source')}</button>}
            </div>)}
            <div className="inline">
              <button type="button" disabled={sourceSaving||!!pendingSourceCheck||sourceForm.references.length>=10} onClick={()=>updateSourceForm({references:[...sourceForm.references,{title:'',url:''}]})}>{t('Add another source')}</button>
              <button type="submit" disabled={sourceSaving||!!pendingSourceCheck||!sourceFormValid}>{sourceSaving?t('Saving source check...'):t('Save source check')}</button>
              {pendingSourceCheck&&<button type="button" disabled={sourceSaving||pendingSourceCheck.identity!==session.identity()} onClick={()=>void saveSourceCheck(true)}>{t('Retry same source check')}</button>}
            </div>
          </form>}
          {sourceCheckError&&<p role="alert">{sourceCheckError}</p>}
          {sourceCheckSaved&&<p role="status">{t('Source check recorded.')}</p>}
        </section>
      </>}
      {tab==='Contacts'&&<><p>{t('Contact research')}: {t(data.contactResearchStatus??'Unknown')}</p>
        <p>{t('Eligible retained recipients can be selected when preparing a grounded draft.')}</p>
        <ContactQuotePreview key={`${data.id}:${data.version}`} buyerId={data.id} buyerVersion={data.version} canQuote={canQuote} t={t}/></>}
      {tab==='Activity'&&<><p>{t('Review')}: {t(data.reviewStatus??'No human review recorded')}</p>
        {data.reviewReason&&<p>{t('Reason')}: {data.reviewReason}</p>}{data.reviewAt&&<p>{t('Reviewed at')}: {data.reviewAt}</p>}</>}
    </div>}
  </section></>;
}
