'use client';
import {useEffect,useRef,useState} from 'react';
import {useWorkspaceSession,useSessionSnapshot} from '@/features/providers/workspace-session';
import {LiveCancelled,LiveError,describeLiveError} from '@/services/live/client';
import {prepareLeadIntent,applyLeadIntent,recoverLeadIntents,getLeadIntent,acknowledgeLeadIntent,cancelLeadIntent,
  type LeadIntentInput,type LeadIntentView} from '@/services/live/lead-intents';
import {leadText,type LeadLocale} from './copy';

export function useLeadOperation(
  buyerId:string|null,actions:readonly string[],readback:()=>Promise<void>,locale:LeadLocale,
){
  const {client,session}=useWorkspaceSession(),snapshot=useSessionSnapshot();
  const [pending,setPending]=useState<LeadIntentView[]>([]),[busy,setBusy]=useState(false);
  const [error,setError]=useState(''),[message,setMessage]=useState(''),[unknown,setUnknown]=useState(false);
  const alive=useRef(true);
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
  const t=(value:string)=>leadText(locale,value);
  const matches=(row:LeadIntentView)=>row.buyer_id===buyerId&&actions.includes(row.action);
  async function refreshPending(){
    const identity=session.identity();
    const rows=await recoverLeadIntents(client,session);
    if(alive.current&&session.isCurrent(identity))setPending(rows.filter(matches));
    return rows.filter(matches);
  }
  useEffect(()=>{
    if(!snapshot.authenticated||!snapshot.scope.project)return;
    const own=new AbortController(),identity=session.identity();
    void recoverLeadIntents(client,session,own.signal).then(rows=>{
      if(!own.signal.aborted&&session.isCurrent(identity))setPending(rows.filter(row=>row.buyer_id===buyerId&&actions.includes(row.action)));
    }).catch(cause=>{if(!own.signal.aborted&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));});
    return()=>own.abort();
  },[client,session,snapshot.identity,snapshot.authenticated,snapshot.scope.project,buyerId,actions]);
  async function run(input:LeadIntentInput,success:string){
    if(busy)return;
    const identity=session.identity();setBusy(true);setError('');setMessage('');
    try{
      const staged=await prepareLeadIntent(client,session,input);
      await applyLeadIntent(client,session,staged);
      if(!alive.current||!session.isCurrent(identity))return;
      await readback();
      await acknowledgeLeadIntent(client,session,staged.id);
      if(alive.current&&session.isCurrent(identity)){setUnknown(false);setMessage(t(success));await refreshPending();}
    }catch(cause){
      if(alive.current&&session.isCurrent(identity)&&!(cause instanceof LiveCancelled)){
        const uncertain=!(cause instanceof LiveError)||cause.status===0||cause.status>=500;
        setUnknown(uncertain);
        setError(uncertain?t('The save result is unconfirmed. Read the original operation before another edit.'):t(describeLiveError(cause)));
        try{await refreshPending();}catch{/* The unresolved state remains explicit; never substitute an empty history. */}
      }
    }finally{if(alive.current&&session.isCurrent(identity))setBusy(false);}
  }
  async function resolve(row:LeadIntentView,resume=false){
    if(busy)return;
    const identity=session.identity();setBusy(true);setError('');
    try{
      const current=await getLeadIntent(client,session,row.id);
      if(current.state==='applied'||resume){
        await applyLeadIntent(client,session,current);await readback();
        await acknowledgeLeadIntent(client,session,current.id);
        if(alive.current&&session.isCurrent(identity)){setUnknown(false);setMessage(t('Lead evidence saved.'));}
      }else if(alive.current&&session.isCurrent(identity))setMessage(t('Unsubmitted original operation.'));
      await refreshPending();
    }catch(cause){if(alive.current&&session.isCurrent(identity)&&!(cause instanceof LiveCancelled))setError(t(describeLiveError(cause)));}
    finally{if(alive.current&&session.isCurrent(identity))setBusy(false);}
  }
  async function cancel(row:LeadIntentView){
    const identity=session.identity();setBusy(true);
    try{
      const value=await cancelLeadIntent(client,session,row.id);
      if(value.state==='applied'){await readback();await acknowledgeLeadIntent(client,session,value.id);}
      if(alive.current&&session.isCurrent(identity)){setUnknown(false);setError('');await refreshPending();}
    }catch(cause){if(alive.current&&session.isCurrent(identity)&&!(cause instanceof LiveCancelled))setError(t(describeLiveError(cause)));}
    finally{if(alive.current&&session.isCurrent(identity))setBusy(false);}
  }
  return {pending,busy,error,message,unknown,run,resolve,cancel,refreshPending,setMessage};
}

export function LeadRecovery({operation,locale}:{
  operation:ReturnType<typeof useLeadOperation>;locale:LeadLocale;
}){
  const t=(value:string)=>leadText(locale,value);
  return <>{operation.pending.map(row=><div className="activity" key={row.id}>
    <p>{t('Original operation is pending. Read back or cancel it first.')}</p>
    <div className="inline">
      <button type="button" disabled={operation.busy} onClick={()=>void operation.resolve(row)}>{t('Read original operation')}</button>
      {row.state==='prepared'&&!row.redacted&&<button type="button" disabled={operation.busy} onClick={()=>void operation.resolve(row,true)}>{t('Continue original operation')}</button>}
      <button type="button" disabled={operation.busy} onClick={()=>void operation.cancel(row)}>{t('Cancel original operation')}</button>
    </div>
  </div>)}
  {operation.error&&<p role="alert">{operation.error}</p>}
  {operation.message&&<p role="status">{operation.message}</p>}</>;
}
