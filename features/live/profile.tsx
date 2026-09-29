'use client';
import {useEffect,useRef,useState} from 'react';
import type {components} from '@/services/generated/buyeros-api';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {ActionIntent} from '@/services/live/action-intent';
import {LiveCancelled,LiveError,describeLiveError} from '@/services/live/client';
import {approveProfile} from '@/services/live/writes';

type Project=components['schemas']['Project'];
type ICP=components['schemas']['ICPVersion'];
type Ready={kind:'ready';project:Project;versions:ICP[]};
type State=Ready|{kind:'loading'}|{kind:'error';message:string};
function message(error:unknown):string{return error instanceof LiveError?describeLiveError(error):error instanceof Error?error.message:'Profile request failed';}
function exact<T>(items:T[],predicate:(item:T)=>boolean):T|null{return items.find(predicate)??null;}
function changeSummary(current:ICP,previous:ICP|null):string[]{
  if(!previous)return [];
  const changes:string[]=[];
  for(const key of ['offer_facts','requirements','markets','buyer_types','languages','desired_roles'] as const){
    if(JSON.stringify(current[key])!==JSON.stringify(previous[key]))changes.push(key.replaceAll('_',' '));
  }
  return changes;
}
export function LiveProfilePanel({canApprove=false,t=(text:string)=>text}: {canApprove?:boolean;t?:(text:string)=>string}) {
  const {session,client}=useWorkspaceSession();
  const [state,setState]=useState<State>({kind:'loading'});
  const [refresh,setRefresh]=useState(0);
  const [selectedId,setSelectedId]=useState<string|null>(null);
  const [confirmed,setConfirmed]=useState(false);
  const [busy,setBusy]=useState(false);
  const [actionError,setActionError]=useState('');
  const action=useRef(new ActionIntent<void>());
  const busyRef=useRef(false);
  useEffect(()=>{
    let active=true;
    const own=new AbortController();
    const scope=session.current(),identity=session.identity();
    if(!scope.workspace||!scope.project)return()=>{active=false;own.abort();};
    const signal=AbortSignal.any([own.signal,session.controller().signal]);
    const path=`/v1/workspaces/${encodeURIComponent(scope.workspace)}/projects/${encodeURIComponent(scope.project)}`;
    void (async()=>{
      try{
        const token=session.token();
        const project=await client.request<Project>({path,token,scope:identity,signal});
        const versions:ICP[]=[];
        for(let offset=0;;){
          const page=await client.request<{items:ICP[];offset:number;limit:number;total:number}>({
            path:`${path}/icp-versions?offset=${offset}&limit=100`,token,scope:identity,signal});
          if(page.offset!==offset||page.limit<1||!Array.isArray(page.items))throw new Error('Invalid profile history page');
          versions.push(...page.items);
          if(versions.length>=page.total)break;
          if(!page.items.length)throw new Error('Incomplete profile history');
          offset+=page.items.length;
        }
        if(!active||!session.isCurrent(identity))return;
        setState({kind:'ready',project,versions:versions.sort((a,b)=>b.number-a.number)});
        const requested=new URLSearchParams(window.location.search).get('profile');
        setSelectedId(requested??versions.reduce<ICP|null>((best,row)=>!best||row.number>best.number?row:best,null)?.id??null);
      }catch(error){if(!active||error instanceof LiveCancelled)return;setState({kind:'error',message:message(error)});}
    })();
    return()=>{active=false;own.abort();};
  },[client,session,refresh]);
  if(state.kind==='loading')return <section className="panel" role="status">{t('Loading profile...')}</section>;
  if(state.kind==='error')return <section className="panel" role="alert">{state.message}</section>;
  const {project,versions}=state;
  const missingSelection=Boolean(selectedId)&&!versions.some(row=>row.id===selectedId);
  const selected=missingSelection?null:exact(versions,row=>row.id===selectedId)??versions[0]??null;
  const previous=selected?exact(versions,row=>row.number===selected.number-1):null;
  const changes=selected?changeSummary(selected,previous):[];
  const canApproveSelected=canApprove&&selected?.status==='saved'&&selected.basis_status==='current'&&selected.project_id===project.id;
  async function approve(){
    if(!canApproveSelected||!selected||busyRef.current||!confirmed)return;
    busyRef.current=true;setBusy(true);setActionError('');
    try{
      const fingerprint=JSON.stringify({workspace:project.workspace_id,project:project.id,projectVersion:project.version,
        profile:selected.id,number:selected.number,hash:selected.content_hash});
      await action.current.run(fingerprint,async idempotencyKey=>{
        await approveProfile({client,session,idempotencyKey,project:{id:project.id,version:project.version},
          icpVersion:{id:selected.id,number:selected.number,content_hash:selected.content_hash}});
      });
      setConfirmed(false);setRefresh(value=>value+1);
    }catch(error){if(!(error instanceof LiveCancelled))setActionError(message(error));}
    finally{busyRef.current=false;setBusy(false);}
  }
  function choose(id:string){setSelectedId(id);setConfirmed(false);setActionError('');
    const url=new URL(window.location.href);url.searchParams.set('profile',id);
    window.history.replaceState(window.history.state,'',url.pathname+url.search+url.hash);
  }
  return <section className="panel" aria-label={t('Profile details')}>
    <h2>{t('Profile details')}</h2><p>{project.name} · {t('Project version')} {project.version}</p>
    <p>{t('Current approved')}: {project.active_icp_version_id?`v${versions.find(item=>item.id===project.active_icp_version_id)?.number??'?'}`:'—'}</p>
    <h3>{t('Profile history')}</h3>
    {versions.length===0?<p role="status">{t('No saved profile yet.')}</p>:<div className="inline" role="group" aria-label={t('Profile history')}>
      {versions.map(item=><button type="button" key={item.id} aria-pressed={selected?.id===item.id} onClick={()=>choose(item.id)}>
        v{item.number} · {t(item.status)}{item.id===project.active_icp_version_id?` · ${t('Current approved')}`:''}
      </button>)}
    </div>}
    {missingSelection&&<p role="alert">{t('Profile not found (404)')}</p>}
    {selected&&<article>
      <h3>{t('Profile version')} {selected.number} · {t(selected.status)}</h3>
      <h4>{t('Offer facts')}</h4><ul>{selected.offer_facts.map(fact=><li key={fact.id}>
        {t(fact.field)}: {fact.value} · {t(fact.provenance)}
        {fact.source_document_id&&<div>{t('Source document')}: {fact.source_document_id}</div>}
        {fact.excerpt&&<blockquote>{fact.excerpt}</blockquote>}
      </li>)}</ul>
      <p>{t('Sources')}: {selected.offer_document_ids?.join(', ')||'—'}</p>
      <h4>{t('Requirements')}</h4><ul>{selected.requirements.map(requirement=><li key={requirement.id}>{t(requirement.category)}: {requirement.text}</li>)}</ul>
      <p>{t('Markets')}: {selected.markets.join(', ')} · {t('Languages')}: {selected.languages.join(', ')}</p>
      <p>{t('Buyer type')}: {selected.buyer_types.join(', ')} · {t('Desired buyer roles (optional)')}: {selected.desired_roles?.join(', ')||'—'}</p>
      <h4>{t('Changes from previous version')}</h4><p>{previous?(changes.length?changes.map(t).join(', '):t('No content changes')):t('No previous version')}</p>
      {canApproveSelected&&<><label><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>{t('Confirm approval of this exact version')} v{selected.number}</label>
        <button type="button" disabled={!confirmed||busy} onClick={()=>void approve()}>{busy?t('Approving...'):t('Approve profile')}</button></>}
      {actionError&&<p role="alert">{actionError}</p>}
    </article>}
  </section>;
}
