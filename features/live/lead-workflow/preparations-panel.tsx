'use client';
import {useCallback,useEffect,useState} from 'react';
import {LeadLink} from './link';
import type {components} from '@/services/generated/buyeros-api';
import {useWorkspaceSession,useSessionSnapshot} from '@/features/providers/workspace-session';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
import {loadLeadProgress,loadLeadCase,listLeadReviews,type LeadCaseView,type LeadReviewRecord} from '@/services/live/lead-workflow';
import {loadDraftContext} from '@/services/live/drafts';
import {loadLeadPreparations,listLeadPreparationRevisions,type LeadPreparation,type LeadPreparationInput} from '@/services/live/lead-preparations';
import {createOperationClient} from '@/services/live/operations';
import {leadContext} from '@/services/live/lead-context';
import {useLeadOperation,LeadRecovery} from './operation';
import {leadText,safeLeadUrl,leadTime,type LeadLocale} from './copy';

const actions=['preparation.create','preparation.revise','preparation.review','preparation.archive','preparation.request_review'] as const;
export function LeadPreparationsPanel({locale,canEdit,canReview}:{locale:LeadLocale;canEdit:boolean;canReview:boolean}){
  const {client,session}=useWorkspaceSession(),snapshot=useSessionSnapshot();
  const [companies,setCompanies]=useState<LeadCaseView[]>([]),[buyer,setBuyer]=useState(''),[error,setError]=useState('');
  const t=(value:string)=>leadText(locale,value);
  useEffect(()=>{
    const own=new AbortController(),identity=session.identity();
    void (async()=>{
      const rows:LeadCaseView[]=[];
      for(let offset=0;;){
        const page=await loadLeadProgress(client,session,{},own.signal,offset,100);rows.push(...page.items);
        if(rows.length>=page.total)break;if(!page.items.length)throw new Error('Incomplete company page');offset=rows.length;
      }
      if(!own.signal.aborted&&session.isCurrent(identity)){
        setCompanies(rows);const requested=new URLSearchParams(window.location.search).get('buyer');
        if(requested&&rows.some(row=>row.buyer_id===requested))setBuyer(requested);
      }
    })().catch(cause=>{if(!own.signal.aborted&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));});
    return()=>own.abort();
  },[client,session,snapshot.identity]);
  return <section className="panel" aria-label={t('Lead preparations')}>
    <h2>{t('Lead preparations')}</h2><p>{t('Sending: disabled')}</p>
    <p>{t('Content review is separate from formal sending approval.')}</p>
    {error&&<p role="alert">{t(error)}</p>}
    <label>{t('Preparation company')}<select aria-label={t('Preparation company')} value={buyer} onChange={e=>setBuyer(e.target.value)}>
      <option value="">{t('Choose company')}</option>{companies.map(row=><option key={row.buyer_id} value={row.buyer_id}>{row.company_name}</option>)}
    </select></label>
    {buyer&&<PreparationEditor key={`${snapshot.identity}:${buyer}`} buyerId={buyer} locale={locale} canEdit={canEdit} canReview={canReview}/>}
  </section>;
}
function PreparationEditor({buyerId,locale,canEdit,canReview}:{buyerId:string;locale:LeadLocale;canEdit:boolean;canReview:boolean}){
  const {client,session}=useWorkspaceSession();
  const [rows,setRows]=useState<LeadPreparation[]>([]),[selected,setSelected]=useState(''),[data,setData]=useState<LeadPreparation|null>(null);
  const [context,setContext]=useState<Awaited<ReturnType<typeof loadDraftContext>>|null>(null),[lead,setLead]=useState<LeadCaseView|null>(null);
  const [docs,setDocs]=useState<components['schemas']['OfferDocument'][]>([]);
  const [facts,setFacts]=useState<string[]>([]),[subject,setSubject]=useState(''),[body,setBody]=useState('');
  const [language,setLanguage]=useState<'en'|'zh-HK'>(locale),[reason,setReason]=useState(''),[confirm,setConfirm]=useState(false),[error,setError]=useState('');
  const [history,setHistory]=useState<components['schemas']['LeadPreparationRevisionView'][]>([]),[historyTotal,setHistoryTotal]=useState(0);
  const [offset,setOffset]=useState(0),[total,setTotal]=useState(0);
  const [targetReviews,setTargetReviews]=useState<LeadReviewRecord[]>([]),[targetReview,setTargetReview]=useState('');
  const [loadingSources,setLoadingSources]=useState(false);
  const t=(value:string)=>leadText(locale,value);
  function show(row:LeadPreparation|null){
    setData(row);setSelected(row?.id??'');setSubject(row?.content?.subject??'');setBody(row?.content?.body??'');
    setLanguage(row?.content?.language??locale);setConfirm(false);setHistory([]);setHistoryTotal(0);
    if(row?.content)setFacts((row.content.product_fact_refs??[]).map(fact=>fact.id));
    if(row)setTargetReview(row.content?.lead_review_id??'none');
    else setTargetReview(value=>value||'none');
  }
  const refresh=useCallback(async()=>{
    const identity=session.identity(),ctx=leadContext(session);
    setLoadingSources(true);
    try{
    const reviews:LeadReviewRecord[]=[];
    const readTargets=async()=>{
      for(let start=0;;){
        const page=await listLeadReviews(client,session,buyerId,start,100,undefined,'draft_preparation');
        reviews.push(...page.items);
        if(reviews.length>=page.total)break;
        if(!page.items.length)throw new Error('Incomplete purchasing review history');
        start=reviews.length;
      }
    };
    const [page,current,product,documents]=await Promise.all([
      loadLeadPreparations(client,session,buyerId,offset),loadLeadCase(client,session,buyerId),
      loadDraftContext(client,session,buyerId),createOperationClient(client).requestOperation('listOfferDocuments',{
        path:{workspace_id:ctx.workspace,project_id:ctx.project},query:{offset:0,limit:100},
      },ctx),readTargets(),
    ]);
    if(!session.isCurrent(identity))return;
    setRows(page.items);setTotal(page.total);setLead(current);setContext(product);setDocs(documents.items);setTargetReviews(reviews);setError('');
    if(!page.items.length)setTargetReview(value=>value||(reviews.some(row=>!row.redacted&&row.id===current.reviews.at(-1)?.id)?current.reviews.at(-1)!.id:'none'));
    return page.items;
    }finally{if(session.isCurrent(identity))setLoadingSources(false);}
  },[client,session,buyerId,offset]);
  const readback=useCallback(async()=>{
    const values=await refresh();if(values)show(values.find(row=>row.id===selected)??values[0]??null);
  // show only sets state; selected intentionally binds the original preparation during recovery.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[refresh,selected]);
  const operation=useLeadOperation(buyerId,actions,readback,locale);
  useEffect(()=>{let active=true;void Promise.resolve().then(refresh).then(values=>{
    if(!active||!values)return;show(values[0]??null);
  }).catch(cause=>{if(active&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));});
    return()=>{active=false;};
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[refresh]);
  const approved=context?.icp?.offer_facts.filter(fact=>fact.approved)??[];
  const blocked=loadingSources||operation.busy||operation.unknown||operation.pending.length>0;
  const currentTargets=new Map<string,LeadReviewRecord>();
  for(const row of targetReviews){
    const key=`${row.person_id}:${row.contact_id??''}`;
    if(!currentTargets.has(key))currentTargets.set(key,row);
  }
  const choices=[...currentTargets.values()].filter(row=>!row.redacted);
  const storedReview=targetReviews.find(row=>row.id===data?.content?.lead_review_id);
  if(storedReview&&!storedReview.redacted&&!choices.some(row=>row.id===storedReview.id))choices.unshift(storedReview);
  const chosen=targetReviews.find(row=>row.id===targetReview&&!row.redacted);
  const dirty=Boolean(data?.content&&(subject!==data.content.subject||body!==data.content.body||
    language!==data.content.language||JSON.stringify(facts)!==JSON.stringify((data.content.product_fact_refs??[]).map(f=>f.id))||
    targetReview!==(data.content.lead_review_id??'none')));
  const caveat=docs.some(doc=>doc.status!=='ready'||doc.extraction_metadata?.classification==='image_only'||
    (doc.extraction_metadata?.text_slide_count!==undefined&&doc.extraction_metadata?.slide_count!==undefined&&doc.extraction_metadata.text_slide_count<doc.extraction_metadata.slide_count));
  function input(empty=false):LeadPreparationInput{
    const review=chosen,icp=context?.icp;
    return {person_id:review?.person_id??null,contact_id:review?.contact_id??null,
      subject:empty?'':subject,body:empty?'':body,language,
      product_fact_refs:icp&&context?approved.filter(fact=>empty||facts.includes(fact.id)).map(fact=>({
        id:fact.id,icp_version_id:icp.id,icp_content_hash:icp.content_hash,offer_revision:context.project.offer_revision,
      })):[],observation_ids:review?.observation_ids??[],lead_review_id:review?.id??null,
      company_source_check_ids:lead?.source_check_ids.slice(0,10)??[],previous_revision_id:data?.revision_id??null};
  }
  async function create(){
    await operation.run({action:'preparation.create',buyer_id:buyerId,payload:{...input(true),previous_revision_id:null}},'Preparation saved.');
  }
  async function save(){
    if(!data)return;
    await operation.run({action:'preparation.revise',buyer_id:buyerId,target_id:data.id,expected_version:data.version,payload:input()},'Preparation saved.');
  }
  async function change(action:'preparation.review'|'preparation.request_review'|'preparation.archive'){
    if(!data)return;
    const target={buyer_id:buyerId,target_id:data.id,expected_version:data.version};
    if(action==='preparation.review')await operation.run({...target,action,payload:{
      revision_id:data.revision_id,context_hash:data.context_hash,reason,confirmation:confirm,
    }},'Content review saved.');
    else await operation.run({...target,action,payload:{reason}},'Preparation state saved.');
  }
  async function loadHistory(){
    if(!data)return;const identity=session.identity();
    try{
      const page=await listLeadPreparationRevisions(client,session,data.id,history.length);
      if(session.isCurrent(identity)){setHistory(values=>[...values,...page.items]);setHistoryTotal(page.total);}
    }catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
  }
  const scope=session.current();
  const attachment=(id:string)=>`/app/discover/edit?${new URLSearchParams({workspace:scope.workspace!,project:scope.project!,document:id})}`;
  return <>
    {error&&<p role="alert">{t(error)}</p>}
    {!context&&<p role="status">{t('Loading preparation sources…')}</p>}
    {caveat&&<p role="alert">{t('Product extraction is incomplete; verify the original attachment.')}</p>}
    {context&&approved.length===0&&<p>{t('approved_product_fact_required')}</p>}
    {canEdit&&<button disabled={blocked||!context} onClick={()=>void create()}>{t('Create cited preparation')}</button>}
    {rows.length>0&&<label>{t('Saved preparation')}<select aria-label={t('Saved preparation')} value={selected} disabled={blocked} onChange={e=>show(rows.find(row=>row.id===e.target.value)??null)}>
      {rows.map(row=><option key={row.id} value={row.id}>{row.content?.subject||row.id} · {row.revision_number}</option>)}
    </select></label>}
    {total>20&&<div className="inline"><button disabled={offset===0||blocked} onClick={()=>setOffset(v=>Math.max(0,v-20))}>{t('Previous page')}</button>
      <span>{offset+1}–{Math.min(offset+rows.length,total)} / {total}</span><button disabled={offset+rows.length>=total||blocked} onClick={()=>setOffset(v=>v+20)}>{t('Next page')}</button></div>}
    {data&&<>
      <p>{t('Preparation state')}: {t(data.state)}</p><p>{t('Revision')}: {data.revision_number} · {data.content_hash}</p>
      <p>{t('Source context')}: {data.context_hash}</p>
      {data.blockers.map(item=><p key={item}>{t(item)}</p>)}
      {data.reviewed_at&&<p>{t('Content reviewed at')}: {leadTime(data.reviewed_at,locale)} · {data.reviewed_by_user_id}</p>}
      {data.review_reason&&<p>{t('Content review reason')}: {data.review_reason}</p>}
      {data.state_reason&&<p>{t('Saved state change reason')}: {data.state_reason}</p>}
      {data.redacted?<p role="alert">{t('Source evidence is unavailable or expired.')}</p>:<>
        <label>{t('Preparation purchasing review')}<select aria-label={t('Preparation purchasing review')} value={targetReview}
          disabled={!canEdit||blocked||data.state==='archived'} onChange={e=>{setTargetReview(e.target.value);setConfirm(false);}}>
          <option value="none">{t('No purchasing person selected')}</option>
          {choices.map(row=>{
            const person=lead?.observations?.find(item=>item.person_id===row.person_id&&item.person)?.person;
            const channel=lead?.observations?.find(item=>item.contact_id===row.contact_id&&item.channel)?.channel;
            return <option key={row.id} value={row.id}>{String(person?.full_name??row.person_id)} · {String(channel?.value??t('No direct channel'))} · {t('Revision')} {row.case_version}</option>;
          })}
        </select></label>
        <label>{t('Preparation subject')}<input aria-label={t('Preparation subject')} readOnly={!canEdit} disabled={blocked||data.state==='archived'} maxLength={300} value={subject} onChange={e=>{setSubject(e.target.value);setConfirm(false);}}/></label>
        <label>{t('Preparation body')}<textarea aria-label={t('Preparation body')} readOnly={!canEdit} disabled={blocked||data.state==='archived'} rows={8} maxLength={12000} value={body} onChange={e=>{setBody(e.target.value);setConfirm(false);}}/></label>
        <label>{t('Preparation language')}<select aria-label={t('Preparation language')} disabled={!canEdit||blocked||data.state==='archived'} value={language} onChange={e=>{setLanguage(e.target.value as typeof language);setConfirm(false);}}><option value="en">English</option><option value="zh-HK">繁體中文</option></select></label>
        <fieldset disabled={!canEdit||blocked||data.state==='archived'}><legend>{t('Approved product facts')}</legend>
          {approved.map(fact=><label key={fact.id}><input type="checkbox" checked={facts.includes(fact.id)} onChange={e=>{setFacts(values=>e.target.checked?[...values,fact.id]:values.filter(id=>id!==fact.id));setConfirm(false);}}/>{fact.value}</label>)}
        </fieldset>
        {canEdit&&data.state!=='archived'&&<button disabled={blocked} onClick={()=>void save()}>{t('Save preparation revision')}</button>}
        <div aria-label={t('Cited product facts')}>{data.facts.map((fact,index)=><article key={index}>
          <p>{String(fact.value??'')}</p>{typeof fact.source_document_id==='string'&&<LeadLink href={attachment(fact.source_document_id)}>{String(fact.source_filename??t('Original attachment'))}</LeadLink>}
          {Boolean(fact.excerpt)&&<blockquote>{String(fact.excerpt)}</blockquote>}
          <p>{t('Page')}: {fact.source_page?String(fact.source_page):t('Unknown; see original attachment')}</p>
        </article>)}</div>
        <ul>{data.source_references.map((source,index)=><li key={index}>{typeof source.url==='string'&&safeLeadUrl(source.url)?<a href={safeLeadUrl(source.url)!} target="_blank" rel="noopener noreferrer">{String(source.title)}</a>:String(source.title??'')}
          {Boolean(source.excerpt)&&<blockquote>{String(source.excerpt)}</blockquote>}</li>)}</ul>
      </>}
      {(canEdit||canReview)&&data.state!=='archived'&&<>
        <label>{t('Content review reason')}<textarea aria-label={t('Content review reason')} maxLength={4000} disabled={blocked} value={reason} onChange={e=>setReason(e.target.value)}/></label>
        {canReview&&<><label><input type="checkbox" disabled={blocked} checked={confirm} onChange={e=>setConfirm(e.target.checked)}/>{t('I reviewed this exact preparation content.')}</label>
          <button disabled={blocked||!confirm||reason.trim().length<3||data.blockers.length>0||dirty} onClick={()=>void change('preparation.review')}>{t('Mark content reviewed')}</button></>}
        {canEdit&&<><button disabled={blocked||dirty||reason.trim().length<3||data.blockers.length>0} onClick={()=>void change('preparation.request_review')}>{t('Request content review')}</button>
          <button disabled={blocked||reason.trim().length<3} onClick={()=>void change('preparation.archive')}>{t('Archive preparation')}</button></>}
      </>}
      <button disabled={blocked||history.length>0&&history.length>=historyTotal} onClick={()=>void loadHistory()}>{t('Load revision history')}</button>
      {history.map(row=><article key={row.id}><b>{t('Historical revision')} {row.revision_number}</b><p>{row.content_hash}</p><p>{row.content?.subject??t('Source no longer available.')}</p><p>{row.content?.body}</p></article>)}
    </>}
    <button disabled={blocked} onClick={()=>void readback().catch(cause=>setError(describeLiveError(cause)))}>{t('Refresh preparations')}</button>
    <LeadRecovery operation={operation} locale={locale}/>
  </>;
}
