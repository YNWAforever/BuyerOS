'use client';
import {useEffect,useState} from 'react';
import {loadWorkQueue,workQueueLink,type WorkQueue,type WorkQueueItem} from '@/services/live/work-queue';
import type {Availability} from '@/services/live/mode';
import {loadLive} from '@/services/live/read';
import {toWorkspaces,MapError,type LiveWorkspace} from '@/services/live/mapping';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {LiveUnavailable} from './unavailable';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
import {useSessionSnapshot} from '@/features/providers/workspace-session';

type PanelState =
  | {kind: 'loading'}
  | {kind: 'ready'; workspaces: LiveWorkspace[]}
  | {kind: 'unavailable'; state: Exclude<Availability, 'available'>; reason?: string};

export function LiveOverview({t=(value:string)=>value}:{t?:(value:string)=>string}) {
  const {session, client} = useWorkspaceSession();
  const [state, setState] = useState<PanelState>({kind: 'loading'});

  useEffect(() => {
    let active = true;
    const own = new AbortController();
    void loadLive({client, session, section: 'overview', path: '/v1/workspaces', signal: own.signal})
      .then((result) => {
        // A stale or cancelled read is a silence, not a failure: never map it, never show an error.
        if (!active || result.discarded) return;
        if (result.availability !== 'available') {
          setState({kind: 'unavailable', state: result.availability, reason: result.error?.message});
          return;
        }
        try {
          setState({kind: 'ready', workspaces: toWorkspaces(result.value)});
        } catch (error) {
          // A payload that violates the contract is unavailable, never an empty list.
          setState({kind: 'unavailable', state: 'unavailable', reason: error instanceof MapError ? error.message : 'unexpected response'});
        }
      })
      .catch(() => {});
    return () => { active = false; own.abort(); };
  }, [client, session]);

  if (state.kind === 'loading') {
    return <section className="panel" role="status"><p>{t('Loading live workspace…')}</p></section>;
  }
  if (state.kind === 'unavailable') {
    return <LiveUnavailable state={state.state} reason={state.reason}/>;
  }
  return (
    <section className="panel">
      <div className="section-heading"><h2>{t('Live workspaces')}</h2></div>
      {state.workspaces.length
        ? state.workspaces.map((workspace) => (
            <div className="activity" key={workspace.id}>
              <div><b>{workspace.name}</b><p>{workspace.roles.join(' · ')}</p></div>
            </div>
          ))
        : <p className="muted">{t('No workspaces in this account.')}</p>}
    </section>
  );
}


/** Navigation cards use exactly the same server filters as Results and Operations. */
export function LiveWorkQueue({t,onNavigate}:{t:(value:string)=>string;onNavigate:(path:string)=>void}){
  const {client,session}=useWorkspaceSession(),snapshot=useSessionSnapshot(),scope=snapshot.scope;
  const [result,setResult]=useState<{identity:string;value?:WorkQueue;error?:string}>(),[reload,setReload]=useState(0);
  const current=result?.identity===snapshot.identity?result:undefined;
  useEffect(()=>{
    if(!scope.workspace||!scope.project||!session.token())return;
    const own=new AbortController(),identity=session.identity();setResult({identity});
    void loadWorkQueue(client,session,own.signal)
      .then(value=>{if(!own.signal.aborted&&session.isCurrent(identity))setResult({identity,value});})
      .catch(cause=>{if(!own.signal.aborted&&session.isCurrent(identity)&&!(cause instanceof LiveCancelled))setResult({identity,error:describeLiveError(cause)});});
    return()=>own.abort();
  },[client,session,scope.workspace,scope.project,snapshot.identity,reload]);
  const cards:[WorkQueueItem['kind'],string][]=[['awaiting_review','Awaiting review'],['pending_approval','Pending approvals'],['unassigned','Unassigned buyers'],['failed_job','Failed jobs'],['unknown_fit','Unknown fit'],['unknown_acceptance','Unknown provider acceptance']];
  return <section className="panel" aria-label={t('Daily work queue')} aria-busy={Boolean(scope.project&&!current?.value&&!current?.error)}><h2>{t('Daily work queue')}</h2>
    <p>{t('As of')}: {current?.value?<time dateTime={current.value.as_of}>{new Date(current.value.as_of).toLocaleString()}</time>:'—'}</p>
    <details><summary>{t('Technical details')}</summary><p>{t('Project')}: <code>{scope.project}</code></p></details>
    <div className="grid two-col">{cards.map(([kind,label])=>{
      const item=current?.value?.items.find(row=>row.kind===kind);
      return <div className="activity" key={kind} data-work-queue-kind={kind}><div><b>{t(label)}</b><p><output aria-label={t('Count')}>{item?.count??'—'}</output></p>
      {item&&<p>{Object.entries(item.filters).map(([filter,value])=>`${t(filter)}: ${t(value)}`).join(' · ')}</p>}</div>
      <button type="button" disabled={!item||!scope.workspace||!scope.project} onClick={()=>{if(item&&scope.workspace&&scope.project)onNavigate(workQueueLink(item,{workspaceId:scope.workspace,projectId:scope.project}));}}>{t('Open')}</button></div>;
    })}</div>
    {current?.error&&<p role="alert">{current.error}</p>}
    <button type="button" disabled={!scope.workspace||!scope.project} onClick={()=>setReload(value=>value+1)}>{t('Refresh work queue')}</button>
  </section>;
}
