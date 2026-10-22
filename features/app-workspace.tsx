'use client';
import {usePathname,useRouter} from 'next/navigation';
import {useEffect,useLayoutEffect,useRef,useSyncExternalStore} from 'react';
import Workspace from './workspace';
import {useWorkspaceSession} from './providers/workspace-session';
import {bindHistoryTransitions} from '@/services/live/history-transition';
import {navigationSnapshot,serverNavigationSnapshot,subscribeNavigation,completeNavigationAt,refreshNavigationPresentation} from '@/services/live/navigation-state';
import {useDataMode} from './providers/data-mode';

/** Auth routes share the session provider, never the workspace gate or its data readers. */
export function AppWorkspace(){
 const {mode}=useDataMode();
 const path=usePathname()??'',router=useRouter(),{session}=useWorkspaceSession();
 const routerRef=useRef(router),surface=useRef<HTMLDivElement>(null);
 const pending=useSyncExternalStore(subscribeNavigation,navigationSnapshot,serverNavigationSnapshot);
 useLayoutEffect(()=>{
   if(!pending)return;
   const complete=()=>{if(surface.current?.getClientRects().length)completeNavigationAt(path,window.location.pathname);};
   complete();
   // vinext publishes its render snapshot before committing browser history.
   // Recheck after this commit's layout effects; do not wait for another route
   // change or expose the old editor while the requested RSC response is held.
   const frame=requestAnimationFrame(complete);
   return()=>cancelAnimationFrame(frame);
 },[pending,path,router]);
 useLayoutEffect(()=>{
   routerRef.current=router;
   refreshNavigationPresentation();
   window.dispatchEvent(new Event('buyeros:location'));
   window.dispatchEvent(new Event('buyeros:routecommitted'));
 },[router,path]);
 useEffect(()=>mode==='live'?bindHistoryTransitions(session,window,path=>routerRef.current.replace(path)):undefined,[mode,session]);
 return <div ref={surface}><Workspace mode={mode}/></div>;
}
