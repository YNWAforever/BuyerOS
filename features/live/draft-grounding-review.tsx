"use client";
import {useEffect,useRef,useState} from 'react';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {ActionIntent} from '@/services/live/action-intent';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
import {loadDraftContext,reviewDraftGrounding,type Draft,type Evidence,type Icp} from '@/services/live/drafts';
import {prepareGroundingSegments,splitGroundingSegment,type SegmentPreparation,type GroundingSegment} from '@/services/live/draft-grounding';
export function DraftGroundingReview({draft,canReview,busy,dirty,t,onBusy,onReviewed}:{draft:Draft;canReview:boolean;busy:boolean;dirty:boolean;t:(value:string)=>string;onBusy:(value:boolean)=>void;onReviewed:(value:Draft,identity:string)=>void}){
 const {client,session}=useWorkspaceSession();
 const [segments,setSegments]=useState(()=>prepareGroundingSegments(draft.subject,draft.body));
 const [sources,setSources]=useState<{evidence:Evidence[];icp:Icp|null;asOf:number}|null>(null);
 const [reason,setReason]=useState(''),[confirmed,setConfirmed]=useState(false),[error,setError]=useState('');
 const [splits,setSplits]=useState<Record<number,number>>({}),[sourceEpoch,setSourceEpoch]=useState(0);
 const intent=useRef(new ActionIntent<Draft>()),errorRef=useRef<HTMLParagraphElement>(null);
 useEffect(()=>{let active=true;const identity=session.identity();void loadDraftContext(client,session,draft.buyer_id).then(c=>{
  if(active&&session.isCurrent(identity))setSources({icp:c.icp,evidence:c.evidence,asOf:Date.now()});
 }).catch(cause=>{if(active&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));});return()=>{active=false;};},[client,session,draft.buyer_id,sourceEpoch]);
 useEffect(()=>{if(error)errorRef.current?.focus();},[error]);
 const evidence=(sources?.evidence||[]).filter(e=>draft.evidence_refs.some(r=>r.id===e.id&&r.version===e.version)&&e.status==='available'&&e.relationship==='supports'&&e.kind==='observation'&&e.retention_until&&Date.parse(e.retention_until)>(sources?.asOf??0));
 const icp=sources?.icp;const facts=icp?.offer_facts.filter(f=>f.approved&&draft.value_proposition_fact_ids.includes(f.id))||[];
 function update(index:number,change:Partial<SegmentPreparation>){setConfirmed(false);setSegments(rows=>rows.map((row,i)=>i===index?{...row,...change}:row));}
 const valid=segments.length>=2&&segments.length<=200&&segments.every(s=>s.classification&&s.reason.trim().length>=3&&(s.classification==='non_factual'||s.evidence_refs.length+s.offer_fact_refs.length>0));
 async function submit(){
  if(!canReview||busy||dirty||!valid||!confirmed||!sources||reason.trim().length<3)return;
  const identity=session.identity();onBusy(true);setError('');
  const classified=segments.filter((s):s is GroundingSegment=>s.classification==='factual'||s.classification==='non_factual');
  if(classified.length!==segments.length){onBusy(false);return;}
  const body={revision_id:draft.revision_id,content_hash:draft.content_hash,segments:classified,reason,confirmation:true as const};
  try{const result=await intent.current.run(JSON.stringify({identity,version:draft.version,body}),key=>reviewDraftGrounding(client,session,draft,body,key));
   if(!session.isCurrent(identity))throw new LiveCancelled('scope changed');onReviewed(result,identity);
  }catch(cause){if(session.isCurrent(identity)&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
  finally{if(session.isCurrent(identity))onBusy(false);}
 }
 return <section className="panel" aria-label={t('Manual source review')}>
  <h4>{t('Manual source review')}</h4><p>{t('Classify every segment, read each cited source and the whole message. This records your source review; it does not verify semantic truth.')}</p>
  <p>{t('Revision')}: {draft.revision_number} · {draft.content_hash}</p>
  {dirty&&<p>{t('Save the message before preparing its source review.')}</p>}
  {!canReview&&<p>{t('A reviewer must submit this source review.')}</p>}
  {error&&<p ref={errorRef} role="alert" tabIndex={-1}>{error}</p>}
  {!sources&&<p role="status">{t('Loading current sources...')}</p>}
  {!sources&&error&&<button type="button" disabled={busy} onClick={()=>{setError('');setSourceEpoch(v=>v+1);}}>{t('Reload current sources')}</button>}
  {segments.map((s,index)=><fieldset key={`${s.field}:${s.start}:${s.end}`} disabled={busy||dirty} aria-label={`${t('Segment')} ${index+1}`}>
   <legend>{t('Segment')} {index+1} · {t(s.field==='subject'?'Subject':'Body')} · [{s.start}, {s.end})</legend>
   <pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{s.exact_text}</pre>
   <label>{t('Classification')} <select value={s.classification} onChange={e=>update(index,{classification:e.target.value as SegmentPreparation['classification'],evidence_refs:[],offer_fact_refs:[]})}>
    <option value="">{t('Choose classification')}</option><option value="factual">{t('Factual — cite a source')}</option><option value="non_factual">{t('Non-factual — explain why')}</option>
   </select></label>
   <label>{t('Segment reason')} <input maxLength={400} value={s.reason} onChange={e=>update(index,{reason:e.target.value})}/></label>
   {s.classification==='factual'&&<>
    {evidence.map(e=><label key={e.id} className="live-draft-option"><input type="checkbox" checked={s.evidence_refs.some(r=>r.id===e.id)} onChange={event=>update(index,{evidence_refs:event.target.checked?[...s.evidence_refs,{id:e.id,version:e.version}]:s.evidence_refs.filter(r=>r.id!==e.id)})}/>{t('Evidence')} v{e.version}: {e.excerpt}</label>)}
    {facts.map(f=><label key={f.id} className="live-draft-option"><input type="checkbox" checked={s.offer_fact_refs.some(r=>r.id===f.id)} onChange={event=>{if(icp)update(index,{offer_fact_refs:event.target.checked?[...s.offer_fact_refs,{id:f.id,icp_version_id:icp.id,icp_content_hash:icp.content_hash.replace(/^sha256:/,'')}]:s.offer_fact_refs.filter(r=>r.id!==f.id)});}}/>{t('Offer fact')}: {f.value} · {icp?.id}</label>)}
   </>}
   <label>{t('Split position (code points)')} <input type="number" min={1} max={Array.from(s.exact_text).length-1} value={splits[index]??''} onChange={e=>setSplits(v=>({...v,[index]:Number(e.target.value)}))}/></label>
   <button type="button" disabled={!Number.isInteger(splits[index])||splits[index]<=0||splits[index]>=Array.from(s.exact_text).length||segments.length>=200} onClick={()=>{try{const parts=splitGroundingSegment(s,splits[index]);setSegments(rows=>[...rows.slice(0,index),...parts,...rows.slice(index+1)]);setSplits({});setConfirmed(false);setError('');}catch(cause){setError(describeLiveError(cause));}}}>{t('Split segment')}</button>
  </fieldset>)}
  <label>{t('Overall review reason')} <input maxLength={400} value={reason} disabled={busy||dirty} onChange={e=>{setReason(e.target.value);setConfirmed(false);}}/></label>
  <label><input type="checkbox" disabled={busy||dirty||!valid||!sources} checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>{t('I read the entire exact message and every cited source, including all non-factual classifications.')}</label>
  {canReview&&<button type="button" disabled={busy||dirty||!valid||!confirmed||!sources||reason.trim().length<3} onClick={()=>void submit()}>{t('Submit source review')}</button>}
 </section>;
}
