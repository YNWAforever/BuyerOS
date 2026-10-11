import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
import {moduleUrl,loadModule} from './ts-loader.mjs';
const {SessionScope}=await loadModule('services/live/session.ts');
const {LiveError}=await loadModule('services/live/client.ts');
// Run the actual component read effect. Hook/context stand-ins only capture state;
// this fixture is not browser, genuine Auth, real provider or human acceptance.
let source=ts.transpileModule(fs.readFileSync('features/live/profile.tsx','utf8'),{compilerOptions:{
 module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
source=source.replace(/import\s*\{\s*useEffect,\s*useRef,\s*useState\s*\}\s*from\s*["']react["'];/,
 'const useEffect=(...args)=>globalThis.__c61ProfileHookFixture.useEffect(...args),useRef=(...args)=>globalThis.__c61ProfileHookFixture.useRef(...args),useState=(...args)=>globalThis.__c61ProfileHookFixture.useState(...args);')
 .replace(/import\s*\{\s*useWorkspaceSession\s*\}\s*from\s*["']@\/features\/providers\/workspace-session["'];/,
 'const useWorkspaceSession=()=>globalThis.__c61ProfileHookFixture.value;')
 .replace(/from\s*(["'])(@\/[^"']+)\1/g,(_all,_quote,spec)=>'from '+JSON.stringify(moduleUrl(spec.slice(2)+'.ts')))
 .replace(/from\s*["']react\/jsx-runtime["']/g,'from '+JSON.stringify(import.meta.resolve('react/jsx-runtime')));
assert.ok(source.includes('const useEffect=(...args)=>globalThis.__c61ProfileHookFixture.useEffect(...args),useRef=(...args)=>globalThis.__c61ProfileHookFixture.useRef(...args),useState=(...args)=>globalThis.__c61ProfileHookFixture.useState(...args);'));
const url='data:text/javascript;base64,'+Buffer.from(source).toString('base64');
function deferred(){let resolve;const promise=new Promise(r=>{resolve=r;});return {promise,resolve};}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const page=(offset=0,total=1)=>({items:[{id:'icp-'+offset,project_id:'project',number:offset+1}],offset,limit:100,total});
async function fixture(request){
 const previousWindow=globalThis.window,states=[],calls=[],scope=new SessionScope({mode:'live',actor:'owned',workspace:'ws',project:'project'});scope.setToken('fixture-only');let cleanup;
 globalThis.window={location:{search:''}};
 globalThis.__c61ProfileHookFixture={value:{session:scope,client:{request(input){calls.push(input);return request(input);}}},
  useEffect(fn){cleanup=fn();},useRef(value){return {current:value};},useState(initial){let value=initial;return [value,next=>{value=typeof next==='function'?next(value):next;states.push(value);}];}};
 const {LiveProfilePanel}=await import(url);LiveProfilePanel({});
 return {scope,calls,states,async dispose(){cleanup?.();await tick();globalThis.window=previousWindow;delete globalThis.__c61ProfileHookFixture;}};
}

test('C61 profile starts owned project and first history reads without waiting for either response',async()=>{
 const project=deferred(),history=deferred();const f=await fixture(input=>input.path.includes('/icp-versions')?history.promise:project.promise);
 try{
  await tick();assert.equal(f.calls.length,2,'history must begin while independent project read is pending');
  assert.ok(f.calls.every(input=>input.token==='fixture-only'&&input.scope===f.scope.identity()&&!input.signal.aborted));
 }finally{project.resolve({id:'project',workspace_id:'ws',active_icp_version_id:'icp-0'});history.resolve(page());await tick();await tick();await f.dispose();}
});
test('C61 profile keeps subsequent history pages sequential and does not publish partial history',async()=>{
 const first=deferred(),last=deferred();const f=await fixture(input=>!input.path.includes('/icp-versions')?Promise.resolve({id:'project',workspace_id:'ws'}):input.path.includes('offset=0')?first.promise:last.promise);
 try{
  await tick();assert.equal(f.calls.filter(c=>c.path.includes('/icp-versions')).length,1);
  first.resolve({...page(0,101),items:Array.from({length:100},(_,i)=>({id:'icp-'+i,project_id:'project',number:i+1}))});await tick();
  assert.ok(f.calls.some(c=>c.path.endsWith('offset=100&limit=100')));assert.equal(f.states.some(s=>s?.kind==='ready'),false);
  last.resolve(page(100,101));await tick();const ready=f.states.find(s=>s?.kind==='ready');assert.equal(ready.versions.length,101);assert.equal(ready.versions[0].number,101);
 }finally{first.resolve(page());last.resolve(page(100,101));await f.dispose();}
});
test('C61 profile denies a current history403 without exposing project as a ready approved profile',async()=>{
 const f=await fixture(input=>input.path.includes('/icp-versions')?Promise.reject(new LiveError('denied','FORBIDDEN',403,'fixture-request',false)):Promise.resolve({id:'project',workspace_id:'ws',active_icp_version_id:'icp-0'}));
 try{await tick();await tick();assert.equal(f.states.some(s=>s?.kind==='ready'),false);assert.ok(f.states.some(s=>s?.kind==='error'&&s.message.includes('permission')));}finally{await f.dispose();}
});
test('C61 profile ignores late project/history replies after A-B-A and aborts both owned requests',async()=>{
 const project=deferred(),history=deferred();const f=await fixture(input=>input.path.includes('/icp-versions')?history.promise:project.promise);
 try{await tick();f.scope.next({project:'other'});f.scope.next({project:'project'});project.resolve({id:'project',workspace_id:'ws'});history.resolve(page());await tick();await tick();assert.equal(f.states.some(s=>s?.kind==='ready'),false);assert.ok(f.calls.every(c=>c.signal.aborted));}finally{project.resolve({id:'project'});history.resolve(page());await f.dispose();}
});
