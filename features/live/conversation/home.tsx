'use client';
import type {ReactNode} from 'react';
import {useEffect,useState,useSyncExternalStore} from 'react';
import {ArrowRight,Sparkles} from 'lucide-react';
import type {LiveClient} from '@/services/live/client';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
import type {SessionScope} from '@/services/live/session';
import {loadWorkQueue,workQueueLink,type WorkQueue,type WorkQueueItem} from '@/services/live/work-queue';
import {guidedTemplates} from '../conversation-home';
import type {ThreadListItem} from './thread-list';

type Props = {
  t: (value:string)=>string;
  projectName: string | null;
  threads: ThreadListItem[];
  client: LiveClient;
  session: SessionScope;
  /** The shared composer, rendered between the heading and the task cards. */
  composer: ReactNode;
  onTemplate: (template:typeof guidedTemplates[number])=>void;
  onOpen: (id:string)=>void;
  onNavigate: (path:string)=>void;
};

/** Provider-free attention rows: home owns its read so it still renders in fixture harnesses. */
function HomeAttention({t,client,session,onNavigate}:{t:(value:string)=>string;client:LiveClient;session:SessionScope;onNavigate:(path:string)=>void}){
  const snapshot=useSyncExternalStore(session.subscribe,session.getSnapshot,session.getSnapshot);
  const scope=snapshot.scope;
  const [result,setResult]=useState<{identity:string;value?:WorkQueue;error?:string}>();
  const current=result?.identity===snapshot.identity?result:undefined;
  useEffect(()=>{
    if(!scope.workspace||!scope.project||!session.token())return;
    const own=new AbortController(),identity=session.identity();
    void loadWorkQueue(client,session,own.signal)
      .then(value=>{if(!own.signal.aborted&&session.isCurrent(identity))setResult({identity,value});})
      .catch(cause=>{if(!own.signal.aborted&&session.isCurrent(identity)&&!(cause instanceof LiveCancelled))setResult({identity,error:describeLiveError(cause)});});
    return()=>own.abort();
  },[client,session,scope.workspace,scope.project,snapshot.identity]);
  const cards:[WorkQueueItem['kind'],string][]=[['awaiting_review','Awaiting review'],['pending_approval','Pending approvals'],['unassigned','Unassigned buyers'],['failed_job','Failed jobs']];
  const rows=cards.map(([kind,label])=>({kind,label,item:current?.value?.items.find(row=>row.kind===kind)}))
    .filter(row=>Boolean(row.item&&row.item.count>0)).slice(0,4);
  return <section className="conversation-attention" aria-label={t('Needs attention')} aria-busy={Boolean(scope.project&&!current?.value&&!current?.error)}>
    <div className="conversation-attention-head"><h3>{t('Needs attention')}</h3><button type="button" onClick={()=>onNavigate('/app/overview')}>{t('See all')}</button></div>
    {!current?.value&&!current?.error?<p className="conversation-attention-status" role="status">{t('Loading attention items…')}</p>:
      current.error?<p className="conversation-attention-status" role="alert">{current.error}</p>:
      rows.length?<ul className="conversation-attention-list">{rows.map(row=><li key={row.kind}><button type="button" onClick={()=>onNavigate(workQueueLink(row.item!,{workspaceId:scope.workspace!,projectId:scope.project!}))}><span>{t(row.label)}</span><b>{row.item!.count}</b></button></li>)}</ul>:
      <p className="conversation-attention-status">{t('Nothing needs attention right now.')}</p>}
  </section>;
}

/**
 * Project home: one question, one composer, six outcome cards, recent discussions
 * and the actionable rows from the work queue. No project selector panels.
 */
export function ProjectHome({t,projectName,threads,client,session,composer,onTemplate,onOpen,onNavigate}:Props){
  const recent=threads.filter(row=>!row.archived).slice(0,3);
  return <div className="conversation-home">
    <div className="conversation-home-intro">
      <p className="conversation-home-kicker">{projectName||t('This project')}</p>
      <h2>{t('What do you want to get done?')}</h2>
    </div>
    {composer}
    <section className="conversation-home-section" aria-labelledby="conversation-home-tasks">
      <h3 id="conversation-home-tasks">{t('Start with a task')}</h3>
      <div className="conversation-home-cards">
        {guidedTemplates.map(template=><button type="button" key={template.id} className="conversation-home-card" onClick={()=>onTemplate(template)}>
          <Sparkles size={17} aria-hidden="true"/>
          <span><b>{t(template.title)}</b><small>{t(template.prompt)}</small></span>
        </button>)}
      </div>
    </section>
    {recent.length>0&&<section className="conversation-home-section" aria-labelledby="conversation-home-recent">
      <h3 id="conversation-home-recent">{t('Continue where you left off')}</h3>
      <ul className="conversation-home-recent">{recent.map(row=><li key={row.id}>
        <button type="button" onClick={()=>onOpen(row.id)}><span>{row.title}</span><ArrowRight size={15} aria-hidden="true"/></button>
      </li>)}</ul>
    </section>}
    <HomeAttention t={t} client={client} session={session} onNavigate={onNavigate}/>
  </div>;
}
