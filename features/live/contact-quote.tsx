'use client';



import {useEffect,useMemo,useRef,useState} from 'react';

import {useDataMode} from '@/features/providers/data-mode';

import {useSessionSnapshot,useWorkspaceSession} from '@/features/providers/workspace-session';

import {ActionIntent} from '@/services/live/action-intent';

import {LiveCancelled,describeLiveError} from '@/services/live/client';

import {cancelContactJob,cancelContactQuote,confirmContactQuote,getContactJob,getContactQuote,quoteContact,type ContactJob,type ContactQuote} from '@/services/live/quotes';

import type {RunContext} from '@/services/live/runs';



export function ContactQuotePreview({buyerId,buyerVersion,canQuote,t}:{

  buyerId:string;buyerVersion:number;canQuote:boolean;t:(value:string)=>string;

}) {

  const {session,client}=useWorkspaceSession(),{apiBaseUrl}=useDataMode();

  const snapshot=useSessionSnapshot();

  const scope=snapshot.scope;

  const ctx=useMemo<RunContext|null>(()=>scope.workspace&&scope.project?

    {client,session,apiBaseUrl,workspaceId:scope.workspace,projectId:scope.project}:null,

    [client,session,apiBaseUrl,scope.workspace,scope.project]);

  const [role,setRole]=useState('Procurement manager');

  const [cancelReason,setCancelReason]=useState('Quote no longer needed');

  const [jobCancelReason,setJobCancelReason]=useState('Lookup no longer needed');

  const [quote,setQuote]=useState<ContactQuote|null>(null);

  const [job,setJob]=useState<ContactJob|null>(null);

  const [quoteIdentity,setQuoteIdentity]=useState('');

  const [error,setError]=useState<{identity:string;message:string}|null>(null),[busy,setBusy]=useState(false);

  const quoteIntent=useRef(new ActionIntent<ContactQuote>()),cancelIntent=useRef(new ActionIntent<ContactQuote>()),

    confirmIntent=useRef(new ActionIntent<ContactJob>()),jobCancelIntent=useRef(new ActionIntent<ContactJob>());

  const visibleQuote=quoteIdentity===session.identity()?quote:null;

  const visibleJob=quoteIdentity===session.identity()?job:null;


  useEffect(()=>{
    if(!ctx||!snapshot.authenticated)return;
    const value=new URL(window.location.href).searchParams.get('contact_job');
    if(!value||!/^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$/.test(value))return;
    const identity=session.identity();
    let active=true;
    void getContactJob(ctx,value).then(found=>{
      if(active&&session.isCurrent(identity)){setJob(found);setQuoteIdentity(identity);}
    }).catch(cause=>{
      if(active&&session.isCurrent(identity)&&!(cause instanceof LiveCancelled))
        setError({identity,message:describeLiveError(cause)});
    });
    return ()=>{active=false;};
  },[ctx,session,snapshot.authenticated,snapshot.identity]);

  async function refreshJob(){
    if(!ctx||!visibleJob||busy)return;
    const identity=session.identity();setBusy(true);setError(null);
    try{const value=await getContactJob(ctx,visibleJob.id);if(session.isCurrent(identity))setJob(value);}
    catch(cause){if(session.isCurrent(identity)&&!(cause instanceof LiveCancelled))setError({identity,message:describeLiveError(cause)});}
    finally{setBusy(false);}
  }

  async function cancelJob(){
    if(!ctx||!visibleJob||busy||!canQuote||jobCancelReason.trim().length<3)return;
    const identity=session.identity();setBusy(true);setError(null);
    try{
      const value=await jobCancelIntent.current.run(
        JSON.stringify({id:visibleJob.id,version:visibleJob.version,reason:jobCancelReason.trim()}),
        key=>cancelContactJob(ctx,visibleJob,jobCancelReason.trim(),key));
      if(session.isCurrent(identity))setJob(value);
    }catch(cause){if(session.isCurrent(identity)&&!(cause instanceof LiveCancelled))setError({identity,message:describeLiveError(cause)});}
    finally{setBusy(false);}
  }



  async function viewQuote(){

    if(!ctx||!canQuote||busy||!role.trim())return;

    const identity=session.identity();setBusy(true);setError(null);

    try{

      const value=await quoteIntent.current.run(JSON.stringify({workspace:ctx.workspaceId,project:ctx.projectId,

        buyerId,buyerVersion,role:role.trim()}),key=>quoteContact(ctx,buyerId,buyerVersion,role.trim(),key));

      if(session.isCurrent(identity)){setQuote(value);setJob(null);setQuoteIdentity(identity);}

    }catch(cause){if(session.isCurrent(identity)&&!(cause instanceof LiveCancelled))setError({identity,message:describeLiveError(cause)});}

    finally{setBusy(false);}

  }

  async function refreshQuote(){

    if(!ctx||!visibleQuote||busy)return;

    const identity=session.identity();setBusy(true);setError(null);

    try{const value=await getContactQuote(ctx,visibleQuote.id);if(session.isCurrent(identity))setQuote(value);}

    catch(cause){if(session.isCurrent(identity)&&!(cause instanceof LiveCancelled))setError({identity,message:describeLiveError(cause)});}

    finally{setBusy(false);}

  }

  async function cancelQuote(){

    if(!ctx||!visibleQuote||visibleQuote.status!=='quoted'||busy||cancelReason.trim().length<3)return;

    const identity=session.identity();setBusy(true);setError(null);

    try{const value=await cancelIntent.current.run(JSON.stringify({id:visibleQuote.id,version:visibleQuote.version,reason:cancelReason.trim()}),

      key=>cancelContactQuote(ctx,visibleQuote,cancelReason.trim(),key));if(session.isCurrent(identity))setQuote(value);}

    catch(cause){if(session.isCurrent(identity)&&!(cause instanceof LiveCancelled))setError({identity,message:describeLiveError(cause)});}

    finally{setBusy(false);}

  }

  async function confirmQuote(){

    if(!ctx||!canQuote||!visibleQuote||visibleQuote.status!=='quoted'||

      visibleQuote.eligible_buyer_ids.length===0||busy)return;

    const identity=session.identity();setBusy(true);setError(null);

    try{

      const value=await confirmIntent.current.run(JSON.stringify({id:visibleQuote.id,hash:visibleQuote.quote_hash}),

        key=>confirmContactQuote(ctx,visibleQuote,key));

      if(session.isCurrent(identity)){

        setJob(value);

        const url=new URL(window.location.href);url.searchParams.set('contact_job',value.id);

        window.history.replaceState(null,'',url);

        setQuote({...visibleQuote,status:'consumed',version:visibleQuote.version+1,

          reservation_id:value.reservation_id,consumed_job_id:value.id});

      }

    }catch(cause){if(session.isCurrent(identity)&&!(cause instanceof LiveCancelled))setError({identity,message:describeLiveError(cause)});}

    finally{setBusy(false);}

  }

  return <section className="contact-quote" aria-label={t('Optional contact quote')}>

    <h4>{t('Optional contact quote')}</h4>

    <p>{t('A quote does not reserve money or look up a contact. Confirmation is a separate action.')}</p>

    {canQuote?<div className="inline"><label>{t('Requested business role')} <input value={role} maxLength={100}

      onChange={event=>setRole(event.target.value)}/></label>

      <button type="button" disabled={busy||!role.trim()} onClick={()=>void viewQuote()}>{busy?t('Working...'):t('View contact quote')}</button></div>

      :<p role="status">{t('Operator access is required to request a quote.')}</p>}

    {error?.identity===session.identity()&&<p role="alert">{error.message}</p>}

    {visibleQuote&&<div role="status"><p>{t('Quote status')}: {t(visibleQuote.status)} 繚 {t('Quote ID')}: {visibleQuote.id}</p>

      <p>{t('Requested business role')}: {visibleQuote.roles.join(', ')} 繚 {t('Maximum cost')}: USD {visibleQuote.max_cost.amount}</p>

      <p>{t('Quote expires')}: {visibleQuote.expires_at} 繚 {t('Eligible buyers')}: {visibleQuote.eligible_buyer_ids.length}</p>

      <p>{t('Budget availability is rechecked before any confirmation. No charge or hold exists for this quote.')}</p>

      <ul>{visibleQuote.eligibility.map(line=><li key={line.buyer_id}>{line.buyer_id}: {line.eligible?t('Eligible'):t('Blocked')}

        {line.reason_codes.length>0&&` 繚 ${line.reason_codes.map(t).join(', ')}`}</li>)}</ul>

      {visibleQuote.status==='quoted'&&<label>{t('Cancellation reason')} <input value={cancelReason} maxLength={2000}

        onChange={event=>setCancelReason(event.target.value)}/></label>}

      <div className="inline"><button type="button" disabled={busy} onClick={()=>void refreshQuote()}>{t('Refresh quote')}</button>

        {visibleQuote.status==='quoted'&&<button type="button" disabled={busy||cancelReason.trim().length<3} onClick={()=>void cancelQuote()}>{t('Cancel unused quote')}</button>}

        <button type="button" disabled={busy||!canQuote||visibleQuote.status!=='quoted'||visibleQuote.eligible_buyer_ids.length===0}

          onClick={()=>void confirmQuote()}>{t('Confirm lookup')}</button></div>

    </div>}

    {visibleJob&&<div className="contact-job" role="status">

      <h4>{t('Contact lookup job')}</h4>

      <p>{t('Job ID')}: {visibleJob.id}</p>

      <p>{t('Job status')}: {t(visibleJob.status)} · {t('Reconciliation')}: {t(visibleJob.reconciliation_state)}</p>

      <p>{t('Held cost')}: USD {visibleJob.held_cost.amount} · {t('Settled cost')}: USD {visibleJob.settled_cost.amount}</p>

      <p>{t('Completed')}: {visibleJob.completed_count} · {t('Found')}: {visibleJob.found_count} · {t('Unknown')}: {visibleJob.unknown_count}</p>

      {visibleJob.status==='reserved'&&<p>{t('Lookup accepted and queued. No contact has been found or charge settled yet.')}</p>}

      {visibleJob.unknown_count>0&&<p>{t('An unknown provider result keeps the hold. An administrator must reconcile it before retry or release.')}</p>}

      <p>{t('A contact validity result does not grant outreach permission.')}</p>

      {canQuote&&!['cancelled','found','not_found','failed','reconciled'].includes(visibleJob.status)&&

        <label>{t('Cancellation reason')} <input value={jobCancelReason} maxLength={2000}

          onChange={event=>setJobCancelReason(event.target.value)}/></label>}

      <div className="inline"><button type="button" disabled={busy} onClick={()=>void refreshJob()}>{t('Refresh lookup job')}</button>

        {canQuote&&!['cancelled','found','not_found','failed','reconciled'].includes(visibleJob.status)&&

          <button type="button" disabled={busy||jobCancelReason.trim().length<3} onClick={()=>void cancelJob()}>{t('Cancel lookup job')}</button>}</div>

    </div>}

  </section>;

}
