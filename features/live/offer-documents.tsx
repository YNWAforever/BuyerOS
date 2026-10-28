'use client';

import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import type {components} from '@/services/generated/buyeros-api';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {LiveCancelled,LiveError,describeLiveError} from '@/services/live/client';
import {createDocumentUpload,downloadOriginal,type UploadContext,type UploadProgress} from '@/services/live/document-upload';

type Document=components['schemas']['OfferDocument'];
type Fact=components['schemas']['OfferFact'];
type Page={items:Document[];offset:number;limit:number;total:number};
type Slide=components['schemas']['DocumentSlide'];

export function LiveOfferDocuments({projectId,selected,onSelect,onApply,t,focusDocument}:{
  projectId:string;selected:string[];onSelect:(id:string,selected:boolean)=>void;
  onApply:(fact:Fact)=>void;t:(text:string)=>string;focusDocument?:string;
}) {
  const {client,session}=useWorkspaceSession();
  const [rows,setRows]=useState<Document[]>([]);
  const [file,setFile]=useState<File|null>(null);
  const [busy,setBusy]=useState(false);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState('');
  const [progress,setProgress]=useState<UploadProgress|null>(null);
  const [pendingName,setPendingName]=useState('');
  const [source,setSource]=useState<{id:string;items:Slide[];total:number}|null>(null);
  const fileInput=useRef<HTMLInputElement>(null);
  const workflow=useMemo(()=>{
    let storage:Storage|undefined;try{if(typeof window!=='undefined')storage=window.sessionStorage;}catch{/* Session-local recovery remains available. */}
    return createDocumentUpload(client,storage);
  },[client]);
  const context=useCallback(():UploadContext|null=>{
    const scope=session.current(),identity=session.identity();
    if(!scope.workspace||!scope.actor)return null;
    return {actor:scope.actor,workspace:scope.workspace,project:projectId,identity,token:session.token(),signal:session.controller().signal,isCurrent:()=>session.isCurrent(identity)};
  },[session,projectId]);
  const action=useRef<{fingerprint:string;key:string}|null>(null);
  const path=useCallback((workspace:string)=>
    `/v1/workspaces/${encodeURIComponent(workspace)}/projects/${encodeURIComponent(projectId)}/offer-documents`,[projectId]);
  const refresh=useCallback(async()=>{
    const scope=session.current(),identity=session.identity();
    if(!scope.workspace)return;
    const signal=session.controller().signal,token=session.token();
    try{
      const all:Document[]=[];
      for(let offset=0;;){
        const page=await client.request<Page>({path:`${path(scope.workspace)}?offset=${offset}&limit=100`,token,scope:identity,signal});
        if(page.offset!==offset||page.limit<1||!Array.isArray(page.items)||page.total<0)
          throw new Error('Invalid document page');
        all.push(...page.items);
        if(all.length>=page.total)break;
        if(!page.items.length)throw new Error('Incomplete document page');
        offset+=page.items.length;
      }
      if(session.isCurrent(identity)){setRows(all);setError('');}
    }catch(cause){
      if(cause instanceof LiveCancelled||!session.isCurrent(identity))return;
      setError(cause instanceof LiveError?describeLiveError(cause):cause instanceof Error?cause.message:'Document status failed');
    }finally{if(session.isCurrent(identity))setLoading(false);}
  },[client,path,session]);
  useEffect(()=>{
    const timer=window.setTimeout(()=>{
      const ctx=context();if(ctx){try{setPendingName(workflow.pending(ctx)?.manifest.filename??'');}catch(cause){setError(cause instanceof Error?cause.message:'Upload recovery failed');}}
      void refresh();
    },0);
    return ()=>window.clearTimeout(timer);
  },[refresh,context,workflow]);
  useEffect(()=>{
    let identity=session.identity();
    return session.subscribe(()=>{
      if(identity===session.identity())return;identity=session.identity();
      setRows([]);setFile(null);setBusy(false);setProgress(null);setPendingName('');setSource(null);setError('');action.current=null;
      if(fileInput.current)fileInput.current.value='';
    });
  },[session]);
  useEffect(()=>{
    if(!focusDocument||loading||!rows.some(row=>row.id===focusDocument))return;
    const target=window.document.querySelector<HTMLElement>('[data-discussion-document="true"]');
    target?.focus();target?.scrollIntoView({block:'nearest'});
  },[focusDocument,loading,rows]);

  async function upload(){
    if(!file||busy)return;
    const native=file.name.toLowerCase().endsWith('.pptx')||file.size>4*1024*1024;
    if(file.size<1||file.size>(file.name.toLowerCase().endsWith('.pptx')?20:5)*1024*1024){setError('Select PowerPoint up to 20 MiB, or PDF, text or Markdown up to 5 MiB.');return;}
    const scope=session.current(),identity=session.identity();
    if(!scope.workspace)return;
    setBusy(true);setError('');
    try{
      if(native){
        const ctx=context();if(!ctx)return;
        await workflow.upload(file,ctx,value=>{if(ctx.isCurrent())setProgress(value);});
        if(!ctx.isCurrent())throw new LiveCancelled('scope changed');
        setFile(null);setPendingName('');if(fileInput.current)fileInput.current.value='';
        await refresh();return;
      }
      const bytes=await file.arrayBuffer();
      if(!session.isCurrent(identity))throw new LiveCancelled('scope changed');
      const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)))
        .map(value=>value.toString(16).padStart(2,'0')).join('');
      const fingerprint=`${scope.workspace}:${projectId}:${file.name}:${digest}`;
      if(action.current?.fingerprint!==fingerprint)action.current={fingerprint,key:crypto.randomUUID()};
      const formData=new FormData();
      formData.append('file',file,file.name);
      formData.append('declared_sha256',digest);
      await client.request<Document>({
        path:path(scope.workspace),method:'POST',token:session.token(),scope:identity,
        signal:session.controller().signal,idempotencyKey:action.current.key,formData,
      });
      if(!session.isCurrent(identity))throw new LiveCancelled('scope changed');
      setFile(null);action.current=null;
      if(fileInput.current)fileInput.current.value='';
      await refresh();
    }catch(cause){
      if(cause instanceof LiveCancelled||!session.isCurrent(identity))return;
      const ctx=context();if(ctx){try{setPendingName(workflow.pending(ctx)?.manifest.filename??'');}catch{/* Original recovery error is shown below. */}}
      if(cause instanceof LiveError&&cause.code==='PROVIDER_UNAVAILABLE'){
        const guidance=t('Document storage is unavailable. Keep the file and ask an administrator to check storage before uploading again.');
        setError(cause.requestId?`${guidance} ${t('Request ID')}: ${cause.requestId}`:guidance);
      }else setError(cause instanceof LiveError?describeLiveError(cause):cause instanceof Error?cause.message:'Upload failed');
    }finally{if(session.isCurrent(identity)){setBusy(false);setProgress(null);}}
  }

  async function readSource(document:Document){
    const ctx=context();if(!ctx||busy)return;setBusy(true);setError('');
    try{
      const page=await client.request<{items:Slide[];offset:number;limit:number;total:number}>({
        path:`/v1/workspaces/${encodeURIComponent(ctx.workspace)}/offer-documents/${encodeURIComponent(document.id)}/slides?offset=0&limit=20`,
        token:ctx.token,scope:ctx.identity,signal:ctx.signal});
      if(!ctx.isCurrent())throw new LiveCancelled('scope changed');
      if(!Array.isArray(page.items)||page.offset!==0||page.limit!==20||page.total<0||page.total>100)throw new Error('Invalid slide page');
      setSource({id:document.id,items:page.items,total:page.total});
    }catch(cause){if(ctx.isCurrent()&&!(cause instanceof LiveCancelled))setError(cause instanceof LiveError?describeLiveError(cause):cause instanceof Error?cause.message:'Source read failed');}
    finally{if(ctx.isCurrent())setBusy(false);}
  }
  async function moreSource(){
    const ctx=context(),previous=source;if(!ctx||!previous||busy)return;setBusy(true);setError('');
    try{
      const offset=previous.items.length;
      const page=await client.request<{items:Slide[];offset:number;limit:number;total:number}>({
        path:`/v1/workspaces/${encodeURIComponent(ctx.workspace)}/offer-documents/${encodeURIComponent(previous.id)}/slides?offset=${offset}&limit=20`,
        token:ctx.token,scope:ctx.identity,signal:ctx.signal});
      if(!ctx.isCurrent())throw new LiveCancelled('scope changed');
      if(!Array.isArray(page.items)||page.offset!==offset||page.total!==previous.total||!page.items.length)throw new Error('Incomplete slide page');
      setSource({...previous,items:[...previous.items,...page.items]});
    }catch(cause){if(ctx.isCurrent()&&!(cause instanceof LiveCancelled))setError(cause instanceof LiveError?describeLiveError(cause):cause instanceof Error?cause.message:'Source read failed');}
    finally{if(ctx.isCurrent())setBusy(false);}
  }
  async function download(document:Document){
    const ctx=context();if(!ctx||busy)return;setBusy(true);setError('');
    try{
      const blob=await downloadOriginal(client,document,ctx);
      if(!ctx.isCurrent())throw new LiveCancelled('scope changed');
      const url=URL.createObjectURL(blob),link=window.document.createElement('a');
      link.href=url;link.download=document.filename;link.click();window.setTimeout(()=>URL.revokeObjectURL(url),1000);
    }catch(cause){if(ctx.isCurrent()&&!(cause instanceof LiveCancelled))setError(cause instanceof LiveError?describeLiveError(cause):cause instanceof Error?cause.message:'Original download failed');}
    finally{if(ctx.isCurrent())setBusy(false);}
  }

  async function remove(document:Document){
    if(busy)return;
    const scope=session.current(),identity=session.identity();
    if(!scope.workspace)return;
    setBusy(true);setError('');
    try{
      await client.request<Document>({
        path:`/v1/workspaces/${encodeURIComponent(scope.workspace)}/offer-documents/${encodeURIComponent(document.id)}`,
        method:'DELETE',token:session.token(),scope:identity,signal:session.controller().signal,
        idempotencyKey:crypto.randomUUID(),ifMatch:`"${document.version}"`,
        body:{reason:'Removed by workspace operator'},
      });
      if(!session.isCurrent(identity))throw new LiveCancelled('scope changed');
      onSelect(document.id,false);
      await refresh();
    }catch(cause){
      if(cause instanceof LiveCancelled||!session.isCurrent(identity))return;
      setError(cause instanceof LiveError?describeLiveError(cause):cause instanceof Error?cause.message:'Delete failed');
    }finally{if(session.isCurrent(identity))setBusy(false);}
  }

  return <section className="live-offer-docs" aria-label={t('Offer documents')}>
    <h4>{t('Offer documents')}</h4>
    <p>{t('Upload PowerPoint up to 20 MiB, or PDF, text or Markdown up to 5 MiB. Extracted facts need reviewer approval.')}</p>
    <label>{t('Offer file')}<input ref={fileInput} type="file" accept=".pptx,.pdf,.txt,.md" disabled={busy}
      onChange={event=>{setFile(event.target.files?.[0]??null);}}/></label>
    <div className="live-offer-doc-actions">
      <button type="button" disabled={!file||busy} onClick={()=>void upload()}>{t(busy?'Working...':'Upload document')}</button>
      <button type="button" disabled={busy} onClick={()=>void refresh()}>{t('Refresh document status')}</button>
    </div>
    {loading&&<p role="status">{t('Loading documents...')}</p>}
    {pendingName&&<p role="status">{t('Upload paused. Reselect the same file to resume:')} {pendingName}</p>}
    {progress&&<div role="status"><span>{t(progress.phase==='hashing'?'Checking file...':progress.phase==='completing'?'Saving attachment...':'Uploading attachment...')} {progress.percent}%</span><progress max="100" value={progress.percent}/></div>}
    {error&&<p role="alert">{t(error)}</p>}
    {focusDocument&&!loading&&!rows.some(row=>row.id===focusDocument)&&<p role="status">{t('Selected document is unavailable in this project.')}</p>}
    <ul>{rows.map(document=><li key={document.id} data-discussion-document={focusDocument===document.id?'true':undefined} tabIndex={focusDocument===document.id?-1:undefined}>
      <div className="live-offer-doc-row"><span><strong>{document.filename}</strong> · {t(document.status)}
      {document.failure_code&&<> · {document.failure_code}</>}</span>
      {document.status==='ready'&&<label><input type="checkbox" checked={selected.includes(document.id)}
        onChange={event=>onSelect(document.id,event.target.checked)}/>{t('Use in profile')}</label>}
      {document.status==='ready'&&document.extraction_metadata&&<>
        {document.extraction_metadata.format==='pptx'&&<button type="button" disabled={busy} onClick={()=>void readSource(document)}>{t('View slide text')}</button>}
        <button type="button" disabled={busy} onClick={()=>void download(document)}>{t('Download original')}</button>
      </>}
      {document.status!=='deleted'&&<button type="button" disabled={busy}
        onClick={()=>void remove(document)}>{t('Delete')}</button>}</div>
      {document.status==='ready'&&document.fact_candidates?.map(fact=><div key={fact.id}>
        <span>{fact.field}: {fact.value}</span>
        {fact.excerpt&&<p>{fact.excerpt}</p>}
        <button type="button" onClick={()=>onApply(fact)}>{t('Apply candidate')}</button>
      </div>)}
      {document.status==='ready'&&document.extraction_metadata?.classification==='image_only'&&<p>{t('This presentation contains images without editable slide text. The original file is saved; no text facts were extracted.')}</p>}
      {source?.id===document.id&&<div aria-label={t('Slide text source')}>
        {source.items.map(slide=><article key={slide.number}><strong>{t('Slide')} {slide.number}</strong><p style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{slide.text||t('No editable text on this slide.')}</p></article>)}
        {source.items.length<source.total&&<button type="button" disabled={busy} onClick={()=>void moreSource()}>{t('Load more slides')}</button>}
        <button type="button" onClick={()=>setSource(null)}>{t('Close slide text')}</button>
      </div>}
    </li>)}</ul>
  </section>;
}
