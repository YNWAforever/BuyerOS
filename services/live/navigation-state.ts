/** Ephemeral presentation state shared by retained route trees. No auth or edit
 * payload is stored here; a completed route cannot revive an old loading view. */
export type AppNavigation={id:number;path:string;href:string;fromPath:string};
let pending:AppNavigation|null=null,serial=0;
const listeners=new Set<()=>void>();
const publish=()=>{for(const listener of listeners)listener();};
export const navigationSnapshot=()=>pending;
export const serverNavigationSnapshot=()=>null;
/** Restored route trees must re-read the current ephemeral presentation state. */
export const refreshNavigationPresentation=()=>publish();
export const subscribeNavigation=(listener:()=>void)=>{listeners.add(listener);return()=>{listeners.delete(listener);};};
export function startNavigation(href:string){
 if(typeof window==='undefined')return;
 const target=new URL(href,window.location.origin);
 if(target.origin!==window.location.origin||!target.pathname.startsWith('/app'))return;
 const relative=target.pathname+target.search+target.hash;
 if(pending?.href===relative)return;
 pending={id:++serial,path:target.pathname,href:relative,fromPath:window.location.pathname};publish();
}
export function clearNavigationPresentation(){if(pending){pending=null;publish();}}
export function finishNavigation(id:number){
 if(pending?.id!==id)return;
 pending=null;publish();
}

/** A committed newer route may supersede the requested list (for example a
 * newly started research run). Never expose the old editor before departure,
 * and never trust a retained tree whose route disagrees with the browser. */
export function completeNavigationAt(renderedPath:string,actualPath:string):boolean{
 if(!pending||renderedPath!==actualPath||renderedPath===pending.fromPath)return false;
 finishNavigation(pending.id);return true;
}
