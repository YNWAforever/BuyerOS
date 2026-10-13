'use client';
import {useRef,useState} from 'react';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
import type {BuyerImportSource} from '@/services/live/buyer-import';

function safeUrl(value:string){try{const url=new URL(value);return ['http:','https:'].includes(url.protocol)?url.href:null;}catch{return null;}}
export function BuyerImportSourcePanel({buyerId,t}:{buyerId:string;t:(text:string)=>string}){
  const {client,session}=useWorkspaceSession();
  const [source,setSource]=useState<BuyerImportSource|null>(null),[loaded,setLoaded]=useState(false);
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  const identity=useRef(session.identity());
  async function load(){
    if(busy||loaded)return;const context=session.captureWriteContext();setBusy(true);setError('');
    try{
      const value=await client.request<BuyerImportSource|null>({path:`/v1/workspaces/${encodeURIComponent(context.workspace)}/buyers/${encodeURIComponent(buyerId)}/import-source`,token:session.token(),scope:context.identity,signal:context.signal});
      if(session.isCurrent(identity.current)){setSource(value);setLoaded(true);}
    }catch(cause){if(!(cause instanceof LiveCancelled)&&session.isCurrent(identity.current))setError(describeLiveError(cause));}
    finally{if(session.isCurrent(identity.current))setBusy(false);}
  }
  return <section className="live-buyer-source" aria-label={t('Imported source')}>
    <h4>{t('Imported source')}</h4>
    {!loaded&&<button type="button" disabled={busy} onClick={()=>void load()}>{t(busy?'Working...':'Load imported source')}</button>}
    {error&&<p role="alert">{error}</p>}
    {loaded&&!source&&<p>{t('No spreadsheet source is recorded for this buyer.')}</p>}
    {source&&<>
      <p>{t('Source-provided information. Company identity, buyer fit and contact details still require review.')}</p>
      <p>{t('File')}: {source.file_name} · {t('Source row')}: {source.source_row??source.row_number} · {t('Source date')}: {source.source_date??'—'}</p>
      {source.source_urls.length>0&&<ul>{source.source_urls.map((value,index)=><li key={index}>{safeUrl(value)?<a href={safeUrl(value)!} target="_blank" rel="noopener noreferrer">{value}</a>:value}</li>)}</ul>}
      <details><summary>{t('Original spreadsheet fields')}</summary><dl>{Object.entries(source.original_fields).map(([field,value])=><div key={field}><dt>{field}</dt><dd>{value===null?'—':String(value)}</dd></div>)}</dl><p className="muted">{t('Content hash')}: {source.file_sha256}</p></details>
    </>}
  </section>;
}
