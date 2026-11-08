import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
import {loadModule,moduleUrl} from './ts-loader.mjs';

const {SessionScope}=await loadModule('services/live/session.ts');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
// Execute the production capability hook with hook state captured in memory.
// No API, DB, timers, credentials or provider connections are used.
function capabilitySource(){
 let source=ts.transpileModule(readFileSync('features/live/sales-skills/capability.ts','utf8'),{
  compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
 source=source.replace(/import\s*\{[^}]*\}\s*from\s*['"]react['"];?/, 'const useEffect=(...args)=>globalThis.__nativeSalesHooks.useEffect(...args),useSyncExternalStore=(...args)=>globalThis.__nativeSalesHooks.useSyncExternalStore(...args);')
  .replace(/from ['"](@\/[^'"]+)['"]/g,(_,spec)=>'from '+JSON.stringify(moduleUrl(spec.slice(2)+'.ts')));
 return 'data:text/javascript;base64,'+Buffer.from(source).toString('base64');
}
async function fixture(enabled,{request:requestImpl}={}){
 const oldWindow=globalThis.window,events=new EventTarget(),effects=[],snapshots=[],requests=[];
 const session=new SessionScope({mode:'live',actor:'fixture',workspace:'workspace',project:'project'});session.setToken('synthetic');
 globalThis.window=events;
 globalThis.__nativeSalesHooks={
  useEffect:(fn,deps)=>{effects.push({fn,deps});return()=>{};},
  useSyncExternalStore:(subscribe,get)=>{subscribe(()=>snapshots.push(get()));return get();},
 };
 const client=requestImpl?{request:requestImpl}:{request:async input=>{requests.push(input);return {admission_enabled:true};}};
 const {useSalesCapability:runHook}=await import(capabilitySource());
 const run=()=>runHook(client,session,enabled);
 const settle=async()=>{const cleanups=effects.map(({fn})=>fn());await tick();await tick();return cleanups;};
 return {events,requests,snapshots,session,run,settle,dispose(cleanups){cleanups?.forEach(fn=>fn?.());globalThis.window=oldWindow;}};
}
test('disabled conversation admission adds no capability reads to native offer navigation or focus',async()=>{
 const f=await fixture(false);
 try{f.events.dispatchEvent(new Event('buyeros:location'));f.events.dispatchEvent(new Event('focus'));await tick();assert.equal(f.requests.length,0);assert.ok(f.snapshots.every(snapshot=>snapshot.status==='idle'));}
 finally{f.dispose();}
});
test('enabled admission shares one capability read per identity and a focus/location storm adds none',async()=>{
 const f=await fixture(true);let cleanups;
 try{
  assert.equal(f.run().status,'idle');assert.equal(f.run().status,'idle');
  cleanups=await f.settle();
  assert.equal(f.requests.length,1,'two mounted consumers share one in-flight capability read');
  assert.equal(f.run().status,'enabled');
  for(let index=0;index<5;index++){f.events.dispatchEvent(new Event('focus'));f.events.dispatchEvent(new Event('buyeros:location'));}
  await tick();
  assert.equal(f.requests.length,1,'one focus/location storm right after a successful read adds no request');
  assert.ok(f.snapshots.some(snapshot=>snapshot.status==='enabled'));
 }
 finally{f.dispose(cleanups);}
});
test('a scope change aborts the shared capability read and a stale answer cannot enable the old identity',async()=>{
 let signal,resolve;const requests=[];
 const client={request:input=>{requests.push(input);signal=input.signal;return new Promise(done=>{resolve=done;});}};
 const f=await fixture(true,{request:client.request});let cleanups;
 try{
  const oldIdentity=f.session.identity();
  assert.equal(f.run().status,'idle');
  cleanups=await f.settle();
  assert.equal(requests.length,1);
  assert.equal(f.run().status,'loading');
  f.session.next({project:'other'});
  assert.equal(signal.aborted,true,'scope change aborts the shared capability read');
  resolve({admission_enabled:true});await tick();await tick();
  assert.ok(!f.snapshots.some(snapshot=>snapshot.identity===oldIdentity&&snapshot.status==='enabled'),'a late answer cannot flip the previous identity');
 }
 finally{f.dispose(cleanups);}
});

test('native linked outputs mount their reader only after the user opens the disclosure',async()=>{
 let open=false;
 globalThis.__nativeLinksHooks={useMemo:fn=>fn(),useState:()=>[open,next=>{open=next;}],useRouter:()=>({}),useWorkspaceSession:()=>({session:{},client:{}}),useSessionSnapshot:()=>({identity:'fixture',scope:{}})};
 let code=ts.transpileModule(readFileSync('features/live/sales-skills/native-links.tsx','utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
 code=code.replace(/^import .*;\r?\n/gm,'');
 code='const {useMemo,useState,useRouter,useWorkspaceSession,useSessionSnapshot}=globalThis.__nativeLinksHooks; const liveZh={}; const SalesDocuments=()=>null; const _jsx=(type,props)=>({type,props}),_jsxs=_jsx;\n'+code;
 const {NativeSalesLinks}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
 const props={surface:'buyer',id:'fixture-buyer'};
 const closed=NativeSalesLinks(props);assert.equal(closed.props.children[1],false,'closed linked outputs must not mount SalesDocuments or fetch');
 closed.props.onToggle({currentTarget:{open:true}});
 const opened=NativeSalesLinks(props);assert.equal(opened.props.children[1].props.native.id,'fixture-buyer');
 opened.props.onToggle({currentTarget:{open:false}});assert.equal(NativeSalesLinks(props).props.children[1].props.native.id,'fixture-buyer','collapse retains the mounted editor and its local work');
});
