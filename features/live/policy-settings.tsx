'use client';
import {useEffect, useRef, useState} from 'react';
import type {components} from '@/services/generated/buyeros-api';
import {useWorkspaceSession, useSessionSnapshot} from '@/features/providers/workspace-session';
import {LiveCancelled, describeLiveError} from '@/services/live/client';
import {createOperationClient} from '@/services/live/operations';
import {ActionIntent} from '@/services/live/action-intent';
import type {SessionScope} from '@/services/live/session';

type Policy = components['schemas']['PolicyDecision'];
type Suppression = components['schemas']['Suppression'];
type Purpose = Policy['purpose'];
const PURPOSES: Purpose[] = ['account_research','contact_research','draft_preparation','outreach','export_accounts','export_contacts'];
const SUPPRESSION_PURPOSES: Suppression['purposes'] = ['contact_research','draft_preparation','outreach','export_contacts'];

function policyContext(session:SessionScope){
  const captured=session.captureWriteContext();
  return {...captured,getToken:async()=>{const token=session.token();if(!token)throw new Error('Sign-in required');return token;},
    isCurrent:()=>session.isCurrent(captured.identity)};
}
export function LivePolicySettings({roles,t}:{roles:string[];t:(label:string)=>string}) {
  const {session,client}=useWorkspaceSession(),snapshot=useSessionSnapshot();
  const workspace=snapshot.scope.workspace,project=snapshot.scope.project;
  const canAdmin=roles.includes('workspace_admin');
  const canRead=canAdmin||roles.some(role=>role==='operator'||role==='reviewer');
  const [policies,setPolicies]=useState<Policy[]>([]),[suppressions,setSuppressions]=useState<Suppression[]>([]);
  const [loading,setLoading]=useState(true),[error,setError]=useState(''),[message,setMessage]=useState(''),[refresh,setRefresh]=useState(0);
  const [domain,setDomain]=useState(''),[reason,setReason]=useState('');
  const [purpose,setPurpose]=useState<Purpose>('contact_research'),[status,setStatus]=useState<'blocked'|'requires_review'>('blocked');
  const [policyVersion,setPolicyVersion]=useState(''),[basis,setBasis]=useState(''),[provenance,setProvenance]=useState(''),[country,setCountry]=useState('HK');
  const [retention,setRetention]=useState(30),[expiry,setExpiry]=useState('');
  const [busy,setBusy]=useState(false);
  const policyIntent=useRef(new ActionIntent<Policy>()),suppressionIntent=useRef(new ActionIntent<Suppression>());
  const removalIntent=useRef(new ActionIntent<Suppression>());
  useEffect(()=>{
    if(!workspace||!canRead)return;
    let active=true;
    void (async()=>{
      try{
        const op=createOperationClient(client),ctx=policyContext(session);
        const nextPolicies:Policy[]=[],nextSuppressions:Suppression[]=[];
        if(canAdmin)for(let offset=0;;){
          const page=await op.requestOperation('listPolicyDecisions',{path:{workspace_id:workspace},query:{offset,limit:100}},ctx);
          nextPolicies.push(...page.items);if(nextPolicies.length>=page.total)break;
          if(!page.items.length)throw new Error('Incomplete policy page');offset+=page.items.length;
        }
        for(let offset=0;;){
          const page=await op.requestOperation('listSuppressions',{path:{workspace_id:workspace},query:{offset,limit:100}},ctx);
          nextSuppressions.push(...page.items);if(nextSuppressions.length>=page.total)break;
          if(!page.items.length)throw new Error('Incomplete suppression page');offset+=page.items.length;
        }
        if(active){setPolicies(nextPolicies);setSuppressions(nextSuppressions);setLoading(false);setError('');}
      }catch(cause){if(active&&!(cause instanceof LiveCancelled)){setError(describeLiveError(cause));setLoading(false);}}
    })();
    return()=>{active=false;};
  },[workspace,project,client,session,canRead,canAdmin,refresh]);
  async function recordPolicy(){
    if(!canAdmin||!workspace||!project||!policyVersion.trim()||!basis.trim()||!provenance.trim()||!expiry||busy)return;
    const expiresAt=new Date(expiry);
    if(!Number.isFinite(expiresAt.getTime())||expiresAt<=new Date()){setError(t('Choose a future expiry.'));return;}
    setBusy(true);setError('');setMessage('');
    try{
      const ctx=policyContext(session),body={subject_type:'project' as const,subject_id:project,controller_scope_id:workspace,
        purpose,status,policy_version:policyVersion.trim(),basis_reference:basis.trim(),provenance:provenance.trim(),
        countries:[country.trim().toUpperCase()],expires_at:expiresAt.toISOString(),retention_days:retention};
      await policyIntent.current.run(JSON.stringify({ctx:ctx.identity,body}),key=>
        createOperationClient(client).requestOperation('recordPolicyDecision',{
          path:{workspace_id:workspace},header:{'Idempotency-Key':key},body},ctx));
      setMessage('Policy recorded. Restricted work remains blocked until a reviewed permit exists.');
      setRefresh(value=>value+1);
    }catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    finally{setBusy(false);}
  }
  async function addSuppression(){
    if(!canAdmin||!workspace||!domain.trim()||reason.trim().length<3||busy)return;
    setBusy(true);setError('');setMessage('');
    try{
      const ctx=policyContext(session),body={subject_type:'domain' as const,normalized_domain:domain.trim(),controller_scope_id:workspace,
        purposes:SUPPRESSION_PURPOSES,reason:reason.trim()};
      await suppressionIntent.current.run(JSON.stringify({ctx:ctx.identity,body}),key=>
        createOperationClient(client).requestOperation('createSuppression',{
          path:{workspace_id:workspace},header:{'Idempotency-Key':key},body},ctx));
      setDomain('');setReason('');setMessage('Suppression added. Existing approvals and contacts require new review.');
      setRefresh(value=>value+1);
    }catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    finally{setBusy(false);}
  }
  async function removeSuppression(item:Suppression){
    if(!canAdmin||!workspace||!item.active||reason.trim().length<3||busy)return;
    setBusy(true);setError('');setMessage('');
    try{
      const ctx=policyContext(session),body={reason:reason.trim()};
      await removalIntent.current.run(JSON.stringify({ctx:ctx.identity,id:item.id,version:item.version,body}),key=>
        createOperationClient(client).requestOperation('removeSuppression',{
          path:{workspace_id:workspace,suppression_id:item.id},
          header:{'Idempotency-Key':key,'If-Match':`"${item.version}"`},body},ctx));
      setMessage('Suppression removed. Prior approvals and quarantined contacts stay invalid.');
      setRefresh(value=>value+1);
    }catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
    finally{setBusy(false);}
  }
  return <section className="panel" aria-label={t('Policy and suppression')}>
    <h2>{t('Policy and suppression')}</h2>
    <p className="notice" role="status">{t('Research, contact lookup, draft approval and export require an approved purpose policy. Unknown or expired policy blocks action. Ask the data owner and qualified reviewer to approve controller scope, jurisdictions and retention.')}</p>
    {!canRead&&<p role="alert">{t('Your role cannot view policy records. Ask a workspace administrator.')}</p>}
    {loading&&canRead&&<p role="status">{t('Loading policy records…')}</p>}
    {error&&<p role="alert">{error}</p>}{message&&<p role="status">{t(message)}</p>}
    {canAdmin&&<div className="settings-grid">
      <div><h3>{t('Record restrictive project policy')}</h3>
        <p>{t('Permitted decisions cannot be activated here.')}</p>
        <label>{t('Purpose')} <select value={purpose} onChange={event=>setPurpose(event.target.value as Purpose)}>{PURPOSES.map(value=><option key={value} value={value}>{t(value)}</option>)}</select></label>
        <label>{t('Decision')} <select value={status} onChange={event=>setStatus(event.target.value as typeof status)}><option value="blocked">{t('blocked')}</option><option value="requires_review">{t('requires_review')}</option></select></label>
        <label>{t('Policy version')} <input value={policyVersion} onChange={event=>setPolicyVersion(event.target.value)} maxLength={64}/></label>
        <label>{t('Basis reference')} <input value={basis} onChange={event=>setBasis(event.target.value)} maxLength={1000}/></label>
        <label>{t('Provenance')} <input value={provenance} onChange={event=>setProvenance(event.target.value)} maxLength={1000}/></label>
        <label>{t('Country code')} <input value={country} onChange={event=>setCountry(event.target.value)} maxLength={2}/></label>
        <label>{t('Retention days')} <input type="number" min={1} max={3650} value={retention} onChange={event=>setRetention(Number(event.target.value))}/></label>
        <label>{t('Expiry')} <input type="datetime-local" value={expiry} onChange={event=>setExpiry(event.target.value)}/></label>
        <button disabled={busy||!project||!policyVersion.trim()||basis.trim().length<3||provenance.trim().length<3||!expiry||!/^[A-Z]{2}$/.test(country.toUpperCase())||retention<1||retention>3650} onClick={()=>void recordPolicy()}>{t('Record policy')}</button>
      </div>
      <div><h3>{t('Add domain suppression')}</h3>
        <p>{t('A suppression blocks contact research, drafts, outreach and contact export for the domain.')}</p>
        <label>{t('Domain')} <input value={domain} onChange={event=>setDomain(event.target.value)} placeholder="example.com"/></label>
        <label>{t('Reason')} <textarea value={reason} onChange={event=>setReason(event.target.value)}/></label>
        <button disabled={busy||!domain.trim()||reason.trim().length<3} onClick={()=>void addSuppression()}>{t('Add suppression')}</button>
      </div>
    </div>}
    {canRead&&<div className="settings-grid">
      {canAdmin&&<div><h3>{t('Policy history')} ({policies.length})</h3>
        {!loading&&policies.length===0&&<p>{t('No policy records. Restricted work is blocked.')}</p>}
        {policies.map(item=><p key={item.id}><strong>{t(item.status)}</strong> · {t(item.purpose)} · {item.subject_type} {item.subject_id} · {t('Expires')} {item.expires_at}</p>)}
      </div>}
      <div><h3>{t('Suppression history')} ({suppressions.length})</h3>
        {!loading&&suppressions.length===0&&<p>{t('No suppression records.')}</p>}
        {suppressions.map(item=><div key={item.id} className="suppression-row"><span><strong>{item.active?t('Active'):t('Removed')}</strong> · {item.normalized_domain||item.subject_id} · {item.purposes.map(t).join(', ')}</span>
          {canAdmin&&item.active&&<button disabled={busy||reason.trim().length<3} onClick={()=>void removeSuppression(item)}>{t('Remove with reason above')}</button>}</div>)}
      </div>
    </div>}
  </section>;
}
