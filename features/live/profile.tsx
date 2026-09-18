'use client';
import {useEffect,useState} from 'react';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {LiveCancelled} from '@/services/live/client';
import {toIcpVersions, MapError, type LiveIcpVersion} from '@/services/live/mapping';
import {approveProfile} from '@/services/live/writes';

interface ProjectView { id: string; name: string; version: number; active_icp_version_id: string | null; }

type PanelState =
  | {kind: 'empty'}
  | {kind: 'loading'}
  | {kind: 'ready'; project: ProjectView; icp: LiveIcpVersion | null}
  | {kind: 'error'; message: string};

function toProjectView(raw: unknown): ProjectView {
  if (typeof raw !== 'object' || raw === null) throw new MapError('unexpected project response');
  const row = raw as Record<string, unknown>;
  if (typeof row.id !== 'string' || !row.id) throw new MapError('missing required field: id');
  if (typeof row.name !== 'string' || !row.name) throw new MapError('missing required field: name');
  if (typeof row.version !== 'number') throw new MapError('missing required field: version');
  return {
    id: row.id,
    name: row.name,
    version: row.version,
    active_icp_version_id: typeof row.active_icp_version_id === 'string' ? row.active_icp_version_id : null,
  };
}

/** The active revision when the project names one, else the newest saved revision. */
function pickActive(activeId: string | null, versions: LiveIcpVersion[]): LiveIcpVersion | null {
  if (!versions.length) return null;
  if (activeId) {
    const active = versions.find((version) => version.id === activeId);
    if (active) return active;
  }
  return versions.reduce((best, version) => (version.number > best.number ? version : best), versions[0]);
}

function messageOf(err: unknown, fallback: string): string {
  const failure = err as {message?: string; code?: string};
  return failure.code || failure.message || fallback;
}

export function LiveProfile({project, icpVersion, onApprove, busy, error}: {
  project: {name: string; version: number; active_icp_version_id: string | null} | null;
  icpVersion: {id: string; number: number; status: string} | null;
  onApprove: () => void; busy: boolean; error?: string;
}) {
  if (!project) return <section className="panel" role="status"><p>No project yet. Save a profile to create one.</p></section>;
  return (
    <section className="panel" role="status">
      <h3>{project.name}</h3>
      <p>Project version {project.version}</p>
      {icpVersion ? <p>Profile v{icpVersion.number} - {icpVersion.status}</p> : <p>No saved profile yet.</p>}
      <button onClick={onApprove} disabled={busy || !icpVersion || icpVersion.status === 'approved'}>Approve profile</button>
      {error ? <p role="alert">{error}</p> : null}
    </section>
  );
}

export function LiveProfilePanel() {
  const {session, client} = useWorkspaceSession();
  const [state, setState] = useState<PanelState>(() => {
    const scope = session.current();
    return scope.workspace && scope.project ? {kind: 'loading'} : {kind: 'empty'};
  });
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState('');

  useEffect(() => {
    let active = true;
    const own = new AbortController();
    const scope = session.current();
    if (!scope.workspace || !scope.project) return () => { active = false; own.abort(); };
    const identity = session.identity();
    const signal = AbortSignal.any([session.controller().signal, own.signal]);
    const path = `/v1/workspaces/${scope.workspace}/projects/${scope.project}`;
    void (async () => {
      try {
        const project = toProjectView(await client.request<unknown>({path, token: session.token(), scope: identity, signal}));
        const icp = pickActive(project.active_icp_version_id, toIcpVersions(
          await client.request<unknown>({path: `${path}/icp-versions`, token: session.token(), scope: identity, signal}),
        ));
        if (!active || !session.isCurrent(identity)) return;
        setState({kind: 'ready', project, icp});
      } catch (err) {
        if (!active || err instanceof LiveCancelled) return;
        setState({kind: 'error', message: messageOf(err, 'Failed to load profile')});
      }
    })();
    return () => { active = false; own.abort(); };
  }, [client, session, refresh]);

  async function approve() {
    if (state.kind !== 'ready' || !state.icp) return;
    setBusy(true);
    setActionError('');
    try {
      const key = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      await approveProfile({
        client, session, idempotencyKey: key, project: {id: state.project.id},
        icpVersion: {id: state.icp.id, number: state.icp.number, content_hash: state.icp.contentHash},
      });
      setRefresh((value) => value + 1);
    } catch (err) {
      if (!(err instanceof LiveCancelled)) setActionError(messageOf(err, 'Approve failed'));
    } finally {
      setBusy(false);
    }
  }

  if (state.kind === 'loading') return <section className="panel" role="status"><p>Loading profile...</p></section>;
  if (state.kind === 'error') return <section className="panel" role="alert"><p>{state.message}</p></section>;
  if (state.kind === 'empty') return <LiveProfile project={null} icpVersion={null} onApprove={() => {}} busy={false}/>;
  return <LiveProfile project={state.project} icpVersion={state.icp} onApprove={approve} busy={busy} error={actionError || undefined}/>;
}
