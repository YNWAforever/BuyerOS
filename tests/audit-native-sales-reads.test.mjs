import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
import {loadModule,moduleUrl} from './ts-loader.mjs';

const {SessionScope}=await loadModule('services/live/session.ts');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
// Execute the production capability hook with hook state captured in memory.
// No API, DB, timers, credentials or provider connections are used.
let source=ts.transpileModule(readFileSync('features/live/sales-skills/capability.ts','utf8'),{
 compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
source=source.replace(/import .* from ['"]react['"];?/, 'const useEffect=(...args)=>globalThis.__nativeSalesHooks.useEffect(...args),useState=(...args)=>globalThis.__nativeSalesHooks.useState(...args),useSyncExternalStore=(...args)=>globalThis.__nativeSalesHooks.useSyncExternalStore(...args);')
 .replace(/from ['"](@\/[^'"]+)['"]/g,(_,spec)=>'from '+JSON.stringify(moduleUrl(spec.slice(2)+'.ts')));
async function fixture(enabled){
 const oldWindow=globalThis.window,events=new EventTarget(),effects=[],states=[],requests=[];
 const session=new SessionScope({mode:'live',actor:'fixture',workspace:'workspace',project:'project'});session.setToken('synthetic');
 globalThis.window=events;
 globalThis.__nativeSalesHooks={useEffect:fn=>effects.push(fn),useState:initial=>[initial,value=>states.push(value)],useSyncExternalStore:(_subscribe,get)=>get()};
 const {useSalesCapability:runHook}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
 runHook({request:async input=>{requests.push(input);return {admission_enabled:true};}},session,enabled);
 const cleanups=effects.map(fn=>fn());await tick();
 return {events,requests,states,session,dispose(){cleanups.forEach(fn=>fn?.());globalThis.window=oldWindow;}};
}
test('disabled conversation admission adds no capability reads to native offer navigation or focus',async()=>{
 const f=await fixture(false);
 try{f.events.dispatchEvent(new Event('buyeros:location'));f.events.dispatchEvent(new Event('focus'));await tick();assert.equal(f.requests.length,0);assert.equal(f.states.length,0);}
 finally{f.dispose();}
});
test('enabled admission still rechecks current policy on entry, focus and navigation',async()=>{
 const f=await fixture(true);
 try{assert.equal(f.requests.length,1);f.events.dispatchEvent(new Event('focus'));await tick();f.events.dispatchEvent(new Event('buyeros:location'));await tick();assert.equal(f.requests.length,3);assert.ok(f.requests.every(r=>r.path.endsWith('/sales-tasks/capability')));assert.ok(f.states.every(s=>s.identity===f.session.identity()&&s.enabled));}
 finally{f.dispose();}
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
