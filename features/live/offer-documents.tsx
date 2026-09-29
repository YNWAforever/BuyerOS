'use client';

import {useCallback,useEffect,useRef,useState} from 'react';
import type {components} from '@/services/generated/buyeros-api';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {LiveCancelled,LiveError,describeLiveError} from '@/services/live/client';

type Document=components['schemas']['OfferDocument'];
type Fact=components['schemas']['OfferFact'];
type Page={items:Document[];offset:number;limit:number;total:number};

export function LiveOfferDocuments({projectId,selected,onSelect,onApply,t}:{
  projectId:string;selected:string[];onSelect:(id:string,selected:boolean)=>void;
  onApply:(fact:Fact)=>void;t:(text:string)=>string;
}) {
  const {client,session}=useWorkspaceSession();
  const [rows,setRows]=useState<Document[]>([]);
  const [file,setFile]=useState<File|null>(null);
  const [busy,setBusy]=useState(false);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState('');
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
    const timer=window.setTimeout(()=>{void refresh();},0);
    return ()=>window.clearTimeout(timer);
  },[refresh]);

  async function upload(){
    if(!file||busy)return;
    if(file.size<1||file.size>5*1024*1024){setError('Select a file up to 5 MiB.');return;}
    const scope=session.current(),identity=session.identity();
    if(!scope.workspace)return;
    setBusy(true);setError('');
    try{
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
      await refresh();
    }catch(cause){
      if(cause instanceof LiveCancelled||!session.isCurrent(identity))return;
      setError(cause instanceof LiveError?describeLiveError(cause):cause instanceof Error?cause.message:'Upload failed');
    }finally{if(session.isCurrent(identity))setBusy(false);}
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
    <p>{t('Upload PDF, text or Markdown up to 5 MiB. Extracted facts need reviewer approval.')}</p>
    <label>{t('Offer file')}<input type="file" accept=".pdf,.txt,.md" disabled={busy}
      onChange={event=>{setFile(event.target.files?.[0]??null);action.current=null;}}/></label>
    <div className="live-offer-doc-actions">
      <button type="button" disabled={!file||busy} onClick={()=>void upload()}>{t(busy?'Working...':'Upload document')}</button>
      <button type="button" disabled={busy} onClick={()=>void refresh()}>{t('Refresh document status')}</button>
    </div>
    {loading&&<p role="status">{t('Loading documents...')}</p>}
    {error&&<p role="alert">{t(error)}</p>}
    <ul>{rows.map(document=><li key={document.id}>
      <div className="live-offer-doc-row"><span><strong>{document.filename}</strong> · {t(document.status)}
      {document.failure_code&&<> · {document.failure_code}</>}</span>
      {document.status==='ready'&&<label><input type="checkbox" checked={selected.includes(document.id)}
        onChange={event=>onSelect(document.id,event.target.checked)}/>{t('Use in profile')}</label>}
      {document.status!=='deleted'&&<button type="button" disabled={busy}
        onClick={()=>void remove(document)}>{t('Delete')}</button>}</div>
      {document.status==='ready'&&document.fact_candidates?.map(fact=><div key={fact.id}>
        <span>{fact.field}: {fact.value}</span>
        <button type="button" onClick={()=>onApply(fact)}>{t('Apply candidate')}</button>
      </div>)}
    </li>)}</ul>
  </section>;
}
