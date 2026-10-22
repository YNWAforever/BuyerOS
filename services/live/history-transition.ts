import type {SessionScope} from './session';
import {LiveCancelled} from './client';
import {clearNavigationPresentation} from './navigation-state';
const marker='__buyeros_transition_index';

/** Restore the current history entry before asking editors. Only an accepted
 * transition releases the original popstate to the framework. No draft text or
 * authentication material is written to history or persistent storage. */
export function bindHistoryTransitions(session:SessionScope,browser:Window=window,navigate?:(path:string)=>void):()=>void{
 // Progressive browser hook runs before popstate can restore a cached tree.
 // Only cancelable, same-document traversals are guarded here. Hard navigations
 // retain the editor's native beforeunload protection.
 type EarlyEntry={key:string;url:string;index:number};
 type EarlyNavigation=EventTarget&{traverseTo(key:string):{finished:Promise<unknown>};currentEntry?:EarlyEntry;entries?:()=>EarlyEntry[]};
 type EarlyEvent=Event&{navigationType:string;destination:{sameDocument:boolean;key:string;url:string}};
 const early=(browser as Window&{navigation?:EarlyNavigation}).navigation;
 // WebKit can leave the native traversal cursor inconsistent after a
 // canceled Navigation API event. Use the existing restore-before-decision
 // strategy for that engine. This selects a guard implementation only; browser
 // identification is never used for authentication or authorization.
 const webkit=browser.navigator?.vendor==='Apple Computer, Inc.'&&
   /AppleWebKit\//.test(browser.navigator.userAgent);
 if(!webkit&&early&&typeof early.traverseTo==='function'){
   let allowed:string|null=null,disposed=false,stopReplay:((cause:unknown)=>void)|null=null;
   const capture=(key:string,url:string)=>{
     if(typeof early.entries!=='function'||!early.currentEntry)return null;
     const entries=early.entries(),source=early.currentEntry,target=entries.find(row=>row.key===key);
     if(!target||target.url!==url||source.url!==browser.location.href||
       !Number.isSafeInteger(source.index)||source.index<0||!Number.isSafeInteger(target.index)||target.index<0||
       entries[source.index]?.key!==source.key||entries[target.index]?.key!==target.key||
       entries.slice(Math.min(source.index,target.index),Math.max(source.index,target.index)+1)
         .some(row=>{try{return new URL(row.url).origin!==browser.location.origin;}catch{return true;}})){
       throw new LiveCancelled('history changed');
     }
     return {sourceKey:source.key,sourceUrl:source.url,sourceIndex:source.index,targetIndex:target.index};
   };
   const before=(event:Event)=>{
     const value=event as EarlyEvent;
     if(value.navigationType!=='traverse'||!value.destination)return;
     if(allowed!==null){
       if(allowed===value.destination.key&&value.destination.sameDocument){allowed=null;clearNavigationPresentation();return;}
       if(value.cancelable)value.preventDefault();
       stopReplay?.(new LiveCancelled('history replay target changed'));return;
     }
     if(!value.destination.sameDocument)return;
     if(!value.cancelable||!session.hasBlockingTransitionGuards()){clearNavigationPresentation();return;}
     const target=new URL(value.destination.url),key=value.destination.key;
     if(target.origin!==browser.location.origin)return;
     value.preventDefault();
     let original:ReturnType<typeof capture>;
     try{original=capture(key,target.href);}catch{return;}
     void session.transition(async()=>{
       if(disposed)return;
       // Reconcile a confirmed arrival instead of attempting another traversal.
       if(early.currentEntry?.key===key&&browser.location.href===target.href)return;
       clearNavigationPresentation();
       if(!original){allowed=key;await early.traverseTo(key).finished;return;}
       const current=capture(key,target.href);
       if(!current||current.sourceKey!==original.sourceKey||current.sourceUrl!==original.sourceUrl||
          current.sourceIndex!==original.sourceIndex||current.targetIndex!==original.targetIndex){
         throw new LiveCancelled('history changed');
       }
       const delta=current.targetIndex-current.sourceIndex;
       if(!delta||Math.abs(delta)>=browser.history.length)throw new LiveCancelled('history changed');
       // A canceled traverseTo tracker can remain rejected in WebKit. Replay
       // the verified native history delta, while the next navigate event must
       // still match the exact approved key. No route or guard is bypassed.
       await new Promise<void>((resolve,reject)=>{
         let complete=false;
         const cleanup=()=>{
           early.removeEventListener('navigatesuccess',arrived);
           early.removeEventListener('navigateerror',failed);
           browser.removeEventListener('popstate',arrived);
           stopReplay=null;allowed=null;
         };
         const finish=(cause?:unknown)=>{if(complete)return;complete=true;cleanup();if(cause)reject(cause);else resolve();};
         const arrived=()=>{
           if(early.currentEntry?.key===key&&browser.location.href===target.href)finish();
         };
         const failed=()=>finish(new LiveCancelled('history traversal failed'));
         stopReplay=cause=>finish(cause);allowed=key;
         early.addEventListener('navigatesuccess',arrived);
         early.addEventListener('navigateerror',failed);
         browser.addEventListener('popstate',arrived);
         try{browser.history.go(delta);}catch(cause){finish(cause);}
       });
     }).catch(cause=>{allowed=null;if(!(cause instanceof LiveCancelled))console.error('Guarded traversal could not complete.');});
   };
   const committed=()=>{browser.dispatchEvent(new Event('buyeros:location'));};
   early.addEventListener('navigatesuccess',committed);
   early.addEventListener('navigate',before);
   return()=>{disposed=true;stopReplay?.(new LiveCancelled('scope changed'));early.removeEventListener('navigate',before);early.removeEventListener('navigatesuccess',committed);};
 }
 const history=browser.history,originalPush=history.pushState,originalReplace=history.replaceState;
 // Internal bookkeeping must not call the framework's notifying replace shim.
 const rawReplace=Object.getPrototypeOf(history).replaceState as History['replaceState'];
 const tagged=(state:unknown,index:number)=>({...((state&&typeof state==='object'&&!Array.isArray(state))?state:{}),[marker]:index});
 const position=(state:unknown)=>{
   if(!state||typeof state!=='object')return undefined;
   const record=state as Record<string,unknown>;
   // Pinned vinext beta.5 writes its traversal cursor through native, captured
   // History methods. Its index is routing metadata, never authorization.
   for(const key of ['__vinext_historyIndex',marker]){
     const value=record[key];if(typeof value==='number'&&Number.isSafeInteger(value)&&value>=0)return value;
   }
   return undefined;
 };
 let index=Number.isSafeInteger(position(history.state))?position(history.state) as number:0;
 let currentUrl=browser.location.href,currentState=tagged(history.state,index);
 let disposed=false,pending=false,accepted=false,restoreTo:number|null=null,restored:(()=>void)|null=null;
 rawReplace.call(history,currentState,'');
 const remember=()=>{currentUrl=browser.location.href;currentState=history.state;const next=position(currentState);if(typeof next==='number'&&Number.isSafeInteger(next))index=next;};
 const announce=()=>browser.dispatchEvent(new Event('buyeros:location'));
 const push:History['pushState']=function(state,unused,url){index++;originalPush.call(history,tagged(state,index),unused,url);remember();announce();};
 const replace:History['replaceState']=function(state,unused,url){originalReplace.call(history,tagged(state,index),unused,url);remember();announce();};
 history.pushState=push;history.replaceState=replace;
 const applyPop=(event:PopStateEvent)=>{
   if(!navigate){remember();announce();return;}
   event.stopImmediatePropagation();
   const target=new URL(browser.location.href),next=position(event.state);
   if(target.origin!==new URL(currentUrl).origin)return;
   if(typeof next==='number')index=next;
   // Retain the browser's Back/Forward position, but let the application router
   // perform the transition. The emitted framework's native pop handler reloads
   // the document and discards its in-memory session.
   rawReplace.call(history,tagged(event.state,index),'',currentUrl);
   const href=target.pathname+target.search+target.hash;
   browser.dispatchEvent(new CustomEvent('buyeros:navigationstart',{detail:{href}}));
   navigate(href);
 };
 const pop=(event:PopStateEvent)=>{
   if(accepted){accepted=false;applyPop(event);return;}
   const next=position(event.state);
   if(restoreTo!==null){
     event.stopImmediatePropagation();
     if(next===restoreTo){restoreTo=null;remember();const resolve=restored;restored=null;resolve?.();}
     else if(typeof next==='number')history.go(restoreTo-next);
     return;
   }
   if(!session.hasBlockingTransitionGuards()){remember();return;}
   event.stopImmediatePropagation();
   const target=browser.location.href,delta=typeof next==='number'?index-next:0;
   if(!delta||Math.abs(delta)>history.length){
     // Unmarked same-document history predates this binding. Preserve the
     // current page, then use a guarded native navigation for that target.
     rawReplace.call(history,currentState,'',currentUrl);
     if(!pending){pending=true;void session.transition(async()=>{if(!disposed)browser.location.assign(target);}).finally(()=>{pending=false;});}
     return;
   }
   restoreTo=index;
   const ready=new Promise<void>(resolve=>{restored=resolve;});
   history.go(delta);
   if(pending)return;
   pending=true;
   void ready.then(async()=>{
     if(disposed)return;
     await session.transition(async()=>{if(!disposed){accepted=true;history.go(-delta);}});
   }).catch(cause=>{
     if(!(cause instanceof LiveCancelled))console.error('Guarded history navigation could not complete.');
   }).finally(()=>{pending=false;});
 };
 const synchronize=()=>{if(!pending&&restoreTo===null&&!accepted)remember();};
 // vinext can announce a render commit before native history commits.
 // Track the actual browser success as well, without replacing a pending
 // source/target while the dirty-editor decision is unresolved.
 early?.addEventListener('navigatesuccess',synchronize);
 browser.addEventListener('buyeros:routecommitted',synchronize);
 browser.addEventListener('popstate',pop,true);
 return()=>{
   disposed=true;early?.removeEventListener('navigatesuccess',synchronize);browser.removeEventListener('popstate',pop,true);browser.removeEventListener('buyeros:routecommitted',synchronize);restored?.();restored=null;
   if(history.pushState===push)history.pushState=originalPush;
   if(history.replaceState===replace)history.replaceState=originalReplace;
 };
}
