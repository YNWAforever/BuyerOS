import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
import {loadModule,moduleUrl} from './ts-loader.mjs';

const {SessionScope}=await loadModule('services/live/session.ts');
const {LiveError}=await loadModule('services/live/client.ts');
const flush=()=>new Promise(resolve=>setImmediate(resolve));

// Execute the production module with hook state captured in memory. No API, DB,
// timers, credentials or provider connections are used; the reader accepts an
// injected clock so coalescing/backoff are deterministic.
function capabilitySource(){
 let source=ts.transpileModule(readFileSync('features/live/sales-skills/capability.ts','utf8'),{
  compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
 source=source.replace(/import\s*\{[^}]*\}\s*from\s*['"]react['"];?/,
  'const useEffect=(...args)=>globalThis.__capabilityHooks.useEffect(...args),useSyncExternalStore=(...args)=>globalThis.__capabilityHooks.useSyncExternalStore(...args);')
  .replace(/from ['"](@\/[^'"]+)['"]/g,(_,spec)=>'from '+JSON.stringify(moduleUrl(spec.slice(2)+'.ts')));
 return 'data:text/javascript;base64,'+Buffer.from(source).toString('base64');
}
globalThis.__capabilityHooks={useEffect:()=>{},useSyncExternalStore:(_subscribe,get)=>get()};
const capability=await import(capabilitySource());
const {CapabilityReader,salesCapabilityShell,salesCapabilityCopy,salesCapabilityText}=capability;

function clock(){
 let time=1_000;const timers=[];
 return {
  now:()=>time,
  schedule:(run,delayMs)=>{const timer={at:time+delayMs,run,done:false};timers.push(timer);return timer;},
  cancel:timer=>{if(timer)timer.done=true;},
  advance(ms){time+=ms;for(;;){const next=timers.find(timer=>!timer.done&&timer.at<=time);if(!next)return;next.done=true;next.run();}},
 };
}
function session(){
 const scope=new SessionScope({mode:'live',actor:'fixture',workspace:'workspace',project:'project'});
 scope.setToken('synthetic');return scope;
}
function reader(client,scope){return new CapabilityReader(client,scope,clock());}

test('capability reader settles on explicit enabled/disabled, never a boolean fallback',async()=>{
 const scope=session(),requests=[];
 const r=reader({request:async input=>{requests.push(input);return {admission_enabled:true};}},scope);
 assert.equal(r.getSnapshot().status,'idle');
 r.start();await flush();
 assert.equal(r.getSnapshot().status,'enabled');
 assert.equal(r.getSnapshot().identity,scope.identity());
 assert.equal(requests.length,1);
 assert.equal(requests[0].method,'GET');
 assert.equal(requests[0].scope,scope.identity());
 assert.match(requests[0].path,/\/sales-tasks\/capability$/);
 const disabled=reader({request:async()=>({admission_enabled:false})},session());
 disabled.start();await flush();
 assert.equal(disabled.getSnapshot().status,'disabled','a server-answered false is disabled, not unavailable');
 r.dispose();disabled.dispose();
});

test('capability reads are single-flight per identity across subscribers',async()=>{
 const scope=session(),pending=[];
 const r=reader({request:()=>new Promise(resolve=>pending.push(()=>resolve({admission_enabled:true})))},scope);
 r.start();r.start();r.refresh('location');r.refresh('focus');
 await flush();
 assert.equal(pending.length,1,'concurrent triggers share one in-flight request');
 pending[0]();await flush();
 assert.equal(r.getSnapshot().status,'enabled');
 r.dispose();
});

test('focus refresh is suppressed for a fresh success and revalidates after the window',async()=>{
 const scope=session(),requests=[];let time;
 const c=clock();time=c;
 const r=new CapabilityReader({request:async input=>{requests.push(input);return {admission_enabled:true};}},scope,c);
 r.start();await flush();
 assert.equal(requests.length,1);
 for(let index=0;index<5;index++)r.refresh('focus');
 await flush();
 assert.equal(requests.length,1,'five focus events right after a successful read add no request');
 time.advance(60_001);r.refresh('focus');await flush();
 assert.equal(requests.length,2,'focus revalidates current policy once the answer is stale');
 r.dispose();
});

test('location refresh stays available but is coalesced',async()=>{
 const scope=session(),requests=[];
 const c=clock();
 const r=new CapabilityReader({request:async input=>{requests.push(input);return {admission_enabled:true};}},scope,c);
 r.start();await flush();
 c.advance(2_000);r.refresh('location');await flush();
 assert.equal(requests.length,2,'a later location change refreshes current policy');
 r.refresh('location');r.refresh('location');await flush();
 assert.equal(requests.length,2,'location changes in the same window share the read');
 c.advance(1_501);r.refresh('location');await flush();
 assert.equal(requests.length,3);
 r.dispose();
});

test('retryable failures retry a bounded number of times, then expose a recoverable unavailable state',async()=>{
 const scope=session(),c=clock();let calls=0;
 const r=new CapabilityReader({request:async()=>{calls++;throw new LiveError('request deadline exceeded','REQUEST_TIMEOUT',0,'',true);}},scope,c);
 r.start();await flush();
 assert.equal(calls,1);assert.equal(r.getSnapshot().status,'loading');assert.equal(r.getSnapshot().attempts,1);
 c.advance(400);await flush();
 assert.equal(calls,2);assert.equal(r.getSnapshot().attempts,2);
 c.advance(1_200);await flush();
 assert.equal(calls,3,'automatic retry is bounded');
 assert.equal(r.getSnapshot().status,'unavailable');
 assert.equal(r.getSnapshot().attempts,3);
 assert.match(r.getSnapshot().reason,/timed out/i);
 assert.equal(typeof r.getSnapshot().retry,'function');
 r.getSnapshot().retry();await flush();
 assert.equal(calls,3,'manual retry is ignored during the cooldown');
 c.advance(5_001);r.getSnapshot().retry();await flush();
 assert.equal(calls,4,'manual retry starts a new bounded burst after the cooldown');
 r.dispose();
});

test('non-retryable failures become unavailable without replay',async()=>{
 const scope=session();let calls=0;
 const r=reader({request:async()=>{calls++;throw new LiveError('request failed','NOT_FOUND',404,'',false);}},scope);
 r.start();await flush();
 assert.equal(calls,1);
 assert.equal(r.getSnapshot().status,'unavailable');
 assert.equal(r.getSnapshot().attempts,1);
 r.dispose();
});

test('a failed background revalidation of an enabled workspace becomes unavailable after bounded retry',async()=>{
 const scope=session(),c=clock();let fail=false,calls=0;
 const r=new CapabilityReader({request:async()=>{calls++;if(fail)throw new LiveError('service unavailable','SERVICE_UNAVAILABLE',503,'',true);return {admission_enabled:true};}},scope,c);
 r.start();await flush();
 assert.equal(r.getSnapshot().status,'enabled');
 fail=true;c.advance(60_001);r.refresh('focus');await flush();
 assert.equal(r.getSnapshot().status,'enabled','a revalidation keeps the last settled state visible');
 assert.equal(r.getSnapshot().refreshing,true);
 c.advance(400);await flush();c.advance(1_200);await flush();
 assert.equal(calls,4,'initial success plus three bounded revalidation attempts');
 assert.equal(r.getSnapshot().status,'unavailable');
 assert.match(r.getSnapshot().reason,/temporarily unavailable/i);
 assert.equal(salesCapabilityShell(true,r.getSnapshot()),'unavailable');
 r.dispose();
});

test('workspace-picker derives the shell from the explicit state and suppresses legacy content while blocked',()=>{
 const source=readFileSync('features/live/workspace-picker.tsx','utf8');
 assert.match(source,/const shell=salesCapabilityShell\(conversationEnabled,capability\)/);
 assert.match(source,/const conversationHome=shell==='conversation'/);
 assert.match(source,/const capabilityBlocked=shell==='checking'\|\|shell==='unavailable'/);
 assert.match(source,/isLiveOverviewRoute\(pathname,conversationHome\)&&!capabilityBlocked/);
 assert.match(source,/shell==='checking' && <section className="panel" role="status"/);
 assert.match(source,/shell==='unavailable' && <section className="panel" role="alert"/);
 assert.match(source,/capability\.retry\(\)/);
 assert.match(source,/!capabilityBlocked && !documentsForPath/);
 assert.match(source,/discussionForPath\(pathname,conversationHome\)/);
 assert.match(source,/discussion && <LiveConversation/);
});

test('a scope change aborts the in-flight read and a stale answer cannot flip state',async()=>{
 const scope=session(),oldIdentity=scope.identity();let signal,resolve;
 const r=reader({request:input=>{signal=input.signal;return new Promise(done=>{resolve=done;});}},scope);
 r.start();await flush();
 assert.equal(r.getSnapshot().status,'loading');
 scope.next({project:'other'});
 assert.equal(signal.aborted,true,'the scope change aborts the shared capability read');
 resolve({admission_enabled:true});await flush();await flush();
 assert.notEqual(r.getSnapshot().status,'enabled');
 assert.equal(r.getSnapshot().identity,oldIdentity);
});

test('shell decision renders the legacy shell only for a genuine disabled answer',()=>{
 const state=(status,extra={})=>({status,identity:'i',reason:'',attempts:0,refreshing:false,updatedAt:0,retry:()=>{},...extra});
 assert.equal(salesCapabilityShell(false,state('idle')),'legacy');
 assert.equal(salesCapabilityShell(true,state('idle')),'checking');
 assert.equal(salesCapabilityShell(true,state('loading')),'checking');
 assert.equal(salesCapabilityShell(true,state('enabled')),'conversation');
 assert.equal(salesCapabilityShell(true,state('disabled')),'legacy');
 assert.equal(salesCapabilityShell(true,state('unavailable',{reason:'Service temporarily unavailable. Retry after checking the status.'})),'unavailable');
});

test('new notices ship as EN/zh-HK pairs for locale integration',()=>{
 for(const key of Object.keys(salesCapabilityCopy.en)){
  assert.equal(typeof salesCapabilityCopy.en[key],'string');
  assert.equal(typeof salesCapabilityCopy['zh-HK'][key],'string');
  assert.notEqual(salesCapabilityCopy.en[key],salesCapabilityCopy['zh-HK'][key]);
  assert.equal(salesCapabilityText('zh-HK',key),salesCapabilityCopy['zh-HK'][key]);
 }
});

test('two mounted consumers share one capability read and a focus/location storm adds none',async()=>{
 const oldWindow=globalThis.window,events=new EventTarget();
 const hooks={effects:[],snapshots:[]};
 globalThis.window=events;
 globalThis.__capabilityHooks={
  useEffect:(fn,deps)=>{hooks.effects.push({fn,deps});return()=>{};},
  useSyncExternalStore:(subscribe,get)=>{subscribe(()=>hooks.snapshots.push(get()));return get();},
 };
 try{
  const scope=session(),requests=[];
  const client={request:async input=>{requests.push(input);return {admission_enabled:true};}};
  const first=capability.useSalesCapability(client,scope,true);
  const second=capability.useSalesCapability(client,scope,true);
  assert.equal(first.status,'idle');assert.equal(second.status,'idle');
  const cleanups=hooks.effects.map(({fn})=>fn());
  await flush();await flush();
  assert.equal(requests.length,1,'two components share one capability read');
  assert.equal(capability.useSalesCapability(client,scope,true).status,'enabled');
  for(let index=0;index<5;index++){events.dispatchEvent(new Event('focus'));events.dispatchEvent(new Event('buyeros:location'));}
  await flush();await flush();
  assert.equal(requests.length,1,'focus/location immediately after success must not refetch');
  assert.ok(hooks.snapshots.some(snapshot=>snapshot.status==='enabled'));
  cleanups.forEach(cleanup=>cleanup?.());
 }finally{globalThis.window=oldWindow;}
});
