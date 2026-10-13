'use client';
import {useEffect,useMemo,useRef,useState} from 'react';
import {useSessionSnapshot,useWorkspaceSession} from '@/features/providers/workspace-session';
import {LiveCancelled,LiveError,describeLiveError} from '@/services/live/client';
import {BuyerImportWorkflow,type BuyerImportPreview,type BuyerImportResult} from '@/services/live/buyer-import';

/** Remount on scope generation so no file, preview or late result can cross projects. */
export function LiveBuyerImport({onImported,t}:{onImported:()=>void;t:(text:string)=>string}){
  const snapshot=useSessionSnapshot();
  return <BuyerImportForm key={snapshot.identity} onImported={onImported} t={t}/>;
}
function BuyerImportForm({onImported,t}:{onImported:()=>void;t:(text:string)=>string}){
  const {client,session}=useWorkspaceSession();
  const workflow=useMemo(()=>new BuyerImportWorkflow(client,session),[client,session]);
  const [file,setFile]=useState<File|null>(null),[preview,setPreview]=useState<BuyerImportPreview|null>(null);
  const [result,setResult]=useState<BuyerImportResult|null>(null),[confirmed,setConfirmed]=useState(false);
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[uncertain,setUncertain]=useState(false);
  const [expanded,setExpanded]=useState(false);
  const [importId,setImportId]=useState(()=>{
    if(typeof window==='undefined')return '';
    const params=new URLSearchParams(window.location.search),value=params.get('buyer_import')??'';
    return params.get('buyer_import_project')===session.current().project&&/^[a-f0-9-]{36}$/i.test(value)?value:'';
  });
  const [recovering,setRecovering]=useState(()=>Boolean(importId));
  const mounted=useRef(true),fileInput=useRef<HTMLInputElement>(null),notified=useRef(''),recovered=useRef(false);
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  function remember(id:string){
    setImportId(id);const url=new URL(window.location.href);
    if(id){url.searchParams.set('buyer_import',id);url.searchParams.set('buyer_import_project',session.current().project!);}
    else{url.searchParams.delete('buyer_import');url.searchParams.delete('buyer_import_project');}
    window.history.replaceState(window.history.state,'',url.pathname+url.search+url.hash);
  }
  function committed(value:BuyerImportResult){
    setResult(value);setPreview(null);setUncertain(false);setError('');
    if(notified.current!==value.id){notified.current=value.id;onImported();}
  }
  useEffect(()=>{
    if(!importId||recovered.current)return;
    let active=true;
    void workflow.lookup(importId).then(value=>{
      if(!active)return;recovered.current=true;setRecovering(false);
      if(value.status==='completed'){
        setResult(value);setPreview(null);setUncertain(false);
        if(notified.current!==value.id){notified.current=value.id;onImported();}
      }
      else setPreview(value);
    }).catch(cause=>{if(active&&!(cause instanceof LiveCancelled)){recovered.current=true;setRecovering(false);setUncertain(true);setError(describeLiveError(cause));}});
    return()=>{active=false;};
  },[workflow,importId,onImported]);
  async function stage(){
    if(!file||busy||uncertain||recovering)return;setBusy(true);setError('');setResult(null);
    try{const value=await workflow.preview(file);if(!mounted.current)return;recovered.current=true;setPreview(value);setConfirmed(false);remember(value.id);}
    catch(cause){if(mounted.current&&!(cause instanceof LiveCancelled))setError(cause instanceof LiveError?describeLiveError(cause):cause instanceof Error?cause.message:'Import preview failed.');}
    finally{if(mounted.current)setBusy(false);}
  }
  async function confirm(){
    if(!preview||!confirmed||busy)return;setBusy(true);setError('');
    try{const value=await workflow.confirm(preview);if(mounted.current)committed(value);}
    catch(cause){if(mounted.current&&!(cause instanceof LiveCancelled)){setUncertain(true);setError(describeLiveError(cause));}}
    finally{if(mounted.current)setBusy(false);}
  }
  async function reconcile(){
    if(!importId||busy)return;setBusy(true);setError('');
    try{const value=await workflow.lookup(importId);if(!mounted.current)return;
      if(value.status==='completed')committed(value);else{setPreview(value);setUncertain(false);}
    }catch(cause){if(mounted.current&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    finally{if(mounted.current)setBusy(false);}
  }
  function reset(){setExpanded(true);setPreview(null);setResult(null);setFile(null);setConfirmed(false);setError('');remember('');if(fileInput.current)fileInput.current.value='';}
  return <details className="live-buyer-import" open={expanded||!!preview||!!result||!!error} onToggle={event=>setExpanded(event.currentTarget.open)}>
    <summary>{t('Import buyers from Excel or CSV')}</summary>
    <p>{t('Preview the source rows, then confirm the candidates to add. Imported buyers remain unreviewed; research and email do not start.')}</p>
    {!preview&&!result&&<div className="inline">
      <label>{t('Buyer spreadsheet')} <input ref={fileInput} type="file" accept=".csv,.xlsx" disabled={busy||uncertain||recovering} onChange={event=>{setFile(event.target.files?.[0]??null);setError('');}}/></label>
      <button type="button" disabled={!file||busy||recovering} onClick={()=>void stage()}>{busy?t('Working...'):t('Preview import')}</button>
      <span>{t('CSV or XLSX, up to 5 MiB. Company name is required; website and source fields are optional.')}</span>
    </div>}
    {error&&<p role="alert">{t(error)}</p>}
    {uncertain&&<p role="status">{t('The import result is unconfirmed. Check its status before starting another import; retry keeps the original confirmation.')}</p>}
    {preview&&<>
      <p><strong>{preview.file_name}</strong> · {t('Rows')}: {preview.total_rows} · {t('Ready to import')}: {preview.ready_rows} · {t('Duplicates skipped')}: {preview.duplicate_rows} · {t('Invalid rows')}: {preview.invalid_rows}</p>
      <div className="table-scroll" tabIndex={0} role="region" aria-label={t('Import preview rows')}>
        <table><thead><tr>{['Source row','Company','Domain','Source date','Status'].map(label=><th key={label} scope="col">{t(label)}</th>)}</tr></thead>
          <tbody>{preview.rows.map(row=><tr key={row.row_number}><td>{row.source_row??row.row_number}</td><td>{row.name||'—'}</td><td>{row.normalized_domain??t('Unknown')}</td><td>{row.source_date??'—'}</td><td>{t(row.status)}{row.errors.length>0&&<ul>{row.errors.map((message,index)=><li key={index}>{t(message)}</li>)}</ul>}</td></tr>)}</tbody></table>
      </div>
      {preview.invalid_rows>0&&<p role="status">{t('Correct every invalid row and preview the file again before importing.')}</p>}
      <label><input type="checkbox" checked={confirmed} disabled={busy||!preview.can_import} onChange={event=>setConfirmed(event.target.checked)}/>{t('I checked these source rows and want to add the eligible candidates as unreviewed buyers.')}</label>
      <div className="inline"><button type="button" disabled={busy||!confirmed||!preview.can_import} onClick={()=>void confirm()}>{t(uncertain?'Retry same import':'Confirm buyer import')}</button>
        <button type="button" disabled={busy} onClick={()=>void reconcile()}>{t('Check import status')}</button>
        {!uncertain&&<button type="button" disabled={busy} onClick={reset}>{t('Choose another file')}</button>}</div>
    </>}
    {result&&<><p role="status">{t('Imported {count} buyers; skipped {duplicates} duplicates.').replace('{count}',String(result.imported_rows)).replace('{duplicates}',String(result.skipped_duplicate_rows))}</p><button type="button" disabled={busy||recovering} onClick={reset}>{t('Import another file')}</button></>}
    {importId&&!preview&&!result&&<button type="button" disabled={busy||recovering} onClick={()=>void reconcile()}>{t('Check import status')}</button>}
  </details>;
}
