'use client';
import {useEffect,useState} from 'react';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {LiveCancelled} from '@/services/live/client';
import {toEvidencePage,type LiveEvidence} from '@/services/live/mapping';

export function LiveBuyerDetail({buyerId,onClose}:{buyerId:string; onClose:()=>void}) {
  const {session,client}=useWorkspaceSession();
  const [evidence,setEvidence]=useState<LiveEvidence[]>([]);
  const [error,setError]=useState('');
  useEffect(()=>{
    let active=true; const own=new AbortController();
    const scope=session.current();
    if(!scope.workspace||!scope.project)return ()=>{active=false;own.abort();};
    const identity=session.identity();
    const signal=AbortSignal.any([session.controller().signal,own.signal]);
    const path=`/v1/workspaces/${scope.workspace}/buyers/${buyerId}/evidence`;
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
  },[client,session,buyerId]);
  return (
    <section className="panel" role="status">
      <div className="inline spread"><h3>Buyer evidence</h3><button onClick={onClose}>Close</button></div>
      {error?<p role="alert">{error}</p>:null}
      {evidence.length?evidence.map((row)=>(
        <div className="activity" key={row.id}>
          <div><b>{row.relationship}</b><p>{row.excerpt}</p></div>
        </div>
      )):<p className="muted">No evidence recorded.</p>}
    </section>
  );
}
