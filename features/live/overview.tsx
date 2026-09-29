'use client';
import {useEffect,useState} from 'react';
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
  const {client,session}=useWorkspaceSession(),scope=useSessionSnapshot().scope;
  const [failed,setFailed]=useState<number|null>(null),[error,setError]=useState('');
  const [asOf]=useState(()=>new Date().toISOString());
  useEffect(()=>{
    if(!scope.workspace||!scope.project)return;
    const own=new AbortController(),identity=session.identity(),token=session.token();if(!token)return;
    void client.request<{total:number}>({path:`/v1/workspaces/${encodeURIComponent(scope.workspace)}/jobs?status=failed&offset=0&limit=1`,
      token,scope:identity,signal:AbortSignal.any([own.signal,session.controller().signal])})
      .then(value=>{if(!own.signal.aborted&&session.isCurrent(identity))setFailed(value.total);})
      .catch(cause=>{if(!own.signal.aborted&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));});
    return()=>own.abort();
  },[client,session,scope.workspace,scope.project]);
  const cards:[string,string,string][]=[
    ['Awaiting review','/app/results?review=awaiting_review',''],
    ['Pending approvals','/app/operations',''],
    ['Unassigned buyers','/app/results?queue=unassigned',''],
    ['Failed jobs','/app/operations?job_status=failed',failed===null?'—':String(failed)],
    ['Unknown fit','/app/results?queue=unknown',''],
    ['Unknown provider acceptance','/app/operations',''],
  ];
  return <section className="panel" aria-label={t('Daily work queue')}><h2>{t('Daily work queue')}</h2>
    <p>{t('Project')}: <code>{scope.project}</code> · {t('As of')}: {asOf?new Date(asOf).toLocaleString(): '—'}</p>
    <div className="grid two-col">{cards.map(([label,path,count])=><div className="activity" key={label}>
      <div><b>{t(label)}</b>{count&&<p>{count}</p>}</div><button type="button" onClick={()=>onNavigate(path)}>{t('Open')}</button></div>)}</div>
    {error&&<p role="alert">{error}</p>}
  </section>;
}
