'use client';
import {useCallback,useEffect,useRef,useState} from 'react';
import {useSessionSnapshot,useWorkspaceSession} from '@/features/providers/workspace-session';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
import {listDraftDeliveryMessages,type DeliveryMessagePage} from '@/services/live/delivery-history';
import type {Draft} from '@/services/live/drafts';

const zh:Record<string,string>={
  'Native delivery history':'站內寄送紀錄','Refresh delivery history':'重新整理寄送紀錄',
  'Loading delivery history…':'正在載入寄送紀錄…','No native delivery records.':'尚無站內寄送紀錄。',
  'Approved export and manual outcomes remain available.':'仍可使用已批准匯出及手動結果紀錄。',
  'History retains each original approved revision. Refreshing does not send or change your draft.':'紀錄保留原本已批准的版本。重新整理不會寄送或更改草稿。',
  'Prepared':'已準備','Submission in progress':'正在提交','Outcome unknown':'結果未知',
  'Accepted by provider':'供應商已受理','Delivered':'已送達','Bounced':'退信',
  'Complaint received':'收到投訴','Unsubscribed':'已退訂','Failed':'失敗','Rejected':'被拒絕',
  'Keep this original message. Ask a workspace administrator to reconcile it before any further action.':'請保留此原訊息，並請工作區管理員先核對結果，再採取其他行動。',
  'Provider acceptance does not confirm delivery.':'供應商受理不代表訊息已送達。',
  'Revision':'版本','Updated':'更新時間','Record details':'紀錄詳情','Message':'訊息',
  'Approval':'審批','Revision ID':'版本識別碼','Records':'紀錄數',
  'Previous delivery page':'上一頁寄送紀錄','Next delivery page':'下一頁寄送紀錄',
};
const labels={prepared:'Prepared',submitting:'Submission in progress',unknown:'Outcome unknown',
  accepted:'Accepted by provider',delivered:'Delivered',bounced:'Bounced',complained:'Complaint received',
  unsubscribed:'Unsubscribed',failed:'Failed',rejected:'Rejected'} as const;
type View={identity:string;draftId:string;status:'loading'|'ready'|'error';page:DeliveryMessagePage|null;error:string};

export function DraftDeliveryHistory({draft,locale}:{draft:Pick<Draft,'id'|'workspace_id'|'project_id'>;locale:'en'|'zh-HK'}){
  const {client,session}=useWorkspaceSession(),snapshot=useSessionSnapshot();
  const {id,workspace_id,project_id}=draft,identity=snapshot.identity;
  const available=snapshot.authenticated&&snapshot.scope.workspace===workspace_id&&snapshot.scope.project===project_id;
  const [view,setView]=useState<View|null>(null),sequence=useRef(0);
  const t=(text:string)=>locale==='zh-HK'?(zh[text]||text):text;
  const load=useCallback(async(offset:number)=>{
    if(!available)return;
    const ticket=++sequence.current;
    setView({identity,draftId:id,status:'loading',page:null,error:''});
    try{
      const page=await listDraftDeliveryMessages(client,session,{id,workspace_id,project_id},offset);
      if(ticket===sequence.current&&session.isCurrent(identity))setView({identity,draftId:id,status:'ready',page,error:''});
    }catch(error){
      if(ticket!==sequence.current||!session.isCurrent(identity)||error instanceof LiveCancelled)return;
      setView({identity,draftId:id,status:'error',page:null,error:describeLiveError(error)});
    }
  },[available,client,session,id,workspace_id,project_id,identity]);
  const invalidate=useCallback(()=>{sequence.current++;},[]);
  useEffect(()=>{
    let active=true;
    void Promise.resolve().then(()=>{if(active)void load(0);});
    return()=>{active=false;invalidate();};
  },[load,invalidate]);
  // Hide a previous actor/project's result during render, before the next effect.
  const current=available&&view?.identity===identity&&view.draftId===id?view:null;
  const page=current?.page??null,busy=available&&(!current||current.status==='loading');
  return <section className="card" aria-label={t('Native delivery history')} aria-busy={busy}>
    <h3>{t('Native delivery history')}</h3>
    <p>{t('History retains each original approved revision. Refreshing does not send or change your draft.')}</p>
    <button type="button" disabled={busy||!available} onClick={()=>void load(page?.offset??0)}>{t('Refresh delivery history')}</button>
    {busy?<p role="status">{t('Loading delivery history…')}</p>:null}
    {current?.status==='error'?<p role="alert">{current.error}</p>:null}
    {page?<>
      <p role="status">{t('Records')}: {page.total}</p>
      {page.items.length===0?<p>{t('No native delivery records.')} {t('Approved export and manual outcomes remain available.')}</p>:null}
      <ul>{page.items.map(row=><li key={row.id}>
        <p><strong>{t(labels[row.state])}</strong> · {t('Revision')} {row.revision_number}</p>
        {row.state==='unknown'?<p>{t('Keep this original message. Ask a workspace administrator to reconcile it before any further action.')}</p>:null}
        {row.state==='accepted'?<p>{t('Provider acceptance does not confirm delivery.')}</p>:null}
        <p>{t('Updated')}: <time dateTime={row.updated_at}>{new Date(row.updated_at).toLocaleString(locale)}</time></p>
        <details style={{overflowWrap:'anywhere'}}><summary>{t('Record details')}</summary>
          <dl><dt>{t('Message')}</dt><dd>{row.id}</dd><dt>{t('Revision ID')}</dt><dd>{row.draft_revision_id}</dd><dt>{t('Approval')}</dt><dd>{row.approval_id}</dd></dl>
        </details>
      </li>)}</ul>
      <div className="inline">
        <button type="button" disabled={busy||page.offset===0} onClick={()=>void load(Math.max(0,page.offset-page.limit))}>{t('Previous delivery page')}</button>
        <button type="button" disabled={busy||page.offset+page.limit>=page.total} onClick={()=>void load(page.offset+page.limit)}>{t('Next delivery page')}</button>
      </div>
    </>:null}
  </section>;
}
