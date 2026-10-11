'use client';

import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
import {createOperationClient} from '@/services/live/operations';
import {buyerOperationContext,createBuyerSnapshot,readBuyerQuery} from '@/services/live/buyers';
import {candidateReviewDraft,expireCandidateReviewDraft,updateCandidateReviewDraft,bindCandidateReviewSource,getCandidateReviewContext,loadResearchCandidates,submitCandidateReview,
  type CandidatePage,type CandidateReviewDraft} from '@/services/live/research-candidates';
import type {RunContext} from '@/services/live/runs';

type CompanyChoice={id:string;name:string;domain?:string};
export function ResearchCandidateObservations({ctx,runId,canReview,t}:{ctx:RunContext;runId:string;canReview:boolean;t:(s:string)=>string}){
 const [offset,setOffset]=useState(0),[selected,setSelected]=useState<string|null>(null),[reload,setReload]=useState(0);
 const loadKey=JSON.stringify([ctx.session.identity(),runId,offset,reload]);
 const [loaded,setLoaded]=useState<{key:string;page:CandidatePage|null;error:string}>({key:'',page:null,error:''});
 const page=loaded.key===loadKey?loaded.page:null,error=loaded.key===loadKey?loaded.error:'';
 useEffect(()=>{let active=true;const identity=ctx.session.identity();
  void loadResearchCandidates(ctx,runId,offset,20).then(value=>{if(active&&ctx.session.isCurrent(identity))setLoaded({key:loadKey,page:value,error:''});})
   .catch(e=>{if(active&&ctx.session.isCurrent(identity)&&!(e instanceof LiveCancelled))setLoaded({key:loadKey,page:null,error:describeLiveError(e)});});
  return()=>{active=false;};
 },[ctx,runId,offset,reload,loadKey]);
 return <section className="candidate-observations" aria-label={t('Candidate observations')}>
  <h3>{t('Candidate observations')}</h3><p>{t('Search metadata is a lead, not verified company, fit or buyer-role evidence.')}</p>
  {!canReview&&<p>{t('A reviewer must verify the existing company and source.')}</p>}
  {error&&<p role="alert">{error} <button type="button" onClick={()=>setReload(v=>v+1)}>{t('Retry loading')}</button></p>}
  {!page&&!error&&<p role="status">{t('Loading candidate observations…')}</p>}
  {page&&<><p>{t('Actual observations')}: {page.total}</p>
   {!page.items.length&&<p>{t('No candidate observations yet.')}</p>}
   <ul className="candidate-list">{page.items.map(item=><li key={item.raw_candidate_id}>
    <p><strong>{t('Search metadata')}</strong>: {item.title??t('Source unavailable')}</p>
    <p>{t('Source status')}: {t(item.source_status)} · {t('Entity mapping')}: {t(item.mapping_status)}</p>
    {item.source_url&&<a href={item.source_url} target="_blank" rel="noopener noreferrer">{t('Search source link')}</a>}
    <details><summary>{t('Technical details')}</summary><p>{t('Observation ID')}: {item.raw_candidate_id}</p></details>
    {canReview&&item.source_status==='page_available'&&<button type="button" onClick={()=>setSelected(item.raw_candidate_id)}>{t('Review candidate')}</button>}
    {item.source_status==='awaiting_reconciliation'&&<p>{t('Original page retrieval needs reconciliation. Do not fetch again.')}</p>}
   </li>)}</ul>
   <div className="inline"><button type="button" disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-20))}>{t('Previous candidates')}</button>
    <span>{page.total?offset+1:0}–{Math.min(offset+page.items.length,page.total)} / {page.total}</span>
    <button type="button" disabled={offset+page.items.length>=page.total} onClick={()=>setOffset(offset+20)}>{t('Next candidates')}</button>
    <button type="button" onClick={()=>setReload(v=>v+1)}>{t('Refresh candidates')}</button></div></>}
  {selected&&canReview&&<CandidateReviewEditor key={selected} ctx={ctx} runId={runId} rawId={selected} t={t} onClose={()=>setSelected(null)} onSaved={()=>setReload(v=>v+1)}/>}
 </section>;
}

