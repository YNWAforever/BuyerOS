import type {components} from '../generated/buyeros-api';
import {LiveCancelled,LiveError,type LiveClient,type LiveRequest} from './client';

export type UploadContext={actor:string;workspace:string;project:string;identity:string;token?:string;signal:AbortSignal;isCurrent:()=>boolean};
type Document=components['schemas']['OfferDocument'];
type Stage=components['schemas']['DocumentUpload'];
type Chunk=components['schemas']['DocumentContentChunk'];
type Manifest=components['schemas']['DocumentUploadStart'];
type Pending={version:1;actor:string;workspace:string;project:string;manifest:Manifest;key:string;uploadId?:string};
export type UploadProgress={phase:'hashing'|'uploading'|'completing'|'complete';percent:number};
const CHUNK=2097152;
const PREFIX='buyeros:document-upload:v1:';
const MIME:Record<string,Manifest['media_type']>={pptx:'application/vnd.openxmlformats-officedocument.presentationml.presentation',pdf:'application/pdf',txt:'text/plain',md:'text/markdown'};
const part=(s:string)=>encodeURIComponent(s);
const base=(ctx:UploadContext)=>`/v1/workspaces/${part(ctx.workspace)}`;
const guard=(ctx:UploadContext)=>{if(ctx.signal.aborted||!ctx.isCurrent())throw new LiveCancelled('scope changed');};
export async function sha256(bytes:Uint8Array<ArrayBuffer>|ArrayBuffer):Promise<string>{
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(n=>n.toString(16).padStart(2,'0')).join('');
}
function sameManifest(a:Pick<Stage,'filename'|'media_type'|'byte_length'|'source_sha256'>,b:Manifest){return a.filename===b.filename&&a.media_type===b.media_type&&a.byte_length===b.byte_length&&a.source_sha256===b.source_sha256;}
function checkedStage(stage:Stage,manifest:Manifest,ctx:UploadContext):Stage{
  if(!stage||!sameManifest(stage,manifest)||stage.workspace_id!==ctx.workspace||stage.project_id!==ctx.project
    ||typeof stage.id!=='string'||!stage.id||stage.chunk_size!==CHUNK||stage.chunk_count!==Math.ceil(manifest.byte_length/CHUNK)
    ||!Array.isArray(stage.received_chunks)||stage.received_chunks.length>10||!['uploading','completed','failed','expired'].includes(stage.status)
    ||stage.received_chunks.some(c=>!Number.isInteger(c.index)||c.index<0||c.index>=stage.chunk_count||!/^[a-f0-9]{64}$/.test(c.sha256))
    ||new Set(stage.received_chunks.map(c=>c.index)).size!==stage.received_chunks.length)
    throw new Error('Invalid upload status. Keep the original file and check the connection.');
  return stage;
}
function checkedDocument(doc:Document,manifest:Manifest,ctx:UploadContext):Document{
  guard(ctx);
  if(!doc||doc.workspace_id!==ctx.workspace||doc.project_id!==ctx.project||doc.sha256!==manifest.source_sha256
    ||doc.filename!==manifest.filename||doc.media_type!==manifest.media_type||doc.status!=='ready')
    throw new Error('Saved attachment does not match the original file.');
  return doc;
}

