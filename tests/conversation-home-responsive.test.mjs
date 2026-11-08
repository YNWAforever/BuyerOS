import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {readFileSync,readdirSync,mkdirSync,mkdtempSync,writeFileSync,rmSync} from 'node:fs';
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
const {chromium}=await import('@playwright/test');

// Device discussions and workspace notes now live behind native disclosures.
// Use the visible control rather than forcing hidden descendants or changing UI defaults.
async function openDiscussion(page){
 await page.locator('.live-discussion').waitFor({state:'attached'});
 const disclosure=page.locator('details').filter({has:page.locator('.live-discussion')}).first();
 if(await disclosure.count()&&!await disclosure.evaluate(node=>node.open))await disclosure.locator(':scope > summary').click();
 await page.locator('.live-discussion').waitFor();
}

const {LiveNavigation}=await import('../features/live/navigation.tsx');
const {LiveFrame}=await import('../features/live/shell.tsx');
const cssDir='.vercel/output/static/_next/static/css';
const css=readFileSync(cssDir+'/'+readdirSync(cssDir).find(name=>/^layout\..*\.css$/.test(name)),'utf8');
for(const conversationHome of [false,true])test(`conversation navigation fits desktop, tablet and mobile (flag ${conversationHome?'ON':'OFF'})`,async()=>{
 const browser=await chromium.launch({...(process.env.BUYEROS_CORE_CHROMIUM?{executablePath:process.env.BUYEROS_CORE_CHROMIUM}:{}),headless:true});
 try{
  const navigation=LiveNavigation({t:x=>x,navigate:()=>{},pathname:'/app',authorized:true,projectKnown:true,canEdit:true,projectActive:true,canCreate:true,conversationHome});
  const frame=LiveFrame({t:x=>x,pathname:'/app',navigation,footer:null,header:null,children:null,conversationHome});
  const page=await browser.newPage();await page.setContent('<style>'+css+'</style>'+renderToStaticMarkup(frame));
  for(const width of [320,390,480,481,600,768,820,1023,1024,1440]){
   await page.setViewportSize({width,height:1000});
   const pageWidth=await page.evaluate(()=>document.documentElement.scrollWidth);
   assert.ok(pageWidth<=width,`viewport ${width}px overflows to ${pageWidth}px`);
   assert.equal(await page.getByRole('button',{name:'Operations',exact:true}).count(),1);
  }
 }finally{await browser.close();}
});

// Exercise real rendering at every width, including long in-memory record contents.
const {LiveDiscussion}=await import('../features/live/discussion.tsx');
const sampleThread={id:'local-12345678-1234-4123-8123-123456789012',templateId:'understand-documents',title:'Review documents',createdAt:1,updatedAt:2,messages:[{id:'m1',text:'A long question '+('字'.repeat(100))}],sources:[]};
const aiProfile='a5000000-0000-4000-8000-000000000001',aiFact='a6000000-0000-4000-8000-000000000001';
const aiCitation={id:`fact:profile:${aiProfile}:${aiFact}`,label:'Approved offer fact',locator:{surface:'profile',id:aiProfile}};
sampleThread.sources=[{id:aiCitation.id,label:aiCitation.label}];
sampleThread.messages.push({id:'m2',kind:'ai',status:'needs_review',fixture:true,text:'A cited fixture reply '+('字'.repeat(100)),citations:[aiCitation]});
const sampleContext=[{title:'Documents & outputs',items:[{id:'document:d1',label:'Offer document',title:'source'.repeat(40)+'.pdf',status:'parsing',path:'/app/discover/edit?document=d1'}]},{title:'Offer facts',items:[{id:'fact:f1',label:'Candidate offer fact',title:'product',detail:'內容'.repeat(250),status:'candidate',path:'/app/discover/edit'}]}];
for(const locale of ['en','zh-HK'])test(`thread and context fit 320??440px in ${locale}`,async()=>{
 const {liveZh}=await import('../features/live/locale.ts');const t=value=>locale==='zh-HK'?(liveZh[value]||value):value;
 const browser=await chromium.launch({...(process.env.BUYEROS_CORE_CHROMIUM?{executablePath:process.env.BUYEROS_CORE_CHROMIUM}:{}),headless:true});
 try{
  const panel=LiveDiscussion({t,locale,thread:sampleThread,threads:[sampleThread],value:'Question',notice:'',context:sampleContext,navigate:()=>{},onTemplate:()=>{},onChange:()=>{},onSend:()=>{},onSource:()=>{},onRefresh:()=>{},onAsk:()=>{},canAsk:true});
  const nav=LiveNavigation({t,navigate:()=>{},pathname:'/app',authorized:true,projectKnown:true,canEdit:true,projectActive:true,canCreate:true,conversationHome:true});
  const frame=LiveFrame({t,pathname:'/app',navigation:nav,footer:null,header:null,children:panel,conversationHome:true});
  const page=await browser.newPage();await page.setContent('<style>'+css+readFileSync('features/live/discussion.css','utf8')+'</style>'+renderToStaticMarkup(frame));
  for(const width of [320,390,480,481,600,768,820,1023,1024,1440]){
   await page.setViewportSize({width,height:1000});const actual=await page.evaluate(()=>document.documentElement.scrollWidth);
   assert.ok(actual<=width,`${locale} thread viewport ${width}px overflows to ${actual}px`);
   assert.equal(await page.getByRole('textbox').count(),1);assert.equal(await page.getByRole('checkbox').count(),2);
   assert.equal(await page.getByRole('button',{name:t('Ask BuyerOS'),exact:true}).isEnabled(),true);
   assert.equal(await page.getByLabel(t('Reply citations')).getByRole('button').count(),1);
  }
 }finally{await browser.close();}
});

// ---------------------------------------------------------------------------
// Conversation-first studio browser gate. This is CI-only verification: the
// sandbox cannot spawn a browser, so every assertion below is deterministic and
// scoped to fixtures. Screenshots are written for review artifacts.
// ---------------------------------------------------------------------------
const fixture=await import('./conversation-browser-fixture.mjs');
const {workspace,project,threadId,turnId,proposalId,outputId,newThreadId,documentId,citationId,
 buyerId,buyerThreadId,buyerProposalId}=fixture;
const shots='test-results/conversation-studio';
mkdirSync(shots,{recursive:true});
const prefix=`/v1/workspaces/${workspace}/projects/${project}`;
const uuidPattern=/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/;

function standardApi(options={}){
 const {absent=false,failFirstSend=false,contentOnly=false}=options;
 return async ({req,url,state})=>{
  const method=req.method();
  if(url.pathname.endsWith('/conversation-turns')&&method==='OPTIONS')
   return absent?{status:404,json:{code:'NOT_FOUND',message:'request failed'}}:{status:204};
  if(url.pathname===prefix)return {json:fixture.envelope({id:project,workspace_id:workspace,status:'active',offer_revision:1,active_icp_version_id:fixture.profileId,name:'Fixture project'})};
  if(url.pathname.endsWith('/sales/skills'))return {json:fixture.envelope({skills:[{id:'sales-research'},{id:'review-buyers'}]})};
  if(url.pathname.endsWith('/sales-tasks/capability'))return {json:fixture.envelope({admission_enabled:true})};
  if(url.pathname.endsWith('/conversation-threads')&&method==='GET'){
   const searching=Boolean(url.searchParams.get('q'))||url.searchParams.get('archived')==='true';
   const items=searching?[]:[fixture.studioSummary];
   return {json:fixture.envelope({items,total:items.length,offset:0,limit:50})};
  }
  const threadGet=url.pathname.match(/\/conversation-threads\/([0-9a-f-]+)$/);
  if(threadGet&&method==='GET'){
   if(state.createdThread&&state.createdThread.id===threadGet[1]){state.thread=state.createdThread;return {json:fixture.envelope(state.createdThread)};}
   const resolved=contentOnly?{...fixture.studioThread,sources:[],messages:[{...fixture.userMessage},
     {...fixture.assistantMessage,parts:[{kind:'text',text:'Here is the brief.'}]}]}:fixture.studioThread;
   state.thread=state.thread??resolved;
   return {json:fixture.envelope(resolved)};
  }
  if(url.pathname.endsWith('/conversation-turns')&&method==='POST'){
   state.turnCalls=(state.turnCalls??0)+1;
   const body=req.postDataJSON();
   if(failFirstSend&&state.turnCalls===2)return {status:503,json:{code:'CONVERSATION_MODEL_UNAVAILABLE',message:'private server detail'}};
   if(!('thread_id' in body)){
    const created=fixture.newConversation(body.text);state.createdThread=created.thread;state.thread=created.thread;return {json:fixture.envelope(created)};
   }
   const base=state.thread??fixture.studioThread;
   state.thread={...base,version:base.version+1,messages:[...base.messages,
    {id:'b6000000-0000-4000-8000-000000000001',seq:base.messages.length+1,role:'user',text:body.text,client_message_id:body.client_message_id,turn_id:turnId,created_at:'2026-10-01T00:02:00.000Z',parts:[]},
    {id:'b7000000-0000-4000-8000-000000000001',seq:base.messages.length+2,role:'assistant',text:'Here is the follow-up.',client_message_id:null,turn_id:turnId,created_at:'2026-10-01T00:02:10.000Z',parts:[{kind:'text',text:'Here is the follow-up.'}]}]};
   return {json:fixture.envelope({thread:state.thread,turn:{id:turnId,status:'completed',parts:[{kind:'text',text:'Here is the follow-up.'}],notices:[]}})};
  }
  if(/\/conversation-turns\/[0-9a-f-]+\/decisions$/.test(url.pathname)&&method==='POST')
   return {json:fixture.envelope({thread:state.thread??fixture.studioThread,turn:fixture.decisionTurn()})};
  if(url.pathname.endsWith('/conversation-threads')&&method==='POST'){
   const body=req.postDataJSON();const created=fixture.newConversation(body.messages?.[0]?.text??'Note');
   state.createdThread=created.thread;return {json:fixture.envelope(created.thread),status:201};
  }
  const append=url.pathname.match(/\/conversation-threads\/([0-9a-f-]+)\/messages$/);
  if(append&&method==='POST'){
   const body=req.postDataJSON();
   state.thread={...(state.thread??fixture.studioThread),version:(state.thread??fixture.studioThread).version+1,
    messages:[...(state.thread??fixture.studioThread).messages,{id:'b8000000-0000-4000-8000-000000000001',seq:9,role:'user',text:body.text,client_message_id:null,turn_id:null,created_at:'2026-10-01T00:03:00.000Z',parts:[]}]};
   return {json:fixture.envelope(state.thread)};
  }
  return null;
 };
}