function CandidateReviewEditor({ctx,runId,rawId,t,onClose,onSaved}:{ctx:RunContext;runId:string;rawId:string;t:(s:string)=>string;onClose:()=>void;onSaved:()=>void}){
 const draft=useMemo(()=>candidateReviewDraft(ctx,runId,rawId),[ctx,runId,rawId]);
 const [,render]=useState(0),[confirmed,setConfirmed]=useState(false),[error,setError]=useState(''),[loading,setLoading]=useState(false),[q,setQuery]=useState(''),[choices,setChoices]=useState<CompanyChoice[]>([]),[total,setTotal]=useState<number|null>(null);
 const mounted=useRef(true),busy=useRef(false),touch=useCallback(()=>render(v=>v+1),[]);
 const locked=draft.phase!=='editing';
 const existingReview=draft.context?.entity_status==='reviewed'&&!draft.frozen;
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 useEffect(()=>{
  const deadline=draft.context?Date.parse(draft.context.page.retention_until):NaN;
  if(!Number.isFinite(deadline))return;
  const expire=()=>{expireCandidateReviewDraft(draft);touch();};
  if(deadline<=Date.now()){expire();return;}
  const timer=setTimeout(expire,Math.min(deadline-Date.now(),2_147_483_647));return()=>clearTimeout(timer);
 },[draft,draft.context,touch]);
 function change(patch:Partial<Pick<CandidateReviewDraft,'companyId'|'excerpt'|'reason'>>){if(!updateCandidateReviewDraft(draft,patch))return;setConfirmed(false);touch();}
 async function find(){
  if(busy.current||locked)return;busy.current=true;setLoading(true);setError('');const identity=ctx.session.identity();
  try{const snapshot=await createBuyerSnapshot(ctx.client,ctx.session,readBuyerQuery(new URLSearchParams({q}).toString()));
   const page=await createOperationClient(ctx.client).requestOperation('listBuyers',{path:{workspace_id:ctx.workspaceId,project_id:ctx.projectId},query:{snapshot_id:snapshot.id,offset:0,limit:20}},buyerOperationContext(ctx.session));
   if(mounted.current&&ctx.session.isCurrent(identity)){setChoices([...new Map(page.items.map(item=>[item.company_id,{id:item.company_id,name:item.name,domain:item.normalized_domain}])).values()]);setTotal(page.total);}}
  catch(e){if(mounted.current&&ctx.session.isCurrent(identity)&&!(e instanceof LiveCancelled))setError(describeLiveError(e));}
  finally{busy.current=false;if(mounted.current&&ctx.session.isCurrent(identity))setLoading(false);}
 }
 async function source(){
  if(busy.current||locked||!draft.companyId)return;busy.current=true;setLoading(true);setError('');const identity=ctx.session.identity();
  try{const value=await getCandidateReviewContext(ctx,runId,rawId,draft.companyId);
   if(mounted.current&&ctx.session.isCurrent(identity)){if(!bindCandidateReviewSource(draft,value))throw new Error('Current chosen-company review context required');setConfirmed(false);touch();}}
  catch(e){if(mounted.current&&ctx.session.isCurrent(identity)&&!(e instanceof LiveCancelled))setError(describeLiveError(e));}
  finally{busy.current=false;if(mounted.current&&ctx.session.isCurrent(identity))setLoading(false);}
 }
 async function save(){
  if(busy.current||draft.phase==='accepted'||draft.phase==='expired'||existingReview||(!confirmed&&draft.phase!=='unknown'))return;
  busy.current=true;setError('');const identity=ctx.session.identity();
  try{const pending=submitCandidateReview(ctx,runId,rawId,draft);touch();await pending;if(mounted.current&&ctx.session.isCurrent(identity)){touch();onSaved();}}
  catch(e){if(mounted.current&&ctx.session.isCurrent(identity)&&!(e instanceof LiveCancelled)){setError(describeLiveError(e));touch();}}
  finally{busy.current=false;}
 }
 return <section className="candidate-review" aria-label={t('Entity source review')}>
  <div className="inline spread"><h4>{t('Entity source review')}</h4><button type="button" onClick={onClose}>{t('Close review')}</button></div>
  <p>{t('Select an independently known existing company. Name, domain or email similarity does not establish identity.')}</p>
  <div className="run-grid"><label>{t('Find existing companies')}<input disabled={locked||loading} value={q} maxLength={200} onChange={e=>setQuery(e.target.value)}/></label>
   <button type="button" disabled={locked||loading} onClick={()=>void find()}>{t('Find existing companies')}</button>
   <label>{t('Existing company')}<select aria-label={t('Existing company')} disabled={locked||loading} value={draft.companyId} onChange={e=>change({companyId:e.target.value})}>
    <option value="">{t('Choose an existing company')}</option>{choices.map(c=><option key={c.id} value={c.id}>{c.name}{c.domain?` · ${c.domain}`:''}</option>)}
    {draft.companyId&&!choices.some(c=>c.id===draft.companyId)&&<option value={draft.companyId}>{draft.context?.company.legal_name??t('Previously selected company')}</option>}
   </select></label></div>
  {total!==null&&<p>{t('Matching existing buyers')}: {total}. {t('Only the first 20 buyers are shown; refine your search.')}</p>}
  <details><summary>{t('Select a company outside this project')}</summary><label>{t('Existing company UUID')}<input disabled={locked||loading} value={draft.companyId} onChange={e=>change({companyId:e.target.value})}/></label><p>{t('The server will resolve this existing workspace company before review.')}</p></details>
  <button type="button" disabled={locked||loading||!draft.companyId} onClick={()=>void source()}>{t('Load current source')}</button>
  {loading&&<p role="status">{t('Loading current review material…')}</p>}
  {error&&<p role="alert">{t(error)}</p>}
  {draft.context&&<><p><strong>{draft.context.company.legal_name}</strong> · {draft.context.company.domain??t('No company domain')}</p>
   <a href={draft.context.page.url} target="_blank" rel="noopener noreferrer">{t('Current licensed page')}</a><p>{t('Source expiry')}: {draft.context.page.retention_until}</p>
   <blockquote>{draft.context.page.excerpt}</blockquote>
   <label>{t('Exact page quote')}<textarea aria-label={t('Exact page quote')} disabled={locked} value={draft.excerpt} onChange={e=>change({excerpt:e.target.value})}/></label>
   <label>{t('Entity review reason')}<textarea aria-label={t('Entity review reason')} disabled={locked} maxLength={400} value={draft.reason} onChange={e=>change({reason:e.target.value})}/></label>
   <label className="inline"><input type="checkbox" disabled={locked} checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>{t('I selected this existing company and checked the exact page quote.')}</label>
  </>}
  {existingReview&&<p role="status">{t('An entity review already exists. Read current evidence and reconcile the original review before a new intent.')}</p>}
  {draft.phase==='unknown'&&<p role="status">{t('The save is unconfirmed. Keep the same company, quote, reason and key when retrying.')}</p>}
  {draft.phase==='expired'&&<p role="status">{t('Source expired. The original key is retained; reconcile this review before any new intent.')}</p>}
  {draft.phase==='accepted'?<p role="status">{t('Entity review saved. Fit and buyer role still need separate evidence.')}</p>:
   draft.phase!=='expired'&&<button type="button" disabled={loading||existingReview||draft.phase==='pending'||!draft.context||(!confirmed&&draft.phase!=='unknown')} onClick={()=>void save()}>{t(draft.phase==='unknown'?'Retry same entity review':'Save entity review')}</button>}
 </section>;
}
