import {useEffect,useRef,useState} from 'react';
import {reviewResearch,conversationLimits,type ResearchReview} from '@/services/live/conversation-research';
import {startRun,getRun,type Run} from '@/services/live/runs';
import {scopedThreadApi,type ServerThread} from '@/services/live/conversation-threads';
import {salesTasks} from '@/services/live/sales-tasks';
import type {SalesSchema as S} from '@/services/live/sales-transport';
import {salesError,type SalesProps} from './workspace';
type Pending={body:Parameters<typeof startRun>[1];run?:Run;revision:number;sources:S['SourceRef'][];key:string;arguments:S['TaskDetail']['arguments'];thread?:ServerThread;threadSaved?:boolean};
export function NativeResearch({client,session,t,navigate,task,guidance,onSaved}:{task:S['TaskDetail'];guidance:S['CoreGuidance'];onSaved:()=>void}&Omit<SalesProps,'locale'>){
 const api=salesTasks(client,session),key='native-run:'+task.id;
 const [review,setReview]=useState<ResearchReview|null>(null),[cost,setCost]=useState('0.500000'),[target,setTarget]=useState(10),[busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[pending,setPending]=useState<Pending|undefined>(api.recovery.get(key) as Pending|undefined);
 const active=useRef(true);useEffect(()=>()=>{active.current=false;},[]);
 const current=()=>active.current&&session.isCurrent(api.identity);
 const scope=session.current(),ctx={client,session,workspaceId:scope.workspace!,projectId:scope.project!,apiBaseUrl:''};
 async function perform(fn:()=>Promise<void>){if(busy)return;setBusy(true);setNotice('');try{await fn();}catch(e){if(current())setNotice(salesError(e));}finally{if(current())setBusy(false);}}
 async function confirm(){let attempt=pending;if(!attempt&&!review)return;if(!attempt){attempt={body:{icp_version_id:review!.profileId,target_companies:target,max_cost:{amount:Number(cost).toFixed(6),currency:'USD'},limits:{...conversationLimits}},revision:task.revision,sources:task.source_refs,key:guidance.action.idempotency_key,arguments:task.arguments};api.recovery.set(key,attempt);setPending(attempt);}if(!attempt.run){attempt.run=await startRun(ctx,attempt.body,attempt.key);api.recovery.set(key,attempt);}if(current())await attach(attempt);}
 async function attach(attempt:Pending){if(!attempt.run)return;const run=await getRun(ctx,attempt.run.id);if(!current())return;
 const threads=scopedThreadApi(client,session,api.identity);
 if(!attempt.threadSaved){attempt.thread??=await threads.get(task.thread_id);if(!current())return;
  if(!attempt.thread.runs?.some(r=>r.id===run.id))await threads.run(attempt.thread,{id:run.id,label:'Research run',status:run.status});
  attempt.threadSaved=true;api.recovery.set(key,attempt);
 }
 if(!current())return;
 if(!['completed','partial'].includes(run.status)){setNotice('Research run saved to discussion. Check run progress before selecting its evidence.');setPending({...attempt});onSaved();return;}
 const refs=[...attempt.sources.filter(r=>r.kind!=='run'),{id:run.id,version:run.version,kind:'run',locator:'run:'+run.id,retention_class:'durable'} as S['SourceRef']];await api.followup(task.id,{user_message:'Selected reviewed native research',arguments:attempt.arguments,source_refs:refs},attempt.revision);api.recovery.delete(key);if(!current())return;setPending(undefined);setNotice('Saved to discussion');onSaved();}
 return <section><h3>{t('Research runs')}</h3>{notice&&<p role="alert">{t(notice)}</p>}<button disabled={busy||!!pending} onClick={()=>void perform(async()=>{setReview(await reviewResearch(client,session,true,session.controller().signal));})}>{t('Review research cost')}</button>
 {pending&&!review&&<button disabled={busy} onClick={()=>void perform(confirm)}>{t('Retry same research request')}</button>}
 {review&&<><p>{t('Approved profile')} #{review.profileNumber} · {t('Budget remaining')} USD {review.remaining}</p><label>{t('Maximum cost (USD)')}<input disabled={!!pending} type="number" min="0.000001" max={review.remaining} step="0.000001" value={cost} onChange={e=>setCost(e.target.value)}/></label><label>{t('Target companies')}<input disabled={!!pending} type="number" min={1} max={100} value={target} onChange={e=>setTarget(Number(e.target.value))}/></label><details><summary>{t('Limits')}</summary><dl>{Object.entries(conversationLimits).map(([k,v])=><div key={k}><dt>{t(k.replaceAll('_',' '))}</dt><dd>{v}</dd></div>)}</dl></details><button disabled={busy||!Number.isFinite(Number(cost))||Number(cost)<=0||Number(cost)>Number(review.remaining)||target<1||target>100||!Number.isInteger(target)} onClick={()=>void perform(confirm)}>{t(pending?'Retry same research request':'Confirm and start research')}</button></>}
 {pending?.run&&<><button disabled={busy} onClick={()=>void perform(()=>attach(pending))}>{t('Attach accepted run')}</button><button onClick={()=>navigate(`/app/discover/${pending.run!.id}`)}>{t('Open run')}</button></>}
 </section>;
}
