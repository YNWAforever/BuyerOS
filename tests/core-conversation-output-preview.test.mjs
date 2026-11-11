import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
registerHooks({resolve(s,c,next){try{return next(s,c);}catch(e){if(s.startsWith('.'))for(const ext of ['.ts','.tsx'])try{return next(s+ext,c);}catch{}throw e;}},load(u,c,next){if(/\.tsx?$/.test(u))return {format:'module',shortCircuit:true,source:ts.transpileModule(readFileSync(new URL(u),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText};return next(u,c);}});

const {PREVIEW_MAX_BYTES,PREVIEW_SANDBOX,PREVIEW_CSP_META,previewSandboxTokens,sandboxedPreviewHtml,previewRequestUrl,
  previewStatusKind,previewContentTypeAllowed,previewNoticeKey,fetchOutputPreview}=await import('../features/live/conversation/output-preview.ts');

const workspace='11111111-1111-4111-8111-111111111111',project='22222222-2222-4222-8222-222222222222',
  outputId='33333333-3333-4333-8333-333333333333';
const encoder=new TextEncoder();
function htmlResponse(chunks,extraHeaders={}){
  return new Response(new ReadableStream({start(controller){
    for(const chunk of chunks)controller.enqueue(typeof chunk==='string'?encoder.encode(chunk):chunk);
    controller.close();
  }}),{status:200,headers:{'content-type':'text/html; charset=utf-8',...extraHeaders}});
}

test('preview URL builder encodes the scope, output and own revision',()=>{
  assert.equal(previewRequestUrl({baseUrl:'',workspace,project,outputId,revision:3}),
    `/v1/workspaces/${workspace}/projects/${project}/sales-outputs/${outputId}/preview?revision=3`);
  assert.equal(previewRequestUrl({baseUrl:'https://api.example.test/',workspace,project,outputId,revision:1}),
    `https://api.example.test/v1/workspaces/${workspace}/projects/${project}/sales-outputs/${outputId}/preview?revision=1`);
  assert.equal(previewRequestUrl({baseUrl:'',workspace:'w s',project:'p/2',outputId:'id?x',revision:12}),
    '/v1/workspaces/w%20s/projects/p%2F2/sales-outputs/id%3Fx/preview?revision=12');
  assert.equal(previewRequestUrl({baseUrl:'',workspace:'',project,outputId,revision:1}),null);
  assert.equal(previewRequestUrl({baseUrl:'',workspace,project,outputId,revision:0}),null);
  assert.equal(previewRequestUrl({baseUrl:'',workspace,project,outputId,revision:1.5}),null);
});

test('preview HTTP statuses map to honest non-retrying outcomes',()=>{
  for(const status of [200,204,206])assert.equal(previewStatusKind(status),'ok');
  for(const status of [401,403])assert.equal(previewStatusKind(status),'denied');
  assert.equal(previewStatusKind(404),'missing');
  for(const status of [400,409,429,500,503])assert.equal(previewStatusKind(status),'unavailable');
  assert.equal(previewNoticeKey('denied'),'You no longer have access to this output.');
  assert.equal(previewNoticeKey('missing'),'This output is no longer available.');
  assert.equal(previewNoticeKey('unavailable'),'Preview unavailable');
  assert.equal(previewNoticeKey('truncated'),'Preview truncated');
});

test('the preview document is sandboxed and mirrors the endpoint CSP',()=>{
  assert.equal(PREVIEW_SANDBOX,'');
  assert.deepEqual(previewSandboxTokens(),[]);
  assert.equal(PREVIEW_SANDBOX.includes('allow'),false);
  assert.equal(PREVIEW_MAX_BYTES,65536);
  assert.ok(PREVIEW_CSP_META.startsWith('<meta http-equiv="Content-Security-Policy"'));
  assert.match(PREVIEW_CSP_META,/content="default-src 'none'"/);
  assert.equal(sandboxedPreviewHtml('<p>body</p>'),PREVIEW_CSP_META+'<p>body</p>');
  assert.ok(sandboxedPreviewHtml('<p>body</p>').startsWith(PREVIEW_CSP_META),'the policy precedes server content');
});

test('oversized preview HTML is capped and marked truncated',async()=>{
  const oversized=encoder.encode(`<!doctype html><body>HEAD${'x'.repeat(PREVIEW_MAX_BYTES)}`);
  const outcome=await fetchOutputPreview({baseUrl:'',workspace,project,outputId,revision:1,
    fetchImpl:async()=>htmlResponse([oversized])});
  assert.equal(outcome.kind,'ready');
  assert.equal(outcome.truncated,true);
  assert.ok(encoder.encode(outcome.html).length<=PREVIEW_MAX_BYTES);
  assert.ok(outcome.html.startsWith('<!doctype html><body>HEAD'));
});

test('preview HTML at or under the cap is returned untruncated',async()=>{
  const html='<html><body><h1>Research brief</h1></body></html>';
  const outcome=await fetchOutputPreview({baseUrl:'',workspace,project,outputId,revision:2,
    fetchImpl:async()=>htmlResponse([html])});
  assert.deepEqual(outcome,{kind:'ready',html,truncated:false});
});

test('an exactly aligned oversized body is not silently truncated',async()=>{
  const exactCap='a'.repeat(PREVIEW_MAX_BYTES);
  // Exactly the budget, then EOF: complete and untruncated.
  const eof=await fetchOutputPreview({baseUrl:'',workspace,project,outputId,revision:3,
    fetchImpl:async()=>htmlResponse([exactCap])});
  assert.equal(eof.truncated,false);
  assert.equal(encoder.encode(eof.html).length,PREVIEW_MAX_BYTES);
  // Exactly the budget, then one more byte: must be marked truncated and cancelled.
  const over=await fetchOutputPreview({baseUrl:'',workspace,project,outputId,revision:3,
    fetchImpl:async()=>htmlResponse([exactCap,'b'])});
  assert.equal(over.truncated,true);
  assert.equal(encoder.encode(over.html).length,PREVIEW_MAX_BYTES);
  assert.equal(over.html.includes('b'),false);
  // A final chunk that consumes the remaining budget exactly, followed by more data.
  const aligned=await fetchOutputPreview({baseUrl:'',workspace,project,outputId,revision:3,
    fetchImpl:async()=>htmlResponse(['a'.repeat(PREVIEW_MAX_BYTES-1),'bbbbb'])});
  assert.equal(aligned.truncated,true);
  assert.equal(encoder.encode(aligned.html).length,PREVIEW_MAX_BYTES);
});

test('preview fetch maps 401/403/404, server and network failures without retrying',async()=>{
  const calls=[];
  const make=(status,body='')=>async url=>{calls.push(url);return new Response(body,{status});};
  const denied=await fetchOutputPreview({baseUrl:'',workspace,project,outputId,revision:1,fetchImpl:make(403)});
  assert.deepEqual(denied,{kind:'error',error:'denied'});
  const expired=await fetchOutputPreview({baseUrl:'',workspace,project,outputId,revision:1,fetchImpl:make(401)});
  assert.deepEqual(expired,{kind:'error',error:'denied'});
  const missing=await fetchOutputPreview({baseUrl:'',workspace,project,outputId,revision:1,fetchImpl:make(404)});
  assert.deepEqual(missing,{kind:'error',error:'missing'});
  const server=await fetchOutputPreview({baseUrl:'',workspace,project,outputId,revision:1,fetchImpl:make(500)});
  assert.deepEqual(server,{kind:'error',error:'unavailable'});
  const offline=await fetchOutputPreview({baseUrl:'',workspace,project,outputId,revision:1,
    fetchImpl:async()=>{throw new Error('offline');}});
  assert.deepEqual(offline,{kind:'error',error:'unavailable'});
  assert.equal(calls.length,4,'one request per call, never an automatic retry');
  for(const url of calls)assert.match(url,/\/sales-outputs\/33333333-3333-4333-8333-333333333333\/preview\?revision=1$/);
});

test('preview fetch refuses a non-HTML or redirected login response',async()=>{
  assert.equal(previewContentTypeAllowed('text/html'),true);
  assert.equal(previewContentTypeAllowed('text/html; charset=utf-8'),true);
  assert.equal(previewContentTypeAllowed('application/json'),false);
  assert.equal(previewContentTypeAllowed(null),false);
  const notHtml=await fetchOutputPreview({baseUrl:'',workspace,project,outputId,revision:1,
    fetchImpl:async()=>new Response('{"login":true}',{status:200,headers:{'content-type':'application/json'}})});
  assert.deepEqual(notHtml,{kind:'error',error:'unavailable'});
  const redirected=htmlResponse(['<html>sign in</html>']);
  Object.defineProperty(redirected,'redirected',{value:true});
  Object.defineProperty(redirected,'url',{value:'https://app.example.test/sign-in'});
  const login=await fetchOutputPreview({baseUrl:'',workspace,project,outputId,revision:1,
    fetchImpl:async()=>redirected});
  assert.deepEqual(login,{kind:'error',error:'unavailable'});
});

test('aborting the preview cancels the body reader and resolves unavailable',async()=>{
  let cancelled=false;
  const stream=new ReadableStream({start(controller){
    controller.enqueue(encoder.encode('<p>partial'));
  },cancel(){cancelled=true;}});
  const controller=new AbortController();
  const pending=fetchOutputPreview({baseUrl:'',workspace,project,outputId,revision:1,signal:controller.signal,
    fetchImpl:async()=>new Response(stream,{status:200,headers:{'content-type':'text/html'}})});
  await new Promise(resolve=>setTimeout(resolve,20));
  controller.abort();
  const outcome=await pending;
  assert.deepEqual(outcome,{kind:'error',error:'unavailable'});
  assert.equal(cancelled,true,'the response body reader is cancelled on abort');
});

test('a stalled preview request times out instead of loading forever',async()=>{
  const started=Date.now();
  const outcome=await fetchOutputPreview({baseUrl:'',workspace,project,outputId,revision:1,timeoutMs:25,
    fetchImpl:(url,init)=>new Promise((resolve,reject)=>{
      init.signal.addEventListener('abort',()=>reject(new DOMException('aborted','AbortError')),{once:true});
    })});
  assert.deepEqual(outcome,{kind:'error',error:'unavailable'});
  assert.ok(Date.now()-started<1_000,'the preview request is bounded by a timeout');
});

test('preview fetch sends the authenticated same-origin HTML read',async()=>{
  let received=null;
  const outcome=await fetchOutputPreview({baseUrl:'',workspace,project,outputId,revision:7,token:'synthetic-token',
    fetchImpl:async (url,init)=>{received={url,init};
      return new Response('<p>ok</p>',{status:200,headers:{'content-type':'text/html'}});}});
  assert.equal(outcome.kind,'ready');
  assert.match(received.url,/\/preview\?revision=7$/);
  assert.equal(received.init.method,'GET');
  assert.equal(received.init.headers.Authorization,'Bearer synthetic-token');
  assert.match(received.init.headers.Accept,/text\/html/);
});
