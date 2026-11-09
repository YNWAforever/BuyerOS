import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
registerHooks({resolve(s,c,next){try{return next(s,c);}catch(e){if(s.startsWith('.'))for(const ext of ['.ts','.tsx'])try{return next(s+ext,c);}catch{}throw e;}},load(u,c,next){if(/\.tsx?$/.test(u))return {format:'module',shortCircuit:true,source:ts.transpileModule(readFileSync(new URL(u),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText};return next(u,c);}});

const {PREVIEW_MAX_BYTES,PREVIEW_SANDBOX,previewSandboxTokens,previewRequestUrl,previewStatusKind,
  previewNoticeKey,fetchOutputPreview}=await import('../features/live/conversation/output-preview.ts');

const workspace='11111111-1111-4111-8111-111111111111',project='22222222-2222-4222-8222-222222222222',
  outputId='33333333-3333-4333-8333-333333333333';

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

test('the preview frame is sandboxed with no capability tokens',()=>{
  assert.equal(PREVIEW_SANDBOX,'');
  assert.deepEqual(previewSandboxTokens(),[]);
  assert.equal(PREVIEW_SANDBOX.includes('allow'),false);
  assert.equal(PREVIEW_MAX_BYTES,65536);
});

test('oversized preview HTML is capped and marked truncated',async()=>{
  const oversized=new TextEncoder().encode(`<!doctype html><body>HEAD${'x'.repeat(PREVIEW_MAX_BYTES)}`);
  const response=new Response(new ReadableStream({start(controller){
    controller.enqueue(oversized);controller.close();
  }}),{status:200,headers:{'content-type':'text/html'}});
  const outcome=await fetchOutputPreview({baseUrl:'',workspace,project,outputId,revision:1,
    fetchImpl:async()=>response});
  assert.equal(outcome.kind,'ready');
  assert.equal(outcome.truncated,true);
  assert.ok(new TextEncoder().encode(outcome.html).length<=PREVIEW_MAX_BYTES);
  assert.ok(outcome.html.startsWith('<!doctype html><body>HEAD'));
});

test('preview HTML at or under the cap is returned untruncated',async()=>{
  const html='<html><body><h1>Research brief</h1></body></html>';
  const outcome=await fetchOutputPreview({baseUrl:'',workspace,project,outputId,revision:2,
    fetchImpl:async()=>new Response(html,{status:200,headers:{'content-type':'text/html'}})});
  assert.deepEqual(outcome,{kind:'ready',html,truncated:false});
  const atCap='a'.repeat(PREVIEW_MAX_BYTES);
  const exact=await fetchOutputPreview({baseUrl:'',workspace,project,outputId,revision:2,
    fetchImpl:async()=>new Response(atCap,{status:200})});
  assert.equal(exact.truncated,false);
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

test('preview fetch sends the authenticated same-origin HTML read',async()=>{
  let received=null;
  const outcome=await fetchOutputPreview({baseUrl:'',workspace,project,outputId,revision:7,token:'synthetic-token',
    fetchImpl:async (url,init)=>{received={url,init};return new Response('<p>ok</p>',{status:200});}});
  assert.equal(outcome.kind,'ready');
  assert.match(received.url,/\/preview\?revision=7$/);
  assert.equal(received.init.method,'GET');
  assert.equal(received.init.headers.Authorization,'Bearer synthetic-token');
  assert.match(received.init.headers.Accept,/text\/html/);
});
