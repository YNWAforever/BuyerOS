'use client';
import {useEffect,useRef,useState} from 'react';
import {useWorkspaceSession,useSessionSnapshot} from '@/features/providers/workspace-session';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
import {ActionIntent} from '@/services/live/action-intent';
import {downloadText} from '@/services/live/download-text';
import type {ReviewSelection} from '@/services/live/buyer-selection';
import type {Draft} from '@/services/live/drafts';
import {createBuyerExport,createDraftExport,getExport,readExportContent,type ExportJob} from '@/services/live/exports';

const zh:Record<string,string>={
  'Authorized export':'授權匯出','Selected scope':'所選範圍','Company-only CSV':'只含公司資料 CSV',
  'Company + eligible contact CSV':'公司及合資格聯絡資料 CSV',
  'Include eligible contact data':'包括合資格聯絡資料','Prepare export':'準備匯出',
  'Prepare approved copy':'準備已批准副本','Draft copy format':'草稿副本格式',
  'Download text':'下載文字','Copy to clipboard':'複製到剪貼簿',
  'Download CSV':'下載 CSV','Refresh export':'重新整理匯出',
  'Allowed':'允許','Excluded':'排除','Expires':'到期','Export is ready.':'匯出已備妥。',
  'Content copied after current authorization.':'重新核對授權後已複製內容。',
  'Download requested after current authorization.':'重新核對授權後已要求下載。',
  'Only current policy and, for addressed drafts, current exact approval allow content.':'只有現行政策及已指定收件人草稿的有效精確審批，才可取得內容。',
  'Copy and download never send a message.':'複製及下載均不會寄送訊息。',
  'No selection':'尚未選擇','ready':'已備妥','revoked':'已撤銷','expired':'已過期',
};

export function ExportDialog({locale,selection,draft,canExport=true}:{locale:'en'|'zh-HK';
  selection?:ReviewSelection|null;draft?:Draft|null;canExport?:boolean}){
  const {client,session}=useWorkspaceSession(),snapshot=useSessionSnapshot();
  const t=(value:string)=>locale==='zh-HK'?(zh[value]||value):value;
  const [includeContacts,setIncludeContacts]=useState(false);
  const [draftFormat,setDraftFormat]=useState<'text'|'clipboard'>('text');
  const [job,setJob]=useState<ExportJob|null>(null),[busy,setBusy]=useState(false);
  const [error,setError]=useState(''),[notice,setNotice]=useState('');
  const intent=useRef(new ActionIntent<ExportJob>());
  const mode=draft?'draft':'buyers';
  const scopeKey=snapshot.identity;
  useEffect(()=>{
    const id=new URLSearchParams(window.location.search).get('export');
    if(!id||!snapshot.authenticated||!snapshot.scope.workspace||!snapshot.scope.project)return;
    let active=true;
    void getExport(client,session,id).then(value=>{if(active&&value.project_id===snapshot.scope.project&&value.kind===(mode==='draft'?'draft_text':'buyer_csv'))setJob(value);})
      .catch(cause=>{if(active&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));});
    return()=>{active=false;};
  },[client,session,scopeKey,snapshot.authenticated,snapshot.scope.workspace,snapshot.scope.project,mode]);
  function remember(id:string){const url=new URL(window.location.href);url.searchParams.set('export',id);
    window.history.replaceState(window.history.state,'',url.pathname+url.search+url.hash);}
  async function prepare(){
    if(!canExport||busy||(!draft&&!selection))return;
    setBusy(true);setError('');setNotice('');
    try{
      const fingerprint=JSON.stringify({scopeKey,mode,selection,draftId:draft?.id,
        draftVersion:draft?.version,includeContacts,draftFormat});
      const created=await intent.current.run(fingerprint,key=>draft
        ?createDraftExport(client,session,draft,draftFormat,key)
        :createBuyerExport(client,session,selection!,includeContacts,key));
      setJob(created);remember(created.id);setNotice(t('Export is ready.'));
    }catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    finally{setBusy(false);}
  }
  async function refresh(){
    if(!job||busy)return;setBusy(true);setError('');
    try{setJob(await getExport(client,session,job.id));}
    catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    finally{setBusy(false);}
  }
  async function release(){
    if(!job||busy||job.status!=='ready')return;setBusy(true);setError('');setNotice('');
    try{
      const {text,contentType}=await readExportContent(client,session,job.id);
      if(job.kind==='draft_text'&&job.format==='clipboard'){
        await navigator.clipboard.writeText(text);
        setNotice(t('Content copied after current authorization.'));
      }else{
        downloadText(text,contentType,job.kind==='buyer_csv'?`buyeros-export-${job.id}.csv`:`buyeros-draft-${job.id}.txt`);
        setNotice(t('Download requested after current authorization.'));
      }
    }catch(cause){if(!(cause instanceof LiveCancelled)){
      setError(describeLiveError(cause));try{setJob(await getExport(client,session,job.id));}catch{}
    }}finally{setBusy(false);}
  }
  const count=selection?.kind==='explicit'?selection.buyers.length:selection?.kind==='snapshot'?'snapshot':0;
  return <section className="panel live-export" role="region" aria-label={t('Authorized export')}>
    <h3>{t('Authorized export')}</h3>
    <p>{t('Only current policy and, for addressed drafts, current exact approval allow content.')}</p>
    <p>{t('Copy and download never send a message.')}</p>
    {mode==='buyers'?<>
      <p>{t('Selected scope')}: {count||t('No selection')}</p>
      <label><input type="checkbox" checked={includeContacts} onChange={event=>setIncludeContacts(event.target.checked)}/>
        {t('Include eligible contact data')}</label>
      <p>{t(includeContacts?'Company + eligible contact CSV':'Company-only CSV')}</p>
    </>:<label>{t('Draft copy format')} <select value={draftFormat} onChange={event=>setDraftFormat(event.target.value as 'text'|'clipboard')}>
      <option value="text">{t('Download text')}</option><option value="clipboard">{t('Copy to clipboard')}</option></select></label>}
    <div className="inline"><button type="button" disabled={busy||!canExport||(!draft&&!selection)} onClick={()=>void prepare()}>
      {mode==='draft'?t('Prepare approved copy'):t('Prepare export')}</button>
      {job&&<button type="button" disabled={busy} onClick={()=>void refresh()}>{t('Refresh export')}</button>}</div>
    {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
    {job&&<div><p>{job.id} · {t(job.status)} · {t('Allowed')}: {job.record_count} · {t('Excluded')}: {job.excluded_records.length}</p>
      {job.expires_at&&<p>{t('Expires')}: {new Date(job.expires_at).toLocaleString(locale)}</p>}
      {job.excluded_records.length>0&&<ul>{job.excluded_records.map((item,index)=><li key={`${item.entity_id||index}:${index}`}>
        {item.entity_id||''} · {item.reason_code}</li>)}</ul>}
      {job.status==='ready'&&<button type="button" disabled={busy||!canExport} onClick={()=>void release()}>
        {job.kind==='buyer_csv'?t('Download CSV'):job.format==='clipboard'?t('Copy to clipboard'):t('Download text')}</button>}
    </div>}
  </section>;
}
