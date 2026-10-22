'use client';
import {useEffect,useRef,useState} from 'react';
import type {components} from '@/services/generated/buyeros-api';
import {useWorkspaceSession,useSessionSnapshot} from '@/features/providers/workspace-session';
import {createOperationClient} from '@/services/live/operations';
import {leadContext} from '@/services/live/lead-context';
import {LiveCancelled,describeLiveError} from '@/services/live/client';
type Member=components['schemas']['EligibleAssignee'];

/** Restricted existing owner projection; never use the admin membership API. */
export function useOwnerDirectory(ownMembershipId:string|null,enabled:boolean){
 const {client,session}=useWorkspaceSession(),scope=useSessionSnapshot();
 const [search,setSearch]=useState(''),[query,setQuery]=useState(''),[offset,setOffset]=useState(0),[retry,setRetry]=useState(0);
 const [result,setResult]=useState<{key:string;items:Member[];total:number}|null>(null),[failure,setFailure]=useState<{key:string;message:string}|null>(null);
 const [known,setKnown]=useState<{identity:string;items:Member[]}|null>(null);
 const sequence=useRef(0),key=JSON.stringify([scope.identity,query,offset,retry]);
 useEffect(()=>{const timer=setTimeout(()=>{setQuery(search.trim());setOffset(0);},250);return()=>clearTimeout(timer);},[search]);
 useEffect(()=>{
   if(!enabled)return;
   const own=new AbortController(),identity=session.identity(),serial=++sequence.current;
   const current=()=>!own.signal.aborted&&session.isCurrent(identity)&&serial===sequence.current;
   void (async()=>{
     const ctx=leadContext(session,own.signal),op=createOperationClient(client),path={workspace_id:ctx.workspace};
     const page=await op.requestOperation('listEligibleAssignees',{path,query:{q:query,offset,limit:20}},ctx);
     let ownMember:Member[]=[];
     if(ownMembershipId&&!page.items.some(row=>row.membership_id===ownMembershipId)){
       const exact=await op.requestOperation('listEligibleAssignees',{path,query:{q:ownMembershipId,offset:0,limit:20}},ctx);
       ownMember=exact.items.filter(row=>row.membership_id===ownMembershipId);
     }
     if(current()){
       setResult({key,items:page.items,total:page.total});setFailure(null);
       setKnown(previous=>({identity,items:[...new Map([...(previous?.identity===identity?previous.items:[]),...page.items,...ownMember].map(row=>[row.user_id,row])).values()].slice(-200)}));
     }
   })().catch(cause=>{if(current()&&!(cause instanceof LiveCancelled))setFailure({key,message:describeLiveError(cause)});});
   return()=>own.abort();
 },[enabled,client,session,scope.identity,ownMembershipId,query,offset,retry,key]);
 const members=enabled&&known?.identity===scope.identity?known.items:[];
 const ownUserId=members.find(row=>row.membership_id===ownMembershipId)?.user_id??null;
 return {search,setSearch,items:enabled&&result?.key===key?result.items:[],total:enabled&&result?.key===key?result.total:0,offset,
   more:()=>setOffset(value=>value+20),retry:()=>setRetry(value=>value+1),
   error:enabled&&failure?.key===key?failure.message:'',loading:enabled&&result?.key!==key&&failure?.key!==key,
   ownUserId,name:(id:string)=>{const member=members.find(row=>row.user_id===id);return member&&member.display_name!==member.user_id?member.display_name:null;}};
}
