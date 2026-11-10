import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
registerHooks({resolve(s,c,next){try{return next(s,c);}catch(e){if(s.startsWith('.'))for(const ext of ['.ts','.tsx'])try{return next(s+ext,c);}catch{}throw e;}},load(u,c,next){if(/\.tsx?$/.test(u))return {format:'module',shortCircuit:true,source:ts.transpileModule(readFileSync(new URL(u),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText};return next(u,c);}});

const {ATTACHED_DOCUMENT_LABEL,attachmentReduce,attachmentBusy,attachmentPercent,documentSource,
  sourceAlreadyAttached,attachThreadSource,classifyUploadFailure,createAttachmentGuard,nextAttachmentPercent}=await import('../features/live/conversation/attachment.ts');
const {UploadError,uploadMessages,UPLOAD_ACCEPT,UPLOAD_ACCEPTED_EXTENSIONS,UPLOAD_MAX_BYTES,createDocumentUpload}=await import('../services/live/document-upload.ts');
const {ConversationThreads}=await import('../services/live/conversation-threads.ts');
const {SessionScope}=await import('../services/live/session.ts');
const {liveZh}=await import('../features/live/locale.ts');

const documentId='33333333-3333-4333-8333-333333333333';

test('attachment state machine moves idle → uploading(progress) → attaching → attached',()=>{
  let state=attachmentReduce({phase:'idle'},{type:'start'});
  assert.deepEqual(state,{phase:'uploading',percent:0});
  assert.equal(attachmentBusy(state),true);
  state=attachmentReduce(state,{type:'progress',percent:42.4});
  assert.deepEqual(state,{phase:'uploading',percent:42});
  assert.equal(attachmentPercent(state),42);
  assert.equal(attachmentBusy(state),true);
  state=attachmentReduce(state,{type:'uploaded'});
  assert.deepEqual(state,{phase:'attaching'});
  assert.equal(attachmentPercent(state),100);
  state=attachmentReduce(state,{type:'attached'});
  assert.deepEqual(state,{phase:'attached'});
  assert.equal(attachmentBusy(state),false);
  assert.deepEqual(attachmentReduce(state,{type:'reset'}),{phase:'idle'});
});

test('progress is clamped, monotonic and a start cannot interrupt an in-flight attachment',()=>{
  const uploading=attachmentReduce({phase:'idle'},{type:'start'});
  assert.deepEqual(attachmentReduce(uploading,{type:'progress',percent:-5}),{phase:'uploading',percent:0});
  assert.deepEqual(attachmentReduce(uploading,{type:'progress',percent:300}),{phase:'uploading',percent:100});
  assert.deepEqual(attachmentReduce(uploading,{type:'progress',percent:70}),{phase:'uploading',percent:70});
  assert.deepEqual(attachmentReduce({phase:'uploading',percent:70},{type:'progress',percent:30}),{phase:'uploading',percent:70},'progress never regresses');
  assert.equal(nextAttachmentPercent(70,30),70);
  assert.equal(nextAttachmentPercent(70,85),85);
  assert.equal(attachmentReduce(uploading,{type:'start'}),uploading,'duplicate start is ignored while busy');
  const attaching=attachmentReduce(uploading,{type:'uploaded'});
  assert.equal(attachmentReduce(attaching,{type:'start'}),attaching);
  assert.equal(attachmentReduce({phase:'idle'},{type:'progress',percent:10}).phase,'idle');
});

test('failure branches stay honest and mark only retryable failures',()=>{
  const uploading=attachmentReduce({phase:'idle'},{type:'start'});
  const rejected=attachmentReduce(uploading,{type:'fail',failure:'rejected',message:'Select PowerPoint up to 20 MiB, or PDF, text or Markdown up to 5 MiB.'});
  assert.deepEqual(rejected,{phase:'failed',failure:'rejected',message:'Select PowerPoint up to 20 MiB, or PDF, text or Markdown up to 5 MiB.',retryable:false});
  const upload=attachmentReduce(uploading,{type:'fail',failure:'upload',message:'The attachment could not be uploaded. Try again.'});
  assert.equal(upload.retryable,true);
  const attach=attachmentReduce(attachmentReduce(uploading,{type:'uploaded'}),{type:'fail',failure:'attach',message:'The attachment could not be added to this discussion. Try again.'});
  assert.equal(attach.retryable,true);
  assert.deepEqual(attachmentReduce({phase:'attached'},{type:'start'}),{phase:'uploading',percent:0},'a later file can start again');
  assert.equal(attachmentReduce({phase:'uploading',percent:20},{type:'attached'}).phase,'attached');
});

test('document sources use the persisted allowlisted identity',()=>{
  assert.deepEqual(documentSource(documentId),{id:`document:${documentId}`,label:'Offer document'});
  assert.equal(ATTACHED_DOCUMENT_LABEL,'Offer document');
  assert.equal(sourceAlreadyAttached([{id:`document:${documentId}`,label:'Offer document'}],documentId),true);
  assert.equal(sourceAlreadyAttached([{id:'drive:doc-1',label:'Drive document'}],documentId),false);
});

const thread=(version,sources=[])=>({version,sources});

test('attach saves the document source with the current thread version',async()=>{
  const calls=[];
  const outcome=await attachThreadSource({
    thread:thread(3),documentId,
    save:async (current,sources)=>{calls.push({version:current.version,sources});return thread(current.version+1,sources);},
    refresh:async()=>{throw new Error('must not refresh');},
    isStale:()=>false,
  });
  assert.equal(outcome.kind,'attached');
  assert.equal(outcome.attempts,1);
  assert.equal(calls.length,1);
  assert.equal(calls[0].version,3);
  assert.deepEqual(calls[0].sources,[{id:`document:${documentId}`,label:'Offer document'}]);
  assert.equal(outcome.thread.version,4);
});

test('a stale version refetches and retries exactly once with the fresh version',async()=>{
  const stale=Object.assign(new Error('stale'),{status:412});
  const calls=[],refreshes=[];
  const outcome=await attachThreadSource({
    thread:thread(3),documentId,
    save:async (current,sources)=>{calls.push({version:current.version,sources});
      if(calls.length===1)throw stale;
      return thread(current.version+1,sources);},
    refresh:async current=>{refreshes.push(current.version);return thread(5);},
    isStale:error=>error===stale,
  });
  assert.equal(outcome.kind,'attached');
  assert.equal(outcome.attempts,2);
  assert.deepEqual(refreshes,[3]);
  assert.deepEqual(calls.map(call=>call.version),[3,5]);
  assert.equal(outcome.thread.version,6);
  // A second stale conflict is an honest failure, never a third write.
  let writes=0;
  const failed=await attachThreadSource({
    thread:thread(3),documentId,
    save:async()=>{writes+=1;throw stale;},
    refresh:async()=>thread(5),
    isStale:error=>error===stale,
  });
  assert.equal(failed.kind,'failed');
  assert.equal(writes,2,'retry-once, never unbounded');
});

test('duplicate suppression avoids writes and other failures stay honest',async()=>{
  let writes=0;
  const duplicate=await attachThreadSource({
    thread:thread(2,[{id:`document:${documentId}`,label:'Offer document'}]),documentId,
    save:async()=>{writes+=1;throw new Error('must not write');},
    refresh:async()=>thread(3),
    isStale:()=>false,
  });
  assert.equal(duplicate.kind,'duplicate');
  assert.equal(writes,0,'an already-attached document is never written again');
  const nonStale=new Error('server error');
  const failed=await attachThreadSource({
    thread:thread(2),documentId,
    save:async()=>{throw nonStale;},
    refresh:async()=>{throw new Error('must not refresh');},
    isStale:()=>false,
  });
  assert.equal(failed.kind,'failed');assert.equal(failed.error,nonStale);
  const refreshed=await attachThreadSource({
    thread:thread(2),documentId,
    save:async()=>{throw Object.assign(new Error('stale'),{status:412});},
    refresh:async()=>thread(4,[{id:`document:${documentId}`,label:'Offer document'}]),
    isStale:error=>error.status===412,
  });
  assert.equal(refreshed.kind,'duplicate','a refresh that already proves persistence is not rewritten');
  const refreshFailed=await attachThreadSource({
    thread:thread(2),documentId,
    save:async()=>{throw Object.assign(new Error('stale'),{status:412});},
    refresh:async()=>{throw new Error('offline');},
    isStale:error=>error.status===412,
  });
  assert.equal(refreshFailed.kind,'failed');
});

test('upload failures classify by semantic code, never by error class',async()=>{
  for(const [code,retryable] of [['rejected',false],['expired',true],['parse_failed',false],['in_progress',true],['recoverable_io',true]]){
    const classified=classifyUploadFailure(new UploadError(code,uploadMessages.format,retryable),'Transport fallback');
    assert.equal(classified.failure,code==='rejected'?'rejected':'upload',`${code} maps to an upload phase`);
    assert.equal(classified.retryable,retryable,`${code} retryability comes from the code`);
    assert.equal(typeof liveZh[classified.message],'string',`${code} keeps canonical, translated copy`);
  }
  for(const message of Object.values(uploadMessages))assert.equal(typeof liveZh[message],'string','canonical uploader copy is localized');
  const transport=classifyUploadFailure({status:503,code:'UNAVAILABLE'},'Transport fallback');
  assert.deepEqual(transport,{failure:'upload',message:'Transport fallback',retryable:true},'transport failures stay retryable');
  const unknown=classifyUploadFailure(new Error('private detail'),'Generic fallback');
  assert.deepEqual(unknown,{failure:'rejected',message:'Generic fallback',retryable:false},'unknown failures fail closed with localized copy');
  const uploader=createDocumentUpload({request:async()=>{throw new Error('must not call');}});
  const ctx={actor:'a',workspace:'w',project:'p',identity:'id',token:'t',signal:new AbortController().signal,isCurrent:()=>true};
  const file=new File(['bytes'],'unsupported.exe',{type:'application/octet-stream'});
  await assert.rejects(uploader.upload(file,ctx),error=>error instanceof UploadError&&error.code==='rejected'&&error.retryable===false);
});

test('accepted formats and limits come from the uploader module',()=>{
  assert.equal(UPLOAD_ACCEPT,'.pdf,.txt,.md,.pptx');
  assert.deepEqual([...UPLOAD_ACCEPTED_EXTENSIONS],['pdf','txt','md','pptx']);
  assert.equal(UPLOAD_MAX_BYTES.standard,5*1024*1024);
  assert.equal(UPLOAD_MAX_BYTES.pptx,20*1024*1024);
});

test('a synchronous guard closes the double-selection race',()=>{
  const guard=createAttachmentGuard();
  assert.equal(guard.locked,false);
  assert.equal(guard.begin(),true);
  assert.equal(guard.locked,true);
  assert.equal(guard.begin(),false,'a second selection is rejected before React re-renders');
  guard.end();
  assert.equal(guard.locked,false);
  assert.equal(guard.begin(),true);
});

test('thread sources PUT and refresh combine the attach signal with the session signal',async()=>{
  const session=new SessionScope({mode:'live',actor:'a',workspace:'w',project:'p'});session.setToken('synthetic');
  const calls=[];
  const client={request:request=>new Promise((resolve,reject)=>{
    calls.push(request.signal);
    if(request.signal.aborted){reject(new Error('aborted'));return;}
    request.signal.addEventListener('abort',()=>reject(new Error('aborted')),{once:true});
  })};
  const threads=new ConversationThreads(client,session,true);
  const thread={id:'11111111-1111-4111-8111-111111111111',version:3,sources:[]};
  const controller=new AbortController();
  const put=threads.sources(thread,[],controller.signal);
  await new Promise(resolve=>setTimeout(resolve,0));
  controller.abort();
  await assert.rejects(put);
  assert.equal(calls.length,1);
  assert.equal(calls[0].aborted,true,'the sources PUT receives the combined aborted signal');
  const refreshed=new AbortController();
  const get=threads.get(thread.id,refreshed.signal);
  await new Promise(resolve=>setTimeout(resolve,0));
  refreshed.abort();
  await assert.rejects(get);
  assert.equal(calls.at(-1).aborted,true,'the stale refresh GET receives the combined aborted signal');
});
