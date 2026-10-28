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
 assert.match(source,/session\.transition\(async\(\)=>\{if\(mayLeaveOffer\(\)\)\{/);
 assert.match(source,/if\(navigateLocalDiscussion\(pathname,target,conversationHome,window.history\)\)return;/);
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

const stage2Profile='a5000000-0000-4000-8000-000000000001',stage2Fact='a6000000-0000-4000-8000-000000000001';
const stage2Ref={id:`fact:profile:${stage2Profile}:${stage2Fact}`,label:'Approved offer fact',locator:{surface:'profile',id:stage2Profile}};
const stage2Reply={text:'Review the cited approved source.',status:'needs_review',fixture:true,citations:[stage2Ref]};
test('Stage 2 saves and restores only verified AI text and citation refs, under existing caps',async()=>{
 const {DiscussionStore}=await import('../services/live/discussions.ts');
 const data=new Map(),storage={getItem:key=>data.get(key)??null,setItem:(key,value)=>data.set(key,value)};
 const scope={actor:'a',workspace:'w',project:'p'},store=new DiscussionStore(true,scope,storage);
 const thread=store.create('custom','Review my offer');store.select(thread.id,{id:stage2Ref.id,label:stage2Ref.label},true);
 assert.equal(store.appendReply(thread.id,'What is approved?',stage2Reply,[stage2Ref.id]),true);
 const restored=new DiscussionStore(true,scope,storage).getSnapshot().threads[0];
 assert.equal(restored.messages.length,3);assert.deepEqual(restored.messages[2].citations,[stage2Ref]);
 assert.equal(restored.messages[2].kind,'ai');assert.equal(Object.isFrozen(restored.messages[2].citations[0].locator),true);
 assert.equal(store.appendReply(thread.id,'stale selection',stage2Reply,[]),false);
 for(const extra of [{body:'PRIVATE_BODY'},{value:'PRIVATE_FACT'},{url:'https://foreign.invalid'}]){
  const bad={...stage2Reply,citations:[{...stage2Ref,...extra}]};assert.equal(store.appendReply(thread.id,'bad',bad,[stage2Ref.id]),false);
 }
 assert.equal([...data.values()].some(raw=>/PRIVATE_BODY|PRIVATE_FACT|foreign.invalid/.test(raw)),false);
 const key=[...data.keys()][0],saved=data.get(key),badSaved=JSON.parse(saved);
 badSaved.threads[0].messages[2].citations[0].locator.body='PRIVATE_BODY';data.set(key,JSON.stringify(badSaved));
 assert.equal(new DiscussionStore(true,scope,storage).getSnapshot().threads.length,0);data.set(key,saved);
 for(let i=3;i<99;i++)assert.equal(store.append(thread.id,'Local note'),true);
 assert.equal(store.appendReply(thread.id,'over message cap',stage2Reply,[stage2Ref.id]),false);
 assert.equal(store.getSnapshot().threads[0].messages.length,99);
});

test('Stage 2 sends only selected IDs and question; OFF, empty, unavailable and stale scope fail closed',async()=>{
 const {askBuyerOS,replyNotices}=await import('../services/live/conversation-reply.ts');
 const {SessionScope}=await import('../services/live/session.ts');
 const {LiveError,LiveCancelled}=await import('../services/live/client.ts');
 const session=new SessionScope({mode:'live',actor:'a',workspace:'w',project:'p'});session.setToken('fixture');
 const requests=[],client={request:async request=>{requests.push(request);return stage2Reply;}};
 const options={enabled:true,question:'What should I review?',sources:[{id:stage2Ref.id,label:stage2Ref.label}],locale:'en',signal:new AbortController().signal};
 for(const bad of [{enabled:false},{sources:[]}])await assert.rejects(askBuyerOS(client,session,{...options,...bad}));
 assert.equal(requests.length,0);assert.deepEqual(await askBuyerOS(client,session,options),stage2Reply);
 assert.equal(requests[0].method,'POST');assert.match(requests[0].path,/\/conversation-reply$/);
 assert.deepEqual(requests[0].body,{question:options.question,source_ids:[stage2Ref.id],language:'en'});
 await assert.rejects(askBuyerOS({request:async()=>{throw new LiveError('raw secret','CONVERSATION_MODEL_UNAVAILABLE',503,'',false);}},session,options),{message:replyNotices.unavailable});
 for(const candidate of [{...stage2Reply,tool_calls:[{}]},{...stage2Reply,citations:[]},{...stage2Reply,citations:[{...stage2Ref,id:stage2Ref.id.replace(stage2Fact,stage2Profile)}]},{...stage2Reply,citations:[{...stage2Ref,locator:{surface:'document',id:stage2Profile}}]}]){
  await assert.rejects(askBuyerOS({request:async()=>candidate},session,options),{message:replyNotices.invalid});
 }
 let resolve;const pending=askBuyerOS({request:()=>new Promise(done=>resolve=done)},session,options);
 await Promise.resolve();session.next({project:'other'});resolve(stage2Reply);await assert.rejects(pending,LiveCancelled);
});

test('Stage 2 optional missing API stays non-blocking and genuine permission denial retains the scope guard',async()=>{
 const {askBuyerOS,replyNotices}=await import('../services/live/conversation-reply.ts');
 const {SessionScope}=await import('../services/live/session.ts');
 const {createLiveClient}=await import('../services/live/client.ts');
 const session=new SessionScope({mode:'live',actor:'a',workspace:'w',project:'p'});session.setToken('fixture');
 let status=404,message='request failed';const client=createLiveClient(async()=>new Response(JSON.stringify({code:'NOT_FOUND',message}),{status}));
 const denied=[];client.subscribeAccessDenied(event=>denied.push(event));
 const options={enabled:true,question:'Review?',sources:[{id:stage2Ref.id,label:stage2Ref.label}],locale:'en',signal:new AbortController().signal};
 await assert.rejects(askBuyerOS(client,session,options),{message:replyNotices.unavailable});assert.equal(denied.length,0);
 status=403;await assert.rejects(askBuyerOS(client,session,options),{message:replyNotices.sources});assert.equal(denied.length,1);
 status=404;message='workspace not found';
 await assert.rejects(askBuyerOS(client,session,options),{message:replyNotices.unavailable});assert.equal(denied.length,2);
 message='unrecognized failure';
 await assert.rejects(askBuyerOS(client,session,options),{message:replyNotices.unavailable});assert.equal(denied.length,3);
 message=undefined;
 await assert.rejects(askBuyerOS(client,session,options),{message:replyNotices.unavailable});assert.equal(denied.length,4);
 message='request failed';
 await assert.rejects(client.request({path:'/v1/workspaces/w/projects/p',scope:session.identity(),token:session.token()}));assert.equal(denied.length,5);
});

test('Stage 2 citations use existing guarded navigation, and empty sources disable AI ask',async()=>{
 const {LiveDiscussion}=await import('../features/live/discussion.tsx');
 const routes=[],props={t:x=>x,locale:'en',thread:null,threads:[],value:'A question',notice:'',context:[],navigate:path=>routes.push(path),onTemplate(){},onChange(){},onSend(){},onSource(){},onRefresh(){},onAsk(){},canAsk:true};
 assert.equal(button(LiveDiscussion(props),'Ask BuyerOS').props.disabled,true);
 const thread={id:'local-12345678-1234-4123-8123-123456789012',templateId:'custom',title:'Discussion',sources:[{id:stage2Ref.id,label:stage2Ref.label}],messages:[{id:'ai',kind:'ai',...stage2Reply}]};
 const tree=LiveDiscussion({...props,thread});
 assert.equal(button(tree,'Ask BuyerOS').props.disabled,false);button(tree,'Approved offer fact').props.onClick();
 assert.equal(routes[0],`/app/overview?profile=${stage2Profile}`);
 const html=renderToStaticMarkup(tree);assert.match(html,/AI reply · needs review/);assert.match(html,/Fixture reply · no live model/);
 assert.doesNotMatch(html,/Guided step · no AI/);
 const {liveZh}=await import('../features/live/locale.ts');const {replyNotices}=await import('../services/live/conversation-reply.ts');
 for(const notice of Object.values(replyNotices))assert.ok(liveZh[notice]);
 const backend=readFileSync('services/api/buyeros_api/api/routes/conversation.py','utf8')+readFileSync('services/api/buyeros_api/services/conversation_reply.py','utf8');
 assert.doesNotMatch(backend,/execute_external|admit_run|quote_lookup|confirm_lookup|httpx|LiveFitDomainRunner|AsyncJob\(/);
});

test('local discussion selection replaces its deep-link without invoking route transport',async()=>{
 const {navigateLocalDiscussion}=await import('../features/live/conversation-home.ts');
 const entries=[],history={state:{existing:'routing metadata'},replaceState:(...args)=>entries.push(args)};
 const target=new URL('https://fixture.invalid/app/discussions/local-12345678-1234-4123-8123-123456789012?workspace=w&project=p');
 assert.equal(navigateLocalDiscussion('/app',target,true,history),true);
 assert.deepEqual(entries,[[history.state,'','/app/discussions/local-12345678-1234-4123-8123-123456789012?workspace=w&project=p']]);
 for(const [from,to,enabled] of [['/app',target,false],['/app/outreach',target,true],['/app',new URL('https://fixture.invalid/app/results'),true]]){
  assert.equal(navigateLocalDiscussion(from,to,enabled,history),false);
 }
 assert.equal(entries.length,1);
});

test('Stage 2b requires explicit research confirmation and reuses the gated run contract',async()=>{
 const {confirmResearch,conversationLimits,researchNotice,researchNotices}=await import('../services/live/conversation-research.ts');
 const {SessionScope}=await import('../services/live/session.ts');
 const {LiveError}=await import('../services/live/client.ts');
 const {liveZh}=await import('../features/live/locale.ts');
 const workspace='a1000000-0000-4000-8000-000000000001',project='a2000000-0000-4000-8000-000000000001',run='a4000000-0000-4000-8000-000000000001';
 const session=new SessionScope({mode:'live',actor:'fixture',workspace,project});session.setToken('fixture');
 const calls=[];let failure=null;
 const client={request:async req=>{calls.push(req);if(failure)throw failure;return {id:run,workspace_id:workspace,project_id:project,status:'queued',buyers:'PRIVATE_BUYER_BODY'};}};
 const options={enabled:true,confirmed:true,review:{profileId:stage2Profile,profileNumber:1,remaining:'1.000000'},maxCost:'0.500000',target:10};
 for(const changes of [{enabled:false},{confirmed:false},{maxCost:'2.000000'},{target:101}])await assert.rejects(confirmResearch(client,session,{...options,...changes}));
 assert.equal(calls.length,0);
 failure=new LiveError('raw private error','REQUEST_TIMEOUT',0,'',true);
 await assert.rejects(confirmResearch(client,session,options));const unknownKey=calls[0].idempotencyKey;
 failure=null;assert.deepEqual(await confirmResearch(client,session,options),{id:run,label:'Research run',status:'queued'});
 assert.equal(calls[1].idempotencyKey,unknownKey);
 assert.match(calls[0].path,/\/projects\/[^/]+\/runs$/);assert.equal(calls[0].method,'POST');
 assert.deepEqual(calls[0].body,{icp_version_id:stage2Profile,target_companies:10,max_cost:{amount:'0.500000',currency:'USD'},limits:conversationLimits});
 for(const code of ['CAPABILITY_DISABLED','PROVIDER_UNAVAILABLE','POLICY_BLOCKED','BUDGET_LIMIT','STALE_REVISION']){
  failure=new LiveError('raw private error',code,code==='STALE_REVISION'?412:409,'',false);
  await assert.rejects(confirmResearch(client,session,options));const rejected=calls.at(-1).idempotencyKey;
  assert.equal(researchNotice(failure),researchNotices[code]);assert.ok(liveZh[researchNotices[code]]);
  failure=null;await confirmResearch(client,session,options);assert.notEqual(calls.at(-1).idempotencyKey,rejected);
 }
 assert.equal(researchNotice(new LiveError('private','PERMISSION_DENIED',403,'',false)),researchNotices.forbidden);
 for(const value of Object.values(researchNotices))assert.ok(liveZh[value],value);
});

test('Stage 2b persists only generic run references and never live model bodies',async()=>{
 const {DiscussionStore}=await import('../services/live/discussions.ts');
 const saved=new Map(),storage={getItem:key=>saved.get(key)??null,setItem:(key,value)=>saved.set(key,value)};
 const scope={actor:'fixture',workspace:'workspace',project:'project'};
 const store=new DiscussionStore(true,scope,storage),thread=store.create('research-market','Review a research scope');
 const run={id:'a4000000-0000-4000-8000-000000000001',label:'Research run',status:'queued'};
 assert.equal(store.saveRun(thread.id,{...run,body:'PRIVATE_BUYER_BODY'}),false);
 assert.equal(store.saveRun(thread.id,run),true);
 assert.equal(store.saveRun(thread.id,{...run,status:'partial'}),true);
 store.select(thread.id,{id:stage2Ref.id,label:stage2Ref.label},true);
 assert.equal(store.appendReply(thread.id,'Review?',{...stage2Reply,fixture:false,text:'PRIVATE_FACT_BODY'},[stage2Ref.id]),false);
 const restored=new DiscussionStore(true,scope,storage);
 assert.deepEqual(restored.getSnapshot().threads[0].runs,[{...run,status:'partial'}]);
 assert.doesNotMatch([...saved.values()].join(''),/PRIVATE_BUYER_BODY|PRIVATE_FACT_BODY/);
 const {liveZh}=await import('../features/live/locale.ts');
 for(const file of ['features/live/conversation-research.tsx'])for(const [,text] of readFileSync(file,'utf8').matchAll(/\bt\('([^']+)'\)/g))assert.ok(liveZh[text],text);
});

test('Stage 2b retains an uncertain research key through a later permission denial',async()=>{
 const {confirmResearch}=await import('../services/live/conversation-research.ts');
 const {SessionScope}=await import('../services/live/session.ts');
 const {LiveError}=await import('../services/live/client.ts');
 const workspace='a1000000-0000-4000-8000-000000000001',project='a2000000-0000-4000-8000-000000000001';
 const run='a4000000-0000-4000-8000-000000000001',accepted=new Map(),keys=[];
 const session=new SessionScope({mode:'live',actor:'fixture',workspace,project});session.setToken('fixture');
 let permitted=true,loseResponse=true;
 const client={request:async req=>{
  keys.push(req.idempotencyKey);
  if(!permitted)throw new LiveError('permission revoked','PERMISSION_DENIED',403,'',false);
  if(!accepted.has(req.idempotencyKey))accepted.set(req.idempotencyKey,{id:accepted.size?crypto.randomUUID():run,workspace_id:workspace,project_id:project,status:'queued'});
  if(loseResponse){loseResponse=false;throw new LiveError('response lost','REQUEST_TIMEOUT',0,'',true);}
  return accepted.get(req.idempotencyKey);
 }};
 const options={enabled:true,confirmed:true,review:{profileId:stage2Profile,profileNumber:1,remaining:'1.000000'},maxCost:'0.500000',target:10};
 await assert.rejects(confirmResearch(client,session,options));
 permitted=false;await assert.rejects(confirmResearch(client,session,options));
 permitted=true;
 assert.deepEqual(await confirmResearch(client,session,options),{id:run,label:'Research run',status:'queued'});
 assert.equal(new Set(keys).size,1,'a later denial cannot prove that the original request was never accepted');
 assert.equal(accepted.size,1,'retry after permission restoration must not admit a second run');
});
