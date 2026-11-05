import type {LiveClient} from './client';
import {LiveCancelled} from './client';
import type {SessionScope} from './session';
import {ActionIntent} from './action-intent';
import type {components} from '../generated/sales-api';
export type SalesSchema = components['schemas'];
/** Scoped, memory-only mutation identities. Recovery reads do not depend on entry flags. */
export class SalesTransport {
  readonly drafts = new Map<string, {text:string; skill?:string; arguments?:Record<string,SalesSchema['JsonValue']>; sources?:SalesSchema['SourceRef'][]; taskId?:string; baseline?:string}>();
  readonly recovery=new Map<string,unknown>();
  actionId(fingerprint:string):string{const key='action:'+fingerprint;let id=this.recovery.get(key) as string|undefined;if(!id){id=crypto.randomUUID();this.recovery.set(key,id);}return id;}
  private intents=new Map<string,ActionIntent<unknown>>();
  readonly identity:string;
  private root:string;
  constructor(protected client:LiveClient,protected session:SessionScope){
    this.identity=session.identity();const s=session.current();
    this.root=`/v1/workspaces/${encodeURIComponent(s.workspace??'')}/projects/${encodeURIComponent(s.project??'')}`;
    const clear=()=>{this.intents.clear();this.drafts.clear();this.recovery.clear();};
    const off=session.subscribeBeforeClear(clear);
    const unsub=session.subscribe(()=>{if(!session.isCurrent(this.identity)){clear();off();unsub();}});
  }
  async request<T>(path:string,method='GET',body?:unknown,version?:number):Promise<T>{
    const current=()=>this.session.isCurrent(this.identity)&&this.session.getSnapshot().authenticated;
    if(!current())throw new LiveCancelled('scope changed');
    const send=(idempotencyKey?:string)=>this.client.request<T>({path:this.root+path,method,body,ifMatch:version===undefined?undefined:`"${version}"`,idempotencyKey,scope:this.identity,token:this.session.token(),signal:this.session.controller().signal});
    const fingerprint=JSON.stringify([path,method,body,version]);
    let result:T;
    if(method==='GET')result=await send();
    else {let intent=this.intents.get(fingerprint);if(!intent){intent=new ActionIntent();this.intents.set(fingerprint,intent);}result=await intent.run(fingerprint,send) as T;this.intents.delete(fingerprint);}
    if(!current())throw new LiveCancelled('scope changed');return result;
  }
}
