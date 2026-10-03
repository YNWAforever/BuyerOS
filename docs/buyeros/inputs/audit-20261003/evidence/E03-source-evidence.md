# E03 Source evidence
Baseline: a78859fe474f5722be3755b10e2586436b53bf97. Public source; no environment values collected.
Each excerpt is frozen to this commit; current line numbers must be rechecked after changes.

## features/live/workspace-picker.tsx
SHA256: `e6475e8bf7162d010bcb6e83367007ddd3b84245baa7825639ed7ef18c33c103`
[GitHub permalink](https://github.com/YNWAforever/BuyerOS/blob/a78859fe474f5722be3755b10e2586436b53bf97/features/live/workspace-picker.tsx)
```text
65:   const [locale, setLocale] = useState<'en'|'zh-HK'>('en');
66:   const [prefVersion,setPrefVersion]=useState(1),[localeSaving,setLocaleSaving]=useState(false),[localeError,setLocaleError]=useState('');
67:   const [localeReadyFor,setLocaleReadyFor]=useState<string|null>(null);
68:   const t = (value:string) => locale === 'zh-HK' ? (liveZh[value] || zh[value] || value) : value;
69:   useEffect(() => {document.documentElement.lang=locale;},[locale]);
70:   const workspace = snapshot.scope.workspace, project = snapshot.scope.project;
71:   const authorized = workspaces.kind === 'ready' && workspaces.items.some(item => item.id === workspace);
72:   const localeReady = authorized && snapshot.authenticated && localeReadyFor === snapshot.identity;
```
```text
174:     router.push(target.pathname+target.search);
175:   }
176:   if (!auth) return <main className="main-shell"><section className="panel" role="status"><h1>Live sign-in unavailable</h1><p>{authError || 'Configure an Auth0 public SPA client, issuer, client ID and API audience.'}</p></section></main>;
177:   if (!snapshot.authenticated) return <main className="main-shell"><section className="panel"><h1>FIMMICK BuyerOS</h1><p>Sign in to access your workspaces.</p><button onClick={() => void auth.signIn(pathname + window.location.search)}>Sign in</button></section></main>;
178:   return <main className="main-shell live-workspace"><div className="content">
179:     <header className="topbar live-topbar"><b>FIMMICK BuyerOS</b><span>{t('Live workspace')}</span><label>{t('Language')} <select aria-label={t('Language')} value={locale} onChange={e=>void updateLocale(e.target.value as 'en'|'zh-HK')} disabled={localeSaving||!localeReady}><option value="en">English</option><option value="zh-HK">繁體中文</option></select></label><button onClick={() => {session.setToken(undefined); void auth.signOut();}}>{t('Sign out')}</button></header>
180:     <LiveNavigation t={t} navigate={navigate} authorized={authorized} projectKnown={projectKnown} canEdit={canEdit} projectActive={projectActive} canCreate={canCreate}/>
181:     <section className="panel" aria-label={t('Workspace selection')}><h2>{t('Workspaces')}</h2>
182:       {workspaces.kind === 'loading' && <p role="status">{t('Loading workspaces…')}</p>}
183:       {workspaces.kind === 'error' && <><p role="alert">{workspaces.message}</p><button onClick={()=>{setWorkspaces({kind:'loading'});setWorkspaceRefresh(value=>value+1);}}>{t('Retry loading workspaces')}</button></>}
184:       {workspaces.kind === 'ready' && (workspaces.items.length ? <label>{t('Workspace')} <select aria-label={t('Workspace')} value={workspace || ''} onChange={event=>chooseWorkspace(event.target.value)}><option value="">{t('Choose workspace')}</option>{workspaces.items.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label> : <p>{t('No workspace membership. Ask an administrator for access.')}</p>)}
185:       {authorized && <p>{t('Role')}: {workspaces.items.find(item=>item.id===workspace)?.roles.map(t).join(', ')}</p>}
186:     </section>
187:     {selectionError && <section className="panel" role="alert">{selectionError}</section>}
```
```text
190:       {projects.kind === 'loading' && <p role="status">{t('Loading projects…')}</p>}
191:       {projects.kind === 'error' && <><p role="alert">{projects.message}</p><button onClick={()=>{setProjects({kind:'loading'});setProjectRefresh(value=>value+1);}}>{t('Retry loading projects')}</button></>}
192:       {projects.kind === 'ready' && (projects.items.length ? <label>{t('Project')} <select aria-label={t('Project')} value={project || ''} onChange={event=>chooseProject(event.target.value)}><option value="">{t('Choose project')}</option>{projects.items.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label> : <p>{t('No projects yet.')}</p>)}
193:       {(canCreate||canEdit&&projectKnown&&projectActive) && <div className="inline">{canCreate&&<button onClick={()=>navigate('/app/discover/new')}>{t('New project')}</button>}{canEdit&&projectKnown&&projectActive&&<button onClick={()=>navigate('/app/discover/edit')}>{t('Edit offer')}</button>}</div>}
194:     </section>}
195:     {authorized && canCreate && pathname === '/app/discover/new' && <LiveOfferWizard key={`new-${workspace}`} mode="create" onSaved={saved} t={t}/>}
196:     {authorized && canEdit && projectKnown && projectActive && pathname === '/app/discover/edit' && <LiveOfferWizard key={`edit-${workspace}-${project}`} mode="edit" projectId={project!} onSaved={saved} t={t}/>}
197:     {authorized && projectKnown && pathname === '/app' && <><LiveOverview t={t}/><LiveWorkQueue key={`queue-${workspace}-${project}`} t={t} onNavigate={navigate}/><LiveUsage key={`usage-${workspace}-${project}`} locale={locale} t={t}/><LiveProfilePanel key={`${workspace}-${project}`} canApprove={canApprove&&projectActive} t={t}/>{canArchive&&<LiveProjectManager key={`manager-${workspace}-${project}`} projectId={project!} t={t} onArchived={()=>{session.next({project:null});updateUrl(router,{project:null,profile:null});setProjects({kind:'loading'});setProjectRefresh(value=>value+1);}}/>}</>}
198:     {authorized && projectKnown && pathname === '/app/results' && <LiveResults key={`results-${workspace}-${project}`} locale={locale} canReview={canApprove} canEdit={canEdit} canQuote={canEdit} canAssign={canCreate} ownMembershipId={workspaces.kind==='ready'?workspaces.items.find(item=>item.id===workspace)?.membershipId??null:null} t={t}/>}
199:     {authorized && projectKnown && pathname === '/app/discover' && <LiveBuyers locale={locale} canReview={canApprove} canEdit={canBuyerEdit} canQuote={canEdit} canAssign={canCreate} ownMembershipId={workspaces.kind==='ready'?workspaces.items.find(item=>item.id===workspace)?.membershipId:null}/>}
200:     {authorized && projectKnown && (pathname === '/app/runs' || /^\/app\/discover\/[^/]+$/.test(pathname) && !['new','edit'].includes(pathname.split('/')[3])) && <LiveRunProgress key={`runs-${workspace}-${project}-${pathname}`} runId={pathname.startsWith('/app/discover/')?pathname.split('/')[3]:undefined} canStart={canEdit&&projectActive} t={t} onOpenBuyers={()=>navigate('/app/discover')}/>}
201:     {authorized && projectKnown && pathname === '/app/outreach' && <LiveDraftEditor key={`drafts-${workspace}-${project}`} locale={locale} canGenerate={canEdit&&projectActive} canReviewSender={canApprove&&projectActive} canRequestReview={canBuyerEdit&&projectActive} canApprove={canApprove&&projectActive} canExport={canBuyerEdit&&projectActive}/>}
202:     {authorized && pathname === '/app/settings' && <><LiveSettings key={`settings-${workspace}`} workspace={workspace!} locale={locale} isAdmin={canArchive} canViewBudget={roles.some(role=>['operator','reviewer','workspace_admin'].includes(role))} onLocale={setLocale} onVersion={setPrefVersion} currentVersion={prefVersion} t={t}/><LivePolicySettings key={`policy-${workspace}`} roles={roles} t={t}/></>}
203:     {authorized && pathname === '/app/operations' && <LiveOperations key={`operations-${workspace}-${project}`} workspace={workspace!} project={projectKnown?project:null} isAdmin={canArchive} onOpenBuyers={()=>navigate('/app/discover')} t={t}/>}
204:     {authorized && !['/app','/app/discover','/app/discover/new','/app/discover/edit','/app/results','/app/runs','/app/outreach','/app/settings','/app/operations'].includes(pathname) && !/^\/app\/discover\/[^/]+$/.test(pathname) && <LiveUnavailable state="unavailable"/>}
205:   </div></main>;
206: }
```

## features/live/settings.tsx
SHA256: `7667bc5e5a2bef9f0a303da85997c2e4503382cb93059a8d8e56f634961e6365`
[GitHub permalink](https://github.com/YNWAforever/BuyerOS/blob/a78859fe474f5722be3755b10e2586436b53bf97/features/live/settings.tsx)
```text
23:       if(!session.isCurrent(identity)||own.signal.aborted)return;
24:       setPref(value);setMarkets(value.default_markets.join(', '));onLocale(value.locale);
25:     }).catch(e=>{if(!(e instanceof LiveCancelled)&&!own.signal.aborted)setError(describeLiveError(e));});
26:     if(isAdmin)void client.request<Page<Membership>>({path:`/v1/workspaces/${workspace}/memberships?offset=0&limit=100`,token,scope:identity,signal}).then(value=>{
27:       if(session.isCurrent(identity)&&!own.signal.aborted)setMembers(value.items);
28:     }).catch(e=>{if(!(e instanceof LiveCancelled)&&!own.signal.aborted)setError(describeLiveError(e));});
29:     return()=>own.abort();
30:   },[client,session,workspace,isAdmin,onLocale,scope.identity]);
```
```text
57:     <label>{t('Default markets')} <input aria-label={t('Default markets')} value={markets} onChange={e=>setMarkets(e.target.value)} placeholder="HK, US"/></label>
58:     <button disabled={!pref||pending} onClick={()=>void saveMarkets()}>{t('Save preferences')}</button>
59:     <p className="muted">{t('Research provider')} · {t('Not connected')}</p>
60:     {canViewBudget&&<BudgetSettings workspace={workspace} isAdmin={isAdmin} t={t}/>}
61:     {isAdmin&&<section aria-label={t('Member management')}><h3>{t('Member management')}</h3>
62:       <p>{t('Only existing verified members can be changed. The last administrator cannot be removed.')}</p>
63:       <label>{t('Change reason')} <input aria-label={t('Change reason')} value={reason} onChange={e=>setReason(e.target.value)}/></label>
64:       {members.map(member=><MemberRow key={`${member.id}-${member.version}`} member={member} pending={pending} t={t} onSave={changeMember}/>)}
65:     </section>}
66:     {error&&<p role="alert">{t(error)}</p>}{status&&<p role="status">{t(status)}</p>}
67:   </section>;
68: }
69: function MemberRow({member,pending,onSave,t}:{member:Membership;pending:boolean;onSave:(m:Membership,roles:string[],active:boolean)=>Promise<void>;t:(value:string)=>string}){
70:   const [selectedRoles,setSelectedRoles]=useState<string[]>(member.roles),[active,setActive]=useState(member.active);
71:   return <div className="inline" style={{flexWrap:'wrap'}}><code>{member.user_id.slice(-8)}</code>
72:     <fieldset aria-label={`${t('Roles')} ${member.user_id.slice(-8)}`}><legend>{t('Roles')}</legend>{roles.map(item=><label key={item}>{t(item)} <input type="checkbox" checked={selectedRoles.includes(item)} onChange={e=>setSelectedRoles(current=>e.target.checked?[...current,item]:current.filter(value=>value!==item))}/></label>)}</fieldset>
73:     <label>{t('Active')} <input type="checkbox" checked={active} onChange={e=>setActive(e.target.checked)}/></label>
74:     <button disabled={pending||selectedRoles.length===0||selectedRoles.length===member.roles.length&&selectedRoles.every(value=>member.roles.includes(value))&&active===member.active} onClick={()=>void onSave(member,selectedRoles,active)}>{t('Save member')}</button>
75:   </div>;
76: }
```

## features/live/operations.tsx
SHA256: `55ba1342550170770efd6c6f0e9606a8139b4d9d7107b473cbeb48333c51c971`
[GitHub permalink](https://github.com/YNWAforever/BuyerOS/blob/a78859fe474f5722be3755b10e2586436b53bf97/features/live/operations.tsx)
```text
1: 'use client';
2: import {useEffect,useState} from 'react';
3: import {useWorkspaceSession,useSessionSnapshot} from '@/features/providers/workspace-session';
4: import {LiveCancelled,describeLiveError} from '@/services/live/client';
5: 
6: type Capability={name:string;status:string;reason_codes:string[];checked_at:string;billable:boolean};
7: type Readiness={ready:boolean;database:string;queue:string;worker:string;checked_at:string};
8: type Audit={id:string;action:string;entity_type:string;entity_id?:string;occurred_at:string;reason_code?:string;request_id?:string};
9: type Page<T>={items:T[];offset:number;limit:number;total:number};
10: type Job={id:string;status:string;requested:number;processed:number;updated:number;blocked:number;conflicts:number;result_page?:Page<{buyer_id:string;status:string;reason_code?:string}>};
11: 
12: export function LiveOperations({workspace,project,isAdmin,onOpenBuyers,t}:{workspace:string;project:string|null;isAdmin:boolean;onOpenBuyers:()=>void;t:(value:string)=>string}){
```
```text
29:       if(session.isCurrent(identity)&&!own.signal.aborted)setReadiness(value);
30:     }).catch(e=>{if(!(e instanceof LiveCancelled)&&!own.signal.aborted)setError(describeLiveError(e));});
31:     return()=>own.abort();
32:   },[client,session,workspace,isAdmin,scope.identity]);
33:   useEffect(()=>{
34:     const own=new AbortController(),identity=session.identity(),token=session.token();if(!token)return;
35:     const query=new URLSearchParams({offset:String(jobOffset),limit:'20'});if(jobStatus)query.set('status',jobStatus);
36:     void client.request<Page<Job>>({path:`/v1/workspaces/${workspace}/jobs?${query}`,token,scope:identity,
37:       signal:AbortSignal.any([own.signal,session.controller().signal])}).then(value=>{
38:       if(session.isCurrent(identity)&&!own.signal.aborted)setJobs(value);
39:     }).catch(e=>{if(!(e instanceof LiveCancelled)&&!own.signal.aborted)setError(describeLiveError(e));});
40:     return()=>own.abort();
41:   },[client,session,workspace,jobOffset,jobStatus,scope.identity]);
42:   useEffect(()=>{
43:     const own=new AbortController(),identity=session.identity(),token=session.token();if(!token)return;
44:     const signal=AbortSignal.any([own.signal,session.controller().signal,AbortSignal.timeout(10_000)]);
45:     void client.request<Page<Job>>({path:`/v1/workspaces/${workspace}/jobs?status=failed&offset=0&limit=1`,token,scope:identity,signal}).then(value=>{
46:       if(session.isCurrent(identity)&&!own.signal.aborted)setFailedCount(value.total);
47:     }).catch(e=>{if(!(e instanceof LiveCancelled)&&!own.signal.aborted&&session.isCurrent(identity)){setFailedCount('unavailable');setError(describeLiveError(e));}});
48:     if(!project)return()=>own.abort();
49:     void (async()=>{
50:       const current=await client.request<{status:string;offer_revision:number}>({path:`/v1/workspaces/${workspace}/projects/${project}`,token,scope:identity,signal});
```
```text
77:       const value=await client.request<Job>({path:`/v1/workspaces/${workspace}/jobs/${requestedId}?offset=0&limit=20`,token,scope:identity,
78:         signal:session.controller().signal});
79:       if(session.isCurrent(identity))setJob(value);
80:     }catch(e){if(!(e instanceof LiveCancelled))setError(describeLiveError(e));}
81:   }
82:   return <section className="panel" aria-label={t('Operations')}><h2>{t('Operations')}</h2>
83:     <p>{t('Live domain state only. Provider readiness remains blocked until verified.')}</p>
84:     <div role="region" aria-label={t('Work queue')}><h3>{t('Work queue')}</h3>
85:       <p>{t('Profile approval')}: {profileQueue==='pending'?'1':profileQueue==='loading'?t('Loading…'):profileQueue==='stale'?t('Profile needs refresh'):profileQueue==='unavailable'?t('Unavailable'):'0'}</p>
86:       <p>{t('Failed jobs')}: {failedCount===null?t('Loading…'):failedCount==='unavailable'?t('Unavailable'):failedCount}</p>
87:       <p>{t('Buyer review')}: {t('Open the live buyer list for current review status.')}</p>
88:       <button disabled={!project} onClick={onOpenBuyers}>{t('Open buyer list')}</button>
89:     </div>
```
```text
```

## features/live/bulk-actions.tsx
SHA256: `7a55ba1d921151d42047293777aca0c4fd1d16a1f7286ab263360a93772b9b45`
[GitHub permalink](https://github.com/YNWAforever/BuyerOS/blob/a78859fe474f5722be3755b10e2586436b53bf97/features/live/bulk-actions.tsx)
```text
31: export function LiveBulkActions({selection,count,canAssign,ownMembershipId,onJob,onCommitted,locale='en'}:{
32:   selection:ReviewSelection|null;count:number;canAssign:boolean;ownMembershipId:string|null;
33:   onJob:(id:string)=>void;onCommitted:()=>void;locale?:Locale;
34: }){
35:   const {session,client}=useWorkspaceSession(),{scope}=useSessionSnapshot();
36:   const [reason,setReason]=useState(''),[confirm,setConfirm]=useState(false),[busy,setBusy]=useState(false);
37:   const [message,setMessage]=useState(''),[error,setError]=useState('');
38:   const intent=useRef(new ActionIntent<BulkOutcome>());
39:   if(!canAssign)return null;
40:   async function assign(){
41:     if(!selection||!scope.workspace||!scope.project||!confirm||busy||reason.trim().length<3)return;
42:     setBusy(true);setError('');setMessage('');
43:     try{
44:       const ctx=buyerOperationContext(session),body={selection,owner_membership_id:ownMembershipId,reason:reason.trim()};
45:       const result=await intent.current.run(JSON.stringify({ctx:ctx.identity,body}),key=>
46:         createOperationClient(client).requestOperation('assignBuyerOwners',{
47:           path:{workspace_id:scope.workspace!,project_id:scope.project!},header:{'Idempotency-Key':key},body,
48:         },ctx));
49:       if(isAsyncJob(result)){onJob(result.id);setMessage(locale==='zh-HK'?`已將 ${result.requested} 列加入工作，請在下方查看進度。`:`${result.requested} buyer rows queued. Open the job below for progress.`);}
50:       else{setMessage(locale==='zh-HK'?`${result.updated} 列已更新；${result.unchanged} 列不變；${result.blocked} 列受阻；${result.conflicts} 列衝突。`:`${result.updated} updated; ${result.unchanged} unchanged; ${result.blocked} blocked; ${result.conflicts} conflicts.`);
51:         if(result.updated)onCommitted();}
52:       setConfirm(false);
53:     }catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
54:     finally{setBusy(false);}
55:   }
56:   return <section className="panel bulk-action-panel" aria-label={copy('Assign buyer owners',locale)}>
57:     <h3>{copy('Assign buyer owners',locale)}</h3>
58:     <p>{locale==='zh-HK'?`預覽：已選 ${count} 位買家；提交前會重新檢查每列的版本和負責人資格。`:`Preview: ${count} selected buyer${count===1?'':'s'}; each current version and owner membership is checked again before commit.`}</p>
59:     <label className="bulk-action-field">{copy('Assignment reason',locale)} <input aria-label={copy('Assignment reason',locale)} value={reason} onChange={event=>setReason(event.target.value)}/></label>
60:     <div className="bulk-action-row"><label><input type="checkbox" aria-label={copy('Confirm owner assignment',locale)} checked={confirm} onChange={event=>setConfirm(event.target.checked)}/> {locale==='zh-HK'?`確認將已選買家${ownMembershipId?'分派給我':'設為沒有負責人'}`:`Confirm assignment ${ownMembershipId?'to me':'to no owner'} for this selection`}</label>
61:       <button type="button" disabled={!selection||count===0||!confirm||reason.trim().length<3||busy} onClick={()=>void assign()}>{copy(busy?'Assigning...':'Assign selected buyers',locale)}</button></div>
```
```text
73:   const reportIntent=useRef(new ActionIntent<ExportJob>());
74:   useEffect(()=>{
75:     if(!jobId||!scope.workspace)return;
76:     let active=true;
77:     void(async()=>{
78:       try{
79:         const ctx=buyerOperationContext(session),op=createOperationClient(client);
80:         const first=await op.requestOperation('getAsyncJob',{path:{workspace_id:scope.workspace!,job_id:jobId},query:{offset:0,limit:100}},ctx);
81:         const collected:Item[]=[...(first.result_page?.items??[])];
82:         const total=first.result_page?.total??0;
83:         for(let offset=collected.length;offset<total;){
84:           const page=await op.requestOperation('getAsyncJob',{path:{workspace_id:scope.workspace!,job_id:jobId},query:{offset,limit:100}},ctx);
85:           const rows=page.result_page?.items??[];
86:           if(!rows.length)throw new Error('Incomplete job result page');
87:           collected.push(...rows);offset+=rows.length;
88:         }
89:         if(active){setJob(first);setItems(collected);setError('');
90:           if(first.status==='completed'&&first.updated&&settled.current!==jobId){settled.current=jobId;onCommitted();}}
91:       }catch(cause){if(active&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
92:     })();
93:     return()=>{active=false;};
94:   },[client,session,scope.workspace,scope.project,jobId,tick,onCommitted]);
95:   const jobStatus=job?.status;
96:   useEffect(()=>{if(!jobStatus||!['queued','running','cancel_requested'].includes(jobStatus))return;
97:     const timer=window.setInterval(()=>setTick(value=>value+1),2000);return()=>window.clearInterval(timer);
98:   },[jobStatus]);
99:   const failures=items.filter(item=>item.status==='blocked'||item.status==='conflict');
```

## features/live/buyer-results.tsx
SHA256: `8736f8aa1894091896d8dc47a40f29214d0a4a18be2ae047af3dc2a18d97a424`
[GitHub permalink](https://github.com/YNWAforever/BuyerOS/blob/a78859fe474f5722be3755b10e2586436b53bf97/features/live/buyer-results.tsx)
```text
149:       <button type="button" onClick={()=>setReload(value=>value+1)}>{t('Refresh results')}</button>
150:     </div>
151:     {snapshot?.clipped&&<p role="status">{t('Showing the first 1000 matching buyers. Narrow filters to select all matching buyers.')}</p>}
152:     {error&&<p role="alert">{t(error)}</p>}{loading&&<p role="status">{t('Loading buyers...')}</p>}
153:     {page&&<>
154:       <div className="inline"><button type="button" disabled={!page.items.length} onClick={selectPage}>{t('Select this page')}</button>
155:         <button type="button" disabled={!snapshot||snapshot.clipped||!snapshot.total} onClick={()=>{setAllFiltered(true);setSelected({});setExcluded([]);}}>{t('Select all filtered')}</button>
156:         <button type="button" onClick={()=>{setAllFiltered(false);setSelected({});setExcluded([]);}}>{t('Clear selection')}</button>
157:         <span aria-live="polite">{t(allFiltered?'{count} selected across this snapshot':'{count} selected explicitly').replace('{count}',String(selectedCount))}</span>
158:       </div>
159:       {page.items.length?page.items.map(buyer=><div className="activity" key={buyer.id}>
160:         <input type="checkbox" aria-label={t('Select {buyer}').replace('{buyer}',buyer.name)} checked={allFiltered?!excluded.includes(buyer.id):buyer.id in selected} onChange={()=>toggle(buyer.id,buyer.version)}/>
161:         <div><b>{buyer.name}</b><p>{t(buyer.fitVerdict||'Fit not assessed')} · {t(buyer.reviewStatus||'Not reviewed')} · {buyer.note||t('No note')}</p></div>
162:         <button type="button" onClick={event=>{lastDetailTrigger.current=event.currentTarget;setDetailId(buyer.id);}}>{t('Details')}</button>
163:         {onManualOutcome&&<button type="button" onClick={()=>onManualOutcome(buyer.id)}>{t('Log outcome')}</button>}
164:       </div>):<p>{t('No buyers in this snapshot.')}</p>}
165:       <div className="inline spread"><div className="inline"><button type="button" disabled={query.offset===0||loading} onClick={()=>changeQuery({offset:Math.max(0,query.offset-query.size)})}>{t('Previous page')}</button>
166:         <span>{t('Rows {from}–{to} of {total}').replace('{from}',String(page.total?query.offset+1:0)).replace('{to}',String(Math.min(query.offset+page.items.length,page.total))).replace('{total}',String(page.total))}</span>
167:         <button type="button" disabled={loading||query.offset+page.items.length>=page.total} onClick={()=>changeQuery({offset:query.offset+query.size})}>{t('Next page')}</button></div>
168:         <label>{t('Rows per page')} <select aria-label={t('Rows per page')} value={query.size} onChange={event=>changeQuery({size:Number(event.target.value) as BuyerQuery['size'],offset:0})}><option value={8}>8</option><option value={12}>12</option><option value={24}>24</option></select></label>
169:       </div>
170:     </>}
171:     {canReview&&page&&<div className="inline"><label>{t('Review status')} <select aria-label={t('Review status')} value={status} onChange={event=>setStatus(event.target.value as typeof status)}>{reviewStatuses.map(value=><option key={value} value={value}>{t(value)}</option>)}</select></label>
172:       <label>{t('Review reason')} <input aria-label={t('Review reason')} value={reason} onChange={event=>setReason(event.target.value)}/></label>
173:       <button type="button" disabled={busy||selectedCount<=0} onClick={()=>void submitReview()}>{t(busy?'Reviewing...':'Apply review')}</button></div>}
174:     {reviewResult&&<p role="status">{t('Review: {updated} updated; {blocked} blocked; {conflicts} conflicts.').replace('{updated}',String(reviewResult.updated)).replace('{blocked}',String(reviewResult.blocked)).replace('{conflicts}',String(reviewResult.conflicts))} {reviewResult.results.filter(row=>row.status==='blocked'||row.status==='conflict').map(row=>`${row.id}: ${row.reason_code??row.status}`).join('; ')}</p>}
175:     {canEdit&&<ExportDialog key={`export:${workspace}:${project}`} locale={locale} selection={selection()} canExport={canEdit}/>}
176:     <LiveBulkActions key={`bulk:${workspace}:${project}`} locale={locale} selection={selection()} count={selectedCount} canAssign={canAssign} ownMembershipId={ownMembershipId} onJob={onJob} onCommitted={onCommitted}/>
177:     {jobId&&<BulkJobPanel locale={locale} jobId={jobId} onJob={onJob} onCommitted={onCommitted} onClose={closeJob}/>}
178:     <LiveBuyerManagementControls key={`management:${workspace}:${project}`} locale={locale} onJob={onJob} query={query} onApplyQuery={patch=>{setSelected({});setAllFiltered(false);setExcluded([]);changeQuery(patch,true);setReload(value=>value+1);}} selection={selection()} canManage={canEdit}/>
179:     {current&&<LiveBuyerDetail key={current.id} buyer={current} locale={locale} canEdit={canEdit} canQuote={canQuote} canReview={canReview} ownMembershipId={ownMembershipId}
180:       onReviewAndNext={(nextStatus,nextReason)=>reviewOneAndNext(current.id,current.version,nextStatus,nextReason)}
181:       onChanged={updated=>{setPage(previous=>previous?{...previous,items:previous.items.map(row=>row.id===updated.id?updated:row)}:previous);setSelected({});setAllFiltered(false);setExcluded([]);}}
```

## features/live/run-progress.tsx
SHA256: `94934ba71f502d8312bac293148e93e23ea9488136fbcd9a3a5311bdeff6152a`
[GitHub permalink](https://github.com/YNWAforever/BuyerOS/blob/a78859fe474f5722be3755b10e2586436b53bf97/features/live/run-progress.tsx)
```text
89:       setDetailError(t('Enter a target from 1 to 100 and a positive USD cap.'));return;
90:     }
91:     busyRef.current=true;setBusy(true);setDetailError('');
92:     try{
93:       const value=await startRun(ctx,{icp_version_id:profile,target_companies:targetCount,
94:         max_cost:{amount:`${amount.split('.')[0]}.${(amount.split('.')[1]??'').padEnd(6,'0')}`,currency:'USD'},limits:{...LIMITS}},crypto.randomUUID());
95:       if(current())router.push(`/app/discover/${encodeURIComponent(value.id)}?${new URLSearchParams({workspace:ctx.workspaceId,project:ctx.projectId})}`);
96:     }catch(error){if(current()&&!(error instanceof LiveCancelled))setDetailError(describeLiveError(error));}
97:     finally{busyRef.current=false;setBusy(false);}
98:   }
99:   async function act(kind:'cancel'|'retry'){
100:     if(!ctx||!run||busyRef.current||reason.trim().length<3)return;
101:     busyRef.current=true;setBusy(true);setDetailError('');
102:     try{const value=kind==='cancel'?await cancelRun(ctx,run,reason.trim(),crypto.randomUUID())
103:       :await retryRun(ctx,run,reason.trim(),crypto.randomUUID());
104:       if(current()){setRun(value);setReason('');}
105:     }catch(error){if(current()&&!(error instanceof LiveCancelled))setDetailError(describeLiveError(error));}
106:     finally{busyRef.current=false;setBusy(false);}
107:   }
108:   if(!ctx)return <section className="panel" role="status">{t('Choose a project to view runs.')}</section>;
```

## features/live/overview.tsx
SHA256: `1151863c0782058075200604ab135967fc7fb48406fc77f6755310beed70e00d`
[GitHub permalink](https://github.com/YNWAforever/BuyerOS/blob/a78859fe474f5722be3755b10e2586436b53bf97/features/live/overview.tsx)
```text
61: 
62: 
63: /** Navigation cards use exactly the same server filters as Results and Operations. */
64: export function LiveWorkQueue({t,onNavigate}:{t:(value:string)=>string;onNavigate:(path:string)=>void}){
65:   const {client,session}=useWorkspaceSession(),scope=useSessionSnapshot().scope;
66:   const [failed,setFailed]=useState<number|null>(null),[error,setError]=useState('');
67:   const [asOf]=useState(()=>new Date().toISOString());
68:   useEffect(()=>{
69:     if(!scope.workspace||!scope.project)return;
70:     const own=new AbortController(),identity=session.identity(),token=session.token();if(!token)return;
71:     void client.request<{total:number}>({path:`/v1/workspaces/${encodeURIComponent(scope.workspace)}/jobs?status=failed&offset=0&limit=1`,
72:       token,scope:identity,signal:AbortSignal.any([own.signal,session.controller().signal])})
73:       .then(value=>{if(!own.signal.aborted&&session.isCurrent(identity))setFailed(value.total);})
74:       .catch(cause=>{if(!own.signal.aborted&&!(cause instanceof LiveCancelled))setError(describeLiveError(cause));});
75:     return()=>own.abort();
76:   },[client,session,scope.workspace,scope.project]);
77:   const cards:[string,string,string][]=[
78:     ['Awaiting review','/app/results?review=awaiting_review',''],
79:     ['Pending approvals','/app/operations',''],
80:     ['Unassigned buyers','/app/results?queue=unassigned',''],
81:     ['Failed jobs','/app/operations?job_status=failed',failed===null?'—':String(failed)],
82:     ['Unknown fit','/app/results?queue=unknown',''],
83:     ['Unknown provider acceptance','/app/operations',''],
84:   ];
85:   return <section className="panel" aria-label={t('Daily work queue')}><h2>{t('Daily work queue')}</h2>
86:     <p>{t('Project')}: <code>{scope.project}</code> · {t('As of')}: {asOf?new Date(asOf).toLocaleString(): '—'}</p>
87:     <div className="grid two-col">{cards.map(([label,path,count])=><div className="activity" key={label}>
88:       <div><b>{t(label)}</b>{count&&<p>{count}</p>}</div><button type="button" onClick={()=>onNavigate(path)}>{t('Open')}</button></div>)}</div>
89:     {error&&<p role="alert">{error}</p>}
90:   </section>;
```

## features/live/drafts.tsx
SHA256: `d53c462b0d6fc73e859ce8ffbb713d0b184516d526ba0ac4eae4d69d6cddfb29`
[GitHub permalink](https://github.com/YNWAforever/BuyerOS/blob/a78859fe474f5722be3755b10e2586436b53bf97/features/live/drafts.tsx)
```text
153:     setError('');try{const opened=await getDraft(client,session,id);setDraft(opened);setSubject(opened.subject);
154:       setBody(opened.body);setDraftLanguage(opened.language==='zh-HK'?'zh-HK':'en');setApprovalConfirmed(false);setStaleDiff([]);replaceQuery({draft:id});}
155:     catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
156:   }
157:   async function prepareFollowUp(){
158:     if(!draft||busy)return;setBusy(true);setError('');
159:     try{const loaded=await loadDraftContext(client,session,draft.buyer_id);setContext(loaded);setRecipient('');
160:       setSelectedFacts((loaded.icp?.offer_facts||[]).filter(f=>f.approved).map(f=>f.id));
161:       setSelectedEvidence(loaded.evidence.filter(eligibleEvidence).map(e=>e.id));
162:       setDraftKind('follow_up');setParentDraftId(draft.id);replaceQuery({buyer:draft.buyer_id});
```
```text
174:   async function refreshCurrentDraft(){
175:     if(!draft||busy)return;
176:     setBusy(true);setError('');
177:     try{const latest=await getDraft(client,session,draft.id);setDraft(latest);
178:       setSubject(latest.subject);setBody(latest.body);setDraftLanguage(latest.language==='zh-HK'?'zh-HK':'en');
179:       setApprovalConfirmed(false);setStaleDiff([]);await refreshList(offset);
180:     }catch(cause){if(!(cause instanceof LiveCancelled))setError(describeLiveError(cause));}
181:     finally{setBusy(false);}
```
```text
246:       <p>{draftKind==='follow_up'?`${t('Follow-up')}: ${parentDraftId}`:t('Initial')}</p>
247:       <label>{t('Recipient (optional)')} <select value={recipient} onChange={event=>setRecipient(event.target.value)} disabled={busy||!canGenerate}>
248:         <option value="">{t('No recipient — unaddressed draft')}</option>
249:         {recipients.map(contact=><option key={contact.id} value={contact.id}>{contact.value} · v{contact.version}</option>)}
250:       </select></label>
251:       <div className="live-draft-fields"><label>{t('Objective')} <input value={objective} maxLength={1000} onChange={e=>setObjective(e.target.value)}/></label>
252:         <label>{t('Tone')} <select value={tone} onChange={e=>setTone(e.target.value as typeof tone)}><option value="professional">professional</option><option value="concise">concise</option><option value="warm">warm</option></select></label>
253:         <label>{t('Language')} <select value={draftLanguage} onChange={e=>setDraftLanguage(e.target.value as typeof draftLanguage)}><option value="en">English</option><option value="zh-HK">繁體中文</option></select></label></div>
254:       <button type="button" disabled={busy||!canGenerate||!project?.sender_identity||!context.icp||(recipient!==''&&!recipients.some(contact=>contact.id===recipient))||(draftKind==='follow_up'&&!parentDraftId)||selectedFacts.length===0||selectedEvidence.length===0||objective.trim().length<3} onClick={()=>void startDraft()}>{t(recipient?'Generate addressed draft':'Generate unaddressed draft')}</button>
255:     </section>}
256:     {job&&<section className="panel" role="status"><h3>{t('Job status')}</h3><p>{job.id} · {t(job.status)}</p><button type="button" disabled={busy} onClick={()=>void refreshJob()}>{t('Refresh job')}</button></section>}
```
```text
277:           <p>{draft.approval_review.sender.display_name} · {draft.approval_review.sender.organization} · {draft.approval_review.sender.business_email} · {draft.approval_review.sender.version_key}</p>
278:           <h5>{t('Claims and sources')}</h5>
279:           {draft.approval_review.evidence.map(item=><p key={item.id}>{item.id} · v{item.version} · {item.source_id}</p>)}
280:           <h5>{t('Policy conditions')}</h5><p>{draft.approval_review.policy_decision_ids.join(', ')}</p>
281:           <p>{draft.approval_review.icp_version_id} · {draft.approval_review.fit_id} · {draft.approval_review.review_id}</p>
282:           <p>{t('Review context')}: {draft.context_hash}</p>
283:         </>:<p>{t('An eligible addressed draft and current policy are required before review.')}</p>}
284:         {staleDiff.length>0&&<div role="alert"><p>{t('Context changed; compare and request a new review.')}</p><ul>{staleDiff.map((item,index)=><li key={index}>{item}</li>)}</ul></div>}
285:         <div className="inline"><button type="button" onClick={()=>void refreshCurrentDraft()} disabled={busy}>{t('Refresh draft')}</button>
286:           {canRequestReview&&draft.recipient_contact_id&&['draft','stale'].includes(draft.status)&&draft.claims.length>0&&
287:             <button type="button" onClick={()=>void requestReview()} disabled={busy||unsaved}>{t('Request exact review')}</button>}</div>
288:         {canApprove&&draft.status==='review_requested'&&draft.approval_review&&<>
289:           <label><input type="checkbox" checked={approvalConfirmed} onChange={event=>setApprovalConfirmed(event.target.checked)}/>
290:             {t('I confirm the exact recipient, sender, message and sources shown above.')}</label>
291:           <button type="button" onClick={()=>void approve()} disabled={busy||unsaved||!approvalConfirmed}>{t('Approve exact revision')}</button>
292:         </>}
293:       </section>
294:       {draft.status==='approved'&&draft.approval_id&&<ExportDialog key={`draft-export:${draft.id}:${draft.version}`} locale={locale} draft={draft} canExport={canExport}/>}
295:     </section>}
296:   </section>;
```

## features/providers/workspace-session.tsx
SHA256: `5903b433afb767ff14f38107995871770fa1d877831dfe946861577440a041eb`
[GitHub permalink](https://github.com/YNWAforever/BuyerOS/blob/a78859fe474f5722be3755b10e2586436b53bf97/features/providers/workspace-session.tsx)
```text
14: export function WorkspaceSessionProvider({children, authConfig}: {children: ReactNode; authConfig?: AuthConfig | null}) {
15:   const {mode, apiBaseUrl} = useDataMode();
16:   const [base] = useState(() => ({session: new SessionScope({mode, actor: ''}), client: createLiveClient(fetch, apiBaseUrl)}));
17:   // The server and hydration pass agree on a null adapter; the browser then instantiates it.
18:   const browser = useSyncExternalStore(noBrowserChange, inBrowser, onServer);
19:   const issuer = authConfig?.issuer, clientId = authConfig?.clientId, audience = authConfig?.audience;
20:   const authState = useMemo((): Pick<SessionValue, 'auth' | 'authError'> => {
21:     if (!browser || mode !== 'live') return {auth: null, authError: null};
22:     if (!issuer || !clientId || !audience) return {auth: null, authError: null};
23:     try {return {auth: createAuthAdapter({issuer, clientId, audience}), authError: null};}
24:     catch {return {auth: null, authError: 'Public OIDC configuration is invalid'};}
25:   }, [browser, mode, issuer, clientId, audience]);
26:   useEffect(() => {
27:     const auth = authState.auth;
```

## app/auth/callback/page.tsx
SHA256: `edc46d340d66d12003264d2367f5c2f552db4df1d9f8c63144825bc85ae2064f`
[GitHub permalink](https://github.com/YNWAforever/BuyerOS/blob/a78859fe474f5722be3755b10e2586436b53bf97/app/auth/callback/page.tsx)
```text
1: 'use client';
2: import {useEffect, useRef, useState} from 'react';
3: import {useRouter} from 'next/navigation';
4: import {useWorkspaceSession} from '@/features/providers/workspace-session';
5: 
6: export default function AuthCallbackPage() {
7:   const {auth, session} = useWorkspaceSession();
8:   const router = useRouter();
9:   const [error, setError] = useState('');
10:   const completion = useRef<Promise<void> | null>(null);
11:   useEffect(() => {
12:     let active = true;
13:     if (!auth) return;
14:     // React may replay effects in development; one callback code can only be exchanged once.
15:     completion.current ??= auth.completeCallback();
16:     void completion.current.then(async () => {
17:       if (!active) return;
18:       const token = await auth.getAccessToken();
19:       if (!active) return;
20:       session.setToken(token);
21:       session.next({actor: auth.subject(), workspace: null, project: null});
22:       router.replace(auth.returnPath());
23:     }).catch(() => { if (active) { session.setToken(undefined); setError('Sign-in failed. Please start again.'); } });
24:     return () => { active = false; };
25:   }, [auth, router, session]);
26:   const message = auth ? error || 'Completing sign-in…' : 'Live sign-in is not configured';
27:   return <main className="main-shell"><section className="panel" role={error || !auth ? 'alert' : 'status'}>{message}</section></main>;
28: }
```

## app/layout.tsx
SHA256: `0388ed4fefabf38b35dce60e023cd46662a6da610b662dd174a6f4f41c097339`
[GitHub permalink](https://github.com/YNWAforever/BuyerOS/blob/a78859fe474f5722be3755b10e2586436b53bf97/app/layout.tsx)
```text
25:   const apiBaseUrl = process.env.BUYEROS_API_BASE_URL ?? '';
26:   // Use the tested resolver rather than re-deriving the rule inline.
27:   const mode = resolveMode(apiBaseUrl);
28:   return (
29:     <html lang="en">
30:       <body className="antialiased">
31:         <DataModeProvider mode={mode} apiBaseUrl={apiBaseUrl}>
32:           <WorkspaceSessionProvider authConfig={process.env.BUYEROS_AUTH0_ISSUER && process.env.BUYEROS_AUTH0_CLIENT_ID && process.env.BUYEROS_AUTH0_AUDIENCE ? {issuer: process.env.BUYEROS_AUTH0_ISSUER, clientId: process.env.BUYEROS_AUTH0_CLIENT_ID, audience: process.env.BUYEROS_AUTH0_AUDIENCE} : null}>
33:             <Workspace mode={mode} />{children}
34:           </WorkspaceSessionProvider>
35:         </DataModeProvider>
36:       </body>
37:     </html>
38:   );
```

## services/api/buyeros_api/services/bulk_service.py
SHA256: `742242ea8061e36472dd624f3782fb4472d705b45614716fbe2b37c73d41bc67`
[GitHub permalink](https://github.com/YNWAforever/BuyerOS/blob/a78859fe474f5722be3755b10e2586436b53bf97/services/api/buyeros_api/services/bulk_service.py)
```text
175:         raise ApiError(404, "NOT_FOUND", "bulk job not found")
176:     total = (await session.execute(select(func.count()).select_from(AsyncJobItem).where(
177:         AsyncJobItem.workspace_id == workspace_id, AsyncJobItem.job_id == job_id,
178:         AsyncJobItem.status != "pending"
179:     ))).scalar_one()
180:     rows = (await session.execute(select(AsyncJobItem).where(
181:         AsyncJobItem.workspace_id == workspace_id, AsyncJobItem.job_id == job_id,
182:         AsyncJobItem.status != "pending"
183:     ).order_by(AsyncJobItem.ordinal).offset(offset).limit(limit))).scalars().all()
184:     results = [{"id": str(item.buyer_id), "status": item.status,
185:                 **({"reason_code": item.reason_code} if item.reason_code else {}),
186:                 **({"version": item.resulting_version} if item.resulting_version else {})}
187:                for item in rows]
188:     return job_data(job, results=results, offset=offset, limit=limit, total=total)
189: 
```

## services/api/buyeros_api/services/draft_service.py
SHA256: `28a1a4ee8a143f860d38c049b17b09c858b77c252c0d90704c31efc03f56aaa9`
[GitHub permalink](https://github.com/YNWAforever/BuyerOS/blob/a78859fe474f5722be3755b10e2586436b53bf97/services/api/buyeros_api/services/draft_service.py)
```text
343:             if (row is None or row[0].version != ref["version"] or row[1] is None
344:                     or row[1].retention_until is None
345:                     or row[1].retention_until <= datetime.now(timezone.utc)):
346:                 raise ApiError(412, "EVIDENCE_STALE", "evidence is unavailable")
347:     for key, value in changes.items():
348:         content[key] = value
349:     # Human edits are retained but lose machine grounding until separately reviewed.
350:     content["claims"] = []
351:     content["grounding_status"] = "needs_review"
352:     context = {key: content.get(key) for key in (
353:         "recipient_contact_id", "sender_identity_version", "evidence_refs", "icp_version_id",
354:         "evidence_set_hash", "policy_decision_ids", "objective", "tone", "language",
355:         "value_proposition_fact_ids")}
356:     content["context_hash"] = _digest(context)
357:     revision = DraftRevision(workspace_id=workspace_id, draft_id=draft.id,
358:         revision_number=draft.current_revision + 1, content=content,
359:         content_hash=_digest(content),
360:         evidence_ids=[row["id"] for row in content.get("evidence_refs", [])],
361:         offer_fact_ids=content["value_proposition_fact_ids"])
362:     session.add(revision)
363:     draft.current_revision += 1
364:     draft.state_version += 1
365:     draft.state = "draft"
366:     draft.review_context_hash = None
367:     draft.review_revision_id = None
368:     draft.review_context = None
369:     await session.execute(update(Approval).where(
370:         Approval.workspace_id == workspace_id, Approval.draft_id == draft.id,
371:         Approval.invalidated_reason.is_(None),
372:     ).values(invalidated_reason="draft_edited", invalidated_at=datetime.now(timezone.utc)))
373:     await session.flush()
374:     await session.refresh(draft)
375:     await session.refresh(revision)
```

## services/api/buyeros_api/services/approval_service.py
SHA256: `ae542665fedd8a2d2940a0438680e7040db5fba4e42c5cdb8036b5daaf16e2aa`
[GitHub permalink](https://github.com/YNWAforever/BuyerOS/blob/a78859fe474f5722be3755b10e2586436b53bf97/services/api/buyeros_api/services/approval_service.py)
```text
120: 
121: async def current_approval_context(session, *, workspace_id, project, draft, revision):
122:     """Resolve all material inputs from current tenant data inside the locked transaction."""
123:     now = datetime.now(timezone.utc)
124:     content = revision.content
125:     if (content.get("grounding_status") != "grounded" or not content.get("subject", "").strip()
126:             or not content.get("body", "").strip() or not content.get("claims")):
127:         raise ApiError(412, "STALE_REVISION", "grounded nonempty draft required")
128:     if content.get("kind") not in {"initial", "follow_up"}:
129:         raise ApiError(412, "STALE_REVISION", "draft kind changed")
130:     try:
131:         recipient_id = uuid.UUID(str(content["recipient_contact_id"]))
132:         icp_id = uuid.UUID(str(content["icp_version_id"]))
133:     except (KeyError, TypeError, ValueError) as exc:
134:         raise ApiError(412, "STALE_REVISION", "addressed draft and current profile required") from exc
135:     buyer = (await session.execute(select(ProjectBuyer).where(
136:         ProjectBuyer.workspace_id == workspace_id, ProjectBuyer.project_id == project.id,
```

## services/api/buyeros_api/api/routes/workspaces.py
SHA256: `d612aca141ccf9092106e03aa99334094f4b28b05990b1d831a5c6567fe7f34b`
[GitHub permalink](https://github.com/YNWAforever/BuyerOS/blob/a78859fe474f5722be3755b10e2586436b53bf97/services/api/buyeros_api/api/routes/workspaces.py)
```text
20: 
21:     items: list[dict] = []
22:     async with get_engine().connect() as conn:
23:         # `users` is not RLS-protected: resolve the actor by immutable (issuer, subject).
24:         user_id = (
25:             await conn.execute(select(User.id).where(User.issuer == principal.issuer, User.subject == principal.subject))
26:         ).scalar_one_or_none()
27:         if user_id is not None:
28:             # `workspaces` is not RLS-protected either; enumerate candidates, then read the
29:             # membership only under that workspace's transaction-local tenant context.
30:             candidates = (await conn.execute(select(Workspace.id, Workspace.name).order_by(Workspace.id))).all()
31:             for workspace_id, name in candidates:
32:                 await conn.execute(
33:                     text("SELECT set_config('app.workspace_id', :ws, true)"), {"ws": str(workspace_id)}
34:                 )
35:                 membership = (
36:                     await conn.execute(
37:                         select(Membership.id, Membership.roles).where(
38:                             Membership.workspace_id == workspace_id,
39:                             Membership.user_id == user_id,
40:                             Membership.active.is_(True),
41:                         )
42:                     )
43:                 ).one_or_none()
44:                 if membership is not None:
45:                     items.append(
46:                         {
47:                             "id": str(workspace_id),
48:                             "name": name,
49:                             "membership_id": str(membership.id),
50:                             "roles": list(membership.roles),
51:                             "data_mode": "live",
52:                         }
53:                     )
54:     return envelope(
55:         {"items": items[offset : offset + limit], "offset": offset, "limit": limit, "total": len(items)}, request.state.request_id
56:     )
```

## services/api/buyeros_api/api/routes/jobs.py
SHA256: `d34cc540ae046eaed6f099c0dc62bb882ac4aa884d340ec20bd5aba4a6ff2994`
[GitHub permalink](https://github.com/YNWAforever/BuyerOS/blob/a78859fe474f5722be3755b10e2586436b53bf97/services/api/buyeros_api/api/routes/jobs.py)
```text
17: 
18: 
19: @router.get("/jobs")
20: async def list_async_jobs(
21:     workspace_id: uuid.UUID, request: Request,
22:     offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
23:     status: Literal["queued", "running", "cancel_requested", "cancelled", "completed", "failed"] | None = None,
24:     project_id: uuid.UUID | None = None,
25:     principal: Principal = Depends(get_principal),
26: ):
27:     async with tenant_scoped(workspace_id) as session:
28:         member = await load_membership(session, principal=principal, workspace_id=workspace_id)
29:         if not permission_for_roles(member["roles"], "listAsyncJobs"):
30:             raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
31:         conditions = [AsyncJob.workspace_id == workspace_id]
32:         if "workspace_admin" not in member["roles"]:
33:             conditions.append(AsyncJob.actor_user_id == member["user_id"])
34:         if status is not None:
35:             conditions.append(AsyncJob.status == status)
36:         if project_id is not None:
37:             conditions.append(AsyncJob.project_id == project_id)
38:         total = (await session.execute(select(func.count()).select_from(AsyncJob).where(*conditions))).scalar_one()
39:         rows = (await session.execute(select(AsyncJob).where(*conditions)
40:             .order_by(AsyncJob.created_at.desc(), AsyncJob.id.desc())
41:             .offset(offset).limit(limit))).scalars().all()
42:         data = {"items": [job_data(row) for row in rows], "offset": offset, "limit": limit, "total": total}
43:     return envelope(data, request.state.request_id)
44: 
45: 
46: @router.get("/jobs/{job_id}")
47: async def get_async_job(
48:     workspace_id: uuid.UUID, job_id: uuid.UUID, request: Request,
```

## services/api/buyeros_api/api/verifier.py
SHA256: `a47d8fdfc88f81d44e838fde481381321f3aab9de9c8737d24898da3017ae7b9`
[GitHub permalink](https://github.com/YNWAforever/BuyerOS/blob/a78859fe474f5722be3755b10e2586436b53bf97/services/api/buyeros_api/api/verifier.py)
```text
1: """RS256 token verification over a JWKS cache (P10).
2: 
3: Enforces the algorithm allow-list and key selection, then defers claim rules to
4: the pure `claims_to_principal` so claim logic stays in one tested place.
5: """
6: 
7: import httpx
8: import jwt
9: 
10: from .auth import AuthError, Principal, claims_to_principal, jwks_uri_for
11: from .jwks import JwksError, JwksKeyCache
12: 
13: ALLOWED_ALGORITHMS = ("RS256",)
14: 
15: 
16: async def fetch_jwks_document(jwks_uri: str) -> dict:
17:     async with httpx.AsyncClient(timeout=5.0) as client:
18:         response = await client.get(jwks_uri)
19:         response.raise_for_status()
20:         return response.json()
21: 
22: 
23: class TokenVerifier:
24:     def __init__(self, jwks_cache: JwksKeyCache, *, issuer: str, audience: str) -> None:
25:         self._jwks = jwks_cache
26:         self._issuer = issuer
27:         self._audience = audience
28: 
29:     async def verify(self, token: str) -> Principal:
30:         try:
31:             header = jwt.get_unverified_header(token)
32:         except jwt.PyJWTError as exc:
33:             raise AuthError("malformed token") from exc
34:         if header.get("alg") not in ALLOWED_ALGORITHMS:
35:             raise AuthError("unsupported algorithm")
36:         kid = header.get("kid")
37:         if not kid:
```

## services/api/buyeros_api/providers/base.py
SHA256: `6245feaaada4c893ac4f223d703e2868950b796ccec68c98647b0a58fd357224`
[GitHub permalink](https://github.com/YNWAforever/BuyerOS/blob/a78859fe474f5722be3755b10e2586436b53bf97/services/api/buyeros_api/providers/base.py)
```text
12: SubmissionState = Literal["accepted", "unknown", "rejected"]
13: StatusState = Literal["accepted", "pending", "unknown", "succeeded", "not_found", "failed"]
14: _QUANTUM = Decimal("0.000001")
15: # No real vendor has been selected and verified for this repository.
16: SELECTED_LIVE_PROVIDERS: frozenset[str] = frozenset()
17: 
18: 
19: @dataclass(frozen=True)
20: class Money:
```
```text
96: 
97: 
98: def activation_blockers(capability: ProviderCapability, *, market: str, language: str,
99:                         role: str, environment: str = "production") -> tuple[str, ...]:
100:     """Fail closed for evidence or safety gaps; each service is evaluated separately."""
101:     blockers: list[str] = []
102:     if environment != "test" and capability.provider not in SELECTED_LIVE_PROVIDERS:
103:         blockers.append("PROVIDER_UNSELECTED")
104:     if capability.provider == "fixture" and environment != "test":
105:         blockers.append("FIXTURE_IN_PRODUCTION")
```

## services/api/buyeros_api/api/routes/drafts.py
SHA256: `f9a777d9bf733560796b01105a6f4b66f3b4c8e5a72cb40180c8025a3dc19a67`
[GitHub permalink](https://github.com/YNWAforever/BuyerOS/blob/a78859fe474f5722be3755b10e2586436b53bf97/services/api/buyeros_api/api/routes/drafts.py)
```text
275: 
276: 
277: @router.post("/drafts/{draft_id}/deliver")
278: async def disabled_delivery_boundary(workspace_id: uuid.UUID, draft_id: uuid.UUID,
279:                                      principal: Principal = Depends(get_principal)) -> dict:
280:     # This endpoint must remain side-effect free even for an approved draft.
281:     raise ApiError(403, "DELIVERY_DISABLED", "delivery is disabled")
```

## services/api/buyeros_api/execution/handlers/draft_generate.py
SHA256: `fcdafe7d3f4d6384565a3b929a4f540104688403b5d416c8f81e1e9a9309e9d1`
[GitHub permalink](https://github.com/YNWAforever/BuyerOS/blob/a78859fe474f5722be3755b10e2586436b53bf97/services/api/buyeros_api/execution/handlers/draft_generate.py)
```text
27: def render_grounded_template(*, facts: list[dict], evidence: list[dict], objective: str,
28:                              tone: str, language: str, kind: str) -> dict:
29:     facts, evidence = _sources(facts, evidence)
30:     if tone not in {"professional", "concise", "warm"} or kind not in {"initial", "follow_up"}:
31:         raise ValueError("unsupported draft style")
32:     if language not in {"en", "zh-HK"}:
33:         raise ValueError("unsupported draft language")
34:     if not isinstance(objective, str) or not 3 <= len(objective) <= 1000:
35:         raise ValueError("invalid objective")
36:     claims = ([{"text": row["value"], "kind": "offer_fact", "offer_fact_ids": [str(row["id"])],
37:                 "evidence_ids": []} for row in facts]
38:               + [{"text": row["excerpt"], "kind": "observation", "offer_fact_ids": [],
39:                   "evidence_ids": [str(row["id"])]} for row in evidence])
40:     if language == "zh-HK":
41:         salutation = "你好，"
42:         offer_prefix = "我們提供："
43:         observation_prefix = "參考公開資料："
44:         close = "如果合適，歡迎安排交流。"
45:         subject_prefix = "業務簡介：" if kind == "initial" else "跟進："
46:     else:
47:         salutation = "Hello,"
48:         offer_prefix = "We offer: "
49:         observation_prefix = "Public source excerpt: "
50:         close = "Would a conversation be useful?"
51:         subject_prefix = "Introduction: " if kind == "initial" else "Follow-up: "
52:     body = "\n\n".join([
53:         salutation,
54:         *[offer_prefix + row["value"] + f" [offer_fact:{row['id']}]" for row in facts],
55:         *[observation_prefix + '"' + row["excerpt"] + '"' + f" [evidence:{row['id']}:v{row['version']}]"
56:           for row in evidence],
57:         close,
58:     ])
59:     if len(body) > 20000:
60:         raise ValueError("grounded draft exceeds body bound")
61:     return {"subject": subject_prefix + facts[0]["value"][:100], "body": body,
62:             "claims": claims, "recipient_contact_id": None, "route": ROUTE,
63:             "prompt_version": ROUTE, "objective": objective, "tone": tone,
64:             "language": language, "kind": kind}
65: 
66: 
```

## docs/buyeros/REMAINING_DEVELOPMENT_STATUS.md
SHA256: `cbf84ac6a3eb348a1d6f5f19b5e811ad05c680564648c8007495dfda5c6be6cc`
[GitHub permalink](https://github.com/YNWAforever/BuyerOS/blob/a78859fe474f5722be3755b10e2586436b53bf97/docs/buyeros/REMAINING_DEVELOPMENT_STATUS.md)
```text
1: # BuyerOS execution status — 2026-10-01
2: 
3: This is the current execution ledger for the 2026-09-27 implementation pack. The older `PROGRESS.md` and `tasks/index.json` contain historical plan and BO approval records; their approval states are not changed here. At execution start the checked-out source was `f43a9d88b334c2c4029fa06fa71624ed52efe4a2` on `p14-buyer-lists`, with origin `https://github.com/YNWAforever/BuyerOS.git`. Current application/deployment and production configuration evidence is in the latest 2026-10-01 rollout checkpoint below; earlier entries retain their historical scope. The working tree was clean before T00. The audit baseline `5e61f401bf1bcdf80ea1ce254dd9c62e8eedbab0` was fetched for comparison; it is not an ancestor of this branch, so findings require current-source verification.
4: 
5: ## Current Cloudflare release candidate
6: 
7: Reviewed code/configuration `d6c2849d50b5851cd24bcab24ce0db4b73ecc3e8`;
8: temporary-preview preparation `07a7537befbf1e2290ee7079e18a258083615ed6`;
9: [complete current handoff](CLOUDFLARE_RELEASE_CANDIDATE_HANDOFF_20261001.md).
10: CF01–CF07 complete; CF00 local complete/hosted pending; CF08 local RC complete/
11: external activation pending. Code implemented and fictional fixture verified;
12: actual local Queue/Workflow/HMAC/native PostgreSQL integration verified.
13: Required API650/worker186, UI7 and retained legacy4/8/1/3/1/2 are zero-skip CF07
14: proof; CF08 controller27, Node19 and owned PG18 compatibility29 pass. No backend/
15: business/UI route changes after CF07; its UI suite was not rerun after the CF08
16: configuration/optional protection-header deltas; subsequent Linux CI8/8 at
17: d8ca315/test-merge8634fba reran the full7-case journey successfully. Both90-second budget mechanisms
18: are locally schema/build verified; hosted enforcement/native package/protection
19: is NOT RUN. No Cloudflare resource, production migration/provider call or
20: Cloudflare controller/schema/selector deployment occurred. Existing Git automation
21: published a READY branch app/API preview dpl_EPr4wsjaMNcgo3XA2itL1NxDGsc7 at d8ca315
22: (iad1/targetnull); no hosted job proof follows. Historical app deployment facts below retain
23: only their earlier scope; no migration deployed SHA exists.
24: 
25: Next eligible decision is the exact two-hour private protected-preview setup
26: in the handoff, including fresh empty Neon and dedicated Vercel project;
27: production cutover, all-day Neon quota/plan, providers/R2/policy/pilot and
28: independent/assistive review remain separate. Do not restart completed tasks.
29: 
30: ### Current CF00 preparation checkpoint
31: 
32: Prepared an overlay-only, default-off diagnostic and source/target renderer;
33: release API/gateway/selector/schema unchanged. Final committed-source focused
34: suite48 passed/0 failed/errors/skips in93.90s,46 retained deprecation warnings.
35: Actual loopback61-second wait/replay after app recreation, native PDF/8-second
36: kill, restricted worker and interrupted/resumed/cross-tenant checkpoint pass.
37: No test fixture points remotely; only its host guard is substituted locally.
38: Windows Linux caps and the positive deployed child/package/two-hop/protection
39: checks remain NOT RUN. Current runbook has exact inputs, guards and SHA.
40: 
```