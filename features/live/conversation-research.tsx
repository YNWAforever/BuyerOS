'use client';
import {useEffect,useRef,useState} from 'react';
import type {LiveClient} from '@/services/live/client';
import {LiveCancelled} from '@/services/live/client';
import type {SessionScope} from '@/services/live/session';
import {DiscussionStore,type LocalThread} from '@/services/live/discussions';
import {confirmResearch,reviewResearch,refreshResearch,conversationLimits,researchNotice,researchNotices,type ResearchReview,type RunReference} from '@/services/live/conversation-research';
import {hasUncertainResearch} from '@/services/live/runs';

const limitLabels:Record<string,string>={query_rounds:'Query rounds',max_queries_per_run:'Queries per run',max_results:'Maximum results',max_pages:'Maximum pages',max_page_bytes:'Bytes per page',max_duration_seconds:'Time limit (seconds)',max_model_tokens:'Model token limit',provider_concurrency:'Concurrent provider calls'};
function cost(value:string){if(!/^(?:0|[1-9]\d{0,13})(?:\.\d{1,6})?$/.test(value))return null;const [whole,fraction='']=value.split('.');return `${whole}.${fraction.padEnd(6,'0')}`;}
type Props={client:LiveClient;session:SessionScope;store:DiscussionStore;thread:LocalThread;t:(text:string)=>string;navigate:(path:string)=>void};
export function ConversationResearch({client,session,store,thread,t,navigate}:Props){
  const [review,setReview]=useState<ResearchReview|null>(null),[maxCost,setMaxCost]=useState('0.500000'),[target,setTarget]=useState(10);
  const [busy,setBusy]=useState(false),[notice,setNotice]=useState('');
  const mounted=useRef(true),pending=useRef(false),dialog=useRef<HTMLDialogElement>(null),proposal=useRef<HTMLButtonElement>(null);
  const identity=session.identity();
  const current=()=>mounted.current&&session.isCurrent(identity)&&!!session.token();
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
  useEffect(()=>{
    if(review){dialog.current?.showModal();dialog.current?.querySelector<HTMLButtonElement>('button')?.focus();}
  },[review]);
  async function propose(){
    if(pending.current||!current())return;
    pending.current=true;setBusy(true);setNotice('');
    try{const value=await reviewResearch(client,session,true,session.controller().signal);if(current())setReview(value);}
    catch(error){if(current()&&!(error instanceof LiveCancelled))setNotice(error instanceof Error&&error.message===researchNotices.context?error.message:researchNotice(error));}
    finally{pending.current=false;if(current())setBusy(false);}
  }
  function close(){if(pending.current)return;dialog.current?.close();setReview(null);proposal.current?.focus();}
  async function save(ref:RunReference){
    if(!current())return;
    let saved=false;
    await store.withLocalWrite(current,()=>{saved=store.saveRun(thread.id,ref);});
    if(current()&&!saved)setNotice('Research was accepted, but its reference could not be saved. Open Research runs.');
  }
  async function confirm(){
    if(!review||pending.current||!current())return;
    pending.current=true;setBusy(true);setNotice('');
    try{
      const run=await confirmResearch(client,session,{enabled:true,confirmed:true,review,maxCost:cost(maxCost)??maxCost,target});
      await save(run);if(current()){dialog.current?.close();setReview(null);proposal.current?.focus();}
    }catch(error){if(current()&&!(error instanceof LiveCancelled))setNotice(researchNotice(error));}
    finally{pending.current=false;if(current())setBusy(false);}
  }
  async function refresh(id:string){
    if(pending.current||!current())return;pending.current=true;setBusy(true);
    try{await save(await refreshResearch(client,session,true,id));}
    catch(error){if(current()&&!(error instanceof LiveCancelled))setNotice('Run status could not be refreshed. Open Research runs to check.');}
    finally{pending.current=false;if(current())setBusy(false);}
  }
  const normalizedCost=cost(maxCost);
  const uncertain=hasUncertainResearch({client,session,workspaceId:session.current().workspace!,projectId:session.current().project!,apiBaseUrl:''});
  return <section className="live-conversation-research" aria-label={t('Research from this discussion')}>
    <h2>{t('Research from this discussion')}</h2>
    <p>{t('Propose research, review the approved profile and budget, then confirm. Research never starts automatically.')}</p>
    <button type="button" ref={proposal} disabled={busy} onClick={()=>void propose()}>{t('Propose research')}</button>
    <div role="status" aria-live="polite">{notice&&t(notice)}</div>
    {thread.runs?.map(run=><article key={run.id}><b>{t(run.label)}</b> <span>{t(run.status)}</span><code>{run.id}</code>
      <button type="button" disabled={busy} onClick={()=>void refresh(run.id)}>{t('Refresh run status')}</button>
      <button type="button" onClick={()=>navigate(`/app/discover/${encodeURIComponent(run.id)}`)}>{t('Open run · results, timeouts, cancel & retry')}</button>
    </article>)}
    <dialog ref={dialog} className="live-research-confirm" aria-labelledby="conversation-research-title" onCancel={event=>{event.preventDefault();close();}}>
      <h2 id="conversation-research-title">{t('Confirm paid research')}</h2>
      {review&&<><p>{t('Approved profile')} #{review.profileNumber} <code>{review.profileId}</code></p>
        <p>{t('Budget remaining')} · USD {review.remaining}</p>
        <label>{t('Maximum cost (USD)')}<input inputMode="decimal" value={maxCost} disabled={busy||uncertain} onChange={event=>setMaxCost(event.target.value)} /></label>
        <label>{t('Target companies')}<input type="number" min={1} max={100} value={target} disabled={busy||uncertain} onChange={event=>setTarget(Number(event.target.value))}/></label>
        <dl>{Object.entries(conversationLimits).map(([key,value])=><div key={key}><dt>{t(limitLabels[key])}</dt><dd>{value}</dd></div>)}</dl>
        <p>{t('Current capability, provider, policy and budget gates are checked again when you confirm. A queued run is not completed research.')}</p>
        {uncertain&&<p>{t(researchNotices.unknown)}</p>}
        <div role="status">{notice&&t(notice)}</div>
        <button type="button" disabled={busy} onClick={close}>{t('Back to discussion')}</button>
        <button type="button" disabled={busy||!normalizedCost||Number(maxCost)<=0||Number(maxCost)>Number(review.remaining)||!Number.isInteger(target)||target<1||target>100} onClick={()=>void confirm()}>{t(uncertain?'Retry same research request':'Confirm and start research')}</button>
      </>}
    </dialog>
  </section>;
}
