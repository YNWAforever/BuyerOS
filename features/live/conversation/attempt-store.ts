/**
 * Tab-scoped recovery for an uncertain send.
 *
 * The editable draft lives in the workspace draft store; this record is separate
 * so editing or reloading never rewrites the unresolved request. `sessionStorage`
 * is deliberate: recovery is for this tab and does not leak attempt text into a
 * new tab or another signed-in scope. The route key keeps a first send on /new
 * (or /app) recoverable even though it has no thread id yet.
 */
import {readAttempt,type TurnAttempt,type UnresolvedAttempt} from './attempt';

const prefix='buyeros.conversation.attempt.v1';
// JSON may expand a single control character into six code units.
const maxSerializedLength=32*1024;
export type AttemptStorage={getItem(key:string):string|null;setItem(key:string,value:string):void;removeItem(key:string):void};
function defaultStorage():AttemptStorage|null{
  try{return typeof window==='undefined'?null:window.sessionStorage;}catch{return null;}
}
export function attemptStorageKey(scopeKey:string,routeKey:string):string{
  return `${prefix}.${scopeKey}.${routeKey}`;
}
export function readUnresolvedAttempt(scopeKey:string,routeKey:string,storage:AttemptStorage|null=defaultStorage()):UnresolvedAttempt|null{
  if(!storage)return null;
  try{
    const raw=storage.getItem(attemptStorageKey(scopeKey,routeKey));
    if(!raw||raw.length>maxSerializedLength)return null;
    return readAttempt(JSON.parse(raw),routeKey);
  }catch{return null;}
}
export function writeUnresolvedAttempt(scopeKey:string,routeKey:string,attempt:TurnAttempt,storage:AttemptStorage|null=defaultStorage(),now=Date.now()):UnresolvedAttempt|null{
  if(!storage)return null;
  const stored={...attempt,savedAt:now,routeKey};
  try{
    const serialized=JSON.stringify(stored);
    if(serialized.length>maxSerializedLength)return null;
    storage.setItem(attemptStorageKey(scopeKey,routeKey),serialized);
    return stored;
  }catch{return null;}
}
export function clearUnresolvedAttempt(scopeKey:string,routeKey:string,storage:AttemptStorage|null=defaultStorage()):void{
  if(!storage)return;
  try{storage.removeItem(attemptStorageKey(scopeKey,routeKey));}catch{/* storage may be denied */}
}
