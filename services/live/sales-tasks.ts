import {SalesTransport,type SalesSchema as S} from './sales-transport';
import {LiveCancelled,type LiveClient} from './client';
import type {SessionScope} from './session';
export class SalesTasks extends SalesTransport {
  capability(signal?:AbortSignal){return signal?this.getAbortable<S['SalesCapability']>('/sales-tasks/capability',signal):this.request<S['SalesCapability']>('/sales-tasks/capability');}
  nativeSources(signal?:AbortSignal){return signal?this.getAbortable<S['SalesNativeSources']>('/sales-tasks/native-sources',signal):this.request<S['SalesNativeSources']>('/sales-tasks/native-sources');}
  skills(){return this.request<S['SkillPage']>('/sales/skills');}
  start(input:S['TaskInput'],threadVersion:number){return this.request<S['TaskDetail']>('/sales-tasks','POST',input,threadVersion);}
  list(thread:string,offset=0){return this.request<S['TaskCollectionResponse']['data']>(`/sales-tasks?thread_id=${encodeURIComponent(thread)}&offset=${offset}&limit=50`);}
  get(id:string){return this.request<S['TaskDetail']>(`/sales-tasks/${encodeURIComponent(id)}`);}
  events(id:string,after=0){return this.request<S['EventPage']>(`/sales-tasks/${encodeURIComponent(id)}/events?after=${after}`);}
  cancel(id:string,version:number){return this.request<S['TaskRecord']>(`/sales-tasks/${id}/cancel`,'POST',undefined,version);}
  followup(id:string,input:S['TaskFollowup'],version:number){return this.request<S['TaskDetail']>(`/sales-tasks/${id}/followups`,'POST',input,version);}
  guidance(id:string){return this.request<S['CoreGuidance']>(`/sales-tasks/${id}/core-guidance`);}
  prepare(id:string,version:number){return this.request<S['OutputVersion']>(`/sales-tasks/${id}/core-preparation`,'POST',undefined,version);}
  preview(id:string,proposal:S['ActionProposal']){return this.request<S['ExecutionPreview']>(`/sales-tasks/${id}/execution-preview`,'POST',proposal);}
  review(id:string,input:S['StepReviewInput'],version:number){return this.request<S['ExecutionReview']>(`/sales-tasks/${id}/reviews`,'POST',input,version);}
  admit(id:string,input:S['StepAdmission'],version:number){return this.request<S['StepReceipt']>(`/sales-tasks/${id}/steps`,'POST',input,version);}
  steps(id:string){return this.request<S['StepCollectionResponse']['data']>(`/sales-tasks/${id}/steps`);}
  /** Read-only GET under a caller-owned lifetime. Mutations keep the transport's own guards. */
  async getAbortable<T>(path:string,signal:AbortSignal):Promise<T>{
    const identity=this.identity,current=()=>this.session.isCurrent(identity)&&this.session.getSnapshot().authenticated;
    if(!current())throw new LiveCancelled('scope changed');
    const scope=this.session.current(),root=`/v1/workspaces/${encodeURIComponent(scope.workspace??'')}/projects/${encodeURIComponent(scope.project??'')}`;
    const result=await this.client.request<T>({path:root+path,method:'GET',token:this.session.token(),scope:identity,signal:AbortSignal.any([signal,this.session.controller().signal])});
    if(!current())throw new LiveCancelled('scope changed');return result;
  }
}
const cache=new WeakMap<SessionScope,SalesTasks>();
export function salesTasks(client:LiveClient,session:SessionScope){let api=cache.get(session);if(!api||api.identity!==session.identity()){api=new SalesTasks(client,session);cache.set(session,api);}return api;}
