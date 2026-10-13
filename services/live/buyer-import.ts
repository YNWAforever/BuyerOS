import {ActionIntent} from './action-intent';
import {LiveCancelled,type LiveClient} from './client';
import type {SessionScope,WriteContext} from './session';
import type {components} from '@/services/generated/buyeros-api';

export type BuyerImportRow=components['schemas']['BuyerImportRow'];
export type BuyerImportPreview=components['schemas']['BuyerImportPreview'];
export type BuyerImportResult=components['schemas']['BuyerImportResult'];
export type BuyerImportSource=components['schemas']['BuyerImportSource'];

/** Keeps one request identity through a lost response; never starts paid work. */
export class BuyerImportWorkflow {
  private previews:ActionIntent<BuyerImportPreview>;
  private confirmations:ActionIntent<BuyerImportResult>;
  constructor(private client:LiveClient,private session:SessionScope,newKey?:()=>string){
    this.previews=new ActionIntent(newKey);this.confirmations=new ActionIntent(newKey);
  }
  private context(){
    const context=this.session.captureWriteContext();
    if(!context.project)throw new Error('Select a project.');
    return context;
  }
  private path(context:WriteContext){
    return `/v1/workspaces/${encodeURIComponent(context.workspace)}/projects/${encodeURIComponent(context.project!)}/buyer-imports`;
  }
  private current(context:WriteContext){
    if(!this.session.isCurrent(context.identity)||context.signal.aborted)throw new LiveCancelled('scope changed');
  }
  async preview(file:File):Promise<BuyerImportPreview>{
    if(!/\.(csv|xlsx)$/i.test(file.name)||file.size<1||file.size>5*1024*1024)throw new Error('Select a CSV or XLSX file up to 5 MiB.');
    const context=this.context(),bytes=await file.arrayBuffer();this.current(context);
    const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),value=>value.toString(16).padStart(2,'0')).join('');
    this.current(context);
    const fingerprint=JSON.stringify([context.identity,file.name,digest]);
    const result=await this.previews.run(fingerprint,key=>{
      this.current(context);
      const formData=new FormData();formData.append('file',file,file.name);
      return this.client.request<BuyerImportPreview>({path:`${this.path(context)}/preview`,method:'POST',
        token:this.session.token(),scope:context.identity,signal:context.signal,idempotencyKey:key,formData});
    });
    this.current(context);return result;
  }
  async confirm(preview:Pick<BuyerImportPreview,'id'|'preview_digest'>):Promise<BuyerImportResult>{
    const context=this.context(),body={preview_digest:preview.preview_digest,confirmation:true};
    const result=await this.confirmations.run(JSON.stringify([context.identity,preview.id,body]),key=>{
      this.current(context);
      return this.client.request<BuyerImportResult>({path:`${this.path(context)}/${encodeURIComponent(preview.id)}/confirm`,method:'POST',
        token:this.session.token(),scope:context.identity,signal:context.signal,idempotencyKey:key,body});
    });
    this.current(context);return result;
  }
  async lookup(id:string):Promise<BuyerImportPreview|BuyerImportResult>{
    const context=this.context();
    const result=await this.client.request<BuyerImportPreview|BuyerImportResult>({path:`${this.path(context)}/${encodeURIComponent(id)}`,
      token:this.session.token(),scope:context.identity,signal:context.signal});
    this.current(context);return result;
  }
}
