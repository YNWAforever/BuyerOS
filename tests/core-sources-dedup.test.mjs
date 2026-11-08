import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';

// Execute the production source picker with hook state captured in memory. No API,
// DB, timers, credentials or provider connections are used.
let code=ts.transpileModule(readFileSync('features/live/sales-skills/sources.tsx','utf8'),{
 compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
code=code.replace(/^import .*;\r?\n/gm,'');
code=`const useEffect=(...args)=>globalThis.__sourcesHooks.useEffect(...args),useState=(...args)=>globalThis.__sourcesHooks.useState(...args),_jsx=(type,props)=>({type,props}),_jsxs=_jsx;
class LiveCancelled extends Error{}
const salesError=error=>'notice:'+((error&&error.message)||'failed');
const salesTasks=(...args)=>globalThis.__sourcesDeps.salesTasks(...args);
const loadDiscussionContext=(...args)=>globalThis.__sourcesDeps.loadDiscussionContext(...args);
`+code;
globalThis.__sourcesHooks={useEffect:()=>{},useState:initial=>[initial,()=>{}]};
const {loadSourceChoices,sourceChoiceLabel,SelectedSources}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));

test('source choices map native, fact, document and output refs in one read burst',async()=>{
 const signal=new AbortController().signal,seen=[];
 const api={
  getAbortable:async(path,lifetime)=>{seen.push([path,lifetime]);return path===''?{offer_revision:7}:
   {items:[{id:'out1',revision:2,kind:'outreach_preparation',availability:'available'},{id:'out2',revision:1,kind:'followup_preparation',availability:'pending'}]};},
  nativeSources:async lifetime=>{seen.push(['native-sources',lifetime]);return {items:[{label:'buyer 12345678',ref:{id:'buyer-1',version:3,kind:'buyer',locator:'buyer:buyer-1',retention_class:'durable'}}]};},
 };
 const sections=[{title:'Documents & outputs',items:[
  {id:'fact:profile:profile-1:fact-1',title:'Price band',status:'approved'},
  {id:'fact:profile:profile-1:fact-2',title:'Unapproved',status:'candidate'},
  {id:'document:document-1',title:'brief.pdf',status:'ready'},
  {id:'document:document-2',title:'parsing.pdf',status:'parsing'},
 ]}];
 const rows=await loadSourceChoices(api,lifetime=>{seen.push(['context',lifetime]);return Promise.resolve(sections);},signal);
 assert.deepEqual(rows.map(row=>row.kind),['buyer','project_fact','document','output']);
 assert.deepEqual(rows.find(row=>row.kind==='project_fact').ref,{id:'fact-1',kind:'project_fact',version:7,locator:'fact:profile:profile-1:fact-1',retention_class:'durable'});
 assert.equal(rows.find(row=>row.kind==='document').ref.id,'document-1');
 assert.equal(rows.filter(row=>row.kind==='output').length,1);
 assert.equal(rows.find(row=>row.kind==='output').labelKind,'outreach_preparation','the output kind stays available for render-time localization');
 assert.equal(seen.length,4);
 assert.ok(seen.every(([,lifetime])=>lifetime===signal),'every read shares the caller-owned lifetime');
});

test('an aborted source burst rejects instead of applying a stale answer',async()=>{
 const controller=new AbortController();
 const api={getAbortable:async()=>({offer_revision:1}),nativeSources:async()=>({items:[]})};
 const pending=loadSourceChoices(api,()=>Promise.resolve([]),controller.signal);
 controller.abort();
 await assert.rejects(pending,{message:'cancelled'});
});

test('choice labels localize at render time and preserve server labels',()=>{
 assert.equal(sourceChoiceLabel({kind:'output',ref:{version:2}},value=>`T(${value})`),'T(output) · 2');
 assert.equal(sourceChoiceLabel({kind:'output',labelKind:'outreach_preparation',ref:{version:2}},value=>`T(${value})`),'T(outreach preparation) · 2');
 assert.equal(sourceChoiceLabel({label:'brief.pdf',kind:'document',ref:{version:1}},()=>''),'brief.pdf');
});

test('rerenders do not re-issue the source reads and no read starts before the effect',()=>{
 const hooks={effects:[]};
 globalThis.__sourcesHooks={useEffect:(fn,deps)=>{hooks.effects.push({fn,deps});return()=>{};},useState:initial=>[initial,()=>{}]};
 const session={identity:()=>'identity',isCurrent:id=>id==='identity'};
 const client={};
 let reads=0;
 const api={getAbortable:async()=>({offer_revision:1}),nativeSources:async()=>({items:[]})};
 globalThis.__sourcesDeps={salesTasks:()=>{reads++;return api;},loadDiscussionContext:()=>Promise.resolve([])};
 const render=(t)=>SelectedSources({client,session,t,navigate:()=>{},sources:[],setSources:()=>{},disabled:false});
 const english=value=>`EN:${value}`,chinese=value=>`ZH:${value}`;
 render(english);render(chinese);
 assert.equal(hooks.effects.length,2,'each render registers its effect');
 const [first,second]=hooks.effects;
 assert.equal(first.deps.length,3,'effect depends on client, session and identity only');
 assert.ok(Object.is(first.deps[0],second.deps[0])&&Object.is(first.deps[1],second.deps[1])&&Object.is(first.deps[2],second.deps[2]),'deps stay referentially stable across a translation-only rerender');
 assert.ok(!first.deps.includes(english)&&!first.deps.includes(chinese),'the unstable translation function is not an effect dependency');
 assert.equal(reads,0,'rendering alone never issues reads');
 const cleanup=first.fn();
 assert.equal(reads,1);
 cleanup();
});

test('cleanup aborts every stale source read instead of only ignoring results',()=>{
 const hooks={effects:[]};
 globalThis.__sourcesHooks={useEffect:(fn,deps)=>{hooks.effects.push({fn,deps});return()=>{};},useState:initial=>[initial,()=>{}]};
 const session={identity:()=>'identity',isCurrent:id=>id==='identity'};
 const signals=[];
 const pending=lifetime=>{signals.push(lifetime);return new Promise((_resolve,reject)=>lifetime.addEventListener('abort',()=>reject(new Error('aborted')),{once:true}));};
 globalThis.__sourcesDeps={
  salesTasks:()=>({getAbortable:(_path,lifetime)=>pending(lifetime),nativeSources:lifetime=>pending(lifetime)}),
  loadDiscussionContext:(_client,_session,options)=>pending(options.signal),
 };
 SelectedSources({client:{},session,t:value=>value,navigate:()=>{},sources:[],setSources:()=>{},disabled:false});
 const cleanup=hooks.effects[0].fn();
 assert.equal(signals.length,4,'context, project, outputs and native sources share one burst');
 assert.ok(signals.every(lifetime=>!lifetime.aborted));
 cleanup();
 assert.ok(signals.every(lifetime=>lifetime.aborted),'unmount aborts the in-flight reads');
});
