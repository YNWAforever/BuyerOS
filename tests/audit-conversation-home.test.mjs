import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
import {renderToStaticMarkup} from 'react-dom/server';
const root=resolve('.'),rootUrl=pathToFileURL(root+'/').href;
registerHooks({resolve(specifier,context,next){
 if(specifier.startsWith('@/'))specifier=pathToFileURL(resolve(root,specifier.slice(2))).href;
 try{return next(specifier,context);}catch(error){
  if(error.code!=='ERR_MODULE_NOT_FOUND'||!context.parentURL?.startsWith(rootUrl))throw error;
  for(const ext of ['.ts','.tsx']){try{return next(specifier+ext,context);}catch{}}
  throw error;
 }
},load(url,context,next){
 if(url.startsWith(rootUrl)&&/\.tsx?$/.test(url))return {format:'module',shortCircuit:true,source:ts.transpileModule(readFileSync(new URL(url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText};
 return next(url,context);
}});
const {LiveNavigation}=await import('../features/live/navigation.tsx');
const {liveRouteMeta,LiveFrame,LiveTopbar}=await import('../features/live/shell.tsx');
const props={t:x=>x,navigate:()=>{},pathname:'/app',authorized:true,projectKnown:true,canEdit:true,projectActive:true,canCreate:true};
function nodes(node){if(Array.isArray(node))return node.flatMap(nodes);if(!node||typeof node!=='object')return [];return [node,...nodes(node.props?.children)];}
function copy(node){if(Array.isArray(node))return node.map(copy).join('');if(typeof node==='string')return node;return copy(node?.props?.children??[]);}
function button(tree,label){const found=nodes(tree).find(n=>n.type==='button'&&copy(n)===label);assert.ok(found,`Missing button: ${label}`);return found;}

test('Stage 0 OFF retains #35 Overview and navigation groups',()=>{
 const routes=[];const tree=LiveNavigation({...props,navigate:path=>routes.push(path),conversationHome:false});
 const html=renderToStaticMarkup(tree);
 for(const label of ['Discover &amp; review','Follow up','Manage'])assert.ok(html.includes(label));
 assert.ok(!html.includes('New discussion'));assert.ok(!html.includes('Project work (retained)'));
 button(tree,'Overview').props.onClick();assert.deepEqual(routes,['/app']);
 assert.equal(button(tree,'Overview').props['aria-current'],'page');
});

test('Stage 0 ON exposes discussions and every retained module destination',()=>{
 const routes=[];const tree=LiveNavigation({...props,navigate:path=>routes.push(path),conversationHome:true});
 assert.match(renderToStaticMarkup(tree),/Discussions/);assert.match(renderToStaticMarkup(tree),/Project work \(retained\)/);
 const expected=[['New discussion','/app/discussions/new'],['Prepare follow-up','/app/discussions/prepare-follow-up'],['Review buyers','/app/discussions/review-buyers'],['Overview','/app/overview'],['Offer','/app/discover/edit'],['Research runs','/app/runs'],['Buyers','/app/discover'],['Drafts','/app/outreach'],['Results','/app/results'],['Settings','/app/settings'],['Operations','/app/operations']];
 for(const [label,path] of expected){const b=button(tree,label);assert.equal(b.props.disabled,false);b.props.onClick();assert.equal(routes.at(-1),path);}
 assert.equal(button(tree,'Prepare follow-up').props['aria-current'],undefined);
 assert.equal(button(tree,'Overview').props['aria-current'],undefined);
 const overview=LiveNavigation({...props,conversationHome:true,pathname:'/app/overview'});
 assert.equal(button(overview,'Overview').props['aria-current'],'page');
});

test('Stage 0 retains project and permission gates in both flag states',()=>{
 for(const conversationHome of [false,true]){
  const tree=LiveNavigation({...props,conversationHome,authorized:false,projectKnown:false,canEdit:false,canCreate:false});
  for(const label of ['Offer','Research runs','Buyers','Drafts','Results','Settings','Operations'])assert.equal(button(tree,label).props.disabled,true,label);
  if(conversationHome)assert.equal(button(tree,'New discussion').props.disabled,true);
  const paths=[];const create=LiveNavigation({...props,conversationHome,projectKnown:false,navigate:p=>paths.push(p)});
  button(create,'Offer').props.onClick();assert.deepEqual(paths,['/app/discover/new']);
 }
});

test('Stage 0 flag is opt-in and routes retain the Overview rollback',async()=>{
 const {conversationHomeEnabled,isLiveOverviewRoute,discussionForPath}=await import('../features/live/conversation-home.ts');
 for(const value of [undefined,'','false','0','TRUE'])assert.equal(conversationHomeEnabled(value),false);
 assert.equal(conversationHomeEnabled('true'),true);
 assert.equal(isLiveOverviewRoute('/app',false),true);assert.equal(isLiveOverviewRoute('/app',true),false);
 assert.equal(isLiveOverviewRoute('/app/overview',true),true);assert.equal(isLiveOverviewRoute('/app/overview',false),false);
 assert.equal(discussionForPath('/app',true)?.id,'home');
 assert.equal(discussionForPath('/app/discussions/review-buyers',true)?.id,'review-buyers');
 assert.equal(discussionForPath('/app/discussions/new',true)?.id,'new');
 assert.equal(discussionForPath('/app/discussions/unknown',true),undefined);
 assert.equal(discussionForPath('/app/discussions/prepare-follow-up',false),undefined);
});

test('Stage 0 ON headings and breadcrumb describe the selected discussion',()=>{
 assert.equal(liveRouteMeta('/app',false).title,'Overview');
 assert.equal(liveRouteMeta('/app',true).title,'Discussions');
 assert.equal(liveRouteMeta('/app/overview',true).title,'Overview');
 assert.equal(liveRouteMeta('/app/discussions/review-buyers',true).title,'Review buyers');
 const frame=LiveFrame({t:x=>x,pathname:'/app',conversationHome:true,navigation:null,footer:null,header:null,children:null});
 assert.match(renderToStaticMarkup(frame),/<h1>Discussions<\/h1>/);
 const topbar=LiveTopbar({t:x=>x,pathname:'/app',conversationHome:true,languagePicker:null,signOut:null});
 assert.match(renderToStaticMarkup(topbar),/<b>Discussions<\/b>/);
});

test('Stage 1 rendering sends locally and source/destination actions only invoke callbacks',async t=>{
 const {LiveDiscussion}=await import('../features/live/discussion.tsx');
 const routes=[];let calls=0,sends=0; t.mock.method(globalThis,'fetch',()=>{calls++;throw Error('No action network calls');});
 const tree=LiveDiscussion({t:x=>x,locale:'en',thread:null,threads:[],value:'A local question',notice:'',context:[],navigate:p=>routes.push(p),onTemplate:()=>{},onChange:()=>{},onSend:()=>sends++,onSource:()=>{},onRefresh:()=>{}});
 const html=renderToStaticMarkup(tree);assert.match(html,/Guided step · no AI/);assert.match(html,/Saved on this device only/);
 for(const [label,path] of [['Open in Drafts','/app/outreach'],['Open in Results','/app/results'],['Open in Research runs','/app/runs']]){button(tree,label).props.onClick();assert.equal(routes.at(-1),path);}
 nodes(tree).find(n=>n.type==='form').props.onSubmit({preventDefault(){}});assert.equal(sends,1);assert.equal(calls,0);
 assert.equal(nodes(tree).find(n=>n.type==='textarea').props.disabled,undefined);assert.equal(button(tree,'Send').props.disabled,false);
});

test('Stage 1 has six native templates and strictly opt-in local routes',async()=>{
 const {guidedTemplates,discussionForPath}=await import('../features/live/conversation-home.ts');
 assert.deepEqual(guidedTemplates.map(({title,path})=>[title,path]),[
  ['Guide my first project','/app/discover/edit'],['Understand my documents','/app/discover/edit'],
  ['Research a market','/app/runs'],['Review & shortlist buyers','/app/discover'],
  ['Check a company','/app/discover'],['Prepare a follow-up','/app/outreach']]);
 assert.equal(discussionForPath('/app',true)?.id,'home');
 assert.equal(discussionForPath('/app/discussions/local-12345678-1234-4123-8123-123456789012',true)?.title,'Discussion');
 assert.equal(discussionForPath('/app/discussions/local-12345678-1234-4123-8123-123456789012',false),undefined);
 for(const item of guidedTemplates){assert.ok(item.prompt);assert.ok(item.question);assert.ok(item.choices.length>1);}
});

test('Stage 1 audit covers storage isolation, corrupt recovery, OFF no-storage and zero-network actions',async t=>{
 const {DiscussionStore}=await import('../services/live/discussions.ts');
 const data=new Map();let touched=0,network=0;
 const storage={getItem:k=>{touched++;return data.get(k)??null;},setItem:(k,v)=>{touched++;data.set(k,v);}};
 const scope={actor:'actor-a',workspace:'workspace-a',project:'project-a'};
 const off=new DiscussionStore(false,scope,storage);assert.equal(off.create('custom','Off'),null);assert.equal(touched,0);
 t.mock.method(globalThis,'fetch',()=>{network++;throw Error('Local actions cannot use network');});
 const store=new DiscussionStore(true,scope,storage);
 const {guidedTemplates}=await import('../features/live/conversation-home.ts');
 for(const item of guidedTemplates){const thread=store.create(item.id,item.prompt);assert.ok(thread);assert.ok(store.append(thread.id,'My local step'));}
 const thread=store.getSnapshot().threads[0];store.select(thread.id,{id:'document:doc-1',label:'Offer document'},true);
 assert.equal(network,0);assert.equal(data.size,1);assert.ok(data.has('buyeros.discussions.v1:actor-a:workspace-a:project-a'));
 assert.equal(new DiscussionStore(true,{...scope,project:'project-b'},storage).getSnapshot().threads.length,0);
 assert.equal(new DiscussionStore(true,{...scope,actor:'actor-b'},storage).getSnapshot().threads.length,0);
 assert.equal(new DiscussionStore(true,scope,storage).getSnapshot().threads.length,6);
 data.set('buyeros.discussions.v1:actor-a:workspace-a:project-a','{corrupt');
 const corrupt=new DiscussionStore(true,scope,storage);assert.equal(corrupt.getSnapshot().threads.length,0);assert.ok(corrupt.getSnapshot().notice);
});

test('Stage 1 locale covers templates, deterministic guidance, context and storage notices',async()=>{
 const {liveZh}=await import('../features/live/locale.ts');
 const {zh}=await import('../locales/index.ts');
 const {guidedTemplates,customGuidance}=await import('../features/live/conversation-home.ts');
 for(const item of [...guidedTemplates,customGuidance])for(const text of [item.title,item.prompt,item.question,...item.choices,`Open in ${item.destination}`].filter(Boolean))assert.ok(liveZh[text],text);
 for(const file of ['features/live/discussion.tsx','features/live/discussion-workspace.tsx']){
  const source=readFileSync(file,'utf8');for(const [,text] of source.matchAll(/\bt\('([^']+)'\)/g))assert.ok(liveZh[text]||zh[text]||['Discussion','Templates','Saved results','Send','Discussion workspace'].includes(text),text);
 }
 const source=readFileSync('services/live/discussions.ts','utf8');
 for(const [,text] of source.matchAll(/(?:notice: |ignore\(|refuse\(|notice = |memoryNotice = )'([^']+)'/g))if(text)assert.ok(liveZh[text],text);
});

test('Stage 1 stays behind membership/project checks and existing guarded navigation',()=>{
 const source=readFileSync('features/live/workspace-picker.tsx','utf8');
 assert.match(source,/authorized && projectKnown && discussion && <LiveConversation/);
 assert.match(source,/canViewOffer=\{canEdit&&projectActive\}/);
 assert.match(source,/session\.transition\(async\(\)=>\{if\(mayLeaveOffer\(\)\)\{beginNavigation/);
 assert.match(source,/applyConversationNavigationScope\(target,params,conversationHome\)/);
 assert.match(source,/focusDocument=\{conversationHome\?requested\('document'\)/);
 const controller=readFileSync('features/live/discussion-workspace.tsx','utf8');
 assert.match(controller,/subscribeBeforeClear/);assert.match(controller,/session\.isCurrent\(identity\)/);
 assert.ok(controller.indexOf('if(!conversationHomeEnabled')<controller.indexOf('return <ScopedConversation'));
});

test('source navigation keeps its explicit profile only when conversation home is ON',async()=>{
 const {applyConversationNavigationScope}=await import('../features/live/conversation-home.ts');
 for(const enabled of [false,true]){
  const target=new URL('https://fixture.invalid/app/overview?profile=source-profile');
  applyConversationNavigationScope(target,new URLSearchParams({workspace:'current-ws',project:'current-project',profile:'old-profile'}),enabled);
  assert.equal(target.searchParams.get('profile'),enabled?'source-profile':'old-profile');
  assert.equal(target.searchParams.get('workspace'),'current-ws');assert.equal(target.searchParams.get('project'),'current-project');
 }
});

test('OFF controller never consults session, storage or context',async()=>{
 const {LiveConversation}=await import('../features/live/discussion-workspace.tsx');
 const session=new Proxy({},{get(){throw Error('OFF must not consult discussion dependencies');}});
 assert.equal(LiveConversation({enabled:false,session,client:null,pathname:'/app',locale:'en',t:x=>x,navigate(){},canViewOffer:true,canViewResults:true}),null);
});
