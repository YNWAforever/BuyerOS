/**
 * Retry identity for uncertain sends.
 *
 * A transport interruption (or a reload while the outcome is unknown) leaves the
 * same message unresolved. The retry must replay the original attempt exactly
 * (client message id, text, language, skill and expected thread version), not
 * whatever is selected in the editable composer now. A new message id starts a
 * new attempt.
 */
import type {ChatThread} from './types';

export type TurnAttempt={
  threadId:string|null;
  clientMessageId:string;
  text:string;
  skillId:string|null;
  language:'en'|'zh-HK';
  expectedVersion:number|null;
};
export type UnresolvedAttempt=TurnAttempt&{savedAt:number;routeKey:string};
export function retryAttempt(previous:TurnAttempt|null,next:TurnAttempt):TurnAttempt{
  if(!previous)return next;
  if(previous.clientMessageId!==next.clientMessageId)return next;
  if(previous.threadId!==next.threadId)return next;
  // The original payload is frozen for the duration of the unresolved attempt.
  return {...previous};
}
/** A GET is the first recovery step: never replay a message the thread already saved. */
export function messageHasAttempt(chat:ChatThread,clientMessageId:string):boolean{
  return chat.messages.some(message=>message.clientMessageId===clientMessageId);
}
const uuid=/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;
const routeKeyPattern=/^(new|home|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})$/i;
const skill=/^[a-z0-9][a-z0-9-]{0,79}$/;
export function readAttempt(value:unknown,expectedRouteKey?:string):UnresolvedAttempt|null{
  if(!value||typeof value!=='object')return null;
  const row=value as Record<string,unknown>;
  const threadId=row.threadId===null?null:typeof row.threadId==='string'&&uuid.test(row.threadId)?row.threadId:undefined;
  const clientMessageId=typeof row.clientMessageId==='string'&&uuid.test(row.clientMessageId)?row.clientMessageId:null;
  const text=typeof row.text==='string'&&row.text.trim().length>0&&row.text.length<=4000?row.text:null;
  const skillId=row.skillId===null?null:typeof row.skillId==='string'&&skill.test(row.skillId)?row.skillId:undefined;
  const language=row.language==='en'||row.language==='zh-HK'?row.language:null;
  const expectedVersion=row.expectedVersion===null?null:Number.isSafeInteger(row.expectedVersion)&&(row.expectedVersion as number)>=0?row.expectedVersion as number:undefined;
  const savedAt=Number.isSafeInteger(row.savedAt)?row.savedAt as number:null;
  const routeKey=typeof row.routeKey==='string'&&routeKeyPattern.test(row.routeKey)?row.routeKey:null;
  if(threadId===undefined||!clientMessageId||!text||skillId===undefined||!language||expectedVersion===undefined||savedAt===null||!routeKey)return null;
  if(expectedRouteKey!==undefined&&routeKey!==expectedRouteKey)return null;
  return {threadId,clientMessageId,text,skillId,language,expectedVersion,savedAt,routeKey};
}
