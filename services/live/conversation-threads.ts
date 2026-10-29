import {ActionIntent} from './action-intent';
import {LiveCancelled,LiveError,type LiveClient} from './client';
import type {SessionScope} from './session';
import type {LocalThread,SelectedSource} from './discussions';
import type {RunReference} from './conversation-research';

export type ServerSummary=Omit<LocalThread,'messages'|'sources'|'runs'>&{version:number;access:'owner'|'editor'|'viewer';shareCount:number};
export type ServerThread=ServerSummary&LocalThread;
export type Member={member_id:string;display_name:string};
export type ThreadShare=Member&{role:'viewer'|'editor';active:boolean};
export const threadNotices={stale:'This discussion changed. Copy any unsaved text before reloading.',unavailable:'Workspace discussions are unavailable. Your unsaved text is still here.',missing:'This workspace discussion was not found or is no longer shared with you.'} as const;
export function threadNotice(error:unknown){return (error instanceof LiveError&&error.code==='STALE_REVISION'||error instanceof Error&&error.message===threadNotices.stale)?threadNotices.stale:error instanceof LiveError&&error.status===404?threadNotices.missing:threadNotices.unavailable;}
/** Allowlist the import: AI messages and context bodies never cross this boundary. */
export function workspaceImport(thread:LocalThread,confirmed:boolean){
  if(confirmed!==true)throw new Error('Explicit confirmation required');
  return {confirmed:true,template_id:thread.templateId,title:thread.title,
    messages:thread.messages.filter(message=>!('kind' in message)).map(message=>({text:message.text})),
    sources:thread.sources.map(({id,label})=>({id,label})),runs:(thread.runs??[]).map(({id,label,status})=>({id,label,status}))};
}
/** No browser storage. A scope transition aborts requests and clears all intents. */
export class ConversationThreads{
  private intents=new Map<string,ActionIntent<unknown>>();
  private imports=new Map<string,ReturnType<typeof workspaceImport>>();
  private listRead:Promise<{items:ServerSummary[];total:number;offset:number;limit:number}>|null=null;
  private identity:string;
  private root:string;
  constructor(private client:LiveClient,private session:SessionScope,private enabled:boolean){
    this.identity=session.identity();const scope=session.current();
    this.root=`/v1/workspaces/${encodeURIComponent(scope.workspace??'')}/projects/${encodeURIComponent(scope.project??'')}/conversation-threads`;
    const clear=session.subscribeBeforeClear(()=>{this.intents.clear();this.imports.clear();this.listRead=null;});
    const unsubscribe=session.subscribe(()=>{if(!session.isCurrent(this.identity)){this.intents.clear();this.imports.clear();this.listRead=null;clear();unsubscribe();}});
  }
  async request<T>(suffix:string,method='GET',body?:unknown,version?:number):Promise<T>{
    const scope=this.session.current();
    if(!this.enabled||!this.session.isCurrent(this.identity)||!this.session.token()||scope.mode!=='live'||!scope.actor||!scope.workspace||!scope.project)throw new LiveCancelled('scope changed');
    const send=(idempotencyKey?:string)=>this.client.request<T>({path:this.root+suffix,method,body,ifMatch:version===undefined?undefined:`"${version}"`,idempotencyKey,
      scope:this.identity,token:this.session.token(),signal:this.session.controller().signal,missingIsUnavailable:true});
    let result:T;
    if(method==='POST'||method==='PUT'){
      const key=JSON.stringify([method,suffix,version,body]);let intent=this.intents.get(key);
      if(!intent){intent=new ActionIntent<unknown>();this.intents.set(key,intent);}
      result=await intent.run(JSON.stringify([this.identity,method,suffix,version,body]),send) as T;
    }else result=await send();
    if(!this.session.isCurrent(this.identity)||!this.session.token())throw new LiveCancelled('scope changed');
    if(method!=='GET')this.listRead=null;
    return result;
  }
  list(offset=0){
    if(offset===0&&this.listRead)return this.listRead;
    const read=this.request<{items:ServerSummary[];total:number;offset:number;limit:number}>(`?offset=${offset}&limit=50`);
    if(offset===0)this.listRead=read;return read;
  }
  get(id:string){return this.request<ServerThread>('/'+encodeURIComponent(id));}
  import(thread:LocalThread,confirmed:boolean){
    if(confirmed!==true)throw new Error('Explicit confirmation required');
    let body=this.imports.get(thread.id);if(!body){body=workspaceImport(thread,confirmed);this.imports.set(thread.id,body);}
    return this.request<ServerThread>('','POST',body).then(result=>{this.imports.delete(thread.id);return result;});
  }
  append(thread:ServerThread,text:string){return this.request<ServerThread>(`/${thread.id}/messages`,'POST',{text},thread.version);}
  sources(thread:ServerThread,sources:SelectedSource[]){return this.request<ServerThread>(`/${thread.id}/sources`,'PUT',{sources:sources.map(({id,label})=>({id,label}))},thread.version);}
  run(thread:ServerThread,run:RunReference){const {id,label,status}=run;return this.request<ServerThread>(`/${thread.id}/runs`,'POST',{id,label,status},thread.version);}
}

const clients=new WeakMap<SessionScope,{identity:string;api:ConversationThreads}>();
export function scopedThreadApi(client:LiveClient,session:SessionScope,identity:string){
  let cached=clients.get(session);
  if(!cached||cached.identity!==identity){cached={identity,api:new ConversationThreads(client,session,true)};clients.set(session,cached);}
  return cached.api;
}
