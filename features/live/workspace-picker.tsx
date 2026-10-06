'use client';
import {useEffect, useRef, useState} from 'react';
import {usePathname, useRouter} from 'next/navigation';
import {useWorkspaceSession, useSessionSnapshot} from '@/features/providers/workspace-session';
import {toWorkspaces, toProjects, toIcpVersions, type LiveWorkspace, type LiveProject} from '@/services/live/mapping';
import {LiveCancelled, LiveError, describeLiveError, type LiveClient} from '@/services/live/client';
import {LiveProfilePanel} from './profile';
import {LiveUnavailable} from './unavailable';
import {LiveBuyers} from './buyers';
import {LiveOfferWizard} from './offer-wizard';
import {LiveProjectManager} from './project-manager';
import {LivePolicySettings} from './policy-settings';
import {LiveSettings} from './settings';
import {LiveOperations} from './operations';
import {LiveWorkQueue} from './overview';
import {LiveResults,LiveUsage} from './results';
import {LiveRunProgress} from './run-progress';
import {LiveDraftEditor} from './drafts';
import {LiveNavigation} from './navigation';
import {zh} from '@/locales';
import {liveZh} from './locale';
import type {SessionScope} from '@/services/live/session';

interface Page<T> {items: T[]; offset: number; limit: number; total: number;}
type LoadState<T> = {kind:'loading'} | {kind:'ready'; items:T[]} | {kind:'error'; message:string};
function page(raw: unknown): Page<unknown> {
  if (typeof raw !== 'object' || raw === null) throw new Error('Invalid page');
  const p = raw as Record<string, unknown>;
  if (!Array.isArray(p.items) || !Number.isSafeInteger(p.offset) || !Number.isSafeInteger(p.limit) || !Number.isSafeInteger(p.total) || (p.limit as number) < 1 || (p.total as number) < 0) throw new Error('Invalid page');
  return p as unknown as Page<unknown>;
}
async function allPages<T>(client: LiveClient, session: SessionScope, path: string, map: (data: unknown) => T[], signal: AbortSignal): Promise<T[]> {
  const identity = session.identity(), token = session.token();
  if (!token) throw new Error('Sign-in required');
  const items: T[] = [];
  for (let offset = 0; ; ) {
    const data = await client.request<unknown>({path:`${path}${path.includes('?')?'&':'?'}offset=${offset}&limit=100`, token, scope:identity, signal});
    if (!session.isCurrent(identity)) throw new LiveCancelled('scope changed');
    const current = page(data);
    if (current.offset !== offset || current.total < items.length || current.items.length > 100) throw new Error('Invalid pagination');
    items.push(...map(data));
    if (items.length >= current.total) return items;
    if (!current.items.length || current.items.length !== current.limit) throw new Error('Incomplete pagination');
    offset += current.items.length;
  }
}
function requested(key: string): string | null {return new URLSearchParams(window.location.search).get(key);}
function updateUrl(router: ReturnType<typeof useRouter>, changes: Record<string, string | null>) {
  const url = new URL(window.location.href);
  for (const [key,value] of Object.entries(changes)) if (value) url.searchParams.set(key,value); else url.searchParams.delete(key);
  // Scope selection is a same-document query change; write it synchronously so the
  // following project load cannot read a stale query during a workspace switch.
  void router;
  window.history.replaceState(window.history.state, '', url.pathname + url.search + url.hash);
}
export function LiveWorkspace() {
  const {session, client, auth, authError, authBootstrap} = useWorkspaceSession();
  const snapshot = useSessionSnapshot();
  const router = useRouter(), pathname = usePathname() || '/app';
  const [workspaces, setWorkspaces] = useState<LoadState<LiveWorkspace>>({kind:'loading'});
  const [projects, setProjects] = useState<LoadState<LiveProject>>({kind:'loading'});
  const [selectionError, setSelectionError] = useState('');
  const [workspaceRefresh,setWorkspaceRefresh]=useState(0);
  const [projectRefresh, setProjectRefresh] = useState(0);
  const [locale, setLocale] = useState<'en'|'zh-HK'>('en');
  const [prefVersion,setPrefVersion]=useState(1),[localeSaving,setLocaleSaving]=useState(false),[localeError,setLocaleError]=useState('');
  const [localeReadyFor,setLocaleReadyFor]=useState<string|null>(null);
  const manualLocale = useRef(false);
  useEffect(()=>{try {const saved=localStorage.getItem('buyeros.locale');if(saved==='en'||saved==='zh-HK'){manualLocale.current=true;queueMicrotask(()=>setLocale(saved));}}catch {/* Locale storage is optional. */}},[]);
  const t = (value:string) => locale === 'zh-HK' ? (liveZh[value] || zh[value] || value) : value;
  const localizeError=(message:string)=>{const [guidance,id]=message.split(' Request ID: ');return t(guidance)+(id?` ${t('Request ID')}: ${id}`:'');};
  useEffect(() => {document.documentElement.lang=locale;},[locale]);
  const workspace = snapshot.scope.workspace, project = snapshot.scope.project;
  const authorized = workspaces.kind === 'ready' && workspaces.items.some(item => item.id === workspace);
  const localeReady = authorized && snapshot.authenticated && localeReadyFor === snapshot.identity;
  const projectKnown = projects.kind === 'ready' && projects.items.some(item => item.id === project);
  const projectActive = projects.kind === 'ready' && projects.items.find(item=>item.id===project)?.status === 'active';
  const roles = workspaces.kind === 'ready' ? workspaces.items.find(item=>item.id===workspace)?.roles || [] : [];
  const canCreate = roles.some(role=>['operator','workspace_admin'].includes(role));
  const canEdit = roles.some(role=>['operator','workspace_admin'].includes(role));
  const canApprove = roles.some(role=>['reviewer','workspace_admin'].includes(role));
  const canBuyerEdit = roles.some(role=>['operator','reviewer','workspace_admin'].includes(role));
  const canArchive = roles.includes('workspace_admin');
  useEffect(()=>{
    if(!authorized||!workspace||!snapshot.authenticated)return;
    const own=new AbortController(),identity=session.identity(),token=session.token();if(!token)return;
    void client.request<{locale:'en'|'zh-HK';version:number}>({path:`/v1/workspaces/${workspace}/preferences`,token,scope:identity,
      signal:AbortSignal.any([own.signal,session.controller().signal])}).then(value=>{
      if(!own.signal.aborted&&session.isCurrent(identity)){if(!manualLocale.current)setLocale(value.locale);setPrefVersion(value.version);setLocaleReadyFor(identity);setLocaleError('');}
    }).catch(error=>{if(!own.signal.aborted&&session.isCurrent(identity)&&!(error instanceof LiveCancelled))setLocaleError(describeLiveError(error));});
    return()=>own.abort();
  },[authorized,workspace,snapshot.authenticated,snapshot.identity,client,session]);
  async function updateLocale(value:'en'|'zh-HK'){
    manualLocale.current=true;setLocale(value);
    try {localStorage.setItem('buyeros.locale',value);}catch {/* Display locale works without storage. */}
    if(!localeReady||!workspace||localeSaving)return;
    const identity=session.identity(),token=session.token();if(!token)return;
    setLocaleSaving(true);setLocaleError('');
    try{
      const updated=await client.request<{locale:'en'|'zh-HK';version:number}>({path:`/v1/workspaces/${workspace}/preferences`,
        method:'PATCH',token,scope:identity,body:{locale:value},ifMatch:`"${prefVersion}"`,idempotencyKey:crypto.randomUUID()});
      if(session.isCurrent(identity))setPrefVersion(updated.version);
    }catch(error){if(session.isCurrent(identity)&&!(error instanceof LiveCancelled))setLocaleError(describeLiveError(error));}
    finally{setLocaleSaving(false);}
  }
  function retryAccess(){setSelectionError('');setWorkspaces({kind:'loading'});setWorkspaceRefresh(value=>value+1);}
  const languagePicker=<label>{t('Language')} <select aria-label={t('Language')} value={locale} onChange={e=>void updateLocale(e.target.value as 'en'|'zh-HK')} disabled={localeSaving}><option value="en">English</option><option value="zh-HK">繁體中文</option></select></label>;
  function copyDiagnostics(){
    const message=workspaces.kind==='error'?workspaces.message:'';
    const requestId=message.match(/[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}/i)?.[0]??null;
    // Allow-listed support fields only: no token, OAuth code, email or user claims.
    void navigator.clipboard?.writeText(JSON.stringify({request_id:requestId,time:new Date().toISOString(),
      workspace_id:workspace,project_id:project,login_method:'auth0'},null,2));
  }
  useEffect(() => {
    if (!snapshot.authenticated) return;
    const own = new AbortController();
    const signal = AbortSignal.any([session.controller().signal, own.signal, AbortSignal.timeout(10_000)]);
    void allPages(client,session,'/v1/workspaces',toWorkspaces,signal).then(items => {
      if (own.signal.aborted) return;
      setWorkspaces({kind:'ready',items});
      const target = requested('workspace');
      if (target && !items.some(item => item.id === target)) {setSelectionError('Workspace not found (404)'); session.next({workspace:null,project:null}); return;}
      if (!target && items.length === 1) {session.next({workspace:items[0].id,project:null}); updateUrl(router,{workspace:items[0].id,project:null});}
      else if (target && session.current().workspace !== target) session.next({workspace:target,project:null});
    }).catch(error => {if (own.signal.aborted || error instanceof LiveCancelled) return; if (error instanceof LiveError && error.status === 401) {session.setToken(undefined);return;} setWorkspaces({kind:'error',message:describeLiveError(error)});});
    return () => own.abort();
  }, [client,router,session,snapshot.authenticated,snapshot.scope.actor,snapshot.identity,workspaceRefresh]);
  useEffect(()=>{
    if(!snapshot.authenticated||workspaces.kind!=='loading')return;
    const timer=setTimeout(()=>setWorkspaces(current=>current.kind==='loading'
      ?{kind:'error',message:'Request failed. Try again after checking the connection.'}:current),12_000);
    return()=>clearTimeout(timer);
  },[snapshot.authenticated,workspaces.kind,snapshot.identity,workspaceRefresh]);
  useEffect(() => {
    if (!snapshot.authenticated || !workspace || !authorized) return;
    const own = new AbortController();
    const signal = AbortSignal.any([session.controller().signal, own.signal, AbortSignal.timeout(10_000)]);
    void allPages(client,session,`/v1/workspaces/${encodeURIComponent(workspace)}/projects`,toProjects,signal).then(items => {
      if (own.signal.aborted) return;
      setProjects({kind:'ready',items});
      const target = requested('project');
      if (target && !items.some(item => item.id === target)) {setSelectionError('Project not found (404)'); session.next({project:null}); return;}
      if (target && session.current().project !== target) session.next({project:target});
      else if (!target && items.length === 1) {session.next({project:items[0].id}); updateUrl(router,{project:items[0].id});}
    }).catch(error => {if (own.signal.aborted || error instanceof LiveCancelled) return; if (error instanceof LiveError && error.status === 401) {session.setToken(undefined);return;} setProjects({kind:'error',message:describeLiveError(error)});});
    return () => own.abort();
  }, [authorized,client,router,session,snapshot.authenticated,workspace,projectRefresh,snapshot.identity]);
  useEffect(()=>{
    if(!authorized||projects.kind!=='loading')return;
    const timer=setTimeout(()=>setProjects(current=>current.kind==='loading'
      ?{kind:'error',message:'Request failed. Try again after checking the connection.'}:current),12_000);
    return()=>clearTimeout(timer);
  },[authorized,projects.kind,snapshot.identity,projectRefresh]);
  useEffect(() => {
    const profile = requested('profile');
    if (!profile || !projectKnown || !workspace || !project) return;
    const own = new AbortController();
    const signal = AbortSignal.any([session.controller().signal, own.signal]);
    void allPages(client,session,`/v1/workspaces/${encodeURIComponent(workspace)}/projects/${encodeURIComponent(project)}/icp-versions`,toIcpVersions,signal)
      .then(items => {if (!own.signal.aborted && !items.some(item=>item.id===profile)) setSelectionError('Profile not found (404)');})
      .catch(error => {if (!own.signal.aborted && !(error instanceof LiveCancelled)) setSelectionError('Could not verify profile');});
    return () => own.abort();
  }, [client,session,workspace,project,projectKnown]);
  function mayLeaveOffer(){return !document.querySelector('[data-live-unsaved="true"]') || window.confirm(t('Discard unsaved changes?'));}
  function chooseWorkspace(id:string) {
    if(!mayLeaveOffer())return;
    if (workspaces.kind !== 'ready' || !workspaces.items.some(item => item.id === id)) return;
    setSelectionError(''); setProjects({kind:'loading'});
    session.next({workspace:id,project:null}); updateUrl(router,{workspace:id,project:null,profile:null});
  }
  function chooseProject(id:string) {
    if(!mayLeaveOffer())return;
    if (projects.kind !== 'ready' || !projects.items.some(item => item.id === id)) return;
    setSelectionError(''); session.next({project:id}); updateUrl(router,{project:id,profile:null});
  }
  function saved(info:{projectId:string;icpVersionId:string}) {
    updateUrl(router,{workspace,project:info.projectId,profile:info.icpVersionId});
    session.next({project:info.projectId});
    setProjects({kind:'loading'});
    setProjectRefresh(value=>value+1);
    router.push(`/app?${new URLSearchParams({workspace:workspace!,project:info.projectId,profile:info.icpVersionId})}`);
  }
  function navigate(path:string) {
    if(!mayLeaveOffer())return;
    const params = new URLSearchParams(); if (workspace) params.set('workspace',workspace); if (project) params.set('project',project); if (project && requested('profile')) params.set('profile',requested('profile')!);
    const target=new URL(path,window.location.origin);for(const [key,value] of params)target.searchParams.set(key,value);
    router.push(target.pathname+target.search);
  }
  if (!auth) return <main className="main-shell">{languagePicker}<section className="panel" role={authBootstrap.kind==='configuration_error'?'alert':'status'}><h1>{t(authBootstrap.kind==='initializing'?'Initializing sign-in…':'Live sign-in unavailable')}</h1>{authBootstrap.kind==='configuration_error'&&<p>{authError}</p>}</section></main>;
  if (!snapshot.authenticated) return <main className="main-shell">{languagePicker}<section className="panel"><h1>FIMMICK BuyerOS</h1><p>{t('Sign in to access your workspaces.')}</p><button onClick={() => void auth.signIn(pathname + window.location.search)}>{t('Sign in')}</button></section></main>;
  return <main className="main-shell live-workspace"><div className="content">
    <header className="topbar live-topbar"><b>FIMMICK BuyerOS</b><span>{t('Live workspace')}</span>{languagePicker}<button onClick={() => {session.setToken(undefined); void auth.signOut();}}>{t('Sign out')}</button></header>
    <LiveNavigation t={t} navigate={navigate} authorized={authorized} projectKnown={projectKnown} canEdit={canEdit} projectActive={projectActive} canCreate={canCreate}/>
    <div className="live-scope-grid"><section className="panel" aria-label={t('Workspace selection')}><h2>{t('Workspaces')}</h2>
      {workspaces.kind === 'loading' && <p role="status">{t('Loading workspaces…')}</p>}
      {workspaces.kind === 'error' && <><p role="alert">{localizeError(workspaces.message)}</p><button onClick={retryAccess}>{t('Retry loading workspaces')}</button></>}
      {workspaces.kind === 'ready' && (workspaces.items.length ? <label>{t('Workspace')} <select aria-label={t('Workspace')} value={workspace || ''} onChange={event=>chooseWorkspace(event.target.value)}><option value="">{t('Choose workspace')}</option>{workspaces.items.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label> : <><p>{t('No workspace membership. Ask an administrator for access.')}</p><button onClick={retryAccess}>{t('Check access again')}</button></>)}
      {(workspaces.kind==='error'||workspaces.kind==='ready'&&!workspaces.items.length)&&<><p>{t('Contact your workspace administrator.')}</p><button onClick={copyDiagnostics}>{t('Copy diagnostics')}</button></>}
      {authorized && <p>{t('Role')}: {workspaces.items.find(item=>item.id===workspace)?.roles.map(t).join(', ')}</p>}
    </section>
    {authorized && <section className="panel" aria-label={t('Project selection')}><h2>{t('Projects')}</h2>
      {projects.kind === 'loading' && <p role="status">{t('Loading projects…')}</p>}
      {projects.kind === 'error' && <><p role="alert">{localizeError(projects.message)}</p><button onClick={()=>{setProjects({kind:'loading'});setProjectRefresh(value=>value+1);}}>{t('Retry loading projects')}</button></>}
      {projects.kind === 'ready' && (projects.items.length ? <label>{t('Project')} <select aria-label={t('Project')} value={project || ''} onChange={event=>chooseProject(event.target.value)}><option value="">{t('Choose project')}</option>{projects.items.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label> : <p>{t('No projects yet.')}</p>)}
      {(canCreate||canEdit&&projectKnown&&projectActive) && <div className="inline">{canCreate&&<button onClick={()=>navigate('/app/discover/new')}>{t('New project')}</button>}{canEdit&&projectKnown&&projectActive&&<button onClick={()=>navigate('/app/discover/edit')}>{t('Edit offer')}</button>}</div>}
    </section>}
    </div>
    {selectionError && <section className="panel" role="alert">{t(selectionError)}</section>}
    {localeError && <section className="panel" role="alert">{localizeError(localeError)}</section>}
    {authorized && canCreate && pathname === '/app/discover/new' && <LiveOfferWizard key={`new-${workspace}`} mode="create" onSaved={saved} t={t}/>}
    {authorized && canEdit && projectKnown && projectActive && pathname === '/app/discover/edit' && <LiveOfferWizard key={`edit-${workspace}-${project}`} mode="edit" projectId={project!} onSaved={saved} t={t}/>}
    {authorized && projectKnown && pathname === '/app' && <><LiveWorkQueue key={`queue-${workspace}-${project}`} t={t} onNavigate={navigate}/><LiveUsage key={`usage-${workspace}-${project}`} locale={locale} t={t}/><LiveProfilePanel key={`${workspace}-${project}`} canApprove={canApprove&&projectActive} t={t}/>{canArchive&&<LiveProjectManager key={`manager-${workspace}-${project}`} projectId={project!} t={t} onArchived={()=>{session.next({project:null});updateUrl(router,{project:null,profile:null});setProjects({kind:'loading'});setProjectRefresh(value=>value+1);}}/>}</>}
    {authorized && projectKnown && pathname === '/app/results' && <LiveResults key={`results-${workspace}-${project}`} locale={locale} canReview={canApprove} canEdit={canEdit} canQuote={canEdit} canAssign={canCreate} ownMembershipId={workspaces.kind==='ready'?workspaces.items.find(item=>item.id===workspace)?.membershipId??null:null} t={t}/>}
    {authorized && projectKnown && pathname === '/app/discover' && <LiveBuyers locale={locale} canReview={canApprove} canEdit={canBuyerEdit} canQuote={canEdit} canAssign={canCreate} ownMembershipId={workspaces.kind==='ready'?workspaces.items.find(item=>item.id===workspace)?.membershipId:null}/>}
    {authorized && projectKnown && (pathname === '/app/runs' || /^\/app\/discover\/[^/]+$/.test(pathname) && !['new','edit'].includes(pathname.split('/')[3])) && <LiveRunProgress key={`runs-${workspace}-${project}-${pathname}`} runId={pathname.startsWith('/app/discover/')?pathname.split('/')[3]:undefined} canStart={canEdit&&projectActive} t={t} onOpenBuyers={()=>navigate('/app/discover')}/>}
    {authorized && projectKnown && pathname === '/app/outreach' && <LiveDraftEditor key={`drafts-${workspace}-${project}`} locale={locale} canGenerate={canEdit&&projectActive} canReviewSender={canApprove&&projectActive} canRequestReview={canBuyerEdit&&projectActive} canApprove={canApprove&&projectActive} canExport={canBuyerEdit&&projectActive}/>}
    {authorized && pathname === '/app/settings' && <><LiveSettings key={`settings-${workspace}`} workspace={workspace!} locale={locale} isAdmin={canArchive} canViewBudget={roles.some(role=>['operator','reviewer','workspace_admin'].includes(role))} onLocale={setLocale} onVersion={setPrefVersion} currentVersion={prefVersion} t={t}/><LivePolicySettings key={`policy-${workspace}`} roles={roles} t={t}/></>}
    {authorized && pathname === '/app/operations' && <LiveOperations key={`operations-${workspace}-${project}`} workspace={workspace!} project={projectKnown?project:null} isAdmin={canArchive} onOpenBuyers={()=>navigate('/app/discover')} t={t}/>}
    {authorized && !['/app','/app/discover','/app/discover/new','/app/discover/edit','/app/results','/app/runs','/app/outreach','/app/settings','/app/operations'].includes(pathname) && !/^\/app\/discover\/[^/]+$/.test(pathname) && <LiveUnavailable state="unavailable"/>}
  </div></main>;
}
