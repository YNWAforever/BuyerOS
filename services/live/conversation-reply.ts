import {conversationHomeEnabled} from '@/features/live/conversation-home';
import {LiveCancelled,LiveError,type LiveClient} from './client';
import type {SessionScope} from './session';
import type {SelectedSource} from './discussions';
import {validGroundedReply,type GroundedReply} from './discussion-citations';

export const replyNotices={
  unavailable:'BuyerOS AI is unavailable. Your question is still here; you can use the guided step or try later.',
  sources:'Selected sources are unavailable or not approved. Refresh project context and review your selection.',
  invalid:'The AI reply could not be verified. Review the selected sources and try again.',
} as const;
/** Explicit ask only. No history, source bodies, tools, job admission or retry loop. */
export async function askBuyerOS(client:LiveClient,session:SessionScope,options:{enabled:boolean;question:string;sources:SelectedSource[];locale:'en'|'zh-HK';signal:AbortSignal}):Promise<GroundedReply>{
  const identity=session.identity(),scope=session.current();
  if(!conversationHomeEnabled(options.enabled?'true':undefined)||!session.token()||scope.mode!=='live'||
    !scope.actor||!scope.workspace||!scope.project||!options.question.trim()||options.question.length>4000||
    options.sources.length<1||options.sources.length>20||new Set(options.sources.map(row=>row.id)).size!==options.sources.length)
    throw new Error(replyNotices.sources);
  const signal=AbortSignal.any([options.signal,session.controller().signal]);
  const current=()=>!signal.aborted&&session.isCurrent(identity)&&!!session.token();
  if(!current())throw new LiveCancelled('scope changed');
  try{
    const reply=await client.request<unknown>({
      path:`/v1/workspaces/${encodeURIComponent(scope.workspace)}/projects/${encodeURIComponent(scope.project)}/conversation-reply`,
      method:'POST',scope:identity,token:session.token(),signal,missingIsUnavailable:true,
      body:{question:options.question,source_ids:options.sources.map(row=>row.id),language:options.locale},
    });
    if(!current())throw new LiveCancelled('scope changed');
    if(!validGroundedReply(reply)||reply.citations.some(ref=>!options.sources.some(row=>row.id===ref.id)))throw new Error(replyNotices.invalid);
    return reply;
  }catch(error){
    if(!current()||error instanceof LiveCancelled)throw new LiveCancelled('scope changed');
    if(error instanceof LiveError)throw new Error(error.code==='CONVERSATION_SOURCE_UNAVAILABLE'||[403,422].includes(error.status)?replyNotices.sources:replyNotices.unavailable);
    throw new Error(error instanceof Error&&error.message===replyNotices.invalid?replyNotices.invalid:replyNotices.unavailable);
  }
}
