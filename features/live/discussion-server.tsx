'use client';
import {useLayoutEffect,useMemo} from 'react';
import type {LiveClient} from '@/services/live/client';
import type {SessionScope} from '@/services/live/session';
import {scopedThreadApi} from '@/services/live/conversation-threads';
import {ConversationStudio} from './conversation/studio';

export function useThreadApi(client:LiveClient,session:SessionScope,canViewOffer:boolean){
  const identity=session.identity(),api=useMemo(()=>scopedThreadApi(client,session,identity),[client,session,identity]);
  useLayoutEffect(()=>{if(!canViewOffer)api.forgetReply();},[api,canViewOffer]);
  return api;
}
type Props={client:LiveClient;session:SessionScope;id:string;t:(text:string)=>string;locale:'en'|'zh-HK';navigate:(path:string)=>void;canViewOffer:boolean;canViewResults:boolean};
/**
 * A saved workspace thread opens directly in the conversation-first studio, so the
 * guided task surface is a secondary disclosure rather than the default screen.
 */
export function ServerConversation({client,session,id,t,locale,navigate,canViewOffer,canViewResults}:Props){
  return <ConversationStudio client={client} session={session} t={t} locale={locale} navigate={navigate}
    canViewOffer={canViewOffer} canViewResults={canViewResults} threadId={id} fresh={false}/>;
}