async function fixtureHarness({route:initialRoute='/app/discussions/s/'+threadId,handler=standardApi(),flag=true,locale='en'}={}){
 const {createServer}=await import('vite');
 const dir=mkdtempSync('work/conversation-studio-browser-');
 writeFileSync(dir+'/entry.jsx',fixture.browserEntry);
 const server=await createServer({configFile:false,root,cacheDir:resolve(dir,'node_modules/.vite'),resolve:{alias:{'@':root}},
  optimizeDeps:{noDiscovery:true,include:['react','react-dom/client','react/jsx-runtime','react/jsx-dev-runtime','lucide-react']},
  server:{host:'127.0.0.1',port:0,watch:{ignored:['**/.sites-runtime/**','**/.venv/**','**/.vercel/**','**/dist/**']}},appType:'custom'});
 server.middlewares.use((req,res,next)=>{if(req.url?.startsWith('/fixture')){res.setHeader('content-type','text/html');res.end('<html><body><div id="root"></div><script type="module" src="/'+dir+'/entry.jsx"></script></body></html>');}else next();});
 await server.listen();
 const browser=await chromium.launch({...(process.env.BUYEROS_CORE_CHROMIUM?{executablePath:process.env.BUYEROS_CORE_CHROMIUM}:{}),headless:true});
 const page=await browser.newPage();page.setDefaultTimeout(30000);
 const requests=[],posts=[],errors=[],state={thread:null,createdThread:null,turnCalls:0};
 page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/v1/**',async route=>{
  const request=route.request(),url=new URL(request.url());
  requests.push({method:request.method(),path:url.pathname,search:url.search});
  if(request.method()==='POST'){let body=null;try{body=request.postDataJSON();}catch{body=null;}posts.push({path:url.pathname,body,key:request.headers()['idempotency-key'],match:request.headers()['if-match']});}
  const answer=await handler({req:request,url,state,requests,posts});
  if(answer){if(answer.status===204)return route.fulfill({status:204});return route.fulfill({status:answer.status??200,headers:{'content-type':'application/json','x-request-id':'conversation-studio'},body:JSON.stringify(answer.json)});}
  const data=fixture.contextResponse(url);
  return route.fulfill({status:data?200:403,headers:{'content-type':'application/json','x-request-id':'conversation-studio'},body:JSON.stringify(data?{data,data_mode:'live',request_id:'conversation-studio'}:{error:{code:'PERMISSION_DENIED',message:'denied'},request_id:'conversation-studio'})});
 });
 const query='fixture?route='+encodeURIComponent(initialRoute)+(flag?'':'&flag=off')+(locale==='zh-HK'?'&locale=zh-HK':'');
 await page.goto(server.resolvedUrls.local[0]+query);
 await page.addStyleTag({content:css+readFileSync('features/live/discussion.css','utf8')});
 return {page,browser,server,dir,requests,posts,errors,state,
  close:async()=>{await browser.close();await server.close();rmSync(dir,{recursive:true,force:true});}};
}
async function waitForDestination(page,expected){await page.waitForFunction(value=>window.lastDestination===value,expected);}

test('conversation-first transcript renders typed inline parts and inline decisions',async()=>{
 const harness=await fixtureHarness();
 try{
  const {page,errors,posts}=harness;
  const transcript=page.locator('.conversation-transcript');
  await page.getByRole('textbox',{name:'Message BuyerOS'}).waitFor();
  await page.getByText('Here is the brief.',{exact:true}).waitFor();
  // Inline tool activity keeps its truthful state.
  assert.equal(await page.getByText('Completed',{exact:true}).count(),1);
  // Both inline entry points exist before either navigation can unmount the studio.
  assert.equal(await transcript.getByRole('button',{name:'Open saved output',exact:true}).count(),1);
  assert.equal(await transcript.getByRole('button',{name:'Offer document',exact:true}).count(),1);
  await page.screenshot({path:shots+'/transcript-inline-parts-desktop.png',fullPage:true});
  // Citations are real links to the canonical record.
  await transcript.getByRole('button',{name:'Offer document',exact:true}).click();
  await waitForDestination(page,`/app/discover/edit?document=${documentId}&workspace=${workspace}&project=${project}`);
  // Output links open the saved revision (reload to remount the studio after navigation).
  await page.reload();
  await page.getByText('Here is the brief.',{exact:true}).waitFor();
  await transcript.getByRole('button',{name:'Open saved output',exact:true}).click();
  await waitForDestination(page,`/app/documents/${outputId}?workspace=${workspace}&project=${project}`);
  await page.reload();
  await page.getByText('Here is the brief.',{exact:true}).waitFor();
  // The proposal is an inline approval card, not a chat instruction.
  assert.equal(await transcript.getByRole('button',{name:'Approve',exact:true}).count(),1);
  assert.equal(await transcript.getByRole('button',{name:'Reject',exact:true}).count(),1);
  await transcript.getByRole('button',{name:'Approve',exact:true}).click();
  await page.getByText('Approved. This discussion continues with the result.',{exact:true}).waitFor();
  const decisions=posts.filter(row=>/\/conversation-turns\/[0-9a-f-]+\/decisions$/.test(row.path));
  assert.equal(decisions.length,1,'one explicit decision request');
  assert.deepEqual(decisions[0].body,{proposal_id:proposalId,decision:'approve',expected_thread_version:3});
  assert.match(decisions[0].key??'',/\S/);
  await page.screenshot({path:shots+'/proposal-approval-desktop.png',fullPage:true});
  // Reload rebuilds the same transcript from persisted parts without replaying a turn.
  const turnsBefore=posts.filter(row=>row.path.endsWith('/conversation-turns')).length;
  await page.reload();
  await page.getByText('Here is the brief.',{exact:true}).waitFor();
  assert.equal(posts.filter(row=>row.path.endsWith('/conversation-turns')).length,turnsBefore,'reload never replays a turn');
  // zh-HK pass: same surface, translated labels.
  await page.getByRole('button',{name:'Change language',exact:true}).click();
  await page.getByRole('button',{name:'拒絕',exact:true}).waitFor();
  await page.getByRole('button',{name:'批准',exact:true}).waitFor();
  await page.screenshot({path:shots+'/zh-hk-desktop.png',fullPage:true});
  assert.deepEqual(errors,[]);
 }finally{await harness.close();}
});

test('a new discussion sends exactly one turn for its first message and retries the same client message id',async()=>{
 const harness=await fixtureHarness({route:'/app/discussions/new',handler:standardApi({failFirstSend:true})});
 try{
  const {page,posts,requests}=harness;
  const transcript=page.locator('.conversation-transcript');
  await page.getByRole('textbox',{name:'Message BuyerOS'}).waitFor();
  await page.getByRole('heading',{name:'What would you like to achieve for this project?'}).waitFor();
  // Home entry performs an explicit, method-checked read set; the capability probe is OPTIONS.
  await page.waitForLoadState('networkidle');
  const initial=requests.filter(row=>row.path.startsWith('/v1/'));
  const allow=[prefix,prefix+'/conversation-turns',prefix+'/conversation-threads',prefix+'/sales/skills',
   prefix+'/sales-outputs',prefix+'/sales-tasks',prefix+'/sales-tasks/native-sources',prefix+'/offer-documents',
   prefix+'/icp-versions',prefix+'/runs',prefix+'/usage'];
  for(const row of initial){
   assert.ok(allow.some(allowed=>row.path===allowed||row.path.startsWith(allowed+'/')||row.path.startsWith(allowed+'?')),
    `unexpected initial request ${row.method} ${row.path}${row.search}`);
   if(row.path.endsWith('/conversation-turns'))assert.equal(row.method,'OPTIONS','the turn capability probe never mutates');
   else assert.equal(row.method,'GET','home entry only reads; the turn probe is OPTIONS');
  }
  assert.equal(initial.filter(row=>row.path.endsWith('/conversation-turns')).length,1,'one OPTIONS capability probe');
  for(const required of [prefix,prefix+'/sales/skills',prefix+'/conversation-threads'])
   assert.ok(initial.some(row=>row.path===required),'missing home read '+required);
  await page.screenshot({path:shots+'/home-desktop.png',fullPage:true});
  const composer=page.getByRole('textbox',{name:'Message BuyerOS'});
  await composer.fill('Research this buyer');
  await page.getByRole('button',{name:'Send message',exact:true}).click();
  await page.getByText('Here is the grounded brief.',{exact:true}).waitFor();
  // Amendment A1: the first turn omits thread_id and creates the thread atomically.
  const first=posts.filter(row=>row.path.endsWith('/conversation-turns'));
  assert.equal(first.length,1,'one POST for the first message');
  assert.equal('thread_id' in first[0].body,false);
  assert.equal('expected_thread_version' in first[0].body,false);
  assert.equal(first[0].body.text,'Research this buyer');
  assert.equal(first[0].body.language,'en');
  assert.match(first[0].body.client_message_id,uuidPattern);
  assert.match(first[0].key??'',/\S/);
  // Duplicate-first-message guard: the user text exists exactly once in the transcript.
  assert.equal(await transcript.getByText('Research this buyer',{exact:true}).count(),1);
  assert.match(await page.locator('#fixture-path').textContent(),new RegExp('/app/discussions/s/'+newThreadId));
  // A failed send keeps the draft; retry reuses the same client_message_id and request key.
  const followUp=page.getByRole('textbox',{name:'Message BuyerOS'});
  await followUp.fill('Add a contact');
  await page.getByRole('button',{name:'Send message',exact:true}).click();
  await page.getByText('The result is unconfirmed. Retry the same message to check the saved result instead of running it twice.',{exact:true}).first().waitFor();
  const failed=posts.filter(row=>row.path.endsWith('/conversation-turns')).at(-1);
  assert.match(failed.body.client_message_id,uuidPattern);
  await page.getByRole('button',{name:'Retry send',exact:true}).click();
  await page.getByText('Here is the follow-up.',{exact:true}).waitFor();
  const sent=posts.filter(row=>row.path.endsWith('/conversation-turns')).at(-1);
  assert.equal(sent.body.client_message_id,failed.body.client_message_id,'retry keeps the same message id');
  assert.equal(sent.key,failed.key,'retry keeps the same request key');
  assert.equal(await transcript.getByText('Add a contact',{exact:true}).count(),1);
  // Visible UI keeps the plain "Send" label while the accessible name stays distinct.
  assert.equal(await page.getByRole('button',{name:'Send message',exact:true}).innerText(),'Send');
 }finally{await harness.close();}
});

test('fallback without the turn endpoint saves a truthful note and never fabricates parts',async()=>{
 const harness=await fixtureHarness({handler:standardApi({absent:true,contentOnly:true})});
 try{
  const {page,posts}=harness;
  await page.getByRole('textbox',{name:'Message BuyerOS'}).waitFor();
  await page.getByText('Notes only',{exact:true}).waitFor();
  await page.getByText('Continuous replies are unavailable here. Your messages are saved as notes.',{exact:true}).waitFor();
  await page.getByRole('textbox',{name:'Message BuyerOS'}).fill('Keep this note');
  await page.getByRole('button',{name:'Send message',exact:true}).click();
  await page.getByText('Saved as a note. Select sources to ask BuyerOS.',{exact:true}).first().waitFor();
  const appends=posts.filter(row=>/\/conversation-threads\/[0-9a-f-]+\/messages$/.test(row.path));
  assert.equal(appends.length,1,'the note path appends once');
  assert.equal(appends[0].body.text,'Keep this note');
  assert.equal(posts.filter(row=>row.path.endsWith('/conversation-turns')).length,0,'no invented turn call');
  assert.equal(await page.getByText('Keep this note',{exact:true}).count(),1);
  assert.equal(await page.getByText('Completed',{exact:true}).count(),0,'no fabricated tool activity');
 }finally{await harness.close();}
});

test('unsent composer text survives navigation, reload and remains scoped to the project',async()=>{
 const harness=await fixtureHarness();
 try{
  const {page}=harness;
  const composer=page.getByRole('textbox',{name:'Message BuyerOS'});
  await composer.waitFor();
  await composer.fill('Unsent draft survives');
  // Leave to the conversation home and open the same thread from the store.
  await page.getByRole('button',{name:'Home',exact:true}).click();
  await page.getByRole('textbox',{name:'Message BuyerOS'}).waitFor();
  assert.equal(await page.getByRole('textbox',{name:'Message BuyerOS'}).inputValue(),'Unsent draft survives','draft survives in-app navigation');
  await page.reload();
  await page.getByRole('textbox',{name:'Message BuyerOS'}).waitFor();
  assert.equal(await page.getByRole('textbox',{name:'Message BuyerOS'}).inputValue(),'Unsent draft survives','draft survives reload');
  await page.getByRole('combobox',{name:'Fixture project'}).selectOption('project-b');
  await page.getByRole('textbox',{name:'Message BuyerOS'}).waitFor();
  assert.equal(await page.getByRole('textbox',{name:'Message BuyerOS'}).inputValue(),'','draft is scoped to actor + workspace + project');
  await page.getByRole('combobox',{name:'Fixture project'}).selectOption(project);
  await page.getByRole('textbox',{name:'Message BuyerOS'}).waitFor();
  assert.equal(await page.getByRole('textbox',{name:'Message BuyerOS'}).inputValue(),'Unsent draft survives','draft returns with the original scope');
 }finally{await harness.close();}
});

test('the studio keeps three views separate on mobile and never overflows 320??440px',async()=>{
 const harness=await fixtureHarness();
 try{
  const {page}=harness;
  await page.getByRole('textbox',{name:'Message BuyerOS'}).waitFor();
  for(const width of [320,390,480,481,600,768,820,1023,1024,1440]){
   await page.setViewportSize({width,height:1000});
   const actual=await page.evaluate(()=>document.documentElement.scrollWidth);
   assert.ok(actual<=width,`studio viewport ${width}px overflows to ${actual}px`);
  }
  await page.setViewportSize({width:390,height:844});
  const views=page.getByRole('navigation',{name:'Views'});
  await views.waitFor();
  await page.screenshot({path:shots+'/mobile-390.png',fullPage:true});
  assert.equal(await page.locator('.conversation-threads').isVisible(),false,'mobile conversation view hides the thread list');
  await views.getByRole('button',{name:'Discussions',exact:true}).click();
  await page.locator('.conversation-threads').waitFor();
  assert.equal(await page.locator('.conversation-threads').isVisible(),true,'threads are their own mobile view');
  await page.keyboard.press('Escape');
  await page.waitForFunction(()=>!document.querySelector('.conversation-threads')?.checkVisibility?.());
  assert.equal(await page.locator('.conversation-main').isVisible(),true,'Escape returns to the conversation view');
  await views.getByRole('button',{name:'Context',exact:true}).click();
  await page.locator('.conversation-panel').waitFor();
  assert.equal(await page.locator('.conversation-main').isVisible(),false,'context is its own mobile view, never a squeezed third column');
  await page.keyboard.press('Escape');
  await page.locator('.conversation-main').waitFor();
  // The approved guided form remains reachable as a secondary surface.
  assert.equal(await page.locator('summary',{hasText:'Guided setup'}).count()>=1,true);
 }finally{await harness.close();}
});

test('OFF keeps the prior shell and retained device discussions stay local-only',async()=>{
 const off=await fixtureHarness({flag:false});
 try{
  const {page,requests}=off;
  await page.getByRole('button',{name:'Operations',exact:true}).waitFor();
  assert.equal(await page.getByRole('textbox').count(),0,'flag OFF renders no conversation surface');
  assert.equal(await page.getByText('What would you like to achieve for this project?',{exact:true}).count(),0);
  assert.equal(requests.length,0,'flag OFF performs no conversation reads');
 }finally{await off.close();}
 const on=await fixtureHarness({route:'/app',handler:standardApi()});
 try{
  const {page,requests}=on;
  await page.getByRole('textbox',{name:'Message BuyerOS'}).waitFor();
  await openDiscussion(page);
  await page.getByText('project-evidence.pdf',{exact:false}).waitFor();
  await page.waitForLoadState('networkidle');
  const before=requests.length;
  await page.locator('.live-discussion').getByRole('textbox').fill('Keep this local note');
  await page.getByRole('button',{name:'Send',exact:true}).click();
  await page.locator('.live-discussion').getByLabel('Discussion messages',{exact:true}).getByText('Keep this local note',{exact:true}).waitFor();
  assert.equal(requests.length,before,'device discussions remain local and perform no fetches');
  assert.match(await page.evaluate(()=>Object.keys(localStorage).filter(key=>key.startsWith('buyeros.discussions')).join(',')),/buyeros\.discussions/);
 }finally{await on.close();}
});

test('workspace thread keeps decisions, revoked sources, stale sends and viewer limits explicit',async()=>{
 let writes=[];
 let thread={...fixture.studioThread,access:'editor',sources:[
  {id:'drive:12345678-1234-4123-8123-123456789012:file_one',label:'Google Drive item'},
  {id:'drive:23456789-1234-4123-8123-123456789012:file_two',label:'Google Drive item'},
  {id:citationId,label:'Offer document'}]};
 const handler=async({req,url})=>{
  const method=req.method();
  if(url.pathname.endsWith('/conversation-turns')&&method==='OPTIONS')return {status:204};
  if(url.pathname===prefix)return {json:fixture.envelope({id:project,name:'Fixture project'})};
  if(url.pathname.endsWith('/sales/skills'))return {json:fixture.envelope({skills:[]})};
  if(url.pathname.endsWith('/conversation-threads')&&method==='GET')return {json:fixture.envelope({items:[],total:0,offset:0,limit:50})};
  if(/\/conversation-threads\/[0-9a-f-]+$/.test(url.pathname)&&method==='GET')return {json:fixture.envelope(thread)};
  if(/\/conversation-threads\/[0-9a-f-]+\/sources$/.test(url.pathname)&&method==='PUT'){
   const body=req.postDataJSON();writes.push({body,version:req.headers()['x-buyeros-if-match']});
   if(body.sources.some(source=>source.id.startsWith('drive:')))return {status:422,json:{code:'CONVERSATION_SOURCE_UNAVAILABLE',message:'selected sources need review'}};
   thread={...thread,sources:body.sources,version:thread.version+1};return {json:fixture.envelope(thread)};
  }
  if(url.pathname.endsWith('/conversation-turns')&&method==='POST')return {status:412,json:{code:'STALE_REVISION',message:'discussion changed'}};
  if(/\/conversation-turns\/[0-9a-f-]+\/decisions$/.test(url.pathname)&&method==='POST')return {json:fixture.envelope({thread,turn:fixture.decisionTurn()})};
  return null;
 };
 const harness=await fixtureHarness({handler});
 try{
  const {page,posts}=harness;
  const transcript=page.locator('.conversation-transcript');
  await transcript.getByRole('button',{name:'Approve',exact:true}).waitFor();
  // Approving is a real request against the owning turn.
  await transcript.getByRole('button',{name:'Approve',exact:true}).click();
  await page.getByText('Approved. This discussion continues with the result.',{exact:true}).waitFor();
  const decision=posts.find(row=>row.path.endsWith('/decisions'));
  assert.ok(decision);assert.deepEqual(decision.body,{proposal_id:proposalId,decision:'approve',expected_thread_version:3});
  // Revoked Drive sources cannot be saved one by one; the bulk removal path succeeds.
  const panel=page.locator('.conversation-panel');
  await panel.getByRole('tab',{name:'Sources',exact:true}).click();
  await panel.getByRole('button',{name:'Remove',exact:true}).first().click();
  await page.getByText('Workspace discussions are unavailable. Your unsaved text is still here.',{exact:true}).waitFor();
  assert.equal(writes.length,1);assert.deepEqual(writes[0].body.sources.map(source=>source.id),[thread.sources[1].id,citationId]);
  await panel.getByRole('button',{name:'Remove unavailable Google Drive selections',exact:true}).click();
  await panel.getByRole('button',{name:'Remove unavailable Google Drive selections',exact:true}).waitFor({state:'detached'});
  assert.deepEqual(writes[1].body.sources,[{id:citationId,label:'Offer document'}]);
  assert.equal(thread.sources.length,1,'only the unavailable Drive references are dropped');
  // A stale revision keeps the unsent text and says exactly what to do next.
  await page.getByRole('textbox',{name:'Message BuyerOS'}).fill('Keep this after the conflict');
  await page.getByRole('button',{name:'Send message',exact:true}).click();
  await page.getByText('This discussion changed. Copy any unsaved text, reload and send again.',{exact:true}).waitFor();
  assert.equal(await page.getByRole('textbox',{name:'Message BuyerOS'}).inputValue(),'Keep this after the conflict');
  assert.equal(await page.getByRole('button',{name:'Retry send',exact:true}).count(),1);
  // A viewer reads the same discussion but cannot decide, send or change sources.
  thread={...thread,access:'viewer'};
  await page.reload();
  const viewerComposer=page.getByRole('textbox',{name:'Message BuyerOS'});
  await viewerComposer.waitFor();
  assert.equal(await viewerComposer.isDisabled(),true);
  assert.equal(await transcript.getByRole('button',{name:'Approve',exact:true}).count(),0);
  await page.locator('.conversation-panel').getByRole('tab',{name:'Sources',exact:true}).click();
  assert.equal(await page.locator('.conversation-panel').getByRole('button',{name:'Remove',exact:true}).count(),0);
 }finally{await harness.close();}
});

test('a preset skill chip sends its skill_id once and clears the composer',async()=>{
 const harness=await fixtureHarness({route:'/app/discussions/new',handler:standardApi()});
 try{
  const {page,posts}=harness;
  const transcript=page.locator('.conversation-transcript');
  await page.locator('[data-skill-ids="ready"]').waitFor();
  await page.getByRole('button',{name:'Research a market',exact:true}).waitFor();
  await page.getByRole('button',{name:'Research a market',exact:true}).click();
  await page.getByText('Here is the grounded brief.',{exact:true}).waitFor();
  const turns=posts.filter(row=>row.path.endsWith('/conversation-turns'));
  assert.equal(turns.length,1,'a chip is one turn, not a form submission');
  assert.equal(turns[0].body.skill_id,'sales-research');
  assert.match(turns[0].body.client_message_id,uuidPattern);
  assert.equal(turns[0].body.text,'Help me plan research for a market.');
  assert.equal(await page.getByRole('textbox',{name:'Message BuyerOS'}).inputValue(),'','the composer clears after a chip send');
  assert.equal(await transcript.getByText('Help me plan research for a market.',{exact:true}).count(),1,'exactly one user message is appended');
 }finally{await harness.close();}
});

test('a permission failure keeps the message unsent and surfaces the honest notice',async()=>{
 const handler=standardApi();
 const harness=await fixtureHarness({handler:async input=>{
  if(input.url.pathname.endsWith('/conversation-turns')&&input.req.method()==='POST'){
   return {status:403,json:{code:'PERMISSION_DENIED',message:'private server detail'}};
  }
  return handler(input);
 }});
 try{
  const {page,posts}=harness;
  await page.getByRole('textbox',{name:'Message BuyerOS'}).waitFor();
  await page.getByRole('textbox',{name:'Message BuyerOS'}).fill('Do not lose this message');
  await page.getByRole('button',{name:'Send message',exact:true}).click();
  await page.getByText('You do not have permission to act in this discussion.',{exact:true}).first().waitFor();
  assert.equal(posts.filter(row=>row.path.endsWith('/conversation-turns')).length,1);
  assert.equal(await page.getByRole('textbox',{name:'Message BuyerOS'}).inputValue(),'Do not lose this message','the unsent message stays in the composer');
  assert.equal(await transcript.getByText('Do not lose this message',{exact:true}).count(),0,'a denied send is never appended');
 }finally{await harness.close();}
});

test('an unavailable workspace thread fails explicitly instead of showing another thread',async()=>{
 const handler=async({req,url})=>{
  if(url.pathname.endsWith('/conversation-turns')&&req.method()==='OPTIONS')return {status:204};
  if(url.pathname===prefix)return {json:fixture.envelope({id:project,name:'Fixture project'})};
  if(url.pathname.endsWith('/sales/skills'))return {json:fixture.envelope({skills:[]})};
  if(url.pathname.endsWith('/conversation-threads')&&req.method()==='GET')return {json:fixture.envelope({items:[],total:0,offset:0,limit:50})};
  if(/\/conversation-threads\/[0-9a-f-]+$/.test(url.pathname)&&req.method()==='GET')return {status:404,json:{code:'NOT_FOUND',message:'request failed'}};
  return null;
 };
 const harness=await fixtureHarness({handler});
 try{
  const {page}=harness;
  await page.getByText('Not found in this workspace.',{exact:true}).waitFor();
  await page.getByText('This workspace discussion was not found or is no longer shared with you.',{exact:true}).waitFor();
  assert.equal(await transcript.count(),0,'no transcript for an unavailable thread');
  assert.equal(await page.getByRole('button',{name:'New discussion',exact:true}).count()>=1,true);
 }finally{await harness.close();}
});

test('Discuss this company starts one linked turn and a terminal enrichment card becomes inert',async()=>{
 const handler=async({req,url,state})=>{
  const method=req.method();
  if(url.pathname.endsWith('/conversation-turns')&&method==='OPTIONS')return {status:204};
  if(url.pathname===prefix)return {json:fixture.envelope({id:project,name:'Fixture project'})};
  if(url.pathname.endsWith('/sales/skills'))return {json:fixture.envelope({skills:[{id:'sales-contacts'}]})};
  if(url.pathname.endsWith('/conversation-threads')&&method==='GET')return {json:fixture.envelope({items:[],total:0,offset:0,limit:50})};
  const threadGet=url.pathname.match(/\/conversation-threads\/([0-9a-f-]+)$/);
  if(threadGet&&method==='GET'){
   if(threadGet[1]===buyerThreadId){
    const conversation=state.terminal?fixture.terminalBuyerConversation():fixture.buyerConversation();
    state.buyerThread=conversation.thread;return {json:fixture.envelope(conversation.thread)};
   }
   return {json:fixture.envelope(fixture.studioThread)};
  }
  if(url.pathname.endsWith('/conversation-turns')&&method==='POST'){
   const conversation=fixture.buyerConversation();state.buyerThread=conversation.thread;return {json:fixture.envelope(conversation)};
  }
  if(/\/conversation-turns\/[0-9a-f-]+\/decisions$/.test(url.pathname)&&method==='POST'){
   state.terminal=true;return {json:fixture.envelope(fixture.terminalBuyerConversation())};
  }
  return null;
 };
 const harness=await fixtureHarness({handler});
 try{
  const {page,posts}=harness;
  const transcript=page.locator('.conversation-transcript');
  await page.getByRole('button',{name:'Discuss this company',exact:true}).waitFor();
  await page.getByRole('button',{name:'Discuss this company',exact:true}).click();
  await transcript.getByText('Here is what we can verify about DeltaGrid.',{exact:true}).waitFor();
  // Exactly one thread-first turn; no thread_id, no If-Match, buyer link carried.
  const turns=posts.filter(row=>row.path.endsWith('/conversation-turns'));
  assert.equal(turns.length,1,'one thread-first turn for the company entry');
  assert.equal('thread_id' in turns[0].body,false);
  assert.equal('expected_thread_version' in turns[0].body,false);
  assert.equal(turns[0].match,undefined,'a thread-first turn never sends If-Match');
  assert.equal(turns[0].body.buyer_id,buyerId);
  assert.equal(turns[0].body.template_id,'check-company');
  assert.equal(turns[0].body.skill_id,'sales-contacts');
  assert.match(turns[0].body.client_message_id,uuidPattern);
  assert.equal(turns[0].body.language,'en');
  assert.match(turns[0].body.text,/Discuss this company/);
  assert.match(await page.locator('#fixture-path').textContent(),new RegExp('/app/discussions/s/'+buyerThreadId));
  // Company identity comes from thread.buyerId + the persisted buyer citation; no extra fetch.
  const compose=page.locator('.conversation-compose');
  await compose.getByLabel('Linked company').waitFor();
  assert.match(await compose.getByLabel('Linked company').innerText(),/DeltaGrid/);
  // Always-approval plus an honest cost review with no invented number.
  assert.equal(await transcript.getByText('Approval required',{exact:true}).count(),1);
  assert.equal(await transcript.getByText('Cost review required before any paid request.',{exact:true}).count(),1);
  assert.equal(await page.locator('.conversation-proposal-cost').innerText(),'Cost review required before any paid request.');
  // Approval returns a terminal configuration outcome; the card must become inert.
  await transcript.getByRole('button',{name:'Approve',exact:true}).click();
  await transcript.getByText('Company enrichment cannot run until Xverum dispatch is enabled by an administrator. Nothing was executed.').first().waitFor();
  assert.equal(await transcript.getByText('Failed',{exact:true}).count(),1);
  assert.equal(await transcript.getByText('This step cannot run in the current configuration.',{exact:true}).count(),1);
  assert.equal(await transcript.getByRole('button',{name:'Approve',exact:true}).count(),0,'terminal configuration leaves no actionable decision');
  assert.equal(await transcript.getByRole('button',{name:'Reject',exact:true}).count(),0);
  const decision=posts.find(row=>row.path.endsWith('/decisions'));
  assert.deepEqual(decision.body,{proposal_id:buyerProposalId,decision:'approve',expected_thread_version:1});
  assert.equal(decision.match,'"1"');
 }finally{await harness.close();}
});

// Restored retained-surface scenarios: device discussions and Google Drive remain the

// local-only surfaces they were before the conversation studio became the project home.

// Only two statement changes are needed: scoped Discussion-messages queries (the studio

// transcript uses the same aria-label) and the fixture accessible-name separations above.

test('hydrated Stage 2 explicit ask, citations, unavailable, revocation and OFF network boundary',async()=>{
 const {createServer}=await import('vite');const {mkdirSync,mkdtempSync,writeFileSync,rmSync}=await import('node:fs');
 const {contextResponse,browserEntry,profileId,factId,documentId}=await import('./conversation-browser-fixture.mjs');
 mkdirSync('work',{recursive:true});const dir=mkdtempSync('work/conversation-ai-browser-');writeFileSync(dir+'/entry.jsx',browserEntry);
 const server=await createServer({configFile:false,root,cacheDir:resolve(dir,'node_modules/.vite'),resolve:{alias:{'@':root}},
  optimizeDeps:{noDiscovery:true,include:['react','react-dom/client','react/jsx-runtime','react/jsx-dev-runtime','lucide-react']},server:{host:'127.0.0.1',port:0,watch:{ignored:['**/.sites-runtime/**','**/.venv/**','**/.vercel/**','**/dist/**']}},appType:'custom'});
 server.middlewares.use((req,res,next)=>{if(req.url?.startsWith('/fixture')){res.setHeader('content-type','text/html');res.end('<html><body><div id="root"></div><script type="module" src="/'+dir+'/entry.jsx"></script></body></html>');}else next();});
 await server.listen();let browser;
 try{
  browser=await chromium.launch({...(process.env.BUYEROS_CORE_CHROMIUM?{executablePath:process.env.BUYEROS_CORE_CHROMIUM}:{}),headless:true});
  const page=await browser.newPage(),posts=[],errors=[];page.on('pageerror',error=>errors.push(error.message));
  const ref={id:`fact:profile:${profileId}:${factId}`,label:'Approved offer fact',locator:{surface:'profile',id:profileId}};
  const documentRef={id:`document:${documentId}`,label:'Offer document',locator:{surface:'document',id:documentId}};
  const reply={status:'needs_review',fixture:true,text:'Review the cited approved source before deciding.',citations:[ref,documentRef]};
  let mode='ok',release,started;let received=new Promise(resolve=>started=resolve);
  await page.route('**/v1/**',async route=>{
   const req=route.request();
   if(req.method()==='POST'){
    posts.push({path:new URL(req.url()).pathname,body:req.postDataJSON()});started();
    if(mode==='held')await new Promise(resolve=>release=resolve);
    if(mode==='unavailable')return route.fulfill({status:503,json:{code:'CONVERSATION_MODEL_UNAVAILABLE',message:'private error'}});
    if(mode==='source')return route.fulfill({status:422,json:{code:'CONVERSATION_SOURCE_UNAVAILABLE'}});
    return route.fulfill({json:{data:mode==='invalid'?{...reply,tool_calls:[{name:'research'}]}:reply,data_mode:'live',request_id:'stage2-fixture'}});
   }
   const data=contextResponse(new URL(req.url()));return route.fulfill({status:data?200:403,json:{data,data_mode:'live',request_id:'stage2-fixture'}});
  });
  await page.goto(server.resolvedUrls.local[0]+'fixture');await openDiscussion(page);await page.getByText('project-evidence.pdf',{exact:false}).waitFor();
  await page.locator('.live-discussion').getByRole('textbox').fill('Start a local discussion');
  assert.equal(await page.getByRole('button',{name:'Ask BuyerOS',exact:true}).isDisabled(),true);
  await page.getByRole('button',{name:'Send',exact:true}).click();await page.locator('.live-discussion').getByLabel('Discussion messages',{exact:true}).waitFor();
  await page.getByRole('checkbox').first().click();await page.waitForFunction(()=>document.querySelectorAll('input[type=checkbox]')[0].checked);
  await page.getByRole('checkbox').nth(1).click();await page.waitForFunction(()=>document.querySelectorAll('input[type=checkbox]')[1].checked);
  await page.locator('.live-discussion').getByRole('textbox').fill('What should I review?');
  const ask=()=>page.getByRole('button',{name:'Ask BuyerOS',exact:true});
  await ask().focus();await page.keyboard.press('Enter');
  await page.getByText(reply.text,{exact:true}).waitFor();assert.equal(posts.length,1);
  assert.deepEqual(posts[0].body,{question:'What should I review?',source_ids:[documentRef.id,ref.id],language:'en'});
  assert.ok(posts.every(row=>row.path.endsWith('/conversation-reply')));
  let stored=await page.evaluate(()=>Object.values(localStorage).join(''));
  assert.doesNotMatch(stored,/PRIVATE_FACT_CONTENT|project-evidence.pdf|tool_calls/);
  await page.reload();await openDiscussion(page);await page.getByText(reply.text,{exact:true}).waitFor();
  const citations=page.getByLabel('Reply citations');
  await citations.getByRole('button',{name:'Approved offer fact',exact:true}).click();
  assert.equal(await page.evaluate(()=>window.lastDestination),`/app/overview?profile=${profileId}&workspace=a1000000-0000-4000-8000-000000000001&project=a2000000-0000-4000-8000-000000000001`);
  await page.getByRole('button',{name:'Home',exact:true}).click();await openDiscussion(page);await page.getByRole('region',{name:'Continue working',exact:true}).getByRole('button').click();await openDiscussion(page);
  await page.getByLabel('Reply citations').getByRole('button',{name:'Offer document',exact:true}).click();
  assert.match(await page.evaluate(()=>window.lastDestination),new RegExp(`/app/discover/edit\\?document=${documentId}`));
  await page.getByRole('button',{name:'Home',exact:true}).click();await openDiscussion(page);await page.getByRole('region',{name:'Continue working',exact:true}).getByRole('button').click();await openDiscussion(page);
  for(const state of ['unavailable','source','invalid']){
   mode=state;await page.locator('.live-discussion').getByRole('textbox').fill('Keep this question');await ask().click();
   await page.getByText(state==='unavailable'?'BuyerOS AI is unavailable. Your question is still here; you can use the guided step or try later.':state==='source'?'Selected sources are unavailable or not approved. Refresh project context and review your selection.':'The AI reply could not be verified. Review the selected sources and try again.',{exact:true}).waitFor();
   assert.equal(await page.locator('.live-discussion').getByRole('textbox').inputValue(),'Keep this question');
  }
  const before=await page.evaluate(()=>Object.values(localStorage).join(''));
  mode='held';received=new Promise(resolve=>started=resolve);await ask().click();await received;
  await page.getByRole('button',{name:'Revoke offer access',exact:true}).click();release();
  await ask().waitFor();assert.equal(await ask().isDisabled(),true);
  assert.equal(await page.evaluate(()=>Object.values(localStorage).join('')),before);
  const postCount=posts.length;await page.goto(server.resolvedUrls.local[0]+'fixture?flag=off');
  await page.getByRole('button',{name:'Operations',exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Ask BuyerOS',exact:true}).count(),0);assert.equal(posts.length,postCount);
  assert.deepEqual(errors,[]);
 }finally{await browser?.close();await server.close();rmSync(dir,{recursive:true,force:true});}
});

test('Stage 2b keyboard confirmation, localized gate failures, run continuity and live reply privacy',async()=>{
 const {createServer}=await import('vite');const {mkdirSync,mkdtempSync,writeFileSync,rmSync}=await import('node:fs');
 const {contextResponse,browserEntry,workspace,project,profileId,factId}=await import('./conversation-browser-fixture.mjs');
 const {researchNotices}=await import('../services/live/conversation-research.ts');
 const {liveZh}=await import('../features/live/locale.ts');
 mkdirSync('work',{recursive:true});const dir=mkdtempSync('work/conversation-paid-browser-');writeFileSync(dir+'/entry.jsx',browserEntry);
 const server=await createServer({configFile:false,root,cacheDir:resolve(dir,'node_modules/.vite'),resolve:{alias:{'@':root}},
  optimizeDeps:{noDiscovery:true,include:['react','react-dom/client','react/jsx-runtime','react/jsx-dev-runtime','lucide-react']},server:{host:'127.0.0.1',port:0,watch:{ignored:['**/.sites-runtime/**','**/.venv/**','**/.vercel/**','**/dist/**']}},appType:'custom'});
 server.middlewares.use((req,res,next)=>{if(req.url?.startsWith('/fixture')){res.setHeader('content-type','text/html');res.end('<html><body><div id="root"></div><script type="module" src="/'+dir+'/entry.jsx"></script></body></html>');}else next();});
 await server.listen();let browser;
 try{
  browser=await chromium.launch({...(process.env.BUYEROS_CORE_CHROMIUM?{executablePath:process.env.BUYEROS_CORE_CHROMIUM}:{}),headless:true});
  const page=await browser.newPage(),posts=[],errors=[];let gate=null,status='queued';
  page.on('pageerror',error=>errors.push(error.message));
  const runId='b4000000-0000-4000-8000-000000000001';
  const ref={id:`fact:profile:${profileId}:${factId}`,label:'Approved offer fact',locator:{surface:'profile',id:profileId}};
  await page.route('**/v1/**',async route=>{
   const req=route.request(),url=new URL(req.url());
   if(req.method()==='POST'){
    posts.push({path:url.pathname,body:req.postDataJSON(),key:req.headers()['idempotency-key']});
    if(url.pathname.endsWith('/conversation-reply'))return route.fulfill({json:{data:{status:'needs_review',fixture:false,text:'PRIVATE_LIVE_MODEL_FACT_BODY',citations:[ref]},data_mode:'live',request_id:'paid-fixture'}});
    if(gate)return route.fulfill({status:gate==='403'?403:gate==='STALE_REVISION'?412:gate==='CAPABILITY_DISABLED'||gate==='PROVIDER_UNAVAILABLE'?503:409,json:{code:gate==='403'?'PERMISSION_DENIED':gate,message:'private server details'}});
    return route.fulfill({json:{data:{id:runId,workspace_id:workspace,project_id:project,status,buyers:'PRIVATE_BUYER_BODY'},data_mode:'live',request_id:'paid-fixture'}});
   }
   let data;
   if(url.pathname.endsWith('/budgets')){
    data={items:[['workspace',workspace,'all'],['project',project,'all'],['category',project,'discovery']].map(([scope,scope_id,category])=>({workspace_id:workspace,scope,scope_id,category,period_start:'2026-01-01T00:00:00Z',period_end:'2099-01-01T00:00:00Z',remaining:{amount:'1.000000',currency:'USD'},effective_state:'active'})),offset:0,limit:100,total:3};
   }else if(url.pathname.includes('pilot-budget'))data={id:null,workspace_id:workspace,project_id:project,remaining:null,currency:'USD'};
   else if(url.pathname.endsWith('/runs/'+runId))data={id:runId,workspace_id:workspace,project_id:project,status};
   else{data=contextResponse(url);if(url.pathname.endsWith('/icp-versions')&&url.searchParams.get('limit')==='100')data={...data,limit:100};}
   return route.fulfill({status:data?200:403,json:{data,data_mode:'live',request_id:'paid-fixture'}});
  });
  await page.goto(server.resolvedUrls.local[0]+'fixture');await openDiscussion(page);await page.getByText('project-evidence.pdf',{exact:false}).waitFor();
  await page.addStyleTag({content:css+readFileSync('features/live/discussion.css','utf8')});
  await page.locator('.live-discussion').getByRole('textbox').fill('Research these approved sources');await page.getByRole('button',{name:'Send',exact:true}).click();
  await page.getByRole('button',{name:'Propose research',exact:true}).waitFor();assert.equal(posts.length,0);
  const propose=()=>page.getByRole('button',{name:'Propose research',exact:true});
  await propose().focus();await page.keyboard.press('Enter');await page.getByRole('dialog',{name:'Confirm paid research'}).waitFor();
  assert.equal(posts.length,0,'proposal and review GETs must not start research');
  for(const width of [320,390,768,1024,1440]){
   await page.setViewportSize({width,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth)<=width);
   const box=await page.getByRole('dialog').boundingBox();assert.ok(box.width<=width&&box.height<=900);
  }
  assert.equal(await page.getByRole('dialog').getByText('Budget remaining · USD 1.000000',{exact:true}).count(),1);
  await page.keyboard.press('Escape');await page.getByRole('dialog').waitFor({state:'hidden'});assert.equal(posts.length,0);
  for(const locale of ['en','zh-HK']){
   if(locale==='zh-HK')await page.getByRole('button',{name:'Change language',exact:true}).click();
   const t=value=>locale==='en'?value:(liveZh[value]||value);
   for(const code of ['CAPABILITY_DISABLED','PROVIDER_UNAVAILABLE','POLICY_BLOCKED','BUDGET_LIMIT','STALE_REVISION','403']){
    gate=code;await page.getByRole('button',{name:t('Propose research'),exact:true}).click();await page.getByRole('dialog').waitFor();
    if(code==='CAPABILITY_DISABLED')for(const width of [320,390,768,1024,1440]){
     await page.setViewportSize({width,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth)<=width,locale+' confirmation overflow');
     const bounds=await page.getByRole('dialog').boundingBox();assert.ok(bounds.width<=width&&bounds.height<=900);
    }
    const before=posts.length;await page.getByRole('button',{name:t('Confirm and start research'),exact:true}).focus();await page.keyboard.press('Enter');
    const expected=code==='403'?researchNotices.forbidden:researchNotices[code];await page.getByRole('dialog').getByText(t(expected),{exact:true}).waitFor();
    assert.equal(posts.length,before+1);assert.ok(posts.at(-1).key);assert.ok(posts.every(row=>row.path.endsWith('/runs')));
    await page.getByRole('button',{name:t('Back to discussion'),exact:true}).click();
   }
  }
  await page.getByRole('button',{name:'Change language',exact:true}).click();gate=null;
  await propose().click();await page.getByRole('button',{name:'Confirm and start research',exact:true}).click();
  await page.getByText(runId,{exact:true}).waitFor();assert.equal(posts.at(-1).body.icp_version_id,profileId);
  assert.equal(posts.at(-1).body.max_cost.amount,'0.500000');assert.equal(posts.at(-1).body.limits.max_duration_seconds,300);
  assert.equal(new Set(posts.map(row=>row.key)).size,posts.length,'each confirmed, known-rejected intent gets a new key');
  status='partial';await page.getByRole('button',{name:'Refresh run status',exact:true}).click();await page.locator('.live-conversation-research').getByText('partial',{exact:true}).waitFor();
  await page.reload();await openDiscussion(page);await page.getByText(runId,{exact:true}).waitFor();await page.locator('.live-conversation-research').getByText('partial',{exact:true}).waitFor();
  await page.getByRole('checkbox').nth(1).click();await page.locator('.live-discussion').getByRole('textbox').fill('Which source supports this?');await page.getByRole('button',{name:'Ask BuyerOS',exact:true}).click();
  await page.getByText('PRIVATE_LIVE_MODEL_FACT_BODY',{exact:true}).waitFor();
  assert.doesNotMatch(await page.evaluate(()=>Object.values(localStorage).join('')),/PRIVATE_LIVE_MODEL_FACT_BODY|PRIVATE_BUYER_BODY|PRIVATE_FACT_CONTENT/);
  const count=posts.length;await page.reload();await openDiscussion(page);await page.getByText(runId,{exact:true}).waitFor();assert.equal(await page.getByText('PRIVATE_LIVE_MODEL_FACT_BODY',{exact:true}).count(),0);assert.equal(posts.length,count);
  await page.goto(server.resolvedUrls.local[0]+'fixture?flag=off');await page.getByRole('button',{name:'Operations',exact:true}).waitFor();assert.equal(await propose().count(),0);assert.equal(posts.length,count);
  assert.deepEqual(errors,[]);
 }finally{await browser?.close();await server.close();rmSync(dir,{recursive:true,force:true});}
});


test('Stage 4 Drive admin approval, member selection, ephemeral Ask, conflicts and OFF parity across sizes/locales',async()=>{
 const {createServer}=await import('vite');const {mkdirSync,mkdtempSync,writeFileSync,rmSync}=await import('node:fs');
 const {contextResponse,browserEntry}=await import('./conversation-browser-fixture.mjs');
 mkdirSync('work',{recursive:true});const dir=mkdtempSync('work/conversation-drive-');writeFileSync(dir+'/entry.jsx',browserEntry);
 const server=await createServer({configFile:false,root,cacheDir:resolve(dir,'node_modules/.vite'),resolve:{alias:{'@':root}},optimizeDeps:{noDiscovery:true,include:['react','react-dom/client','react/jsx-runtime','react/jsx-dev-runtime','lucide-react']},server:{host:'127.0.0.1',port:0,watch:{ignored:['**/.sites-runtime/**','**/.venv/**','**/.vercel/**','**/dist/**']}},appType:'custom'});
 server.middlewares.use((req,res,next)=>{if(req.url?.startsWith('/fixture')){res.setHeader('content-type','text/html');res.end('<html><head><style>'+css+'</style></head><body><div id="root"></div><script type="module" src="/'+dir+'/entry.jsx"></script></body></html>');}else next();});
 await server.listen();let browser;
 try{
  browser=await chromium.launch({...(process.env.BUYEROS_CORE_CHROMIUM?{executablePath:process.env.BUYEROS_CORE_CHROMIUM}:{}),headless:true});
  const page=await browser.newPage(),writes=[],reads=[],errors=[];page.on('pageerror',error=>errors.push(error.message));
  let status={version:1,connected:false,available:true,can_manage:true,folders:[],residency_preference:'HK',metadata_cache_seconds:0},uncertain=true,stale=false,denied=false;
  const source={id:'drive:12345678-1234-4123-8123-123456789012:file_one',label:'Google Drive item'};
  await page.route('**/v1/**',route=>{
   const req=route.request(),url=new URL(req.url()),path=url.pathname,method=req.method();
   const ok=data=>route.fulfill({json:{data,data_mode:'live',request_id:'stage4-browser'}});
   if(path.includes('/conversation-connections/')){
    if(method==='GET'){
     reads.push(path);if(denied)return route.fulfill({status:404,json:{code:'NOT_FOUND',message:'connection not found'}});
     if(path.endsWith('/folders'))return ok({items:[{id:'folder_one',label:'Google Drive folder'}]});
     if(path.endsWith('/items'))return ok({items:status.folders.length?[source]:[]});return ok(status);
    }
    writes.push({method,key:req.headers()['idempotency-key'],version:req.headers()['x-buyeros-if-match'],body:method==='DELETE'?undefined:req.postDataJSON()});
    if(stale)return route.fulfill({status:409,json:{code:'STALE_REVISION',message:'changed'}});
    if(method==='POST'){
     status={...status,version:2,connected:true};
     if(uncertain){uncertain=false;return route.fulfill({status:503,json:{code:'DRIVE_UNAVAILABLE',message:'uncertain'}});}
    }else if(method==='PUT')status={...status,version:3,folders:[{id:'folder_one',label:'Google Drive folder'}]};
    else status={...status,version:4,connected:false,folders:[]};return ok(status);
   }
   if(path.endsWith('/conversation-reply')){assert.deepEqual(req.postDataJSON().source_ids,[source.id]);return ok({status:'needs_review',fixture:false,text:'EPHEMERAL_DRIVE_ANSWER',citations:[{...source,locator:{surface:'drive',id:source.id}}]});}
   return ok(contextResponse(url));
  });
  await page.goto(server.resolvedUrls.local[0]+'fixture');await openDiscussion(page);
  const drive=page.getByRole('region',{name:'Google Drive',exact:true});
  await drive.getByRole('button',{name:'Connect Google Drive',exact:true}).click();
  await drive.getByText('The connection change was not confirmed. Reload Google Drive and compare before retrying.',{exact:true}).waitFor();
  await drive.getByRole('button',{name:'Connect Google Drive',exact:true}).click();
  await drive.getByRole('button',{name:'Choose approved folders',exact:true}).click();
  await drive.getByRole('checkbox').check();
  for(const language of ['en','zh-HK']){
   if(language==='zh-HK')await page.getByRole('button',{name:'Change language',exact:true}).click();
   for(const width of [320,390,480,600,768,820,1023,1024,1440]){await page.setViewportSize({width,height:1000});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth)<=width,`${language} Drive overflows ${width}`);}
  }
  await page.getByRole('button',{name:'Change language',exact:true}).click();
  await drive.getByRole('button',{name:'Save approved folders',exact:true}).focus();await page.keyboard.press('Enter');
  await drive.getByRole('button',{name:'Reload Google Drive',exact:true}).click();
  await drive.getByText('Google Drive item 1',{exact:false}).waitFor();
  assert.equal(await drive.getByRole('checkbox').isDisabled(),true,'start a discussion before selecting');
  await page.locator('.live-discussion').getByRole('textbox').fill('Review approved Drive evidence');await page.getByRole('button',{name:'Send',exact:true}).click();
  await page.locator('.live-discussion').getByLabel('Discussion messages',{exact:true}).waitFor();await drive.getByRole('checkbox').click();await page.waitForFunction(()=>document.querySelector('.live-drive input[type=checkbox]')?.checked);await page.locator('.live-discussion').getByRole('textbox').fill('What needs review?');await page.getByRole('button',{name:'Ask BuyerOS',exact:true}).click();
  await page.getByText('EPHEMERAL_DRIVE_ANSWER',{exact:true}).waitFor();
  assert.doesNotMatch(await page.evaluate(()=>Object.values(localStorage).join('')),/EPHEMERAL_DRIVE_ANSWER/);
  assert.equal(writes[0].key,writes[1].key);assert.equal(writes[0].version,'"1"');assert.deepEqual(writes[2].body,{folder_ids:['folder_one']});
  stale=true;await drive.getByRole('button',{name:'Disconnect Google Drive',exact:true}).click();
  await drive.getByText('The connection changed. Reload Google Drive before trying again.',{exact:true}).waitFor();
  stale=false;status={...status,available:false};await drive.getByRole('button',{name:'Reload Google Drive',exact:true}).click();
  await drive.getByText('Google Drive is unavailable. Ask a workspace admin to check the connection.',{exact:true}).waitFor();
  await drive.getByRole('button',{name:'Disconnect Google Drive',exact:true}).click();
  await drive.getByRole('button',{name:'Connect Google Drive',exact:true}).waitFor();assert.equal(await drive.getByRole('button',{name:'Connect Google Drive',exact:true}).isDisabled(),true);
  status={...status,connected:true,available:true,can_manage:false,folders:[{id:'folder_one',label:'Google Drive folder'}]};await drive.getByRole('button',{name:'Reload Google Drive',exact:true}).click();
  await drive.getByText('Google Drive connected',{exact:true}).waitFor();assert.equal(await drive.getByRole('button',{name:'Disconnect Google Drive',exact:true}).count(),0);
  denied=true;await drive.getByRole('button',{name:'Reload Google Drive',exact:true}).click();await drive.getByText('Google Drive access is denied for this workspace.',{exact:true}).waitFor();assert.equal(await drive.getByRole('checkbox').count(),0);
  const before=reads.length;await page.goto(server.resolvedUrls.local[0]+'fixture?flag=off');await page.getByRole('button',{name:'Operations',exact:true}).waitFor();assert.equal(await page.getByRole('region',{name:'Google Drive',exact:true}).count(),0);assert.equal(reads.length,before);
  assert.deepEqual(errors,[]);
 }finally{await browser?.close();await server.close();rmSync(dir,{recursive:true,force:true});}
});

test('Stage 4 a definitively rejected Drive import can save after removing the rejected selections',async()=>{
 const {createServer}=await import('vite');const {mkdirSync,mkdtempSync,writeFileSync,rmSync}=await import('node:fs');
 const {contextResponse,browserEntry}=await import('./conversation-browser-fixture.mjs');
 mkdirSync('work',{recursive:true});const dir=mkdtempSync('work/conversation-drive-import-');writeFileSync(dir+'/entry.jsx',browserEntry);
 const server=await createServer({configFile:false,root,cacheDir:resolve(dir,'node_modules/.vite'),resolve:{alias:{'@':root}},optimizeDeps:{noDiscovery:true,include:['react','react-dom/client','react/jsx-runtime','react/jsx-dev-runtime','lucide-react']},server:{host:'127.0.0.1',port:0,watch:{ignored:['**/.sites-runtime/**','**/.venv/**','**/.vercel/**','**/dist/**']}},appType:'custom'});
 server.middlewares.use((req,res,next)=>{if(req.url?.startsWith('/fixture')){res.setHeader('content-type','text/html');res.end('<html><body><div id="root"></div><script type="module" src="/'+dir+'/entry.jsx"></script></body></html>');}else next();});
 await server.listen();let browser;
 try{
  browser=await chromium.launch({...(process.env.BUYEROS_CORE_CHROMIUM?{executablePath:process.env.BUYEROS_CORE_CHROMIUM}:{}),headless:true});
  const page=await browser.newPage(),imports=[],errors=[];page.on('pageerror',error=>errors.push(error.message));
  const source={id:'drive:12345678-1234-4123-8123-123456789012:file_one',label:'Google Drive item'};
  await page.route('**/v1/**',route=>{
   const req=route.request(),url=new URL(req.url()),path=url.pathname;
   const ok=data=>route.fulfill({json:{data,data_mode:'live',request_id:'stage4-import'}});
   if(path.includes('/conversation-connections/'))return ok(path.endsWith('/items')?{items:[source]}:{version:3,connected:true,available:true,can_manage:false,folders:[{id:'folder_one',label:'Google Drive folder'}],residency_preference:'HK',metadata_cache_seconds:0});
   if(req.method()==='POST'&&path.endsWith('/conversation-threads')){
    const body=req.postDataJSON();imports.push({body,key:req.headers()['idempotency-key']});
    if(body.sources.length)return route.fulfill({status:422,json:{code:'CONVERSATION_SOURCE_UNAVAILABLE',message:'selected sources need review'}});
    return ok({id:'12345678-1234-4123-8123-123456789012',version:1,access:'owner',shareCount:0,templateId:body.template_id,title:body.title,messages:body.messages.map((message,index)=>({...message,id:'m'+index})),sources:[],runs:[],createdAt:1,updatedAt:2});
   }
   return ok(contextResponse(url));
  });
  await page.goto(server.resolvedUrls.local[0]+'fixture');await openDiscussion(page);await page.getByText('project-evidence.pdf',{exact:false}).waitFor();
  await page.locator('.live-discussion').getByRole('textbox').fill('Keep this local note');await page.getByRole('button',{name:'Send',exact:true}).click();
  await page.locator('.live-discussion').getByLabel('Discussion messages',{exact:true}).waitFor();await page.getByRole('region',{name:'Google Drive',exact:true}).getByRole('checkbox').click();
  await page.waitForFunction(()=>document.querySelector('.live-drive input[type=checkbox]')?.checked);
  await page.getByRole('button',{name:'Save to workspace',exact:true}).click();await page.getByRole('button',{name:'Confirm workspace save',exact:true}).click();
  await page.getByText('Workspace discussions are unavailable. Your unsaved text is still here.',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Cancel',exact:true}).click();await page.getByText('Selected for this discussion',{exact:false}).click();
  await page.getByRole('button',{name:'Remove selection',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.live-discussion details summary')?.textContent?.includes('(0)'));
  await page.getByRole('button',{name:'Save to workspace',exact:true}).click();await page.getByRole('button',{name:'Confirm workspace save',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.live-thread-actions')?.textContent?.includes('Open workspace discussion')||document.querySelector('dialog[open] [role=status]')?.textContent?.includes('unavailable'));
  assert.equal(await page.getByRole('button',{name:'Open workspace discussion',exact:true}).count(),1,'the retried import must use the updated source selection');
  assert.equal(imports.length,2);assert.deepEqual(imports[0].body.sources,[source]);assert.deepEqual(imports[1].body.sources,[]);assert.notEqual(imports[0].key,imports[1].key);
  assert.deepEqual(imports[1].body.messages,[{text:'Keep this local note'}]);assert.deepEqual(errors,[]);
 }finally{await browser?.close();await server.close();rmSync(dir,{recursive:true,force:true});}
});



