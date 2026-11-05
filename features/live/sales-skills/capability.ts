import {useEffect,useState,useSyncExternalStore} from 'react';
import type {LiveClient} from '@/services/live/client';
import type {SessionScope} from '@/services/live/session';
import {salesTasks} from '@/services/live/sales-tasks';

/** Entry authority is current workspace policy, independent of saved-output reads. */
export function useSalesCapability(client:LiveClient,session:SessionScope){
 const snapshot=useSyncExternalStore(session.subscribe,session.getSnapshot,session.getSnapshot);
 const [value,setValue]=useState<{identity:string;enabled:boolean}|null>(null);
 useEffect(()=>{
  let active=true;
  const identity=snapshot.identity;
  const refresh=()=>{
   if(!snapshot.authenticated||!snapshot.scope.workspace||!snapshot.scope.project)return;
   void salesTasks(client,session).capability().then(v=>{
    if(active&&session.isCurrent(identity))setValue({identity,enabled:v.admission_enabled});
   }).catch(()=>{if(active)setValue({identity,enabled:false});});
  };
  refresh();window.addEventListener('focus',refresh);
  window.addEventListener('buyeros:location',refresh);
  return()=>{active=false;window.removeEventListener('focus',refresh);window.removeEventListener('buyeros:location',refresh);};
 },[client,session,snapshot.identity,snapshot.authenticated,snapshot.scope.workspace,snapshot.scope.project]);
 return value?.identity===snapshot.identity&&value.enabled;
}