/** Persist only immutable identifiers/manifest. Bytes and bearer tokens stay in memory. */
export function createDocumentUpload(client:LiveClient,storage?:Pick<Storage,'getItem'|'setItem'|'removeItem'>){
  const memory=new Map<string,string>();
  const store=storage??{getItem:(key:string)=>memory.get(key)??null,setItem:(key:string,value:string)=>{memory.set(key,value);},removeItem:(key:string)=>{memory.delete(key);}};
  let busy=false;
  const storageKey=(ctx:UploadContext)=>PREFIX+[ctx.actor,ctx.workspace,ctx.project].map(part).join(':');
  function pending(ctx:UploadContext):Pending|null{
    const value=store.getItem(storageKey(ctx));if(!value)return null;
    let record:Pending;
    try{record=JSON.parse(value);}catch{throw new Error('Upload recovery is unreadable. Keep the original file.');}
    if(record.version!==1||record.actor!==ctx.actor||record.workspace!==ctx.workspace||record.project!==ctx.project
      ||typeof record.key!=='string'||record.key.length<8||record.key.length>200||!record.manifest
      ||!Number.isInteger(record.manifest.byte_length)||record.manifest.byte_length<1||record.manifest.byte_length>20*1024*1024
      ||typeof record.manifest.filename!=='string'||typeof record.manifest.media_type!=='string'||!/^[a-f0-9]{64}$/.test(record.manifest.source_sha256)
      ||(record.uploadId!==undefined&&(typeof record.uploadId!=='string'||!record.uploadId)))throw new Error('Upload recovery belongs to a different scope or is invalid.');
    return record;
  }
  return {pending,
    async upload(file:File,ctx:UploadContext,onProgress:(value:UploadProgress)=>void=()=>{}):Promise<Document>{
      guard(ctx);if(busy)throw new Error('An attachment upload is already in progress.');busy=true;
      const request=<T>(path:string,options:Partial<LiveRequest>={})=>{
        guard(ctx);return client.request<T>({path,token:ctx.token,scope:ctx.identity,signal:ctx.signal,...options});
      };
      try{
        const suffix=file.name.split('.').at(-1)?.toLowerCase()??'',mime=MIME[suffix];
        if(!mime||file.size<1||file.size>(suffix==='pptx'?20:5)*1024*1024)throw new Error('Select PowerPoint up to 20 MiB, or PDF, text or Markdown up to 5 MiB.');
        onProgress({phase:'hashing',percent:0});
        const bytes=await file.arrayBuffer();guard(ctx);
        const digest=await sha256(bytes);guard(ctx);
        const manifest:Manifest={filename:file.name,media_type:mime,byte_length:bytes.byteLength,source_sha256:digest};
        let record=pending(ctx);
        if(record&&!sameManifest(record.manifest,manifest))throw new Error('Select the same file as the unresolved upload. Keep the original file.');
        record??={version:1,actor:ctx.actor,workspace:ctx.workspace,project:ctx.project,manifest,key:crypto.randomUUID()};
        const save=()=>{guard(ctx);store.setItem(storageKey(ctx),JSON.stringify(record));};
        save();
        let stage:Stage;
        if(record.uploadId)stage=await request<Stage>(`${base(ctx)}/offer-document-uploads/${part(record.uploadId)}`);
        else{
          // Lost start responses reconcile by the same manifest/key; the API's
          // original receipt returns current status instead of a second session.
          stage=await request<Stage>(`${base(ctx)}/projects/${part(ctx.project)}/offer-document-uploads`,{method:'POST',body:manifest,idempotencyKey:record.key});
          guard(ctx);checkedStage(stage,manifest,ctx);record.uploadId=stage.id;save();
        }
        guard(ctx);checkedStage(stage,manifest,ctx);
        if(stage.id!==record.uploadId)throw new Error('Upload status does not match the original operation.');
        const resolve=async()=>{
          if(!stage.document_id)throw new Error('Completed upload is missing its document receipt.');
          const doc=await request<Document>(`${base(ctx)}/offer-documents/${part(stage.document_id)}`);
          return checkedDocument(doc,manifest,ctx);
        };
        let doc:Document;
        if(stage.status==='completed')doc=await resolve();
        else{
          if(stage.status==='failed'||stage.status==='expired'){
            store.removeItem(storageKey(ctx));throw new Error(stage.status==='expired'?'Upload expired. Select the original file to start again.':'The file could not be parsed. Staged bytes were removed.');
          }
          const url=`${base(ctx)}/offer-document-uploads/${part(stage.id)}`;
          for(let index=0;index<stage.chunk_count;index++){
            guard(ctx);
            const rawBody=new Uint8Array(bytes.slice(index*CHUNK,(index+1)*CHUNK));
            const hash=await sha256(rawBody);guard(ctx);
            const received=stage.received_chunks.find(c=>c.index===index);
            if(received&&received.sha256!==hash)throw new Error('Received segment does not match the original file hash.');
            if(!received){
              await request<Stage>(`${url}/chunks/${index}`,{method:'PUT',rawBody,chunkSha256:hash,idempotencyKey:`${record.key}:${index}`});
              guard(ctx);
            }
            onProgress({phase:'uploading',percent:Math.round((index+1)/stage.chunk_count*95)});
          }
          onProgress({phase:'completing',percent:95});
          try{doc=checkedDocument(await request<Document>(`${url}/complete`,{method:'POST',body:{},idempotencyKey:record.key}),manifest,ctx);}
          catch(cause){
            guard(ctx);
            if(!(cause instanceof LiveError)||cause.status===400||cause.status===401||cause.status===403||cause.status===404||cause.status===409)throw cause;
            // A network/server/invalid-envelope outcome may already have committed.
            // One readback resolves it; unresolved status retains the original key.
            stage=checkedStage(await request<Stage>(url),manifest,ctx);guard(ctx);
            if(stage.status!=='completed')throw cause;
            doc=await resolve();
          }
        }
        guard(ctx);store.removeItem(storageKey(ctx));onProgress({phase:'complete',percent:100});return doc;
      }finally{busy=false;}
    },
  };
}

/** No Blob is returned until all bounded slices and the whole original hash pass. */
export async function downloadOriginal(client:LiveClient,doc:Document,ctx:UploadContext):Promise<Blob>{
  guard(ctx);
  const length=doc.extraction_metadata?.byte_length;
  if(doc.workspace_id!==ctx.workspace||doc.project_id!==ctx.project||doc.status!=='ready'||!doc.sha256||!/^[a-f0-9]{64}$/.test(doc.sha256)
    ||!length||!Number.isInteger(length)||length<1||length>20*1024*1024)throw new Error('Original attachment is not available.');
  const count=Math.ceil(length/CHUNK),parts:Uint8Array<ArrayBuffer>[]=[];
  for(let index=0;index<count;index++){
    guard(ctx);
    const item=await client.request<Chunk>({path:`${base(ctx)}/offer-documents/${part(doc.id)}/content-chunks/${index}`,token:ctx.token,scope:ctx.identity,signal:ctx.signal});
    guard(ctx);
    if(item.index!==index||item.offset!==index*CHUNK||item.chunk_count!==count||item.source_byte_length!==length||item.source_sha256!==doc.sha256
      ||item.filename!==doc.filename||item.media_type!==doc.media_type||item.byte_length!==Math.min(CHUNK,length-index*CHUNK)
      ||typeof item.body_base64!=='string'||item.body_base64.length>2796204)throw new Error('Original chunk does not match its manifest.');
    const decoded=Uint8Array.from(atob(item.body_base64),c=>c.charCodeAt(0));
    if(decoded.byteLength!==item.byte_length||await sha256(decoded)!==item.chunk_sha256)throw new Error('Original chunk hash mismatch.');
    guard(ctx);parts.push(decoded);
  }
  const joined=new Uint8Array(length);let offset=0;
  for(const bytes of parts){joined.set(bytes,offset);offset+=bytes.byteLength;}
  if(await sha256(joined)!==doc.sha256)throw new Error('Original file hash mismatch.');
  guard(ctx);return new Blob([joined],{type:doc.media_type});
}
