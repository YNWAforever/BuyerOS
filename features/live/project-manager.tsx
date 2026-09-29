'use client';
import {useEffect,useRef,useState} from 'react';
import type {components} from '@/services/generated/buyeros-api';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {ActionIntent} from '@/services/live/action-intent';
import {LiveCancelled,LiveError,describeLiveError} from '@/services/live/client';
import {archiveProject} from '@/services/live/writes';

type Project=components['schemas']['Project'];
export function LiveProjectManager({projectId,onArchived,t}: {projectId:string;onArchived:()=>void;t:(text:string)=>string}){
  const {session,client}=useWorkspaceSession();
  const [project,setProject]=useState<Project|null>(null);
  const [reason,setReason]=useState('');
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const busyRef=useRef(false);
  const action=useRef(new ActionIntent<void>());
  useEffect(()=>{
    let active=true;const own=new AbortController();
    const scope=session.current(),identity=session.identity();
    if(!scope.workspace||scope.project!==projectId)return()=>{active=false;own.abort();};
    const path=`/v1/workspaces/${encodeURIComponent(scope.workspace)}/projects/${encodeURIComponent(projectId)}`;
    void client.request<Project>({path,token:session.token(),scope:identity,
      signal:AbortSignal.any([own.signal,session.controller().signal])})
      .then(row=>{if(active&&session.isCurrent(identity))setProject(row);})
      .catch(cause=>{if(active&&!(cause instanceof LiveCancelled))setError(cause instanceof LiveError?describeLiveError(cause):'Could not load project');});
    return()=>{active=false;own.abort();};
  },[client,session,projectId]);
  async function archive(){
    if(!project||project.status!=='active'||busyRef.current)return;
    busyRef.current=true;setBusy(true);setError('');
    try{
      const scope=session.current();
      const fingerprint=JSON.stringify({actor:scope.actor,workspace:scope.workspace,project:project.id,version:project.version,reason:reason.trim()});
      await action.current.run(fingerprint,async idempotencyKey=>{
        await archiveProject({client,session,idempotencyKey,projectId:project.id,version:project.version,reason});
      });
      onArchived();
    }catch(cause){if(!(cause instanceof LiveCancelled))setError(cause instanceof LiveError?describeLiveError(cause):cause instanceof Error?cause.message:'Archive failed');}
    finally{busyRef.current=false;setBusy(false);}
  }
  return <section className="panel" aria-label={t('Project management')}>
    <h3>{t('Project management')}</h3>
    {project?<p>{project.name} · {t('Project version')} {project.version} · {t(project.status)}</p>:<p role="status">{t('Loading project...')}</p>}
    {project?.status==='active'&&<>
      <label>{t('Archive reason')}<textarea value={reason} onChange={e=>setReason(e.target.value)} maxLength={2000}/></label>
      <button type="button" disabled={busy||reason.trim().length<3} onClick={()=>void archive()}>{busy?t('Archiving...'):t('Archive project')}</button>
    </>}
    {error&&<p role="alert">{error}</p>}
  </section>;
}
