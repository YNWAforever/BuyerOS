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
 assert.equal(button(tree,'Prepare follow-up').props['aria-current'],'page');
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
 assert.equal(discussionForPath('/app',true)?.id,'prepare-follow-up');
 assert.equal(discussionForPath('/app/discussions/review-buyers',true)?.id,'review-buyers');
 assert.equal(discussionForPath('/app/discussions/new',true)?.id,'new');
 assert.equal(discussionForPath('/app/discussions/unknown',true),undefined);
 assert.equal(discussionForPath('/app/discussions/prepare-follow-up',false),undefined);
});

test('Stage 0 ON headings and breadcrumb describe the selected discussion',()=>{
 assert.equal(liveRouteMeta('/app',false).title,'Overview');
 assert.equal(liveRouteMeta('/app',true).title,'Prepare follow-up');
 assert.equal(liveRouteMeta('/app/overview',true).title,'Overview');
 assert.equal(liveRouteMeta('/app/discussions/review-buyers',true).title,'Review buyers');
 const frame=LiveFrame({t:x=>x,pathname:'/app',conversationHome:true,navigation:null,footer:null,header:null,children:null});
 assert.match(renderToStaticMarkup(frame),/<h1>Prepare follow-up<\/h1>/);
 const topbar=LiveTopbar({t:x=>x,pathname:'/app',conversationHome:true,languagePicker:null,signOut:null});
 assert.match(renderToStaticMarkup(topbar),/<b>Prepare follow-up<\/b>/);
});

test('Stage 0 illustrative output, templates and results only navigate to existing modules',async t=>{
 const {LiveDiscussion}=await import('../features/live/discussion.tsx');
 const {discussionForPath}=await import('../features/live/conversation-home.ts');
 const routes=[];let calls=0;t.mock.method(globalThis,'fetch',()=>{calls++;throw Error('No Stage 0 network calls');});
 const tree=LiveDiscussion({t:x=>x,discussion:discussionForPath('/app',true),navigate:path=>routes.push(path)});
 const html=renderToStaticMarkup(tree);
 assert.match(html,/Illustrative conversation/);assert.match(html,/No research, approval or save is executed/);
 for(const [label,path] of [['Preview output / Opens in Drafts','/app/outreach'],['Browse templates in Drafts','/app/outreach'],['Open Results','/app/results']]){
  button(tree,label).props.onClick();assert.equal(routes.at(-1),path);
 }
 assert.equal(calls,0);
 const composer=nodes(tree).find(n=>n.type==='textarea');assert.equal(composer.props.disabled,true);
 assert.equal(button(tree,'Send').props.disabled,true);
});
