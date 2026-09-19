'use client';
import {useCallback,useEffect,useState} from 'react';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {LiveCancelled} from '@/services/live/client';
import {toBuyerPage,type LiveBuyer,type LiveBuyerPage} from '@/services/live/mapping';
import {explicitSelection,snapshotSelection,type ReviewSelection} from '@/services/live/buyer-selection';
import {LiveBuyerDetail} from './buyer-detail';

const REVIEW_STATUSES=['accepted','rejected','needs_information'] as const;

export function LiveBuyers() {
  const {session,client}=useWorkspaceSession();
  const [page,setPage]=useState<LiveBuyerPage|null>(null);
  const [selected,setSelected]=useState<Record<string,number>>({});
  const [detail,setDetail]=useState<string|null>(null);
  const [status,setStatus]=useState<(typeof REVIEW_STATUSES)[number]>('accepted');
  const [reason,setReason]=useState('');
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [reload,setReload]=useState(0);
  const scope=session.current();
  const workspace=scope.workspace;
  const project=scope.project;

  useEffect(()=>{
    let active=true; const own=new AbortController();
    const current=session.current();
    if(!current.workspace||!current.project)return ()=>{active=false;own.abort();};
    const identity=session.identity();
    const signal=AbortSignal.any([session.controller().signal,own.signal]);
    void (async()=>{
      setError('');
      try{
        const snapshot=await client.request<{id:string}>({
          path:`/v1/workspaces/${current.workspace}/projects/${current.project}/buyer-snapshots`,
          method:'POST',scope:identity,token:session.token(),signal,
          body:{filters:{},sort:'name_asc',requested_limit:100},
          idempotencyKey:`snapshot-${Date.now()}-${Math.random().toString(36).slice(2)}`,
        });
        const loaded=toBuyerPage(await client.request<unknown>({
          path:`/v1/workspaces/${current.workspace}/projects/${current.project}/buyers?snapshot_id=${snapshot.id}&offset=0&limit=50`,
          token:session.token(),scope:identity,signal,
        }));
        if(!active||!session.isCurrent(identity))return;
        setPage(loaded); setSelected({});
      }catch(err){
        if(!active||err instanceof LiveCancelled)return;
        const failure=err as {code?:string;message?:string};
        setError(failure.code||failure.message||'Failed to load buyers');
      }
    })();
    return ()=>{active=false;own.abort();};
  },[client,session,reload]);

  const toggle=useCallback((buyer:LiveBuyer)=>{
    setSelected((prev)=>{
      const next={...prev};
      if(next[buyer.id]!==undefined)delete next[buyer.id]; else next[buyer.id]=buyer.version;
      return next;
    });
  },[]);

  function selection():ReviewSelection|null{
    if(!page)return null;
    const ids=Object.keys(selected);
    if(!ids.length)return null;
    const allPage=page.items.every((buyer)=>selected[buyer.id]!==undefined)&&ids.length===page.items.length;
    if(allPage&&page.total>page.items.length){
      return snapshotSelection(page.snapshotId,[]);
    }
    return explicitSelection(ids.map((id)=>({id,version:selected[id]})));
  }

  async function submitReview(){
    const payload=selection();
    if(!payload||reason.trim().length<3){ setError('Select at least one buyer and give a reason.'); return; }
    setBusy(true); setError('');
    try{
      await client.request({
        path:`/v1/workspaces/${workspace}/projects/${project}/buyer-reviews`,method:'POST',
        scope:session.identity(),token:session.token(),
        idempotencyKey:`review-${Date.now()}-${Math.random().toString(36).slice(2)}`,
        body:{selection:payload,status,reason},
      });
      setSelected({}); setReason(''); setReload((value)=>value+1);
    }catch(err){
      if(!(err instanceof LiveCancelled)){
        const failure=err as {code?:string;message?:string};
        setError(failure.code||failure.message||'Review failed');
      }
    }finally{ setBusy(false); }
  }

  if(!workspace||!project)return <section className="panel" role="status"><p>No project selected. Save a profile to create one.</p></section>;
  if(error&&!page)return <section className="panel" role="alert"><p>{error}</p></section>;
  if(!page)return <section className="panel" role="status"><p>Loading buyers...</p></section>;
  return (
    <section className="panel">
      <div className="inline spread"><h2>Buyers</h2><span>{page.total} in this selection</span></div>
      {error?<p role="alert">{error}</p>:null}
      {page.items.length?page.items.map((buyer)=>(
        <div className="activity" key={buyer.id}>
          <input type="checkbox" aria-label={`Select ${buyer.name}`} checked={selected[buyer.id]!==undefined} onChange={()=>toggle(buyer)}/>
          <div><b>{buyer.name}</b><p>{buyer.fitVerdict||'no fit'} - {buyer.reviewStatus||'awaiting_review'} - {buyer.note||'no note'}</p></div>
          <button onClick={()=>setDetail(buyer.id)}>Details</button>
        </div>
      )):<p className="muted">No buyers in this snapshot.</p>}
      <div className="inline">
        <select aria-label="Review status" value={status} onChange={(event)=>setStatus(event.target.value as typeof status)}>
          {REVIEW_STATUSES.map((value)=><option key={value} value={value}>{value}</option>)}
        </select>
        <input aria-label="Review reason" value={reason} onChange={(event)=>setReason(event.target.value)} placeholder="Reason (required)"/>
        <button onClick={submitReview} disabled={busy}>{busy?'Reviewing...':'Apply review'}</button>
      </div>
      {detail?<LiveBuyerDetail buyerId={detail} onClose={()=>setDetail(null)}/>:null}
    </section>
  );
}
