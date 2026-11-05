import {SalesTransport,type SalesSchema as S} from './sales-transport';
import type {LiveClient} from './client';
import type {SessionScope} from './session';
export class SalesOutputs extends SalesTransport {
  permissions(id:string){return this.request<S['OutputPermissions']>(`/sales-outputs/${id}/permissions`);}
  get(id:string,revision?:number){return this.request<S['OutputVersion']>(`/sales-outputs/${encodeURIComponent(id)}${revision===undefined?'':`/versions/${revision}`}`);}
  list(native?:S['NativeRef'],offset=0){return this.request<S['OutputCollectionResponse']['data']>(`/sales-outputs?offset=${offset}&limit=50${native?`&native_surface=${native.surface}&native_id=${encodeURIComponent(native.id)}`:''}`);}
  versions(id:string){return this.request<S['OutputPage']>(`/sales-outputs/${id}/versions`);}
  review(task:string){return this.request<S['OutputReview']>(`/sales-tasks/${task}/output-review`);}
  save(input:S['OutputSave']){return this.request<S['OutputVersion']>('/sales-outputs','POST',input,input.expected_task_revision);}
  apply(proposal:S['ActionProposal'],version:number){return this.request<S['NativeRef']>('/sales-outputs/native-actions','POST',proposal,version);}
  formalDraft(id:string,input:S['FormalDraftInput']){return this.request<S['NativeRef']>(`/sales-outputs/${id}/formal-draft`,'POST',input,input.expected_revision);}
  export(id:string,input:S['OutputExportInput']){return this.request<S['NativeRef']>(`/sales-outputs/${id}/exports`,'POST',input,input.revision);}
}
const cache=new WeakMap<SessionScope,SalesOutputs>();
export function salesOutputs(client:LiveClient,session:SessionScope){let api=cache.get(session);if(!api||api.identity!==session.identity()){api=new SalesOutputs(client,session);cache.set(session,api);}return api;}
