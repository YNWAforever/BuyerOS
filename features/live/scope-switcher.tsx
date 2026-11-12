'use client';
import type {LiveProject, LiveWorkspace} from '@/services/live/mapping';

export type LoadState<T> = {kind:'loading'} | {kind:'ready'; items:T[]} | {kind:'error'; message:string};

type Props = {
  t: (value:string)=>string;
  workspace: string | null;
  project: string | null;
  workspaces: LoadState<LiveWorkspace>;
  projects: LoadState<LiveProject>;
  authorized: boolean;
  canCreate: boolean;
  accessChecking: boolean;
  accessError: string;
  notice: string;
  onWorkspace: (id:string)=>void;
  onProject: (id:string)=>void;
  onNewProject: ()=>void;
  onCheckAccess: ()=>void;
};

/**
 * One-time project context in the sidebar. The same labelled comboboxes carry the
 * workspace and project selection; the repeated selector panels are gone.
 */
export function ScopeSwitcher({t,workspace,project,workspaces,projects,authorized,canCreate,accessChecking,accessError,notice,onWorkspace,onProject,onNewProject,onCheckAccess}:Props){
  return <div className="live-scope" role="group" aria-label={t('Project context')}>
    {workspaces.kind==='loading'&&<p className="live-scope-status" role="status">{t('Loading workspaces…')}</p>}
    {workspaces.kind==='error'&&<><p className="live-scope-alert" role="alert">{t(workspaces.message)}</p><button type="button" className="live-scope-action" onClick={onCheckAccess} disabled={accessChecking}>{t('Retry loading workspaces')}</button></>}
    {workspaces.kind==='ready'&&<>
      <label className="live-scope-field"><span>{t('Workspace')}</span>
        <select aria-label={t('Workspace')} value={workspace||''} onChange={event=>onWorkspace(event.target.value)}>
          {!workspace&&<option value="">{t('Choose workspace')}</option>}
          {workspaces.items.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}
        </select></label>
      {authorized&&<label className="live-scope-field"><span>{t('Project')}</span>
        <select aria-label={t('Project')} value={project||''} onChange={event=>onProject(event.target.value)} disabled={projects.kind!=='ready'}>
          {!project&&<option value="">{projects.kind==='loading'?t('Loading projects…'):t('Choose project')}</option>}
          {projects.kind==='ready'&&projects.items.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}
        </select></label>}
      {authorized&&<div className="live-scope-actions">
        {canCreate&&<button type="button" className="live-scope-action" onClick={onNewProject}>{t('New project')}</button>}
        <button type="button" className="live-scope-action" onClick={onCheckAccess} disabled={accessChecking}>{t(accessChecking?'Checking access…':'Check access')}</button>
      </div>}
    </>}
    {authorized&&projects.kind==='error'&&<p className="live-scope-alert" role="alert">{t(projects.message)}</p>}
    {(notice||accessError)&&<p className="live-scope-alert" role="alert">{t(notice||accessError)}</p>}
  </div>;
}
