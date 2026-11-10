/**
 * Increment 2.3: composer attachment state machine and the one-retry attach step.
 * The upload itself stays entirely in services/live/document-upload.ts; this module
 * only models the UI phases and adds the persisted document source to the thread.
 */
import type {SelectedSource} from './types';

export const ATTACHED_DOCUMENT_LABEL='Offer document';
export type AttachmentFailure='rejected'|'upload'|'attach';
export type AttachmentState=
  |{phase:'idle'}
  |{phase:'uploading';percent:number}
  |{phase:'attaching'}
  |{phase:'attached'}
  |{phase:'failed';failure:AttachmentFailure;message:string;retryable:boolean};
export type AttachmentEvent=
  |{type:'start'}|{type:'progress';percent:number}|{type:'uploaded'}|{type:'attached'}
  |{type:'fail';failure:AttachmentFailure;message:string;retryable?:boolean}|{type:'reset'};
function busy(state:AttachmentState):boolean{
  return state.phase==='uploading'||state.phase==='attaching';
}
export function attachmentBusy(state:AttachmentState):boolean{
  return busy(state);
}
export function attachmentPercent(state:AttachmentState):number{
  if(state.phase==='uploading')return state.percent;
  if(state.phase==='attaching'||state.phase==='attached')return 100;
  return 0;
}
export function attachmentReduce(state:AttachmentState,event:AttachmentEvent):AttachmentState{
  switch(event.type){
    case 'start':
      return busy(state)?state:{phase:'uploading',percent:0};
    case 'progress':
      return state.phase==='uploading'?{phase:'uploading',percent:Math.max(0,Math.min(100,Math.round(event.percent)))}:state;
    case 'uploaded':
      return state.phase==='uploading'?{phase:'attaching'}:state;
    case 'attached':
      return state.phase==='attaching'||state.phase==='uploading'?{phase:'attached'}:state;
    case 'fail':
      return state.phase==='uploading'||state.phase==='attaching'
        ?{phase:'failed',failure:event.failure,message:event.message,retryable:event.retryable??event.failure!=='rejected'}
        :state;
    case 'reset':
      return {phase:'idle'};
    default:
      return state;
  }
}
export function documentSource(documentId:string,label=ATTACHED_DOCUMENT_LABEL):SelectedSource{
  return {id:`document:${documentId}`,label};
}
export function sourceAlreadyAttached(sources:ReadonlyArray<SelectedSource>,documentId:string):boolean{
  const id=`document:${documentId}`;
  return sources.some(source=>source.id===id);
}
export type AttachOutcome<T>=
  |{kind:'attached';thread:T;attempts:1|2}
  |{kind:'duplicate';thread:T}
  |{kind:'failed';error:unknown};
/**
 * Adds the document source with the current thread version. A stale-version
 * conflict refetches the thread and retries exactly once; it never silently
 * drops the attachment. Duplicate sources are suppressed before any write.
 */
export async function attachThreadSource<T extends {version:number;sources:SelectedSource[]}>(input:{
  thread:T;documentId:string;label?:string;
  save:(thread:T,sources:SelectedSource[])=>Promise<T>;
  refresh:(current:T)=>Promise<T>;
  isStale:(error:unknown)=>boolean;
}):Promise<AttachOutcome<T>>{
  const source=documentSource(input.documentId,input.label);
  const withSource=(thread:T):SelectedSource[]=>[...thread.sources,source];
  const hasSource=(thread:T)=>thread.sources.some(row=>row.id===source.id);
  if(hasSource(input.thread))return {kind:'duplicate',thread:input.thread};
  try{
    const saved=await input.save(input.thread,withSource(input.thread));
    return {kind:'attached',thread:saved,attempts:1};
  }catch(error){
    if(!input.isStale(error))return {kind:'failed',error};
    let fresh:T;
    try{fresh=await input.refresh(input.thread);}catch(refreshError){return {kind:'failed',error:refreshError};}
    if(hasSource(fresh))return {kind:'duplicate',thread:fresh};
    try{
      const saved=await input.save(fresh,withSource(fresh));
      return {kind:'attached',thread:saved,attempts:2};
    }catch(second){return {kind:'failed',error:second};}
  }
}
