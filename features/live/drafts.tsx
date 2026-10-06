'use client';
import {useEffect,useMemo,useRef,useState} from 'react';
import {useWorkspaceSession,useSessionSnapshot} from '@/features/providers/workspace-session';
import {LiveCancelled,LiveError,describeLiveError} from '@/services/live/client';
import {ActionIntent} from '@/services/live/action-intent';
import {DraftDirtyDialog,guardDraftTransition,type DirtyDecision} from './draft-dirty-guard';
import {ExportDialog} from './export-dialog';
import {DraftGroundingReview} from './draft-grounding-review';
import {approveExactDraft,editDraft,generateDraft,getDraft,getDraftJob,getProject,listDrafts,loadDraftContext,requestDraftReview,saveSender,
  type Draft,type DraftJob,type Evidence,type Icp,type Project,type Buyer} from '@/services/live/drafts';

const words:Record<string,string>={
  "Reload current sources":"重新載入目前來源",
  "Manual source review":"人工來源覆核",
  "Classify every segment, read each cited source and the whole message. This records your source review; it does not verify semantic truth.":"請分類每個段落，閱讀引用來源及整篇訊息。這會記錄你的來源覆核，不代表系統已驗證語義真確。",
  "Save the message before preparing its source review.":"請先儲存訊息，再準備來源覆核。",
  "A reviewer must submit this source review.":"此來源覆核須由審核員提交。",
  "Loading current sources...":"正在載入目前來源…",
  "Segment":"段落",
  "Classification":"分類",
  "Choose classification":"請選擇分類",
  "Factual — cite a source":"事實陳述：須引用來源",
  "Non-factual — explain why":"非事實陳述：請說明理由",
  "Segment reason":"段落理由",
  "Source":"來源",
  "Source title not supplied":"未提供來源標題",
  "Company":"公司",
  "Source URL unavailable":"來源網址不可用",
  "Observed":"觀察日期",
  "Retrieved":"擷取日期",
  "Not supplied":"未提供",
  "Source details":"來源詳情",
  "Revision details":"版本詳情",
  "Company unavailable":"公司資料不可用",
  "Select segment text":"選取段落文字",
  "Use selected text":"使用選取文字",
  "Advanced segment offsets":"進階段落位置",
  "Sender details":"寄件人詳情",
  "Draft workflow":"草稿流程",
  "1. Edit and save":"1. 修改及儲存",
  "2. Review current sources":"2. 覆核目前來源",
  "3. Approve this exact revision":"3. 批准此精確版本",
  "4. Prepare approved export":"4. 準備已批准匯出",
  "Select text with Shift + Arrow, or place the caret, then use the selection to split. The exact message stays read-only.":"使用 Shift + 方向鍵選取文字或放置游標，再使用選取範圍分段。精確訊息維持唯讀。",
  "Evidence":"證據",
  "Offer fact":"產品事實",
  "Split position (code points)":"分段位置（Unicode 字元）",
  "Split segment":"分開段落",
  "Overall review reason":"整體覆核理由",
  "I read the entire exact message and every cited source, including all non-factual classifications.":"我已閱讀整篇精確訊息及所有引用來源，包括每項非事實分類。",
  "Submit source review":"提交來源覆核",
  "Source review recorded; request a new exact review.":"來源覆核已記錄；請重新要求精確審核。",
  "Reviewed by":"覆核員",

  'Unsaved draft changes':'草稿有未儲存的更改','Save your changes, discard them, or stay with this draft.':'請儲存或捨棄更改，或繼續編輯此草稿。',
  'Save':'儲存','Discard':'捨棄','Cancel':'取消','Draft conflict comparison':'草稿衝突比對',
  'Local unsaved content':'本地未儲存內容','Latest persisted content':'最新已儲存內容','Copy local content':'複製本地內容',

  'Delivery is disabled.':'寄送功能已停用。',
  'review_requested':'\u5f85\u5be9\u6838',
  'approved':'\u5df2\u6279\u51c6',
  'stale':'\u5df2\u5931\u6548',
  'Exact revision review':'\u7cbe\u78ba\u7248\u672c\u5be9\u6838',
  'Request exact review':'\u8981\u6c42\u5be9\u6838\u6b64\u7248\u672c',
  'Approve exact revision':'\u6279\u51c6\u6b64\u7cbe\u78ba\u7248\u672c',
  'Refresh draft':'\u91cd\u65b0\u6574\u7406\u8349\u7a3f',
  'Recipient':'\u6536\u4ef6\u4eba',
  'Review context':'\u5be9\u6838\u80cc\u666f',
  'Policy conditions':'\u653f\u7b56\u689d\u4ef6',
  'I confirm the exact recipient, sender, message and sources shown above.':'\u6211\u78ba\u8a8d\u4ee5\u4e0a\u7cbe\u78ba\u6536\u4ef6\u4eba\u3001\u5bc4\u4ef6\u4eba\u3001\u8a0a\u606f\u53ca\u4f86\u6e90\u3002',
  'Approval recorded; delivery remains disabled.':'\u5be9\u6279\u5df2\u8a18\u9304\uff1b\u767c\u9001\u529f\u80fd\u4ecd\u505c\u7528\u3002',
  'Review requested for this exact revision.':'\u5df2\u8981\u6c42\u5be9\u6838\u6b64\u7cbe\u78ba\u7248\u672c\u3002',
  'An eligible addressed draft and current policy are required before review.':'\u5be9\u6838\u524d\u9808\u6709\u5408\u8cc7\u683c\u6536\u4ef6\u4eba\u53ca\u73fe\u884c\u653f\u7b56\u3002',
  'Context changed; compare and request a new review.':'\u80cc\u666f\u8cc7\u6599\u5df2\u6539\u8b8a\uff1b\u8acb\u6bd4\u5c0d\u4e26\u91cd\u65b0\u8981\u6c42\u5be9\u6838\u3002',
  'Current context requires fresh review.':'\u76ee\u524d\u80cc\u666f\u8cc7\u6599\u9808\u91cd\u65b0\u5be9\u6838\u3002',
  'Drafts':'草稿','Sender identity':'寄件人身份','Reviewed sender':'已審核寄件人',
  'Display name':'顯示名稱','Role title':'職銜','Organization':'機構','Business email':'工作電郵',
  'Country':'國家','Reason for change':'更改原因','I confirm this sender identity':'我確認此寄件人身份',
  'Save sender':'儲存寄件人','Prepare grounded draft':'準備有證據草稿','Approved offer facts':'已批准的產品事實',
  'Supporting buyer evidence':'支持買家的證據','Language':'語言',
  'Free fixed template':'免費固定模板',
  'Internal work objective — does not change the template body':'內部工作目的，不會改變模板正文',
  'Template language':'模板語言',
  'Template language changes only fixed headings, opening and closing; offer facts and source citations stay in their original language and are not automatically translated.':'模板語言只改變固定標題、開場及結尾；產品事實與來源引用保留原語言，不會自動翻譯。',
  'Edit the draft manually after generation; changes need a new grounding review before approval.':'產生後請人手修改草稿；更改須重新審核證據才可批准。',
  'Generate unaddressed draft':'產生未指定收件人的草稿','Job status':'工作狀態',
  'Recipient (optional)':'收件人（可選）','No recipient — unaddressed draft':'不指定收件人 — 未指定收件人的草稿',
  'Generate addressed draft':'產生已指定收件人的草稿',
  'Recipient expired; refresh buyer details.':'收件人資料已到期；請重新整理買家詳情。',
  'Prepare a grounded draft; delivery is disabled.':'準備有證據草稿；發送功能已停用。',
  'Refresh job':'重新整理工作','Draft list':'草稿列表','Previous page':'上一頁','Next page':'下一頁',
  'Open draft':'開啟草稿','Subject':'主旨','Body':'內容','Save revision':'儲存修訂',
  'Revision':'版本','Claims and sources':'陳述及來源','No drafts yet.':'尚未有草稿。',
  'Prepare follow-up':'準備跟進草稿','Follow-up':'跟進','Initial':'首次聯絡',
  'accepted':'已接納','queued':'已列隊','draft':'草稿',
  'Unaddressed preparation only; delivery is disabled.':'只可準備未指定收件人的草稿；發送功能已停用。',
  'Human edits require a new grounding review before approval.':'人工修改後須重新審核證據才可批准。',
  'No reviewed sender. A reviewer must save one before drafting.':'尚無已審核寄件人，須由審核員先儲存。',
  'Current approved profile and accepted buyer are required.':'須有目前已批准的客戶輪廓及已接納買家。',
  'Save changes before leaving this page?':'離開前請先儲存更改。',
};
type Context={project:Project;buyer:Buyer;icp:Icp|null;evidence:Evidence[]};
function replaceQuery(changes:Record<string,string|null>){
  const url=new URL(window.location.href);
  for(const [name,value] of Object.entries(changes))if(value)url.searchParams.set(name,value);else url.searchParams.delete(name);
  window.history.replaceState(window.history.state,'',url.pathname+url.search+url.hash);
}
function eligibleEvidence(row:Evidence){
  return row.status==='available'&&row.relationship==='supports'&&row.kind==='observation'
    &&Boolean(row.retention_until)&&Date.parse(row.retention_until!)>Date.now();
}
export function LiveDraftEditor({locale,canGenerate,canReviewSender,canRequestReview,canApprove,canExport}:{locale:'en'|'zh-HK';canGenerate:boolean;canReviewSender:boolean;canRequestReview:boolean;canApprove:boolean;canExport:boolean}){
  const {client,session}=useWorkspaceSession(),snapshot=useSessionSnapshot();
  const t=(value:string)=>locale==='zh-HK'?(words[value]||value):value;
  const [project,setProject]=useState<Project|null>(null),[context,setContext]=useState<Context|null>(null);
  const [choosing,setChoosing]=useState(false),[conflict,setConflict]=useState<Draft|null>(null);
  const transition=useRef(false),choice=useRef<((decision:DirtyDecision)=>void)|null>(null),returnFocus=useRef<HTMLElement|null>(null);
  const [job,setJob]=useState<DraftJob|null>(null);
  const [draft,setDraft]=useState<Draft|null>(null),[drafts,setDrafts]=useState<Draft[]>([]);
  const [total,setTotal]=useState(0),[offset,setOffset]=useState(0);
  const [selectedFacts,setSelectedFacts]=useState<string[]>([]),[selectedEvidence,setSelectedEvidence]=useState<string[]>([]);
  const [objective,setObjective]=useState('Introduce the approved offer');
  const [recipient,setRecipient]=useState('');
  const [draftKind,setDraftKind]=useState<'initial'|'follow_up'>('initial'),[parentDraftId,setParentDraftId]=useState<string|null>(null);
  const [subject,setSubject]=useState(''),[body,setBody]=useState(''),[draftLanguage,setDraftLanguage]=useState<'en'|'zh-HK'>('en');
  const [senderName,setSenderName]=useState(''),[senderRole,setSenderRole]=useState(''),[senderOrg,setSenderOrg]=useState('');
  const [senderEmail,setSenderEmail]=useState(''),[senderCountry,setSenderCountry]=useState('US');
  const [senderReason,setSenderReason]=useState(''),[senderConfirmed,setSenderConfirmed]=useState(false);
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const [approvalConfirmed,setApprovalConfirmed]=useState(false),[staleDiff,setStaleDiff]=useState<string[]>([]);
  const errorRef=useRef<HTMLParagraphElement>(null),generateIntent=useRef(new ActionIntent<DraftJob>());
  const scope=snapshot.scope,scopeKey=snapshot.identity;
  const unsaved=Boolean(draft&&(subject!==draft.subject||body!==draft.body||draftLanguage!==draft.language));
  useEffect(()=>()=>{choice.current?.('cancel');choice.current=null;},[snapshot.identity]);
  useEffect(()=>{if(error)errorRef.current?.focus();},[error]);
  useEffect(()=>{if(!busy&&returnFocus.current){const target=returnFocus.current;returnFocus.current=null;if(target.isConnected)target.focus();}},[busy]);
  useEffect(()=>{
    if(!unsaved)return;
    const warn=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue='';};
    window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn);
  },[unsaved]);
  useEffect(()=>{
    const params=new URLSearchParams(window.location.search);
    const nextBuyer=params.get('buyer')||'',nextJob=params.get('draft_job')||'',nextDraft=params.get('draft')||'';
    if(!scope.workspace||!scope.project)return;
    let active=true;
    void (async()=>{
      try{
        const [p,page,c,j,d]=await Promise.all([
          getProject(client,session),listDrafts(client,session,0,8),
          nextBuyer?loadDraftContext(client,session,nextBuyer):Promise.resolve(null),
          nextJob?getDraftJob(client,session,nextJob):Promise.resolve(null),
          nextDraft?getDraft(client,session,nextDraft):Promise.resolve(null),
        ]);
        if(!active)return;
        setProject(p);setDrafts(page.items);setTotal(page.total);setOffset(0);setContext(c);setRecipient('');setJob(j);setDraft(d);setApprovalConfirmed(false);setStaleDiff([]);
        if(c){setSelectedFacts((c.icp?.offer_facts||[]).filter(f=>f.approved).map(f=>f.id));
          setSelectedEvidence(c.evidence.filter(eligibleEvidence).map(e=>e.id));}
        if(d){setSubject(d.subject);setBody(d.body);setDraftLanguage(d.language==='zh-HK'?'zh-HK':'en');}
        if(p.sender_identity){setSenderName(p.sender_identity.display_name);setSenderRole(p.sender_identity.role_title||'');
          setSenderOrg(p.sender_identity.organization);setSenderEmail(p.sender_identity.business_email);
          setSenderCountry(p.sender_identity.country);}
      }catch(cause){if(active&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    })();
    return()=>{active=false;};
  },[client,session,scopeKey,scope.workspace,scope.project]);
  async function refreshList(nextOffset:number){
    setError('');try{const page=await listDrafts(client,session,nextOffset,8);setDrafts(page.items);setTotal(page.total);setOffset(nextOffset);}
    catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
  }
  async function persistSender(){
    if(!project||!canReviewSender||busy||!senderConfirmed)return;
    setBusy(true);setError('');setNotice('');
    try{const updated=await saveSender(client,session,project,{display_name:senderName.trim(),
      role_title:senderRole.trim()||undefined,organization:senderOrg.trim(),business_email:senderEmail.trim(),
      country:senderCountry.trim().toUpperCase(),sender_confirmation:true,reason:senderReason.trim()});
      setProject(updated);setNotice(t('Reviewed sender'));setSenderReason('');setSenderConfirmed(false);
    }catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    finally{setBusy(false);}
  }
  async function startDraft(){
    if(!context||!project?.sender_identity||!context.icp||!canGenerate||busy)return;
    if(recipient&&!context.buyer.contacts.some(contact=>contact.id===recipient&&contact.retention_until
      &&Date.parse(contact.retention_until)>Date.now())){setError(t('Recipient expired; refresh buyer details.'));return;}
    setBusy(true);setError('');setNotice('');
    const bodyRequest={buyer_id:context.buyer.id,buyer_version:context.buyer.version,
      recipient_contact_id:recipient||undefined,
      objective:objective.trim(),tone:'professional' as const,language:draftLanguage,approved_offer_fact_ids:selectedFacts,
      evidence_refs:context.evidence.filter(e=>selectedEvidence.includes(e.id)).map(e=>({id:e.id,version:e.version})),
      kind:draftKind,parent_draft_id:draftKind==='follow_up'?parentDraftId||undefined:undefined,
      max_cost:{amount:'0.000000',currency:'USD' as const}};
    try{const accepted=await generateIntent.current.run(JSON.stringify({scopeKey,bodyRequest}),
      key=>generateDraft(client,session,bodyRequest,key));
      setJob(accepted);replaceQuery({draft_job:accepted.id,draft:null});
    }catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    finally{setBusy(false);}
  }
  function applyDraft(opened:Draft,identity:string){
    if(!session.isCurrent(identity))throw new LiveCancelled('scope changed');
    setDraft(opened);setSubject(opened.subject);setBody(opened.body);setDraftLanguage(opened.language==='zh-HK'?'zh-HK':'en');
    setApprovalConfirmed(false);setStaleDiff([]);setConflict(null);replaceQuery({draft:opened.id});
  }
  function decide(value:DirtyDecision){const resolve=choice.current;choice.current=null;setChoosing(false);resolve?.(value);}
  function choose():Promise<DirtyDecision>{setChoosing(true);return new Promise(resolve=>{choice.current=resolve;});}
  async function persistRevision(identity:string){
    if(!draft||!canGenerate)throw new Error('Draft edit permission required');
    if(!session.isCurrent(identity))throw new LiveCancelled('scope changed');
    const updated=await editDraft(client,session,draft,{subject,body,language:draftLanguage},crypto.randomUUID());
    if(!session.isCurrent(identity))throw new LiveCancelled('scope changed');
    applyDraft(updated,identity);setNotice(t('Human edits require a new grounding review before approval.'));
    await refreshList(offset);
  }
  async function performTransition(proceed:(identity:string)=>Promise<void>,saveOnly=false){
    if(busy||transition.current)return;
    const identity=session.identity(),initiator=document.activeElement;transition.current=true;setBusy(true);setError('');
    const guard=()=>{if(!session.isCurrent(identity))throw new LiveCancelled('scope changed');};
    try{
      if(saveOnly)await persistRevision(identity);
      else {const proceeded=await guardDraftTransition({dirty:unsaved,choose,save:()=>persistRevision(identity),proceed:async()=>{guard();await proceed(identity);guard();}});
        if(!proceeded&&initiator instanceof HTMLElement&&session.isCurrent(identity))returnFocus.current=initiator;}
    }catch(cause){
      if(session.isCurrent(identity)&&!(cause instanceof LiveCancelled)){
        setError(describeLiveError(cause));
        if(cause instanceof LiveError&&cause.status===412&&draft){
          try{const latest=await getDraft(client,session,draft.id);guard();setConflict(latest);}catch {/* Preserve local buffer if comparison is unavailable. */}
        }
      }
    }finally{transition.current=false;if(session.isCurrent(identity))setBusy(false);}
  }
  async function refreshJob(){
    if(!job)return;
    await performTransition(async identity=>{const updated=await getDraftJob(client,session,job.id);if(!session.isCurrent(identity))throw new LiveCancelled('scope changed');setJob(updated);
      if(updated.status==='completed'&&updated.result_id){const opened=await getDraft(client,session,updated.result_id);applyDraft(opened,identity);await refreshList(0);}});
  }
  async function openDraft(id:string){await performTransition(async identity=>applyDraft(await getDraft(client,session,id),identity));}
  async function prepareFollowUp(){
    if(!draft||busy)return;setBusy(true);setError('');
    try{const loaded=await loadDraftContext(client,session,draft.buyer_id);setContext(loaded);setRecipient('');
      setSelectedFacts((loaded.icp?.offer_facts||[]).filter(f=>f.approved).map(f=>f.id));
      setSelectedEvidence(loaded.evidence.filter(eligibleEvidence).map(e=>e.id));
      setDraftKind('follow_up');setParentDraftId(draft.id);replaceQuery({buyer:draft.buyer_id});
    }catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    finally{setBusy(false);}
  }
  async function saveRevision(){if(!draft||!unsaved||!canGenerate)return;await performTransition(async()=>{},true);}
  async function refreshCurrentDraft(){if(!draft)return;await performTransition(async identity=>{applyDraft(await getDraft(client,session,draft.id),identity);await refreshList(offset);});}
  async function explainApprovalFailure(cause:unknown,previous:Draft){
    if(cause instanceof LiveCancelled)return;
    setError(describeLiveError(cause));
    if(cause instanceof LiveError&&(cause.status===412||cause.code==='POLICY_BLOCKED')){
      try{const latest=await getDraft(client,session,previous.id);
        const diff:string[]=[];
        if(latest.version!==previous.version)diff.push('Draft state v'+previous.version+' to v'+latest.version);
        if(latest.revision_id!==previous.revision_id)diff.push('Revision '+previous.revision_number+' to '+latest.revision_number);
        if(latest.subject!==previous.subject)diff.push('Subject: '+previous.subject+' to '+latest.subject);
        if(latest.body!==previous.body)diff.push(t('Body')+' changed');
        if(latest.approval_review?.recipient.version!==previous.approval_review?.recipient.version)
          diff.push(t('Recipient')+' version changed');
        if(!diff.length)diff.push(t('Current context requires fresh review.'));
        setStaleDiff(diff);setDraft(latest);setApprovalConfirmed(false);
      }catch{setStaleDiff([t('Current context requires fresh review.')]);}
    }
  }
  async function requestReview(){
    if(!draft||busy||!canRequestReview||unsaved)return;
    setBusy(true);setError('');setNotice('');setStaleDiff([]);
    try{const reviewed=await requestDraftReview(client,session,draft,crypto.randomUUID());
      setDraft(reviewed);setApprovalConfirmed(false);setNotice(t('Review requested for this exact revision.'));
      await refreshList(offset);
    }catch(cause){await explainApprovalFailure(cause,draft);}
    finally{setBusy(false);}
  }
  async function approve(){
    if(!draft||busy||!canApprove||!approvalConfirmed||unsaved)return;
    setBusy(true);setError('');setNotice('');
    try{await approveExactDraft(client,session,draft,crypto.randomUUID());
      const latest=await getDraft(client,session,draft.id);
      setDraft(latest);setApprovalConfirmed(false);setNotice(t('Approval recorded; delivery remains disabled.'));
      await refreshList(offset);
    }catch(cause){await explainApprovalFailure(cause,draft);}
    finally{setBusy(false);}
  }
  const approvedFacts=useMemo(()=>context?.icp?.offer_facts.filter(f=>f.approved)||[],[context]);
  const availableEvidence=useMemo(()=>context?.evidence.filter(eligibleEvidence)||[],[context]);
  const recipients=context?.buyer.contacts.filter(contact=>contact.access_state==='visible'&&contact.value
    &&contact.validity==='provider_marked_valid'&&contact.checked_at&&contact.retention_until)||[];
  return <section className="panel live-draft-editor" aria-label={t('Drafts')}>
    {choosing&&<DraftDirtyDialog decide={decide} canSave={canGenerate} t={t}/>}
    <h2>{t('Drafts')}</h2><p>{t('Prepare a grounded draft; delivery is disabled.')}</p>
    {error&&<p ref={errorRef} tabIndex={-1} role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
    {!project&&<p role="status">Loading draft workspace...</p>}
    {project&&<section className="panel" aria-label={t('Sender identity')}><h3>{t('Sender identity')}</h3>
      {project.sender_identity?<p>{t('Reviewed sender')}: {project.sender_identity.display_name} · {project.sender_identity.organization} · {project.sender_identity.business_email} · {project.sender_identity.version_key}</p>
        :<p>{t('No reviewed sender. A reviewer must save one before drafting.')}</p>}
      <details open={!project.sender_identity}><summary>{t('Sender details')}</summary>{canReviewSender&&<div className="live-draft-fields">
        <label>{t('Display name')} <input value={senderName} maxLength={160} onChange={e=>setSenderName(e.target.value)}/></label>
        <label>{t('Role title')} <input value={senderRole} maxLength={160} onChange={e=>setSenderRole(e.target.value)}/></label>
        <label>{t('Organization')} <input value={senderOrg} maxLength={200} onChange={e=>setSenderOrg(e.target.value)}/></label>
        <label>{t('Business email')} <input type="email" value={senderEmail} maxLength={255} onChange={e=>setSenderEmail(e.target.value)}/></label>
        <label>{t('Country')} <input value={senderCountry} maxLength={2} onChange={e=>setSenderCountry(e.target.value)}/></label>
        <label>{t('Reason for change')} <input value={senderReason} maxLength={400} onChange={e=>setSenderReason(e.target.value)}/></label>
        <label><input type="checkbox" checked={senderConfirmed} onChange={e=>setSenderConfirmed(e.target.checked)}/> {t('I confirm this sender identity')}</label>
        <button type="button" disabled={busy||!senderConfirmed||senderReason.trim().length<3} onClick={()=>void persistSender()}>{t('Save sender')}</button>
      </div>}</details>
    </section>}
    {context&&<section className="panel" aria-label={t('Prepare grounded draft')}><h3>{t('Prepare grounded draft')}</h3>
      <p><strong>{t('Free fixed template')}</strong></p>
      <p>{t('Template language changes only fixed headings, opening and closing; offer facts and source citations stay in their original language and are not automatically translated.')}</p>
      <p>{t('Edit the draft manually after generation; changes need a new grounding review before approval.')}</p>
      <p>{context.buyer.name} · {context.buyer.version} · {t(context.buyer.review?.status||'review required')}</p>
      {!context.icp&&<p role="alert">{t('Current approved profile and accepted buyer are required.')}</p>}
      <fieldset><legend>{t('Approved offer facts')}</legend>{approvedFacts.map(f=><label key={f.id} className="live-draft-option"><input type="checkbox" checked={selectedFacts.includes(f.id)} onChange={e=>setSelectedFacts(v=>e.target.checked?[...v,f.id]:v.filter(id=>id!==f.id))}/>{f.value}</label>)}</fieldset>
      <fieldset><legend>{t('Supporting buyer evidence')}</legend>{availableEvidence.map(e=><label key={e.id} className="live-draft-option"><input type="checkbox" checked={selectedEvidence.includes(e.id)} onChange={event=>setSelectedEvidence(v=>event.target.checked?[...v,e.id]:v.filter(id=>id!==e.id))}/>{e.excerpt} · v{e.version}</label>)}</fieldset>
      <p>{draftKind==='follow_up'?`${t('Follow-up')}: ${parentDraftId}`:t('Initial')}</p>
      <label>{t('Recipient (optional)')} <select value={recipient} onChange={event=>setRecipient(event.target.value)} disabled={busy||!canGenerate}>
        <option value="">{t('No recipient — unaddressed draft')}</option>
        {recipients.map(contact=><option key={contact.id} value={contact.id}>{contact.value} · v{contact.version}</option>)}
      </select></label>
      <div className="live-draft-fields"><label>{t('Internal work objective — does not change the template body')} <input value={objective} maxLength={1000} onChange={e=>setObjective(e.target.value)}/></label>
        <label>{t('Template language')} <select value={draftLanguage} onChange={e=>setDraftLanguage(e.target.value as typeof draftLanguage)} disabled={busy||!canGenerate}><option value="en">English</option><option value="zh-HK">繁體中文</option></select></label></div>
      <button type="button" disabled={busy||!canGenerate||!project?.sender_identity||!context.icp||(recipient!==''&&!recipients.some(contact=>contact.id===recipient))||(draftKind==='follow_up'&&!parentDraftId)||selectedFacts.length===0||selectedEvidence.length===0||objective.trim().length<3} onClick={()=>void startDraft()}>{t(recipient?'Generate addressed draft':'Generate unaddressed draft')}</button>
    </section>}
    {job&&<section className="panel" role="status"><h3>{t('Job status')}</h3><p>{job.id} · {t(job.status)}</p><button type="button" disabled={busy} onClick={()=>void refreshJob()}>{t('Refresh job')}</button></section>}
    {project&&<section className="panel" aria-label={t('Draft list')}><h3>{t('Draft list')}</h3><p>{offset+1}–{Math.min(offset+8,total)} / {total}</p>
      {drafts.length===0&&<p>{t('No drafts yet.')}</p>}{drafts.map(item=><div className="inline" key={item.id}><span>{item.subject} · {t(item.status)} · v{item.version}</span><button type="button" disabled={busy} onClick={()=>void openDraft(item.id)}>{t('Open draft')}</button></div>)}
      <div className="inline"><button type="button" disabled={offset===0} onClick={()=>void refreshList(Math.max(0,offset-8))}>{t('Previous page')}</button><button type="button" disabled={offset+8>=total} onClick={()=>void refreshList(offset+8)}>{t('Next page')}</button></div>
    </section>}
    {draft&&<section className="panel" aria-label={t('Open draft')} data-live-unsaved={unsaved?'true':undefined} data-baseline-revision={draft.revision_id} data-baseline-version={draft.version}>
      <h3>{draft.subject}</h3><p>{t('Revision')}: {draft.revision_number} · {t(draft.status)} · {draft.language}</p>
      <nav aria-label={t('Draft workflow')}><ol><li>{t('1. Edit and save')}</li><li>{t('2. Review current sources')}</li><li>{t('3. Approve this exact revision')}</li><li>{t('4. Prepare approved export')}</li></ol></nav><p>{t('Delivery is disabled.')}</p>
      <div className="live-draft-fields"><label>{t('Subject')} <input value={subject} maxLength={300} onChange={e=>setSubject(e.target.value)} disabled={busy||!canGenerate}/></label>
        <label>{t('Body')} <textarea value={body} maxLength={20000} rows={10} onChange={e=>setBody(e.target.value)} disabled={busy||!canGenerate}/></label>
        <label>{t('Language')} <select value={draftLanguage} onChange={e=>setDraftLanguage(e.target.value as typeof draftLanguage)} disabled={busy||!canGenerate}><option value="en">English</option><option value="zh-HK">繁體中文</option></select></label></div>
      <div className="inline"><button type="button" disabled={!unsaved||busy||!canGenerate} onClick={()=>void saveRevision()}>{t('Save revision')}</button>
      {canGenerate&&<button type="button" disabled={busy} onClick={()=>void prepareFollowUp()}>{t('Prepare follow-up')}</button>}</div>
      {conflict&&<section className="panel" aria-label={t('Draft conflict comparison')}>
        <h4>{t('Draft conflict comparison')}</h4><h5>{t('Local unsaved content')}</h5><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{subject+'\n'+body+'\n'+draftLanguage}</pre>
        <button onClick={()=>void navigator.clipboard?.writeText(subject+'\n'+body+'\n'+draftLanguage)}>{t('Copy local content')}</button>
        <h5>{t('Latest persisted content')}</h5><p>{t('Revision')}: {conflict.revision_number} · v{conflict.version}</p><pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{conflict.subject+'\n'+conflict.body+'\n'+conflict.language}</pre>
      </section>}
      <h4>{t('Claims and sources')}</h4>{draft.claims.map((claim,index)=><p key={index}>{claim.text} · {claim.offer_fact_ids.join(', ')} {claim.evidence_ids.join(', ')}</p>)}
      {draft.claims.length===0&&<p>{t('Human edits require a new grounding review before approval.')}</p>}
      {draft.claims.length===0&&<DraftGroundingReview key={`grounding:${draft.id}:${draft.revision_id}`} draft={draft} canReview={canApprove} busy={busy} dirty={unsaved} t={t} onBusy={setBusy} onReviewed={(updated,identity)=>{applyDraft(updated,identity);setNotice(t('Source review recorded; request a new exact review.'));void refreshList(offset);}}/>}
      {draft.grounding_review&&<p>{t('Reviewed by')}: {draft.grounding_review.reviewed_by} · {draft.grounding_review.reviewed_at} · {draft.grounding_review.reason}</p>}
      <section className="panel" aria-label={t('Exact revision review')}>
        <h4>{t('Exact revision review')}</h4>
        <p>{t('Revision')}: {draft.revision_number} · {draft.content_hash}</p>
        {draft.approval_review?<><h5>{t('Recipient')}</h5>
          <p>{draft.approval_review.recipient.value} · v{draft.approval_review.recipient.version} · {draft.approval_review.recipient.validity}</p>
          <h5>{t('Sender identity')}</h5>
          <p>{draft.approval_review.sender.display_name} · {draft.approval_review.sender.organization} · {draft.approval_review.sender.business_email} · {draft.approval_review.sender.version_key}</p>
          <h5>{t('Claims and sources')}</h5>
          {draft.approval_review.evidence.map(item=><p key={item.id}>{item.id} · v{item.version} · {item.source_id}</p>)}
          <h5>{t('Policy conditions')}</h5><p>{draft.approval_review.policy_decision_ids.join(', ')}</p>
          <p>{draft.approval_review.icp_version_id} · {draft.approval_review.fit_id} · {draft.approval_review.review_id}</p>
          <p>{t('Review context')}: {draft.context_hash}</p>
        </>:<p>{t('An eligible addressed draft and current policy are required before review.')}</p>}
        {staleDiff.length>0&&<div role="alert"><p>{t('Context changed; compare and request a new review.')}</p><ul>{staleDiff.map((item,index)=><li key={index}>{item}</li>)}</ul></div>}
        <div className="inline"><button type="button" onClick={()=>void refreshCurrentDraft()} disabled={busy}>{t('Refresh draft')}</button>
          {canRequestReview&&draft.recipient_contact_id&&['draft','stale'].includes(draft.status)&&draft.claims.length>0&&
            <button type="button" onClick={()=>void requestReview()} disabled={busy||unsaved}>{t('Request exact review')}</button>}</div>
        {canApprove&&draft.status==='review_requested'&&draft.approval_review&&<>
          <label><input type="checkbox" checked={approvalConfirmed} onChange={event=>setApprovalConfirmed(event.target.checked)}/>
            {t('I confirm the exact recipient, sender, message and sources shown above.')}</label>
          <button type="button" onClick={()=>void approve()} disabled={busy||unsaved||!approvalConfirmed}>{t('Approve exact revision')}</button>
        </>}
      </section>
      {draft.status==='approved'&&draft.approval_id&&<ExportDialog key={`draft-export:${draft.id}:${draft.version}`} locale={locale} draft={draft} canExport={canExport}/>}
    </section>}
  </section>;
}
