import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';
const {createLiveClient,LiveCancelled}=await loadModule('services/live/client.ts');
const {createDocumentUpload,downloadOriginal}=await loadModule('services/live/document-upload.ts');
let checks=0;
async function check(name,fn){await fn();console.log('PASS '+name);checks++;}
const sha=async bytes=>Buffer.from(await crypto.subtle.digest('SHA-256',bytes)).toString('hex');
const env=data=>new Response(JSON.stringify({data,request_id:crypto.randomUUID(),data_mode:'live'}),{status:200,headers:{'Content-Type':'application/json'}});
function fixture({lostStart=false,lostChunk=false,lostComplete=false,lostStatus=false,corrupt=false,wholeCorrupt=false,scopeChange=false}={}){
 const map=new Map(),storage={getItem:k=>map.get(k)??null,setItem:(k,v)=>map.set(k,v),removeItem:k=>map.delete(k)};
 const file=new File([new Uint8Array(2*1024*1024+19).fill(7)],'fixture.pptx',{type:'application/vnd.openxmlformats-officedocument.presentationml.presentation'});
 let stage=null,doc=null,current=true;
 const parts=new Map(),calls=[];
 const context={actor:'actor-A',workspace:'workspace-A',project:'project-A',identity:'generation-A',token:'private-test-token',signal:new AbortController().signal,isCurrent:()=>current};
 const fetchImpl=async(path,init)=>{
  calls.push({path,method:init.method,key:init.headers['Idempotency-Key'],body:init.body,headers:init.headers});
  if(path.endsWith('/offer-document-uploads')){
   const manifest=JSON.parse(init.body);
   stage??={...manifest,id:'upload-A',workspace_id:context.workspace,project_id:context.project,chunk_size:2097152,chunk_count:2,received_chunks:[],expires_at:new Date(Date.now()+3600000).toISOString(),status:'uploading',version:1};
   if(lostStart){lostStart=false;throw new Error('lost accepted start');}
   return env(stage);
  }
  if(path.includes('/content-chunks/')){
   const i=Number(path.split('/').at(-1)), bytes=new Uint8Array(await file.slice(i*2097152,(i+1)*2097152).arrayBuffer());
   let hash=await sha(bytes);if(corrupt||wholeCorrupt)bytes[0]^=1;if(wholeCorrupt)hash=await sha(bytes);if(scopeChange)current=false;
   return env({index:i,offset:i*2097152,byte_length:bytes.length,chunk_count:2,source_byte_length:file.size,chunk_sha256:hash,source_sha256:doc.sha256,filename:file.name,media_type:file.type,body_base64:Buffer.from(bytes).toString('base64')});
  }
  if(init.method==='PUT'){
   const index=Number(path.split('/').at(-1));
   const bytes=new Uint8Array(await new Response(init.body).arrayBuffer());
   assert.equal(init.headers['X-Chunk-Sha256'],await sha(bytes));
   assert.ok(bytes.length<=2097152);
   parts.set(index,bytes);
   stage.received_chunks=await Promise.all([...parts].map(async([index,body])=>({index,sha256:await sha(body)})));
   if(lostChunk){lostChunk=false;throw new Error('lost accepted chunk');}
   return env(stage);
  }
  if(path.endsWith('/complete')){
   doc={id:'document-A',workspace_id:context.workspace,project_id:context.project,filename:file.name,media_type:file.type,sha256:stage.source_sha256,status:'ready',version:1,extraction_metadata:{format:'pptx',byte_length:file.size,chunk_size:2097152,slide_count:2}};
   stage.status='completed';stage.document_id=doc.id;
   if(lostComplete){lostComplete=false;throw new Error('lost committed complete');}
   return env(doc);
  }
  if(path.includes('/offer-documents/'))return env(doc);
  if(lostStatus&&stage?.status==='completed'){lostStatus=false;throw new Error('lost receipt readback');}
  return env(stage);
 };
 const client=createLiveClient(fetchImpl);
 return {file,context,client,storage,map,calls,get doc(){return doc;},change(){current=false;}};
}
await check('raw chunk transport is immutable, bounded and authenticated',async()=>{
 const f=fixture();const progress=[];
 const doc=await createDocumentUpload(f.client,f.storage).upload(f.file,f.context,p=>progress.push(p));
 assert.equal(doc.id,'document-A');assert.equal(f.calls.filter(c=>c.method==='PUT').length,2);
 assert.equal(f.map.size,0);assert.equal(progress.at(-1).percent,100);
 assert.equal(f.calls.find(c=>c.method==='PUT').headers.Authorization,'Bearer private-test-token');
});
await check('lost start retains original key across reload and same-file reselection',async()=>{
 const f=fixture({lostStart:true});
 await assert.rejects(()=>createDocumentUpload(f.client,f.storage).upload(f.file,f.context));
 const stored=JSON.stringify([...f.map.values()]);assert.ok(!stored.includes('private-test-token'));assert.ok(!stored.includes('Bearer'));
 await createDocumentUpload(f.client,f.storage).upload(new File([await f.file.arrayBuffer()],f.file.name,{type:f.file.type}),f.context);
 const starts=f.calls.filter(c=>c.path.endsWith('/offer-document-uploads'));assert.equal(starts.length,2);assert.equal(starts[0].key,starts[1].key);
});
await check('lost chunk reads status and does not send the accepted segment twice',async()=>{
 const f=fixture({lostChunk:true});await assert.rejects(()=>createDocumentUpload(f.client,f.storage).upload(f.file,f.context));
 const pending=JSON.parse([...f.map.values()][0]);assert.equal(pending.uploadId,'upload-A');
 await createDocumentUpload(f.client,f.storage).upload(f.file,f.context);
 assert.equal(f.calls.filter(c=>c.method==='PUT'&&c.path.endsWith('/0')).length,1);
});
await check('lost completion resolves receipt without replacing the operation',async()=>{
 const f=fixture({lostComplete:true});const doc=await createDocumentUpload(f.client,f.storage).upload(f.file,f.context);
 assert.equal(doc.id,'document-A');assert.equal(f.calls.filter(c=>c.path.endsWith('/complete')).length,1);assert.equal(f.map.size,0);
});
await check('different selected file cannot replace an unresolved operation',async()=>{
 const f=fixture({lostChunk:true});await assert.rejects(()=>createDocumentUpload(f.client,f.storage).upload(f.file,f.context));
 const n=f.calls.length;
 await assert.rejects(()=>createDocumentUpload(f.client,f.storage).upload(new File(['different'],'other.pptx',{type:f.file.type}),f.context),/same file|original file/i);
 assert.equal(f.calls.length,n);assert.equal(f.map.size,1);
});
await check('scope changes stop writes and late results',async()=>{
 const f=fixture();f.change();await assert.rejects(()=>createDocumentUpload(f.client,f.storage).upload(f.file,f.context),LiveCancelled);assert.equal(f.calls.length,0);
});
await check('simultaneous clicks on one workflow do not duplicate start or completion',async()=>{
 const f=fixture(),upload=createDocumentUpload(f.client,f.storage);
 const results=await Promise.allSettled([upload.upload(f.file,f.context),upload.upload(f.file,f.context)]);
 assert.equal(results.filter(r=>r.status==='fulfilled').length,1);
 assert.equal(f.calls.filter(c=>c.path.endsWith('/complete')).length,1);
});
await check('complete original hash is verified before creating a downloadable blob',async()=>{
 const f=fixture();await createDocumentUpload(f.client,f.storage).upload(f.file,f.context);
 const blob=await downloadOriginal(f.client,f.doc,f.context);
 assert.equal(await sha(await blob.arrayBuffer()),f.doc.sha256);assert.equal(blob.size,f.file.size);
});
await check('corrupt chunk prevents any downloadable file',async()=>{
 const f=fixture({corrupt:true});await createDocumentUpload(f.client,f.storage).upload(f.file,f.context);
 await assert.rejects(()=>downloadOriginal(f.client,f.doc,f.context),/digest|hash|corrupt/i);
});
await check('scope changes during original transfer produce no file',async()=>{
 const f=fixture({scopeChange:true});await createDocumentUpload(f.client,f.storage).upload(f.file,f.context);
 await assert.rejects(()=>downloadOriginal(f.client,f.doc,f.context),LiveCancelled);
 assert.equal(f.calls.filter(c=>c.path.includes('/content-chunks/')).length,1);
});
await check('lost completion and readback retain the same upload until reload reconciliation',async()=>{
 const f=fixture({lostComplete:true,lostStatus:true});
 await assert.rejects(()=>createDocumentUpload(f.client,f.storage).upload(f.file,f.context));
 assert.equal(f.map.size,1);
 const doc=await createDocumentUpload(f.client,f.storage).upload(f.file,f.context);
 assert.equal(doc.id,'document-A');assert.equal(f.calls.filter(c=>c.path.endsWith('/complete')).length,1);
});
await check('valid individual chunk hashes cannot substitute the whole original digest',async()=>{
 const f=fixture({wholeCorrupt:true});await createDocumentUpload(f.client,f.storage).upload(f.file,f.context);
 await assert.rejects(()=>downloadOriginal(f.client,f.doc,f.context),/file hash mismatch/i);
});
await check('a tampered foreign actor recovery record cannot send a write',async()=>{
 const f=fixture({lostStart:true});await assert.rejects(()=>createDocumentUpload(f.client,f.storage).upload(f.file,f.context));
 const [key,value]=[...f.map][0];f.map.set(key,JSON.stringify({...JSON.parse(value),actor:'foreign-actor'}));
 const n=f.calls.length;await assert.rejects(()=>createDocumentUpload(f.client,f.storage).upload(f.file,f.context),/scope|invalid/i);assert.equal(f.calls.length,n);
});
await check('auth retry preserves frozen chunk bytes and its digest',async()=>{
 const raw=new Uint8Array([1,2,3]),digest=await sha(raw),received=[];
 const client=createLiveClient(async(path,init)=>{
  received.push([...new Uint8Array(await new Response(init.body).arrayBuffer())]);
  if(received.length===1){raw[0]=9;return new Response('{}',{status:401});}
  return env({ok:true});
 },'',{refresh:async()=> 'renewed',isCurrent:()=>true});
 await client.request({path:'/v1/workspaces/A/offer-document-uploads/U/chunks/0',method:'PUT',scope:'A',token:'old',rawBody:raw,chunkSha256:digest,idempotencyKey:'immutable-chunk-key'});
 assert.deepEqual(received,[[1,2,3],[1,2,3]]);
});
console.log(`Document upload: ${checks} checks passed`);
