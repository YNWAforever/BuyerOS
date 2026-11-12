import {useEffect,useState} from 'react';
import type {SalesProps} from './workspace';
import {salesError} from './workspace';
import type {SalesSchema as S} from '@/services/live/sales-transport';
import {salesTasks,type SalesTasks} from '@/services/live/sales-tasks';
import {loadDiscussionContext,type ContextSection} from '@/services/live/discussion-context';
import {LiveCancelled} from '@/services/live/client';
export type SourceChoice={label?:string;labelKind?:string;kind:S['SourceRef']['kind'];ref:S['SourceRef']};
export function sourceChoiceLabel(choice:SourceChoice,t:(value:string)=>string){return choice.label??(choice.labelKind?`${t(choice.labelKind.replaceAll('_',' '))} · ${choice.ref.version}`:`${t(choice.kind)} · ${choice.ref.version}`);}
/** One source-picker read burst; every request shares the caller's abort lifetime. */
export async function loadSourceChoices(api:SalesTasks,context:(signal:AbortSignal)=>Promise<ContextSection[]>,signal:AbortSignal):Promise<SourceChoice[]>{
 const [sections,project,outputs,native]=await Promise.all([context(signal),
  api.getAbortable<{offer_revision:number}>('',signal),
  api.getAbortable<S['OutputCollectionPage']>('/sales-outputs?limit=50&offset=0',signal),
  api.nativeSources(signal)]);
 if(signal.aborted)throw new LiveCancelled('cancelled');
 const rows:SourceChoice[]=[...native.items.map(item=>({label:item.label,kind:item.ref.kind,ref:item.ref}))];
 for(const item of sections.flatMap(section=>section.items)){
  if(item.id.startsWith('fact:profile:')&&item.status==='approved')rows.push({label:item.title,kind:'project_fact',ref:{id:item.id.split(':').at(-1)!,kind:'project_fact',version:project.offer_revision,locator:item.id,retention_class:'durable'}});
  if(item.id.startsWith('document:')&&item.status==='ready')rows.push({label:item.title,kind:'document',ref:{id:item.id.slice(9),kind:'document',version:project.offer_revision,locator:item.id,retention_class:'durable'}});
 }
 for(const output of outputs.items??[])if(output.availability==='available')rows.push({labelKind:output.kind,kind:'output',ref:{id:output.id,version:output.revision,kind:'output',locator:`output:${output.id}`,retention_class:'durable'}});
 return rows;
}
export function SelectedSources({client,session,t,navigate,sources,setSources,disabled,onNativeSelect}:{sources:S['SourceRef'][];setSources:(v:S['SourceRef'][]) =>void;disabled:boolean;onNativeSelect?:(ref:S['SourceRef'])=>void}&Omit<SalesProps,'locale'>){
 const [choices,setChoices]=useState<SourceChoice[]>([]),[notice,setNotice]=useState('');
 // The read set is owned by the session identity, not by render identity: an unstable
 // translation function or parent rerender must never re-issue the parallel reads.
 const identity=session.identity();
 useEffect(()=>{
  const own=new AbortController();
  void loadSourceChoices(salesTasks(client,session),signal=>loadDiscussionContext(client,session,{enabled:true,canViewOffer:true,canViewResults:true,signal}),own.signal)
   .then(rows=>{if(!own.signal.aborted&&session.isCurrent(identity))setChoices(rows);})
   .catch(error=>{if(!own.signal.aborted&&session.isCurrent(identity)&&!(error instanceof LiveCancelled))setNotice(salesError(error));});
  return()=>own.abort();
 },[client,session,identity]);
 const all:SourceChoice[]=[...choices,...sources.filter(s=>!choices.some(c=>c.ref.id===s.id&&c.ref.version===s.version)).map(ref=>({kind:ref.kind,ref}))];
 return <details><summary>{t('Selected sources')} ({sources.length})</summary>{notice&&<p role="status">{t(notice)}</p>}{all.map(choice=><label key={choice.ref.id+choice.ref.version}><input type="checkbox" disabled={disabled} checked={sources.some(s=>s.id===choice.ref.id&&s.version===choice.ref.version)} onChange={e=>{setSources(e.target.checked?[...sources.filter(s=>s.kind!==choice.ref.kind||s.id!==choice.ref.id),choice.ref]:sources.filter(s=>s.id!==choice.ref.id||s.version!==choice.ref.version));if(e.target.checked)onNativeSelect?.(choice.ref);}}/>{sourceChoiceLabel(choice,t)}</label>)}<button type="button" onClick={()=>navigate('/app/discover/edit#offer-documents')}>{t('Attach documents')}</button></details>;
}
