'use client';
import {useEffect,useRef,useState} from 'react';
import {useWorkspaceSession,useSessionSnapshot} from '@/features/providers/workspace-session';
import {createOperationClient} from '@/services/live/operations';
import {leadContext} from '@/services/live/lead-context';
import {loadLeadCase} from '@/services/live/lead-workflow';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
import {toBuyerPage,type LiveBuyerPage} from '@/services/live/mapping';
import {leadText,type LeadLocale} from './copy';

/** Existing server snapshots provide bounded search; no lead/evidence directory scan. */
export function PreparationCompanyPicker({buyerId,onSelect,locale}:{buyerId:string;onSelect:(id:string)=>void;locale:LeadLocale}){
 const {client,session}=useWorkspaceSession(),scope=useSessionSnapshot(),t=(value:string)=>leadText(locale,value);
 const [search,setSearch]=useState(''),[query,setQuery]=useState(''),[offset,setOffset]=useState(0),[retry,setRetry]=useState(0);
 const [loaded,setLoaded]=useState<{key:string;page:LiveBuyerPage;clipped:boolean}|null>(null);
 const [failure,setFailure]=useState<{key:string;message:string}|null>(null);
 const [selected,setSelected]=useState<{id:string;name:string}|null>(null),[selectedError,setSelectedError]=useState('');
 const sequence=useRef(0),cached=useRef<{key:string;id:string;clipped:boolean}|null>(null);
 const readKey=JSON.stringify([scope.identity,query,offset,retry]),snapshotKey=JSON.stringify([scope.identity,query,retry]);
 const page=loaded?.key===readKey?loaded.page:null,error=failure?.key===readKey?failure.message:'';
 const loading=!page&&!error;
 useEffect(()=>{const timer=setTimeout(()=>{setQuery(search.trim());setOffset(0);},250);return()=>clearTimeout(timer);},[search]);
 useEffect(()=>{
   const own=new AbortController(),identity=session.identity(),serial=++sequence.current;
   const current=()=>!own.signal.aborted&&session.isCurrent(identity)&&serial===sequence.current;
   void (async()=>{
     const ctx=leadContext(session,own.signal),op=createOperationClient(client);
     let snapshot=cached.current?.key===snapshotKey?cached.current:null;
     if(!snapshot){
       const value=await op.requestOperation('createBuyerSnapshot',{path:{workspace_id:ctx.workspace,project_id:ctx.project},
         header:{'Idempotency-Key':crypto.randomUUID()},body:{filters:{...(query?{q:query}:{})},sort:'name_asc',requested_limit:1000}},ctx);
       if(!current())return;
       snapshot={key:snapshotKey,id:value.id,clipped:value.result_limit_reached};cached.current=snapshot;
     }
     const raw=await op.requestOperation('listBuyers',{path:{workspace_id:ctx.workspace,project_id:ctx.project},
       query:{snapshot_id:snapshot.id,offset,limit:24}},ctx);
     if(current()){setLoaded({key:readKey,page:toBuyerPage(raw),clipped:snapshot.clipped});setFailure(null);}
   })().catch(cause=>{if(current()&&!(cause instanceof LiveCancelled))setFailure({key:readKey,message:describeLiveError(cause)});});
   return()=>own.abort();
 },[client,session,scope.identity,query,offset,retry,readKey,snapshotKey]);
 useEffect(()=>{
   if(!buyerId)return;
   const own=new AbortController(),identity=session.identity();
   void loadLeadCase(client,session,buyerId,own.signal).then(value=>{
     if(!own.signal.aborted&&session.isCurrent(identity)){setSelected({id:buyerId,name:value.company_name});setSelectedError('');}
   }).catch(cause=>{if(!own.signal.aborted&&session.isCurrent(identity)&&!(cause instanceof LiveCancelled))setSelectedError(describeLiveError(cause));});
   return()=>own.abort();
 },[buyerId,client,session,scope.identity]);
 const active=page?.items.find(row=>row.id===buyerId);
 const currentName=active?.name||(selected?.id===buyerId?selected.name:t('Selected company'));
 return <div className="lead-company-picker">
   <label>{t('Search companies')}<input type="search" aria-label={t('Search companies')} value={search} maxLength={200} onChange={event=>setSearch(event.target.value)}/></label>
   {loading&&<p role="status">{t('Loading companies…')}</p>}
   {error&&<div role="alert">{error}<button onClick={()=>setRetry(value=>value+1)}>{t('Retry companies')}</button></div>}
   {selectedError&&<p role="alert">{t('Selected company unavailable.')} {selectedError}</p>}
   {page&&page.items.length===0&&<p>{t(query?'No matching companies.':'No companies yet.')}</p>}
   {loaded?.key===readKey&&loaded.clipped&&<p>{t('Results are limited to 1,000 companies. Refine the search to find another company.')}</p>}
   <label>{t('Preparation company')}<select aria-label={t('Preparation company')} value={buyerId} onChange={event=>onSelect(event.target.value)}>
     <option value="">{t('Choose company')}</option>
     {buyerId&&!active&&<option value={buyerId}>{currentName}</option>}
     {(page?.items??[]).map(row=><option key={row.id} value={row.id}>{row.name}{row.domain?` · ${row.domain}`:''}</option>)}
   </select></label>
   {page&&<div className="inline">
     <button disabled={offset===0||loading} onClick={()=>setOffset(value=>Math.max(0,value-24))}>{t('Previous companies')}</button>
     <span>{page.total?offset+1:0}–{Math.min(offset+page.items.length,page.total)} / {page.total}</span>
     <button disabled={loading||offset+page.items.length>=page.total} onClick={()=>setOffset(value=>value+24)}>{t('Next companies')}</button>
   </div>}
 </div>;
}
