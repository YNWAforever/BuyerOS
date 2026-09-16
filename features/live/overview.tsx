'use client';
import {useEffect,useState} from 'react';
import type {Availability} from '@/services/live/mode';
import {loadLive} from '@/services/live/read';
import {toWorkspaces,MapError,type LiveWorkspace} from '@/services/live/mapping';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {LiveUnavailable} from './unavailable';

type PanelState =
  | {kind: 'loading'}
  | {kind: 'ready'; workspaces: LiveWorkspace[]}
  | {kind: 'unavailable'; state: Exclude<Availability, 'available'>; reason?: string};

export function LiveOverview() {
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
    return <section className="panel" role="status"><p>Loading live workspace…</p></section>;
  }
  if (state.kind === 'unavailable') {
    return <LiveUnavailable state={state.state} reason={state.reason}/>;
  }
  return (
    <section className="panel">
      <div className="section-heading"><h2>Live workspaces</h2></div>
      {state.workspaces.length
        ? state.workspaces.map((workspace) => (
            <div className="activity" key={workspace.id}>
              <div><b>{workspace.name}</b><p>{workspace.roles.join(' · ')}</p></div>
            </div>
          ))
        : <p className="muted">No workspaces in this account.</p>}
    </section>
  );
}
