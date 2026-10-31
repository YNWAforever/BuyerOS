import {ActionIntent} from './action-intent';
import {LiveCancelled,LiveError,type LiveClient} from './client';
import type {SessionScope} from './session';
import {exactFields} from './discussion-citations';
import type {SelectedSource} from './discussions';

export type DriveFolder={id:string;label:'Google Drive folder'};
export type DriveStatus={version:number;connected:boolean;available:boolean;can_manage:boolean;folders:DriveFolder[];residency_preference:'HK';metadata_cache_seconds:0};
export const driveNotices={unavailable:'Google Drive is unavailable. Ask a workspace admin to check the connection.',denied:'Google Drive access is denied for this workspace.',stale:'The connection changed. Reload Google Drive before trying again.',uncertain:'The connection change was not confirmed. Reload Google Drive and compare before retrying.'} as const;
export function driveNotice(error:unknown){return error instanceof LiveError&&error.code==='STALE_REVISION'?driveNotices.stale:error instanceof LiveError&&[401,403,404].includes(error.status)?driveNotices.denied:driveNotices.uncertain;}
export function driveReadNotice(error:unknown){return error instanceof LiveError&&[401,403,404].includes(error.status)?driveNotices.denied:driveNotices.unavailable;}
const id=/^[A-Za-z0-9_-]{1,128}$/;
export const driveSourceId=/^drive:[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}:[A-Za-z0-9_-]{1,128}$/;
function folders(value:unknown):value is DriveFolder[]{return Array.isArray(value)&&value.length<=100&&value.every(item=>exactFields(item,['id','label'])&&typeof item.id==='string'&&id.test(item.id)&&item.label==='Google Drive folder')&&new Set(value.map(item=>item.id)).size===value.length;}
export function driveStatus(value:unknown):DriveStatus{
  if(!exactFields(value,['version','connected','available','can_manage','folders','residency_preference','metadata_cache_seconds'])||!Number.isSafeInteger(value.version)||Number(value.version)<1||
    typeof value.connected!=='boolean'||typeof value.available!=='boolean'||typeof value.can_manage!=='boolean'||!folders(value.folders)||value.folders.length>20||(!value.connected&&value.folders.length>0)||value.residency_preference!=='HK'||value.metadata_cache_seconds!==0)throw new Error(driveNotices.unavailable);
  return value as DriveStatus;
}

/** Metadata-only memory cache (30s); no browser storage. Scope generations fence late data. */
export class ConversationConnections{
  private intents=new Map<string,ActionIntent<unknown>>();
  private reads=new Map<string,{expires:number;promise:Promise<unknown>}>();
  private identity:string;
  constructor(private client:LiveClient,private session:SessionScope,private enabled:boolean){
    this.identity=session.identity();
    const clear=()=>{this.intents.clear();this.reads.clear();};
    const unsubscribe=session.subscribeBeforeClear(clear);
    session.controller().signal.addEventListener('abort',()=>{clear();unsubscribe();},{once:true});
  }
  refresh(){this.reads.clear();}
  async request(suffix='',method='GET',body?:unknown,version?:number):Promise<unknown>{
    const scope=this.session.current(),identity=this.identity;
    const current=()=>this.enabled&&this.session.isCurrent(identity)&&!!this.session.token()&&scope.mode==='live'&&!!scope.workspace&&!!scope.project;
    if(!current())throw new LiveCancelled('scope changed');
    const send=(idempotencyKey?:string)=>{if(!current())throw new LiveCancelled('scope changed');return this.client.request({
      path:`/v1/workspaces/${encodeURIComponent(scope.workspace!)}/projects/${encodeURIComponent(scope.project!)}/conversation-connections/google-drive${suffix}`,
      method,body,scope:identity,token:this.session.token(),signal:this.session.controller().signal,missingIsUnavailable:true,
      idempotencyKey,ifMatch:version===undefined?undefined:`"${version}"`,
    });};
    let result:unknown;
    if(method==='GET'){
      let cached=this.reads.get(suffix);
      if(!cached||cached.expires<=Date.now()){cached={expires:Date.now()+30_000,promise:send()};this.reads.set(suffix,cached);}
      result=await cached.promise;
    }
    else{const fingerprint=JSON.stringify([identity,suffix,method,version,body]);let intent=this.intents.get(fingerprint);if(!intent){intent=new ActionIntent();this.intents.set(fingerprint,intent);}try{result=await intent.run(fingerprint,send);}finally{this.refresh();}}
    if(!current())throw new LiveCancelled('scope changed');
    if(method!=='GET')this.refresh();
    return result;
  }
  async status(){return driveStatus(await this.request());}
  async folders(){const value=await this.request('/folders');if(!exactFields(value,['items'])||!folders(value.items))throw new Error(driveNotices.unavailable);return value.items;}
  async items():Promise<SelectedSource[]>{
    const value=await this.request('/items');if(!exactFields(value,['items'])||!Array.isArray(value.items)||value.items.length>100||!value.items.every(item=>exactFields(item,['id','label'])&&typeof item.id==='string'&&driveSourceId.test(item.id)&&item.label==='Google Drive item')||new Set(value.items.map(item=>item.id)).size!==value.items.length)throw new Error(driveNotices.unavailable);
    return value.items as SelectedSource[];
  }
  async connect(version:number){return driveStatus(await this.request('','POST',{},version));}
  async approve(version:number,folder_ids:string[]){return driveStatus(await this.request('/folders','PUT',{folder_ids},version));}
  async disconnect(version:number){return driveStatus(await this.request('','DELETE',undefined,version));}
}

const clients=new WeakMap<SessionScope,{identity:string;api:ConversationConnections}>();
export function scopedConnections(client:LiveClient,session:SessionScope,identity:string){
  let cached=clients.get(session);
  if(!cached||cached.identity!==identity){cached={identity,api:new ConversationConnections(client,session,true)};clients.set(session,cached);}
  return cached.api;
}
