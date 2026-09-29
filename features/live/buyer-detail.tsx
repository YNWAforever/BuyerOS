'use client';
import {useEffect,useState} from 'react';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {LiveCancelled} from '@/services/live/client';
import {toBuyers,toEvidencePage,type LiveBuyer,type LiveEvidence} from '@/services/live/mapping';

export function LiveBuyerDetail({buyer,onChanged,onClose}:{buyer:LiveBuyer; onChanged:(buyer:LiveBuyer)=>void; onClose:()=>void}) {
  const {session,client}=useWorkspaceSession();
  const [evidence,setEvidence]=useState<LiveEvidence[]>([]);
  const [note,setNote]=useState(buyer.note??'');
  const [error,setError]=useState('');
  const [saveError,setSaveError]=useState('');
  const [saving,setSaving]=useState(false);
  useEffect(()=>{
    let active=true; const own=new AbortController();
    const scope=session.current();
    if(!scope.workspace||!scope.project)return ()=>{active=false;own.abort();};
    const identity=session.identity();
    const signal=AbortSignal.any([session.controller().signal,own.signal]);
    const path=`/v1/workspaces/${scope.workspace}/buyers/${buyer.id}/evidence`;
    void (async()=>{
      try{
        const page=toEvidencePage(await client.request<unknown>({path,token:session.token(),scope:identity,signal}));
        if(!active||!session.isCurrent(identity))return;
        setEvidence(page.items);
      }catch(err){
        if(!active||err instanceof LiveCancelled)return;
        const failure=err as {code?:string;message?:string};
        setError(failure.code||failure.message||'Failed to load evidence');
      }
    })();
    return ()=>{active=false;own.abort();};
  },[client,session,buyer.id]);

  async function saveNote(){
    const scope=session.current();
    if(!scope.workspace)return;
    setSaving(true); setSaveError('');
    try{
      const updated=toBuyers({items:[await client.request<unknown>({
        path:`/v1/workspaces/${scope.workspace}/buyers/${buyer.id}`,method:'PATCH',
        scope:session.identity(),token:session.token(),
        idempotencyKey:`buyer-note-${Date.now()}-${Math.random().toString(36).slice(2)}`,
        ifMatch:`"${buyer.version}"`,body:{note},
      })]})[0];
      setNote(updated.note??'');
      onChanged(updated);
    }catch(err){
      if(!(err instanceof LiveCancelled)){
        const failure=err as {code?:string;message?:string};
        setSaveError(failure.code||failure.message||'Failed to save note');
      }
    }finally{ setSaving(false); }
  }

  return (
    <section className="panel" role="status">
      <div className="inline spread"><h3>Buyer evidence</h3><button onClick={onClose}>Close</button></div>
      {error?<p role="alert">{error}</p>:null}
      <div className="inline">
        <input aria-label="Buyer note" value={note} onChange={(event)=>setNote(event.target.value)} placeholder="Note"/>
        <button onClick={saveNote} disabled={saving}>{saving?'Saving...':'Save note'}</button>
      </div>
      {saveError?<p role="alert">{saveError}</p>:null}
      {evidence.length?evidence.map((row)=>(
        <div className="activity" key={row.id}>
          <div><b>{row.relationship}</b><p>{row.excerpt}</p></div>
        </div>
      )):<p className="muted">No evidence recorded.</p>}
    </section>
  );
}
