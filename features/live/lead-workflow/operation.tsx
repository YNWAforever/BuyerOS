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
  const alive=useRef(true),inFlight=useRef(false),operationEpoch=useRef(0);
  const historyIdentity=`${snapshot.identity}:${buyerId??''}:${actions.join(',')}`;
  const [loadedHistory,setLoadedHistory]=useState('');
  const historyBlocked=loadedHistory!==historyIdentity;
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
  const t=(value:string)=>leadText(locale,value);
  const matches=(row:LeadIntentView)=>row.buyer_id===buyerId&&actions.includes(row.action);
  async function refreshPending(expectedEpoch=operationEpoch.current){
    const identity=session.identity();
    const rows=await recoverLeadIntents(client,session);
    if(alive.current&&session.isCurrent(identity)&&expectedEpoch===operationEpoch.current){setPending(rows.filter(matches));setLoadedHistory(historyIdentity);}
    return rows.filter(matches);
  }
  useEffect(()=>{
    if(!snapshot.authenticated||!snapshot.scope.project)return;
    const own=new AbortController(),identity=session.identity();
    void recoverLeadIntents(client,session,own.signal).then(rows=>{
      if(!own.signal.aborted&&session.isCurrent(identity)){setPending(rows.filter(row=>row.buyer_id===buyerId&&actions.includes(row.action)));setLoadedHistory(historyIdentity);}
    }).catch(cause=>{if(!own.signal.aborted&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));});
    return()=>own.abort();
  },[client,session,snapshot.identity,snapshot.authenticated,snapshot.scope.project,buyerId,actions,historyIdentity]);
  async function run(input:LeadIntentInput,success:string){
    if(inFlight.current||busy||historyBlocked||unknown||pending.length>0)return false;
    inFlight.current=true;
    const epoch=++operationEpoch.current;
    const identity=session.identity();setBusy(true);setError('');setMessage('');
    let staged:LeadIntentView|null=null,applied=false;
    try{
      staged=await prepareLeadIntent(client,session,input);
      const receipt=await applyLeadIntent(client,session,staged);
      applied=true;staged={...staged,state:'applied',receipt,payload:null};
      if(!alive.current||!session.isCurrent(identity))return false;
      await readback();
      await acknowledgeLeadIntent(client,session,staged.id);
      if(alive.current&&session.isCurrent(identity)){
        const acknowledgedId=staged.id;
        setPending(rows=>rows.filter(row=>row.id!==acknowledgedId));
        setUnknown(false);setMessage(t(success));
        // The mutation is complete after canonical readback and ack. Auxiliary
        // history cannot hold the editor/navigation lock or reclassify success.
        void refreshPending(epoch).catch(cause=>{
          if(alive.current&&session.isCurrent(identity)&&epoch===operationEpoch.current&&!(cause instanceof LiveCancelled))setError(t(describeLiveError(cause)));
        });
        return true;
      }
      return false;
    }catch(cause){
      if(alive.current&&session.isCurrent(identity)&&!(cause instanceof LiveCancelled)){
        const uncertain=applied||!(cause instanceof LiveError)||cause.status===0||cause.status>=500;
        setUnknown(uncertain);setMessage('');
        setError(uncertain?t('The save result is unconfirmed. Read the original operation before another edit.'):t(describeLiveError(cause)));
        const original=uncertain&&staged?{...staged,payload:null}:null;
        if(original)setPending(rows=>rows.some(row=>row.id===original.id)?rows:[...rows,original]);
        void refreshPending(epoch).then(()=>{
          if(alive.current&&session.isCurrent(identity)&&epoch===operationEpoch.current&&original){
            // Never lose a known durable handle to an incomplete history page.
            setPending(rows=>rows.some(row=>row.id===original.id)?rows:[...rows,original]);
          }
        }).catch(()=>{/* Keep unknown state and any known handle; readonly retry remains available. */});
      }
          return false;
    }finally{inFlight.current=false;if(alive.current&&session.isCurrent(identity))setBusy(false);}
  }
  async function reloadHistory(){
    if(inFlight.current||busy)return;
    const identity=session.identity();inFlight.current=true;const epoch=++operationEpoch.current;setBusy(true);setError('');setMessage('');
    try{
      await refreshPending(epoch);
      if(alive.current&&session.isCurrent(identity))setMessage(t('Original operation history loaded. Read or continue the existing operation.'));
    }catch(cause){if(alive.current&&session.isCurrent(identity)&&!(cause instanceof LiveCancelled))setError(t(describeLiveError(cause)));}
    finally{inFlight.current=false;if(alive.current&&session.isCurrent(identity))setBusy(false);}
  }
  async function resolve(row:LeadIntentView,resume=false){
    if(busy)return;
    operationEpoch.current++;
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
    operationEpoch.current++;
    const identity=session.identity();setBusy(true);
    try{
      const value=await cancelLeadIntent(client,session,row.id);
      if(value.state==='applied'){await readback();await acknowledgeLeadIntent(client,session,value.id);}
      if(alive.current&&session.isCurrent(identity)){setUnknown(false);setError('');await refreshPending();}
    }catch(cause){if(alive.current&&session.isCurrent(identity)&&!(cause instanceof LiveCancelled))setError(t(describeLiveError(cause)));}
    finally{if(alive.current&&session.isCurrent(identity))setBusy(false);}
  }
  return {pending,busy,error,message,unknown,historyBlocked,reloadHistory,run,resolve,cancel,refreshPending,setMessage};
}

export function LeadRecovery({operation,locale}:{
  operation:ReturnType<typeof useLeadOperation>;locale:LeadLocale;
}){
  const t=(value:string)=>leadText(locale,value);
  return <>
  {operation.historyBlocked&&!operation.error&&!operation.busy&&<p role="status">{t('Checking original operations…')}</p>}
  {(operation.unknown||operation.historyBlocked&&!!operation.error)&&operation.pending.length===0&&
    <button type="button" disabled={operation.busy} onClick={()=>void operation.reloadHistory()}>{t('Refresh original operations')}</button>}
  {operation.pending.map(row=><div className="activity" key={row.id}>
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
