'use client';
import {useState} from 'react';
import {Building2} from 'lucide-react';
import {LiveCancelled,LiveError,type LiveClient} from '@/services/live/client';
import type {SessionScope} from '@/services/live/session';
import {scopedThreadApi} from '@/services/live/conversation-threads';
import {scopedTurns,turnNotice} from '@/services/live/conversation-turn';

export type CompanyDiscussionResult={threadId:string;linked:boolean};
function intentText(locale:'en'|'zh-HK'):string{
  return locale==='zh-HK'?'討論這間公司，以及在接觸前需要確認的事項。':'Discuss this company and what to verify before outreach.';
}
function titleFrom(text:string):string{return text.trim().replace(/\s+/g,' ').slice(0,80);}
/**
 * Thread-first turn linked to one canonical buyer. A missing turn route falls back
 * to a plain discussion created with the same text exactly once (never duplicated),
 * and reports that the company link could not be attached.
 */
export async function startCompanyDiscussion({client,session,locale,buyerId}:{
  client:LiveClient;session:SessionScope;locale:'en'|'zh-HK';buyerId:string;
}):Promise<CompanyDiscussionResult>{
  const text=intentText(locale);
  const clientMessageId=crypto.randomUUID();
  try{
    const result=await scopedTurns(client,session,true).submit({threadId:null,expectedVersion:null,
      text,language:locale,clientMessageId,templateId:'check-company',skillId:'sales-contacts',buyerId});
    return {threadId:result.thread.id,linked:true};
  }catch(error){
    if(error instanceof LiveCancelled)throw error;
    if(!(error instanceof LiveError)||!(error.status===404||error.code==='NOT_FOUND'))throw error;
    // Older server: existing behaviour is a plain discussion seeded once with the intent.
    const created=await scopedThreadApi(client,session,session.identity()).create(titleFrom(text),text);
    return {threadId:created.id,linked:false};
  }
}
type Props={
  client:LiveClient;session:SessionScope;t:(value:string)=>string;locale:'en'|'zh-HK';
  navigate:(path:string)=>void;buyerId:string;buyerName?:string;onStart?:()=>void;
};
export function DiscussCompanyButton({client,session,t,locale,navigate,buyerId,buyerName,onStart}:Props){
  const [busy,setBusy]=useState(false),[notice,setNotice]=useState('');
  async function start(){
    if(busy)return;
    setBusy(true);setNotice('');
    try{
      const result=await startCompanyDiscussion({client,session,locale,buyerId});
      onStart?.();
      navigate(result.linked?`/app/discussions/s/${result.threadId}`:`/app/discussions/s/${result.threadId}?company=unlinked`);
    }catch(error){
      if(error instanceof LiveCancelled)return;
      setNotice(turnNotice(error));
    }finally{setBusy(false);}
  }
  return <div className="conversation-company-start">
    <button type="button" disabled={busy} onClick={()=>void start()} title={buyerName}>
      <Building2 size={16} aria-hidden="true"/>{t(busy?'Starting discussion…':'Discuss this company')}
    </button>
    {notice&&<p role="status">{t(notice)}</p>}
  </div>;
}
