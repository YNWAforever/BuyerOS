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
const {ScopeSwitcher}=await import('../features/live/scope-switcher.tsx');
const {AccountMenu}=await import('../features/live/account-menu.tsx');
const cssDir='.vercel/output/static/_next/static/css';
const css=readFileSync(cssDir+'/'+readdirSync(cssDir).find(name=>/^layout\..*\.css$/.test(name)),'utf8');
for(const conversationHome of [false,true])test(`conversation navigation fits desktop, tablet and mobile (flag ${conversationHome?'ON':'OFF'})`,async()=>{
 const browser=await chromium.launch({...(process.env.BUYEROS_CORE_CHROMIUM?{executablePath:process.env.BUYEROS_CORE_CHROMIUM}:{}),headless:true});
 try{
  const navigation=LiveNavigation({t:x=>x,navigate:()=>{},pathname:'/app',authorized:true,projectKnown:true,canEdit:true,projectActive:true,canCreate:true,conversationHome});
  const scope=ScopeSwitcher({t:x=>x,workspace:'a1000000-0000-4000-8000-000000000001',project:'a2000000-0000-4000-8000-000000000001',
    workspaces:{kind:'ready',items:[{id:'a1000000-0000-4000-8000-000000000001',name:'FIMMICK',roles:['workspace_admin']}]},
    projects:{kind:'ready',items:[{id:'a2000000-0000-4000-8000-000000000001',name:'Golden Resources'}]},
    authorized:true,canCreate:true,accessChecking:false,accessError:'',notice:'',onWorkspace:()=>{},onProject:()=>{},onNewProject:()=>{},onCheckAccess:()=>{}});
  const footer=AccountMenu({t:x=>x,email:'owner@example.test',workspaceName:'FIMMICK',roles:['workspace_admin'],authorized:true,locale:'en',
    onLocale:()=>{},localeSaving:false,localeDisabled:false,accessDetails:null,accessChecking:false,accessError:'',diagnostic:null,
    onRetryAccess:()=>{},onSignOut:()=>{}});
  const frame=LiveFrame({t:x=>x,pathname:'/app',navigation,scope,footer,header:null,children:null,conversationHome});
  const page=await browser.newPage();await page.setContent('<style>'+css+'</style>'+renderToStaticMarkup(frame));
  for(const width of [320,390,480,481,600,768,820,1023,1024,1440]){
   await page.setViewportSize({width,height:1000});
   const pageWidth=await page.evaluate(()=>document.documentElement.scrollWidth);
   assert.ok(pageWidth<=width,`viewport ${width}px overflows to ${pageWidth}px`);
   assert.equal(await page.getByRole('heading',{name:'Workspaces',exact:true}).count(),0,'no repeated selector panel heading');
  }
  const account=page.locator('summary[aria-label="Account menu"]');
  assert.equal(await account.count(),1,'one account control in the sidebar');
  await account.click();
  const accountPanel=page.locator('.live-account-panel');
  assert.equal(await accountPanel.getByRole('button',{name:'Sign out',exact:true}).isVisible(),true);
  assert.equal(await page.getByRole('group',{name:'Manage',exact:true}).getByRole('button',{name:'Operations',exact:true}).count(),1,'workspace administration is a single Manage entry');
 }finally{await browser.close();}
});

// Project home is the SME front door: one question, one composer, six task cards,
// recent work, and no repeated workspace/project selector panels.
test('project home is a task-first dashboard with one heading and no selector panels',async()=>{
 const harness=await fixtureHarness({route:'/app'});
 try{
  const {page,posts}=harness;
  await page.getByRole('textbox',{name:'Message BuyerOS'}).waitFor();
  assert.equal(await page.getByRole('heading',{level:1}).count(),1,'exactly one h1');
  assert.equal(await page.getByRole('heading',{name:'What do you want to get done?',exact:true}).count(),1);
  assert.equal(await page.getByRole('heading',{name:'Start with a task',exact:true}).count(),1);
  assert.equal(await page.locator('.conversation-home-card').count(),6,'all six guided outcomes are visible');
  assert.equal(await page.locator('.live-scope-grid').count(),0,'no selector panels on the home route');
  assert.match(await page.locator('.conversation-home-recent').innerText(),/Research buyer/,'continue rows link saved threads');
  assert.match(await page.locator('.conversation-home-kicker').innerText(),/Fixture project/i);
  await page.screenshot({path:shots+'/home-desktop.png',fullPage:true});
  // A card prefills the reviewed prompt; it never sends on its own.
  await page.locator('.conversation-home-card').first().click();
  assert.equal(await page.getByRole('textbox',{name:'Message BuyerOS'}).inputValue(),'Help me set up my first BuyerOS project.');
  assert.equal(posts.length,0,'selecting a task card sends nothing');
 }finally{await harness.close();}
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
// Bounded aggregates only: the dashboard must never need thread text to render.
const metricsFixture={window_days:7,generated_at:'2026-11-11T12:00:00Z',
 turns:{total:3,by_status:{completed:2,needs_input:1}},
 latency_ms:{samples:3,p50:900,p95:1500,max:2100},
 proposals:{total:2,by_capability:{'research-market':2},by_decision:{approve:1,reject:0},awaiting_decision:1},
 tool_activity:{by_state:{completed:1},outcome_unknown:1},
 model:{unavailable_turns:1},
 budget:{priced_proposals:0,unknown_price_proposals:1,no_cost_proposals:1,
  may_incur_provider_charges:0,estimated:[]}};

function standardApi(options={}){
 const {absent=false,failFirstSend=false,contentOnly=false,skills=null,manage=false,access=null,second=false}=options;
 return async ({req,url,state})=>{
  const method=req.method();
  if(url.pathname.endsWith('/conversation-turns')&&method==='OPTIONS')
   return absent?{status:404,json:{code:'NOT_FOUND',message:'request failed'}}:{status:204};
  if(url.pathname===prefix)return {json:fixture.envelope({id:project,workspace_id:workspace,status:'active',offer_revision:1,active_icp_version_id:fixture.profileId,name:'Fixture project'})};
  if(url.pathname.endsWith('/sales/skills'))return {json:fixture.envelope({skills:skills??[{id:'sales-research'},{id:'review-buyers'}]})};
  if(url.pathname.endsWith('/sales-tasks/capability'))return {json:fixture.envelope({admission_enabled:true})};
  const preferencePut=url.pathname.match(/\/conversation-threads\/([0-9a-f-]+)\/preferences$/);
  if(preferencePut&&method==='PUT'){
   const body=req.postDataJSON();
   if(!manage)return {status:404,json:{code:'NOT_FOUND',message:'not managed'}};
   if(state.failPreferences)return {status:500,json:{code:'INTERNAL',message:'private server detail'}};
   state.preferences={...(state.preferences??{}),[preferencePut[1]]:{pinned:body.pinned===true,archived:body.archived===true}};
   return {json:fixture.envelope(state.preferences[preferencePut[1]])};
  }
  if(url.pathname.endsWith('/conversation-threads')&&method==='GET'){
   const searching=Boolean(url.searchParams.get('q'))||url.searchParams.get('archived')==='true';
   if(manage){
    const archivedView=url.searchParams.get('archived')==='true',q=(url.searchParams.get('q')??'').trim().toLowerCase();
    const project=row=>{const stored=(state.preferences??{})[row.id];
     return {...row,access:state.access??access??row.access,pinned:stored?.pinned===true,archived:stored?.archived===true};};
    let rows=[fixture.studioSummary,...(second?[{...fixture.studioSummary,id:fixture.newThreadId,title:'Other discussion',
     updatedAt:fixture.studioSummary.updatedAt+120_000,archived:false,pinned:false}]:[])].map(project);
    if(archivedView)rows=rows.filter(row=>row.archived);
    if(q)rows=rows.filter(row=>row.title.toLowerCase().includes(q));
    return {json:fixture.envelope({items:rows,total:rows.length,offset:0,limit:50})};
   }
   const items=searching?[]:[fixture.studioSummary];
   return {json:fixture.envelope({items,total:items.length,offset:0,limit:50})};
  }
  const threadGet=url.pathname.match(/\/conversation-threads\/([0-9a-f-]+)$/);
  if(threadGet&&method==='GET'){
   if(state.createdThread&&state.createdThread.id===threadGet[1]){state.thread=state.createdThread;return {json:fixture.envelope(state.createdThread)};}
   const resolved=contentOnly?{...fixture.studioThread,sources:[],messages:[{...fixture.userMessage},
     {...fixture.assistantMessage,parts:[{kind:'text',text:'Here is the brief.'}]}]}:fixture.studioThread;
   if(manage){
    const stored=(state.preferences??{})[threadGet[1]];
    return {json:fixture.envelope({...resolved,access:state.access??access??resolved.access,archived:stored?.archived===true})};
   }
   state.thread=state.thread??resolved;
   return {json:fixture.envelope(resolved)};
  }
  if(url.pathname.endsWith('/conversation-turns/metrics')&&method==='GET'){
   state.metricsReads=(state.metricsReads??0)+1;
   if(state.metricsFail)return {status:503,json:{code:'INTERNAL_ERROR',message:'private server detail'}};
   return {json:fixture.envelope(metricsFixture)};
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
 const requests=[],posts=[],errors=[],state={thread:null,createdThread:null,turnCalls:0,preferences:{},failPreferences:false};
 page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/v1/**',async route=>{
  const request=route.request(),url=new URL(request.url());
  const writeBody=request.method()==='GET'?undefined:(()=>{try{return request.postDataJSON();}catch{return undefined;}})();
  requests.push({method:request.method(),path:url.pathname,search:url.search,...(writeBody===undefined?{}:{body:writeBody})});
  if(request.method()==='POST'){let body;try{body=request.postData()===null?undefined:request.postDataJSON();}catch{body=undefined;}posts.push({path:url.pathname,body,key:request.headers()['idempotency-key'],match:request.headers()['x-buyeros-if-match']??request.headers()['if-match']});}
  const answer=await handler({req:request,url,state,requests,posts});
  if(answer){
    if(answer.status===204)return route.fulfill({status:204});
    if(answer.raw)return route.fulfill({status:answer.raw.status??200,headers:answer.raw.headers??{},body:answer.raw.body??''});
    if(answer.hold)await answer.hold;
    return route.fulfill({status:answer.status??200,headers:{'content-type':'application/json','x-request-id':'conversation-studio'},body:JSON.stringify(answer.json)});
  }
  const data=fixture.contextResponse(url);
  return route.fulfill({status:data?200:403,headers:{'content-type':'application/json','x-request-id':'conversation-studio'},body:JSON.stringify(data?{data,data_mode:'live',request_id:'conversation-studio'}:{error:{code:'PERMISSION_DENIED',message:'denied'},request_id:'conversation-studio'})});
 });
 const query='fixture?route='+encodeURIComponent(initialRoute)+(flag?'':'&flag=off')+(locale==='zh-HK'?'&locale=zh-HK':'');
 await page.goto(server.resolvedUrls.local[0]+query);
 await page.addStyleTag({content:css+readFileSync('features/live/discussion.css','utf8')});
 return {page,browser,server,dir,requests,posts,errors,state,origin:server.resolvedUrls.local[0],
  close:async()=>{await browser.close();await server.close();rmSync(dir,{recursive:true,force:true});}};
}
async function waitForDestination(page,expected){await page.waitForFunction(value=>window.lastDestination===value,expected);}

test('conversation-first transcript renders typed inline parts and inline decisions',async()=>{
 const previewRequests=[];
 let previewDenied=false;
 const baseApi=standardApi();
 const harness=await fixtureHarness({handler:async input=>{
  const {req,url}=input;
  if(req.method()==='GET'&&/\/sales-outputs\/[0-9a-f-]+\/preview$/.test(url.pathname)){
   previewRequests.push({path:url.pathname,search:url.search});
   if(previewDenied)return {status:403,json:{code:'FORBIDDEN',message:'private server detail'}};
   return {raw:{status:200,headers:{'content-type':'text/html; charset=utf-8',
     'content-security-policy':"default-src 'none'; sandbox",'referrer-policy':'no-referrer','cache-control':'no-store'},
     body:'<!doctype html><html><body><h1>Research brief preview</h1><p>Server rendered.</p></body></html>'}};
  }
  return baseApi(input);
 }});
 try{
  const {page,errors,posts,origin}=harness;
  const transcript=page.locator('.conversation-transcript');
  // Inline navigation unmounts the studio; return to the canonical thread route
  // explicitly rather than reloading the destination screen.
  const threadUrl=origin+'fixture?route='+encodeURIComponent('/app/discussions/s/'+threadId);
  // A new document loses the harness-injected stylesheet; re-add it with the CSS-only
  // screenshots and use the canonical thread route after inline navigation.
  const stylePage=()=>page.addStyleTag({content:css+readFileSync('features/live/discussion.css','utf8')});
  const openThread=async()=>{await page.goto(threadUrl);await stylePage();await page.getByText('Here is the brief.',{exact:true}).waitFor();};
  await page.getByRole('textbox',{name:'Message BuyerOS'}).waitFor();
  await page.getByText('Here is the brief.',{exact:true}).waitFor();
  // Inline tool activity keeps its truthful state.
  assert.equal(await page.getByText('Completed',{exact:true}).count(),1);
  // Both inline entry points exist before either navigation can unmount the studio.
  assert.equal(await transcript.getByRole('button',{name:'Open saved output',exact:true}).count(),1);
  assert.equal(await transcript.getByRole('button',{name:'Offer document',exact:true}).count(),1);
  // Increment 2.5: preview is lazy — nothing is fetched before expansion.
  assert.equal(previewRequests.length,0,'no preview request before expansion');
  assert.equal(await transcript.locator('iframe').count(),0);
  await page.screenshot({path:shots+'/transcript-inline-parts-desktop.png',fullPage:true});
  // Expand once: exactly one authenticated request at the output's own revision,
  // rendered as server-authored HTML in a strictly sandboxed frame.
  const outputCard=transcript.locator('.conversation-output').first();
  await outputCard.getByText('Preview',{exact:true}).click();
  const previewFrame=page.locator('iframe.conversation-output-preview-frame');
  await previewFrame.waitFor();
  assert.equal(previewRequests.length,1,'exactly one preview request per expansion');
  assert.match(previewRequests[0].path,new RegExp(`/sales-outputs/${outputId}/preview$`));
  assert.equal(previewRequests[0].search,'?revision=1');
  assert.equal(await previewFrame.getAttribute('sandbox'),'','the frame is sandboxed with no tokens');
  assert.equal(await previewFrame.getAttribute('referrerpolicy'),'no-referrer');
  const previewDoc=await previewFrame.getAttribute('srcdoc');
  assert.match(previewDoc,/^<meta http-equiv="Content-Security-Policy" content="default-src 'none'">/,
    'srcdoc prepends the endpoint CSP because response headers do not apply to a srcdoc document');
  assert.match(previewDoc,/Research brief preview/);
  assert.match(await previewFrame.getAttribute('title'),/Preview: Research brief/);
  assert.equal(await transcript.getByRole('button',{name:'Open saved output',exact:true}).count(),1,'open stays available while previewing');
  await outputCard.getByText('Preview',{exact:true}).click();
  assert.equal(await previewFrame.isVisible(),false,'collapse hides the frame');
  await outputCard.getByText('Preview',{exact:true}).click();
  await previewFrame.waitFor();
  assert.equal(previewRequests.length,1,'re-expansion is cached, never refetched');
  await outputCard.getByText('Preview',{exact:true}).click();
  // Citations are real links to the canonical record.
  await transcript.getByRole('button',{name:'Offer document',exact:true}).click();
  await waitForDestination(page,`/app/discover/edit?document=${documentId}&workspace=${workspace}&project=${project}`);
  // Output links open the saved revision (return to the thread route first).
  await openThread();
  await transcript.getByRole('button',{name:'Open saved output',exact:true}).click();
  await waitForDestination(page,`/app/documents/${outputId}?workspace=${workspace}&project=${project}`);
  await openThread();
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
  await stylePage();
  await page.getByText('Here is the brief.',{exact:true}).waitFor();
  assert.equal(posts.filter(row=>row.path.endsWith('/conversation-turns')).length,turnsBefore,'reload never replays a turn');
  // zh-HK pass: same surface, translated labels.
  await page.getByRole('button',{name:'Change language',exact:true}).click();
  await page.getByRole('button',{name:'拒絕',exact:true}).waitFor();
  await page.getByRole('button',{name:'批准',exact:true}).waitFor();
  await page.getByText('預覽',{exact:true}).first().waitFor();
  await page.screenshot({path:shots+'/zh-hk-desktop.png',fullPage:true});
  // Denied preview: honest notice, no frame, open action unchanged, no auto-retry.
  previewDenied=true;
  await page.reload();
  await stylePage();
  await page.getByText('Here is the brief.',{exact:true}).waitFor();
  const deniedCard=page.locator('.conversation-transcript .conversation-output').first();
  const beforeDenied=previewRequests.length;
  await deniedCard.getByText('Preview',{exact:true}).click();
  await page.getByText('You no longer have access to this output.',{exact:true}).waitFor();
  assert.equal(previewRequests.length,beforeDenied+1,'one denied preview request');
  assert.equal(await page.locator('iframe.conversation-output-preview-frame').count(),0,'a denied preview renders no frame');
  assert.equal(await page.locator('.conversation-transcript').getByRole('button',{name:'Open saved output',exact:true}).count(),1);
  const deniedCount=previewRequests.length;
  await page.waitForTimeout(400);
  assert.equal(previewRequests.length,deniedCount,'a denied preview is never retried automatically');
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
  assert.equal(await page.locator('input[type=file]').count(),0,'attach is hidden on /new');
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
  // Leave to the conversation home, then reopen the same thread from the list:
  // home is a dashboard now, so it must not silently restore the last thread.
  await page.getByRole('button',{name:'Fixture home',exact:true}).click();
  await page.locator('.conversation-thread-items').getByRole('button',{name:'Research buyer',exact:true}).click();
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
  await views.getByRole('button',{name:'Details',exact:true}).click();
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
  await page.getByText('Workspace discussions are unavailable. Your unsaved text is still here.',{exact:true}).first().waitFor();
  assert.equal(writes.length,1);assert.deepEqual(writes[0].body.sources.map(source=>source.id),[thread.sources[1].id,citationId]);
  await panel.getByRole('button',{name:'Remove unavailable Google Drive selections',exact:true}).click();
  await panel.getByRole('button',{name:'Remove unavailable Google Drive selections',exact:true}).waitFor({state:'detached'});
  assert.deepEqual(writes[1].body.sources,[{id:citationId,label:'Offer document'}]);
  assert.equal(thread.sources.length,1,'only the unavailable Drive references are dropped');
  // A stale revision keeps the unsent text and says exactly what to do next.
  await page.getByRole('textbox',{name:'Message BuyerOS'}).fill('Keep this after the conflict');
  await page.getByRole('button',{name:'Send message',exact:true}).click();
  await page.getByText('This discussion changed. Copy any unsaved text, reload and send again.',{exact:true}).first().waitFor();
  assert.equal(await page.getByRole('textbox',{name:'Message BuyerOS'}).inputValue(),'Keep this after the conflict');
  assert.equal(await page.getByRole('button',{name:'Retry send',exact:true}).count(),1);
  // A viewer reads the same discussion but cannot decide, send or change sources.
  thread={...thread,access:'viewer'};
  await page.reload();
  const viewerComposer=page.getByRole('textbox',{name:'Message BuyerOS'});
  await viewerComposer.waitFor();
  // The composer is disabled from the moment a saved thread is opened until its
  // access resolves; poll the disabled state so the product rule is asserted, not timing.
  await page.waitForFunction(()=>{const node=document.querySelector('.conversation-compose textarea');return node instanceof HTMLTextAreaElement&&node.disabled;});
  assert.equal(await viewerComposer.isDisabled(),true);
  assert.equal(await page.getByRole('button',{name:'Cancel turn',exact:true}).count(),0,'a viewer never gets a mutating cancel action');
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
  const transcript=page.locator('.conversation-transcript');
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
  assert.equal(await page.locator('.conversation-transcript').count(),0,'no transcript for an unavailable thread');
  assert.equal(await page.getByRole('textbox',{name:'Message BuyerOS'}).isDisabled(),true,'a failed thread read never opens a writable composer');
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
  // Scope to the card's own visible cost line: the collapsed explainer also holds
  // a cost row in the DOM, so a transcript-wide count would double-count.
  assert.equal(await transcript.locator('.conversation-proposal-cost').count(),1);
  assert.equal(await page.locator('.conversation-proposal-cost').innerText(),'Cost review required before any paid request.');
  // Approval returns a terminal configuration outcome; the card must become inert.
  await transcript.getByRole('button',{name:'Approve',exact:true}).click();
  await transcript.getByText('Company enrichment cannot run until Xverum dispatch is enabled by an administrator. Nothing was executed.').first().waitFor();
  // The explainer mirrors the terminal state inside its collapsed DOM; scope both
  // to the card's own visible elements so the counts stay strict but unambiguous.
  assert.equal(await transcript.locator('.conversation-tool').getByText('Failed',{exact:true}).count(),1);
  assert.equal(await transcript.locator('.conversation-proposal-state').filter({hasText:'This step cannot run in the current configuration.'}).count(),1);
  assert.equal(await transcript.getByRole('button',{name:'Approve',exact:true}).count(),0,'terminal configuration leaves no actionable decision');
  assert.equal(await transcript.getByRole('button',{name:'Reject',exact:true}).count(),0);
  const decision=posts.find(row=>row.path.endsWith('/decisions'));
  assert.deepEqual(decision.body,{proposal_id:buyerProposalId,decision:'approve',expected_thread_version:1});
  assert.equal(decision.match,'"1"');
 }finally{await harness.close();}
});

/** Increment C fixture: stream event routes layered over the standard API stub. */
function streamingApi(overrides={}){
 const base=standardApi();
 return async input=>{
  const {req,url}=input,method=req.method(),path=url.pathname;
  if(method==='OPTIONS'&&path.endsWith('/events'))return {status:204};
  if(method==='POST'&&path.endsWith('/conversation-turns')&&overrides.turn)return overrides.turn(input);
  if(method==='GET'&&/\/conversation-turns\/[0-9a-f-]+\/events$/.test(path)&&overrides.events)
    return overrides.events({...input,after:Number(url.searchParams.get('after')??'0')});
  if(method==='POST'&&/\/conversation-turns\/[0-9a-f-]+\/cancel$/.test(path)&&overrides.cancel)return overrides.cancel(input);
  if(method==='POST'&&/\/conversation-turns\/[0-9a-f-]+\/reconcile$/.test(path)&&overrides.reconcile)return overrides.reconcile(input);
  if(method==='GET'&&/\/conversation-threads\/[0-9a-f-]+$/.test(path)&&overrides.thread)return {json:fixture.envelope(overrides.thread())};
  return base(input);
 };
}

test('streamed turn shows live progress, reconnects from the last cursor and never duplicates persisted parts',async()=>{
 const streamId=fixture.streamTurnId;
 let eventRequests=[],releaseSecond,secondResolve;
 const secondArrived=new Promise(resolve=>{secondResolve=resolve;});
 // Production shape: the POST response already contains the persisted assistant message.
 const user2=fixture.userRow({id:'c5000000-0000-4000-8000-000000000001',seq:3,text:'Streamed follow-up',turnId:streamId});
 const answer=fixture.assistantRow({id:'c6000000-0000-4000-8000-000000000001',seq:4,text:'Persisted streamed answer',turnId:streamId,
   parts:[{kind:'text',text:'Persisted streamed answer'}]});
 const persistedThread=fixture.threadWith({messages:[...fixture.studioThread.messages,user2,answer],version:5});
 const harness=await fixtureHarness({handler:streamingApi({
   thread:()=>persistedThread,
   turn:()=>({json:fixture.envelope({thread:persistedThread,turn:{id:streamId,status:'completed',
     parts:[{kind:'text',text:'Persisted streamed answer'}],notices:[]}})}),
   events:async({after})=>{
     eventRequests.push(after);
     if(eventRequests.length===1)return {raw:{status:200,headers:{'content-type':'text/event-stream','cache-control':'no-store'},
       body:fixture.sse([[1,'turn.started',{status:'running'}],[2,'part',{index:0,part:{kind:'text',text:'Persisted streamed answer'}}]])}};
     secondResolve();
     await new Promise(resolve=>{releaseSecond=resolve;});
     return {raw:{status:200,headers:{'content-type':'text/event-stream','cache-control':'no-store'},
       body:fixture.sse([[3,'tool',{call_id:'c7000000-0000-4000-8000-000000000001',capability:'xverum.enrich_company',state:'completed'}],
         [4,'turn.final',{status:'completed'}]])}};
   },
 })});
 try{
   const {page,posts,errors}=harness;
   const composer=page.getByRole('textbox',{name:'Message BuyerOS'});
   await composer.waitFor();
   await composer.fill('Streamed follow-up');
   await page.getByRole('button',{name:'Send message',exact:true}).click();
   // Persisted response wins immediately: exactly one persisted assistant row, no provisional copy.
   await page.getByText('Persisted streamed answer',{exact:true}).waitFor();
   assert.equal(await page.getByText('Persisted streamed answer',{exact:true}).count(),1,'exactly one persisted assistant row');
   assert.equal(await page.getByText('Shown in this tab only',{exact:true}).count(),0,'no provisional pseudo-row when persisted parts exist');
   // The stream tail is deterministic: the second SSE response is held until released.
   await page.locator('.conversation-stream').waitFor();
   assert.equal(await composer.isDisabled(),true,'composer stays disabled while the stream is running');
   await page.screenshot({path:shots+'/stream-progress-desktop.png',fullPage:true});
   await secondArrived;
   assert.deepEqual(eventRequests,[0,2],'a reconnect resumes after the last seen seq');
   releaseSecond();
   await page.locator('.conversation-stream').waitFor({state:'detached'});
   await page.waitForFunction(()=>{const node=document.querySelector('.conversation-compose textarea');
     return node instanceof HTMLTextAreaElement&&!node.disabled;});
   assert.equal(await page.getByText('Persisted streamed answer',{exact:true}).count(),1,'final refetch never duplicates the persisted row');
   assert.equal(await page.getByText('Streamed follow-up',{exact:true}).count(),1,'no duplicate user row after reconnect');
   assert.equal(posts.filter(row=>row.path.endsWith('/conversation-turns')).length,1,'reconnect never re-submits the turn');
   assert.equal(posts.some(row=>/\/decisions$|\/xverum\/|\/quotes?$|\/approve$|\/send$/.test(row.path)),false,'streaming never dispatches paid work');
   assert.deepEqual(errors,[]);
 }finally{await harness.close();}
});

test('a running turn can be cancelled from the keyboard without a new turn',async()=>{
 // The synchronous POST contract returns a final turn today; this fixture models the
 // early-response/async branch the cancel endpoint exists for, then verifies the
 // cancel contract itself (no body, strong precondition) and that no turn repeats.
 const streamId=fixture.streamTurnId;
 const user2=fixture.userRow({id:'c8000000-0000-4000-8000-000000000001',seq:3,text:'Cancellable follow-up',turnId:streamId});
 const pending=fixture.threadWith({messages:[...fixture.studioThread.messages,user2],version:4});
 const cancelledThread=fixture.threadWith({messages:pending.messages,version:5});
 let cancelled=false;
 const harness=await fixtureHarness({handler:streamingApi({
   thread:()=>cancelled?cancelledThread:fixture.studioThread,
   turn:()=>({json:fixture.envelope({thread:pending,turn:{id:streamId,status:'needs_input',parts:[],notices:[]}})}),
   events:()=>({raw:{status:200,headers:{'content-type':'text/event-stream','cache-control':'no-store'},
     body:fixture.sse([[1,'turn.started',{status:'running'}]])}}),
   cancel:()=>{cancelled=true;return {json:fixture.envelope({thread:cancelledThread,
     turn:{id:streamId,status:'cancelled',parts:[],notices:[]}})};},
 })});
 try{
   const {page,posts,errors}=harness;
   const composer=page.getByRole('textbox',{name:'Message BuyerOS'});
   await composer.waitFor();
   await composer.fill('Cancellable follow-up');
   await page.getByRole('button',{name:'Send message',exact:true}).click();
   const cancel=page.getByRole('button',{name:'Cancel turn',exact:true});
   await cancel.waitFor();
   await cancel.focus();await page.keyboard.press('Enter');
   await page.locator('.conversation-stream').waitFor({state:'detached'});
   const request=posts.find(row=>row.path.endsWith('/cancel'));
   assert.ok(request,'cancel reaches the cancel endpoint');
   assert.equal(request.body,undefined,'cancel sends no body');
   assert.equal(request.match,'"4"','cancel keeps the strong thread precondition');
   assert.ok(request.key);
   assert.equal(posts.filter(row=>row.path.endsWith('/conversation-turns')).length,1);
   await page.waitForFunction(()=>{const node=document.querySelector('.conversation-compose textarea');
     return node instanceof HTMLTextAreaElement&&!node.disabled;});
   assert.equal(await page.getByText('Cancellable follow-up',{exact:true}).count(),1);
   assert.equal(posts.some(row=>/\/decisions$|\/xverum\/|\/quotes?$|\/approve$|\/send$/.test(row.path)),false);
   assert.deepEqual(errors,[]);
 }finally{await harness.close();}
});

test('outcome_unknown recovery reconciles the saved result without repeating the turn',async()=>{
 const streamId=fixture.streamTurnId;
 let resolved=false;
 const unknownParts=[{kind:'notice',code:'XVERUM_DISPATCH_NOT_ENABLED',message:'The provider result is unconfirmed.'},
   {kind:'tool_activity',call_id:'c9000000-0000-4000-8000-000000000001',capability:'xverum.enrich_company',title:'Enrich company',state:'outcome_unknown'}];
 const unknownAssistant=fixture.assistantRow({id:'ca000000-0000-4000-8000-000000000001',seq:2,text:'Enrichment outcome unknown',turnId:streamId,parts:unknownParts});
 const unknownThread=fixture.threadWith({messages:[fixture.studioThread.messages[0],unknownAssistant],version:4});
 const resolvedAssistant=fixture.assistantRow({id:'cb000000-0000-4000-8000-000000000001',seq:3,text:'Recovered result',turnId:'cc000000-0000-4000-8000-000000000001',
   parts:[{kind:'text',text:'Recovered result'},{kind:'tool_activity',call_id:'c9000000-0000-4000-8000-000000000001',capability:'xverum.enrich_company',title:'Enrich company',state:'completed'}]});
 const resolvedThread=fixture.threadWith({messages:[fixture.studioThread.messages[0],resolvedAssistant],version:5});
 const harness=await fixtureHarness({handler:streamingApi({
   thread:()=>resolved?resolvedThread:unknownThread,
   turn:()=>({json:fixture.envelope({thread:unknownThread,turn:{id:streamId,status:'outcome_unknown',parts:unknownParts,notices:[]}})}),
   events:()=>({raw:{status:200,headers:{'content-type':'text/event-stream','cache-control':'no-store'},
     body:fixture.sse([[1,'turn.started',{status:'running'}],[2,'turn.final',{status:'outcome_unknown'}]])}}),
   reconcile:()=>{resolved=true;return {json:fixture.envelope({thread:resolvedThread,
     turn:{id:'cc000000-0000-4000-8000-000000000001',status:'completed',parts:[{kind:'text',text:'Recovered result'}],notices:[]}})};},
 })});
 try{
   const {page,posts,errors}=harness;
   const composer=page.getByRole('textbox',{name:'Message BuyerOS'});
   await composer.waitFor();
   await composer.fill('Recover this outcome');
   await page.getByRole('button',{name:'Send message',exact:true}).click();
   await page.getByText('The outcome is unconfirmed. Check the saved result before trying again.',{exact:true}).waitFor();
   await page.getByRole('button',{name:'Check result',exact:true}).click();
   await page.locator('.conversation-compose').getByText('The saved result was checked.',{exact:true}).waitFor();
   await page.getByText('Recovered result',{exact:true}).waitFor();
   assert.equal(await page.getByText('The outcome is unconfirmed. Check the saved result before trying again.',{exact:true}).count(),0,'the recovery action clears after reconciliation');
   const request=posts.find(row=>row.path.endsWith('/reconcile'));
   assert.ok(request,'reconcile reaches the read-only recovery endpoint');
   assert.equal(request.body,undefined,'reconcile sends no mutation payload');
   assert.equal(request.match,'"4"');
   assert.equal(posts.filter(row=>row.path.endsWith('/conversation-turns')).length,1,'reconcile never repeats the turn');
   assert.equal(posts.some(row=>/\/decisions$|\/xverum\/|\/quotes?$|\/approve$|\/send$/.test(row.path)),false,'recovery stays nonbillable');
   assert.deepEqual(errors,[]);
 }finally{await harness.close();}
});

test('proposal explainer expands persisted data, collapses and keeps a terminal card inert',async()=>{
 const explainerTurnId='d1000000-0000-4000-8000-000000000001',terminalTurnId='d2000000-0000-4000-8000-000000000001';
 const awaitingProposal={kind:'proposal',proposal_id:'d3000000-0000-4000-8000-000000000001',
   capability:'xverum.enrich_company',title:'Enrich company',rationale:'Synthetic rationale for the explainer.',
   arguments_preview:{company:'DeltaGrid',profile_version:2,company_id:'internal-secret'},
   cost:{kind:'provider_credits',amount:'0',unit:'credits',may_incur_provider_charges:true,known:false},
   requires_approval:true};
 const terminalProposal={kind:'proposal',proposal_id:'d4000000-0000-4000-8000-000000000001',
   capability:'drive.read',title:'Read Drive source',rationale:'Terminal fixture rationale.',
   arguments_preview:{folder:'Synthetic folder'},
   cost:{kind:'nonbillable',may_incur_provider_charges:false,known:true},requires_approval:true,
   decision:{choice:'reject',decided_at:'2026-11-09T10:30:00.000Z',decided_by:'a workspace member'}};
 const thread=fixture.threadWith({version:3,messages:[
   fixture.userRow({id:'d8000000-0000-4000-8000-000000000001',seq:1,text:'Explain these proposals',turnId:explainerTurnId}),
   fixture.assistantRow({id:'d5000000-0000-4000-8000-000000000001',seq:2,text:'Proposal summary',turnId:explainerTurnId,parts:[
     {kind:'text',text:'Here are two proposals.'},
     {kind:'citations',items:[{id:`document:${documentId}`,label:'Offer document',kind:'document',href:`/app/discover/edit?document=${documentId}`}]},
     awaitingProposal,terminalProposal]}),
   fixture.assistantRow({id:'d6000000-0000-4000-8000-000000000001',seq:3,text:'Drive read failed',turnId:terminalTurnId,parts:[
     {kind:'tool_activity',call_id:'d7000000-0000-4000-8000-000000000001',capability:'drive.read',title:'Read Drive source',
      state:'failed',started_at:'2026-11-08T00:00:00.000Z',error_code:'DRIVE_READ_NOT_ENABLED'}]}),
 ]});
 const harness=await fixtureHarness({handler:streamingApi({thread:()=>thread})});
 try{
   const {page,requests}=harness;
   await page.getByRole('textbox',{name:'Message BuyerOS'}).waitFor();
   const cards=page.locator('.conversation-proposal');
   await cards.first().waitFor();
   await page.waitForLoadState('networkidle');
   const awaiting=cards.first();
   const rationale=awaiting.getByText('Synthetic rationale for the explainer.',{exact:true});
   assert.equal(await rationale.count(),1);
   assert.equal(await rationale.isVisible(),false,'the explainer is collapsed by default');
   const before=requests.length;
   await awaiting.getByText('Why this proposal',{exact:true}).click();
   assert.equal(requests.length,before,'expanding the explainer performs no fetch');
   const why=awaiting.locator('.conversation-proposal-why');
   assert.equal(await rationale.isVisible(),true);
   assert.equal(await why.getByRole('button',{name:'Offer document',exact:true}).count(),1,'evidence citations stay linked');
   assert.equal(await why.getByText('Cost review required before any paid request.',{exact:true}).count(),1,'known:false keeps the shipped wording');
   assert.equal(await why.getByText('Awaiting approval',{exact:true}).count(),1,'approval state is visible');
   assert.equal(await why.getByText('Unknown',{exact:true}).count(),3,'an undecided proposal keeps explicit unknown decision rows');
   // Arguments render as "<label> <value>" inside one row, so target the row
   // precisely instead of an exact text match on the value alone.
   const argument=why.locator('.conversation-why-arguments li').filter({hasText:'DeltaGrid'});
   assert.equal(await argument.count(),1,'bounded arguments render');
   assert.equal((await argument.innerText()).replace(/\s+/g,' ').trim(),'company DeltaGrid');
   assert.equal(await awaiting.getByText('internal-secret',{exact:true}).count(),0,'internal argument values stay hidden');
   assert.equal(await awaiting.getByRole('button',{name:'Approve',exact:true}).count(),1,'existing approval action unchanged');
   await awaiting.getByText('Why this proposal',{exact:true}).click();
   assert.equal(await rationale.isVisible(),false,'collapse works');
   assert.equal(await awaiting.getByRole('button',{name:'Approve',exact:true}).count(),1);
   const terminal=cards.nth(1);
   await terminal.locator('.conversation-proposal-state').filter({hasText:'This step cannot run in the current configuration.'}).waitFor();
   assert.equal(await terminal.getByRole('button',{name:'Approve',exact:true}).count(),0,'a terminal proposal has no actions');
   assert.equal(await terminal.getByRole('button',{name:'Reject',exact:true}).count(),0);
   await terminal.getByText('Why this proposal',{exact:true}).click();
   const terminalWhy=terminal.locator('.conversation-proposal-why');
   assert.equal(await terminalWhy.getByText('Unknown',{exact:true}).count(),0,'a decided proposal renders persisted values, not Unknown rows');
   assert.equal(await terminalWhy.getByText('Rejected',{exact:true}).count(),1,'the Decision row shows the persisted outcome');
   assert.equal(await terminalWhy.getByText('A workspace member',{exact:true}).count(),1,'Decided by uses the privacy-bounded label');
   const terminalValues=await terminalWhy.locator('dd').allInnerTexts();
   assert.equal(terminalValues.length,8);
   assert.equal(terminalValues.includes('Unknown'),false,'no decision field falls back to Unknown when persisted');
   assert.match(terminalValues[7],/2026/,'Decided at renders the persisted timestamp');
   // EN + zh-HK labels for the new disclosure.
   await page.getByRole('button',{name:'Change language',exact:true}).click();
   await page.getByText('為何有此建議',{exact:true}).first().waitFor();
   const zhCard=page.locator('.conversation-proposal').first();
   await zhCard.getByText('為何有此建議',{exact:true}).click();
   assert.equal(await zhCard.getByText('理由',{exact:true}).count(),1);
   assert.equal(await page.getByText('工作區成員',{exact:true}).count(),1,'zh-HK label for the decision actor');
 }finally{await harness.close();}
});

test('composer attaches a document through the existing ingest path and persists the source',async()=>{
 let releaseComplete;const completeGate=new Promise(resolve=>{releaseComplete=resolve;});
 let uploadStarts=0,uploadChunks=0,uploadCompletes=0,attachFailures=1,access='owner';
 const sourcePuts=[];
 let manifest=null,uploadedDocument=null;
 let thread={...fixture.studioThread,sources:[],version:3,access};
 const baseApi=standardApi();
 const harness=await fixtureHarness({handler:async input=>{
  const {req,url}=input,method=req.method(),path=url.pathname;
  if(method==='POST'&&path===prefix+'/offer-document-uploads'){
   manifest=req.postDataJSON();uploadStarts+=1;
   return {json:fixture.envelope({id:'e1000000-0000-4000-8000-000000000001',workspace_id:workspace,project_id:project,
     filename:manifest.filename,media_type:manifest.media_type,byte_length:manifest.byte_length,source_sha256:manifest.source_sha256,
     chunk_size:2097152,chunk_count:Math.ceil(manifest.byte_length/2097152),received_chunks:[],status:'uploading'})};
  }
  if(method==='PUT'&&/\/offer-document-uploads\/[0-9a-f-]+\/chunks\/\d+$/.test(path)){uploadChunks+=1;return {json:fixture.envelope({})};}
  if(method==='POST'&&/\/offer-document-uploads\/[0-9a-f-]+\/complete$/.test(path)){
   uploadCompletes+=1;await completeGate;
   uploadedDocument={workspace_id:workspace,project_id:project,data_mode:'live',id:documentId,filename:manifest.filename,
     media_type:manifest.media_type,status:'ready',version:1,sha256:manifest.source_sha256,fact_candidates:[]};
   return {json:fixture.envelope(uploadedDocument)};
  }
  // Stateful project context: once the upload completes, the server-side document list
  // must include the just-ingested document (production behaviour), not a static fixture.
  if(method==='GET'&&path.endsWith('/offer-documents')){
   const rows=uploadedDocument?[uploadedDocument]:
     [{workspace_id:workspace,project_id:project,data_mode:'live',id:documentId,filename:'project-evidence.pdf',status:'ready',version:1,fact_candidates:[]}];
   return {json:fixture.envelope({items:rows,total:rows.length,offset:0,limit:20})};
  }
  if(/\/conversation-threads\/[0-9a-f-]+\/sources$/.test(path)&&method==='PUT'){
   const body=req.postDataJSON();
   sourcePuts.push({body,match:req.headers()['x-buyeros-if-match']??req.headers()['if-match']});
   if(attachFailures>0){attachFailures-=1;return {status:500,json:{code:'INTERNAL_ERROR',message:'private detail'}};}
   thread={...thread,sources:body.sources,version:thread.version+1,access};
   return {json:fixture.envelope(thread)};
  }
  if(/\/conversation-threads\/[0-9a-f-]+$/.test(path)&&method==='GET')
   return {json:fixture.envelope({...thread,access})};
  return baseApi(input);
 }});
 try{
  const {page,requests,errors}=harness;
  const composer=page.getByRole('textbox',{name:'Message BuyerOS'});
  await composer.waitFor();
  await page.getByText('Here is the brief.',{exact:true}).waitFor();
  const fileInput=page.getByLabel('Attach document');
  await fileInput.waitFor({state:'attached'});
  // Open the context Sources tab first so we can prove a post-attach refetch occurs.
  // Do not depend on a specific fixture row rendering here: assert the context read
  // was issued, then deterministically remount the picker for the uploaded row below.
  const panel=page.locator('.conversation-panel');
  const offerDocumentReads=()=>requests.filter(row=>row.method==='GET'&&row.path.endsWith('/offer-documents')).length;
  await panel.getByRole('tab',{name:'Sources',exact:true}).click();
  for(let attempt=0;attempt<100&&offerDocumentReads()===0;attempt+=1)await page.waitForTimeout(100);
  assert.ok(offerDocumentReads()>0,'opening Sources requests project context');
  const contextReadsBefore=offerDocumentReads();
  const uploadRequestCount=()=>requests.filter(row=>row.path.includes('/offer-document-uploads')).length;
  assert.equal(uploadRequestCount(),0,'no upload request before a file is selected');
  await fileInput.setInputFiles({name:'fixture-notes.md',mimeType:'text/markdown',buffer:Buffer.from('# Fixture notes\n')});
  const progress=page.getByRole('progressbar');
  await progress.waitFor();
  assert.equal(await progress.getAttribute('aria-valuemin'),'0');
  assert.equal(await progress.getAttribute('aria-valuemax'),'100');
  assert.match(await progress.getAttribute('aria-valuenow'),/^\d+$/);
  assert.equal(await page.getByLabel('Attach document').count(),0,'the attach control is hidden while in flight');
  // Overflow guard for the new composer surfaces (control, progress, later the notice).
  await page.setViewportSize({width:320,height:1000});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth)<=320,'composer fits 320px while uploading');
  await page.setViewportSize({width:1280,height:800});
  releaseComplete();
  // First source write fails: honest attach-specific retryable notice, no optimistic source.
  await page.getByText('The attachment could not be added to this discussion. Try again.',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Retry attachment',exact:true}).count(),1,'the attach failure keeps a retry affordance');
  await page.setViewportSize({width:320,height:1000});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth)<=320,'the failure notice fits 320px');
  await page.setViewportSize({width:1280,height:800});
  assert.equal(await page.locator('.conversation-selected-sources li').count(),0,'no optimistic attached source');
  assert.equal(sourcePuts.length,1);
  assert.equal(sourcePuts[0].match,'"3"');
  assert.deepEqual(sourcePuts[0].body.sources,[{id:`document:${documentId}`,label:'Offer document'}]);
  await page.getByRole('button',{name:'Retry attachment',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.conversation-selected-sources li').length===1);
  assert.equal(sourcePuts.length,2);
  assert.equal(sourcePuts[1].match,'"3"','the retry uses the current thread version');
  assert.deepEqual(sourcePuts[1].body.sources,[{id:`document:${documentId}`,label:'Offer document'}]);
  assert.equal(uploadStarts,1);assert.equal(uploadChunks,1);assert.equal(uploadCompletes,1,'one upload per file; retries never re-ingest');
  assert.equal(await page.getByRole('progressbar').count(),0,'progress clears when the attachment is idle again');
  await page.getByLabel('Attach document').waitFor({state:'attached'});
  // Context panel shows the persisted source, and attaching invalidates/refetches the
  // project context. Remount the picker so the uploaded row assertion is independent
  // of a slow/empty first context render in CI.
  await panel.locator('.conversation-selected-sources').getByText('Offer document',{exact:true}).waitFor();
  for(let attempt=0;attempt<100&&offerDocumentReads()<=contextReadsBefore;attempt+=1)await page.waitForTimeout(100);
  assert.ok(offerDocumentReads()>contextReadsBefore,'attaching invalidates and refetches the context');
  await panel.getByRole('tab',{name:'Results',exact:true}).click();
  await panel.getByRole('tab',{name:'Sources',exact:true}).click();
  await panel.getByText('fixture-notes.md',{exact:false}).first().waitFor();
  assert.ok(await panel.getByText('ready',{exact:true}).count()>=1,'the uploaded document’s own ingestion status is visible');
  // zh-HK label
  await page.getByRole('button',{name:'Change language',exact:true}).click();
  await page.getByLabel('附加文件').waitFor({state:'attached'});
  // Viewer: no control and no upload/source requests.
  access='viewer';
  const uploadsBefore=uploadRequestCount(),putsBefore=sourcePuts.length;
  await page.reload();
  await page.getByText('Here is the brief.',{exact:true}).waitFor();
  await page.waitForLoadState('networkidle');
  assert.equal(await page.locator('input[type=file]').count(),0,'a viewer never sees the attach control');
  assert.equal(uploadRequestCount(),uploadsBefore,'a viewer issues no upload request');
  assert.equal(sourcePuts.length,putsBefore,'a viewer issues no source write');
  assert.deepEqual(errors,[]);
 }finally{await harness.close();}
});

test('a directly opened archived thread offers no attach control and issues no writes',async()=>{
 const baseApi=standardApi();
 const harness=await fixtureHarness({handler:async input=>{
  const {req,url}=input;
  // Direct open: the list is empty, so archived can only come from the thread payload.
  if(url.pathname.endsWith('/conversation-threads')&&req.method()==='GET')
   return {json:fixture.envelope({items:[],total:0,offset:0,limit:50})};
  if(/\/conversation-threads\/[0-9a-f-]+$/.test(url.pathname)&&req.method()==='GET')
   return {json:fixture.envelope({...fixture.studioThread,archived:true,access:'editor'})};
  return baseApi(input);
 }});
 try{
  const {page,requests}=harness;
  await page.getByRole('textbox',{name:'Message BuyerOS'}).waitFor();
  await page.getByText('Here is the brief.',{exact:true}).waitFor();
  assert.equal(await page.locator('input[type=file]').count(),0,'an archived thread never shows the attach control');
  assert.equal(await page.getByRole('progressbar').count(),0);
  assert.equal(requests.filter(row=>row.path.includes('/offer-document-uploads')).length,0,'an archived thread issues no upload request');
  assert.equal(requests.filter(row=>/\/conversation-threads\/[0-9a-f-]+\/sources$/.test(row.path)).length,0,'an archived thread issues no source write');
 }finally{await harness.close();}
});

test('the slash menu lists the offered skill library and inserts without sending',async()=>{
 // Contract-valid SkillDefinitions (the generated client's fields are present) for the
 // 17 authored catalogue skills plus one offered-but-unauthored id.
 const authoredIds=['sales-prospect','sales-research','sales-quick','sales-qualify','sales-contacts','sales-outreach',
   'sales-followup','sales-prep','sales-proposal','sales-objections','sales-icp','sales-competitors','sales-report',
   'sales-report-pdf','first-project','understand-documents','review-buyers'];
 const skills=[...authoredIds.map(id=>({id,version:'1',inputs_schema:{},output_kind:'research_report',
   allowed_actions:['research.read'],languages:id==='sales-report-pdf'?['en']:['en','zh-HK'],
   budget_class:'model',upstream_hash:null})),
  {id:'sales-customer-success',version:'1',inputs_schema:{},output_kind:'research_report',
   allowed_actions:['research.read'],languages:['en','zh-HK'],budget_class:'model',upstream_hash:null}];
 const harness=await fixtureHarness({handler:standardApi({skills})});
 try{
  const {page,requests,posts,errors}=harness;
  const composer=page.getByRole('textbox',{name:'Message BuyerOS'});
  // The textarea's accessible name is localized; after the zh-HK switch use the
  // stable DOM id so the same composer is addressed in either locale.
  const messageBox=page.locator('#conversation-message');
  // The slash menu is gated on !busy: wait for a completed send to settle before
  // typing again, otherwise the send's clear can race the reopened menu. Detect
  // idle structurally (empty enabled composer, no busy ellipsis label) so the wait
  // stays independent of the current locale's Send translation.
  const waitComposerIdle=async()=>{await page.waitForFunction(()=>{
    const message=document.querySelector('#conversation-message');
    if(!(message instanceof HTMLTextAreaElement)||message.disabled||message.value!=='')return false;
    const send=document.querySelector('.conversation-send');
    return !(send instanceof HTMLButtonElement)||!send.textContent.includes('…');
  });};
  const turnPosts=()=>posts.filter(row=>row.path.endsWith('/conversation-turns'));
  await composer.waitFor();
  await page.getByText('Here is the brief.',{exact:true}).waitFor();
  assert.deepEqual(errors,[],'the studio renders without a page error under the catalogue fixture');
  await page.locator('[data-skill-ids="ready"]').waitFor();
  const beforeRequests=requests.length;
  await composer.fill('/');
  const listbox=page.getByRole('listbox',{name:'Skill commands'});
  await listbox.waitFor();
  assert.equal(requests.length,beforeRequests,'opening the library issues no request');
  assert.equal(await listbox.getByRole('option').count(),8,'at most eight options are visible');
  assert.equal(await page.getByText('10 more',{exact:false}).count(),1,'the more count is truthful (18 offered, 8 shown)');
  // IME composition owns Enter/Arrows: neither commits the query nor selects.
  const composingSelected=await listbox.locator('[aria-selected="true"]').getAttribute('id');
  await composer.evaluate(el=>{el.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',isComposing:true,bubbles:true,cancelable:true}));});
  await page.waitForTimeout(40);
  assert.equal(await listbox.locator('[aria-selected="true"]').getAttribute('id'),composingSelected,'IME arrows do not move the menu');
  await composer.evaluate(el=>{el.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',isComposing:true,bubbles:true,cancelable:true}));});
  await page.waitForTimeout(40);
  assert.equal(await listbox.count(),1,'IME Enter does not select a command');
  assert.equal(await composer.inputValue(),'/');
  const firstId=await listbox.locator('[aria-selected="true"]').getAttribute('id');
  await composer.press('ArrowDown');
  await page.waitForFunction(first=>document.querySelector('#conversation-skill-menu [aria-selected="true"]')?.id!==first,firstId);
  const secondId=await listbox.locator('[aria-selected="true"]').getAttribute('id');
  assert.notEqual(secondId,firstId,'ArrowDown moves the active option');
  assert.equal(await composer.getAttribute('aria-activedescendant'),secondId,'the textarea keeps focus and points at the active option');
  // An offered-but-unauthored skill is still reachable via its derived label.
  await composer.fill('/customer');
  await page.waitForFunction(()=>document.querySelectorAll('#conversation-skill-menu [role="option"]').length===1);
  assert.match(await listbox.getByRole('option').first().innerText(),/Customer success/);
  assert.equal(requests.length,beforeRequests,'filtering issues no request');
  // A slash query with no matches closes on Enter and never sends or disappears silently.
  await composer.fill('/zzzz');
  await page.getByText('No matching skills.',{exact:true}).waitFor();
  await composer.press('Enter');
  await listbox.waitFor({state:'detached'});
  assert.equal(await composer.inputValue(),'/zzzz');
  assert.equal(turnPosts().length,0,'zero matches never send');
  // Filter to a skill that is not one of the six guided templates.
  await composer.fill('/objections');
  await page.waitForFunction(()=>document.querySelectorAll('#conversation-skill-menu [role="option"]').length===1);
  await composer.press('Enter');
  await page.waitForFunction(()=>document.querySelector('#conversation-message')?.value.startsWith('Help me prepare responses to likely buyer objections.'));
  assert.equal(turnPosts().length,0,'selecting a command never sends');
  assert.equal(await listbox.count(),0,'selecting closes the menu');
  // A second Enter is the only thing that sends, with the catalogued skill id.
  await composer.press('Enter');
  await page.getByText('Here is the follow-up.',{exact:true}).waitFor();
  assert.equal(turnPosts().length,1,'a slash selection plus Enter sends exactly one turn');
  assert.equal(turnPosts()[0].body.skill_id,'sales-objections');
  assert.match(turnPosts()[0].body.text,/likely buyer objections/);
  // Escape closes without sending and keeps the typed text.
  await waitComposerIdle();
  const postsBefore=posts.length;
  await composer.fill('/');
  await listbox.waitFor();
  await composer.press('Escape');
  await listbox.waitFor({state:'detached'});
  assert.equal(posts.length,postsBefore,'Escape never sends');
  assert.equal(await composer.inputValue(),'/','the slash text is kept after Escape');
  // Locale drift after selection: the skill must be revalidated at send time.
  await composer.fill('/pdf');
  await page.waitForFunction(()=>document.querySelectorAll('#conversation-skill-menu [role="option"]').length===1);
  await composer.press('Enter');
  await page.waitForFunction(()=>document.querySelector('#conversation-message')?.value.startsWith('Help me prepare a report export'));
  const turnsBeforeDrift=turnPosts().length;
  await page.getByRole('button',{name:'Change language',exact:true}).click();
  await page.getByText('此技能不適用於目前語言。',{exact:true}).waitFor();
  assert.equal(await messageBox.inputValue(),'Help me prepare a report export from current results.','the staged prompt stays editable');
  await messageBox.press('Enter');
  for(let attempt=0;attempt<100&&turnPosts().length===turnsBeforeDrift;attempt+=1)await page.waitForTimeout(50);
  assert.equal(turnPosts().length,turnsBeforeDrift+1,'the plain text still sends once');
  assert.equal(turnPosts().at(-1).body.skill_id??null,null,'a locale-disabled skill id is never sent');
  assert.notEqual(turnPosts().at(-1).body.skill_id,'sales-report-pdf','the disabled skill id is never sent');
  // zh-HK: translated labels and a locale-incompatible skill is disabled with a reason.
  await waitComposerIdle();
  await messageBox.fill('/');
  const zhList=page.getByRole('listbox',{name:'技能指令'});
  await zhList.waitFor();
  assert.equal(await zhList.getByRole('option').count(),8);
  await messageBox.fill('/pdf');
  await page.waitForFunction(()=>document.querySelectorAll('#conversation-skill-menu [role="option"]').length===1);
  const disabled=zhList.getByRole('option').first();
  assert.equal(await disabled.getAttribute('aria-disabled'),'true','a locale-incompatible skill is disabled, not hidden');
  assert.equal(await zhList.getByText('此技能不適用於目前語言。').count()>=1,true);
  await messageBox.press('Enter');
  assert.equal(await messageBox.inputValue(),'/pdf','a disabled command cannot be inserted');
  // The open library never overflows a 320px viewport.
  await page.setViewportSize({width:320,height:1000});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth)<=320,'the open slash menu fits 320px');
  await page.setViewportSize({width:1280,height:800});
  assert.deepEqual(errors,[]);
 }finally{await harness.close();}
});

test('discussion preferences pin, archive, reload and the share ACL stay honest',async()=>{
 const harness=await fixtureHarness({handler:standardApi({manage:true,second:true})});
 try{
  const {page,requests,errors,state}=harness;
  const rows=()=>page.locator('.conversation-thread-items button');
  const row=title=>rows().filter({hasText:title});
  const prefWrites=()=>requests.filter(entry=>entry.method==='PUT'&&/\/preferences$/.test(entry.path));
  const openMenu=async()=>{const details=page.locator('.conversation-menu');
   if(!(await details.evaluate(node=>node.open)))await page.locator('summary[aria-label="Discussion menu"]').click();};
  await page.locator('[data-skill-ids="ready"]').waitFor();
  await page.waitForFunction(()=>document.querySelectorAll('.conversation-thread-items button').length===2);
  await page.locator('summary[aria-label="Discussion menu"]').waitFor();
  // Recency order first; pinning moves the current row to the front.
  assert.equal(await rows().first().getAttribute('aria-label'),'Other discussion');
  assert.equal(await row('Research buyer').locator('svg').count(),0,'an unpinned row has no pin glyph');
  await openMenu();
  const pin=page.getByRole('button',{name:'Pin discussion',exact:true});
  assert.equal(await pin.getAttribute('aria-pressed'),'false');
  await pin.click();
  const unpin=page.getByRole('button',{name:'Unpin discussion',exact:true});
  await unpin.waitFor();
  assert.equal(await unpin.getAttribute('aria-pressed'),'true','the pin toggle reflects the stored preference');
  await page.waitForFunction(()=>document.querySelector('.conversation-thread-items button')?.getAttribute('aria-label')==='Research buyer');
  assert.equal(await row('Research buyer').locator('svg').count(),1,'the pinned row shows the pin glyph');
  assert.deepEqual(prefWrites().at(-1).body,{pinned:true,archived:false},'pin preserves the archived flag');
  // Reload: the preference is server-backed, not a local lie.
  await page.reload();
  await page.waitForFunction(()=>document.querySelectorAll('.conversation-thread-items button').length===2);
  await page.waitForFunction(()=>document.querySelector('.conversation-thread-items button')?.getAttribute('aria-label')==='Research buyer');
  await page.locator('summary[aria-label="Discussion menu"]').waitFor();
  await openMenu();
  assert.equal(await page.getByRole('button',{name:'Unpin discussion',exact:true}).getAttribute('aria-pressed'),'true','the pin preference survives reload');
  // Archive: out of the normal list, into the archive view; pinned is preserved.
  await page.getByRole('button',{name:'Archive discussion',exact:true}).click();
  await page.getByRole('button',{name:'Restore discussion',exact:true}).waitFor();
  await page.waitForFunction(()=>[...document.querySelectorAll('.conversation-thread-items button')].every(button=>button.getAttribute('aria-label')!=='Research buyer'));
  assert.deepEqual(prefWrites().at(-1).body,{pinned:true,archived:true},'archive preserves the pinned flag');
  await page.getByRole('button',{name:'Archive view',exact:true}).click();
  await page.waitForFunction(()=>[...document.querySelectorAll('.conversation-thread-items button')].some(button=>button.getAttribute('aria-label')==='Research buyer'));
  // Restore returns it to the normal list.
  await openMenu();
  await page.getByRole('button',{name:'Restore discussion',exact:true}).click();
  await page.getByRole('button',{name:'Archive discussion',exact:true}).waitFor();
  await page.waitForFunction(()=>[...document.querySelectorAll('.conversation-thread-items button')].every(button=>button.getAttribute('aria-label')!=='Research buyer'));
  assert.deepEqual(prefWrites().at(-1).body,{pinned:true,archived:false},'restore preserves the pinned flag');
  await page.getByRole('button',{name:'Archived discussions',exact:true}).click();
  await page.waitForFunction(()=>[...document.querySelectorAll('.conversation-thread-items button')].some(button=>button.getAttribute('aria-label')==='Research buyer'));
  assert.equal(await rows().first().getAttribute('aria-label'),'Research buyer','the restored pinned row is first');
  // Honest failure: no optimistic lie, the row and toggle keep the prior state.
  const draftText='Keep this draft through a failed preference.';
  await page.locator('#conversation-message').fill(draftText);
  state.failPreferences=true;
  await openMenu();
  await page.getByRole('button',{name:'Unpin discussion',exact:true}).click();
  // The same notice also feeds the transcript status line; assert the inline one only.
  const inlineNotice=page.locator('p.conversation-inline-notice')
    .filter({hasText:'Workspace discussions are unavailable. Your unsaved text is still here.'});
  await inlineNotice.waitFor();
  assert.equal((await inlineNotice.textContent())?.trim(),'Workspace discussions are unavailable. Your unsaved text is still here.');
  assert.equal(await page.getByRole('button',{name:'Unpin discussion',exact:true}).getAttribute('aria-pressed'),'true','a failed preference never flips the toggle');
  assert.equal(await rows().first().getAttribute('aria-label'),'Research buyer','the row keeps its pinned-first place');
  assert.equal(await page.locator('#conversation-message').inputValue(),draftText,'a failed preference never loses the draft');
  state.failPreferences=false;
  // The open menu remains inside a 320px viewport.
  await page.setViewportSize({width:320,height:1000});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth)<=320,'the open discussion menu fits 320px');
  await page.setViewportSize({width:1280,height:800});
  assert.deepEqual(errors,[]);
 }finally{await harness.close();}
 // Viewers and editors may pin/archive, but the owner-only share control is absent.
 const viewer=await fixtureHarness({handler:standardApi({manage:true,access:'viewer'})});
 try{
  const {page,requests,errors}=viewer;
  const summary=page.locator('summary[aria-label="Discussion menu"]');
  await summary.waitFor();
  await page.locator('.conversation-head').getByText('Shared with you',{exact:false}).first().waitFor();
  await summary.click();
  assert.equal(await page.getByRole('button',{name:'Share discussion',exact:true}).count(),0,'a viewer has no Share discussion control');
  await page.getByRole('button',{name:'Pin discussion',exact:true}).click();
  const unpin=page.getByRole('button',{name:'Unpin discussion',exact:true});
  await unpin.waitFor();
  assert.equal(await unpin.getAttribute('aria-pressed'),'true','a viewer can pin its own view');
  const writes=()=>requests.filter(entry=>entry.method==='PUT'&&/\/preferences$/.test(entry.path));
  assert.deepEqual(writes().at(-1).body,{pinned:true,archived:false});
  await page.getByRole('button',{name:'Archive discussion',exact:true}).click();
  await page.getByRole('button',{name:'Restore discussion',exact:true}).waitFor();
  assert.deepEqual(writes().at(-1).body,{pinned:true,archived:true},'the viewer archive keeps its pin');
  assert.equal(await page.getByRole('button',{name:'Share discussion',exact:true}).count(),0);
  // The same rule holds for an editor: personal pin/archive yes, owner share dialog no.
  const {state}=viewer;
  state.access='editor';
  await page.reload();
  const editorSummary=page.locator('summary[aria-label="Discussion menu"]');
  await editorSummary.waitFor();
  await page.locator('.conversation-head').getByText('Editor',{exact:false}).first().waitFor();
  await editorSummary.click();
  assert.equal(await page.getByRole('button',{name:'Share discussion',exact:true}).count(),0,'an editor has no Share discussion control');
  const editorUnpin=page.getByRole('button',{name:'Unpin discussion',exact:true});
  await editorUnpin.waitFor();
  assert.equal(await editorUnpin.getAttribute('aria-pressed'),'true','the editor keeps its own preference');
  await editorUnpin.click();
  await page.getByRole('button',{name:'Pin discussion',exact:true}).waitFor();
  assert.deepEqual(errors,[]);
 }finally{await viewer.close();}
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
  await page.getByRole('button',{name:'Fixture home',exact:true}).click();await openDiscussion(page);await page.getByRole('region',{name:'Continue working',exact:true}).getByRole('button').click();await openDiscussion(page);
  await page.getByLabel('Reply citations').getByRole('button',{name:'Offer document',exact:true}).click();
  assert.match(await page.evaluate(()=>window.lastDestination),new RegExp(`/app/discover/edit\\?document=${documentId}`));
  await page.getByRole('button',{name:'Fixture home',exact:true}).click();await openDiscussion(page);await page.getByRole('region',{name:'Continue working',exact:true}).getByRole('button').click();await openDiscussion(page);
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




test('studio keyboard, focus and screen-reader semantics stay honest',async()=>{
 const harness=await fixtureHarness({handler:standardApi({manage:true})});
 try{
  const {page,posts,errors,state}=harness;
  const composer=page.locator('#conversation-message');
  await page.getByText('Here is the brief.',{exact:true}).waitFor();
  // Opening a discussion announces it by moving focus to the thread heading.
  const heading=page.getByRole('heading',{name:'Research buyer',exact:true});
  assert.equal(await heading.getAttribute('tabindex'),'-1');
  await page.waitForFunction(()=>document.activeElement?.tagName==='H1');
  assert.equal(await heading.evaluate(node=>document.activeElement===node),true,'opening a discussion moves focus to its heading');
  assert.equal(await page.getByRole('log',{name:'Discussion messages'}).count(),1,'the transcript is a labelled log');
  // Tab from the top of the studio reaches the thread list, chips, composer and send.
  const outline=async()=>page.evaluate(()=>{const node=document.activeElement,style=getComputedStyle(node);
    return {id:node?.id??'',tag:node?.tagName??'',cls:typeof node?.className==='string'?node.className:'',
      parentCls:typeof node?.parentElement?.className==='string'?node.parentElement.className:'',
      inThreadList:!!node?.closest?.('.conversation-thread-items'),inChips:!!node?.closest?.('.conversation-chips'),
      text:(node?.textContent??'').trim().slice(0,60),outlineStyle:style.outlineStyle,outlineWidth:style.outlineWidth};});
  await page.locator('.conversation-studio').focus();
  const walked=[];
  for(let step=0;step<40;step+=1){
   await page.keyboard.press('Tab');
   const item=await outline();walked.push(item);
   if(item.id==='conversation-message')break;
  }
  assert.ok(walked.some(item=>item.cls.includes('conversation-new')),'tab order reaches the thread list');
  assert.ok(walked.some(item=>item.inThreadList),'a thread row is reachable');
  assert.ok(walked.some(item=>item.inChips),'chips are reachable');
  const textarea=walked.find(item=>item.id==='conversation-message');
  assert.ok(textarea,'tab order reaches the composer');
  assert.notEqual(textarea.outlineStyle,'none','the composer shows a visible focus indicator');
  for(const item of walked)assert.notEqual(item.outlineStyle,'none',`${item.tag}.${item.cls} has a visible focus indicator`);
  // Enter on the send action is the only send; the textarea keeps normal typing.
  await page.keyboard.type('Keyboard question');
  assert.equal(await composer.inputValue(),'Keyboard question');
  await page.keyboard.press('Tab');
  const attach=await outline();
  assert.equal(attach.id,'conversation-attach','the attach control follows the composer');
  const attachOutline=await page.locator('label[for="conversation-attach"]').evaluate(node=>getComputedStyle(node).outlineStyle);
  assert.notEqual(attachOutline,'none','the clipped attach input exposes a visible label indicator');
  await page.keyboard.press('Tab');
  const send=await outline();
  assert.equal(send.cls.includes('conversation-send'),true,'the send action follows the attach control');
  assert.notEqual(send.outlineStyle,'none','the send action has a visible focus indicator');
  await page.keyboard.press('Enter');
  await page.getByText('Here is the follow-up.',{exact:true}).waitFor();
  const turnPosts=()=>posts.filter(row=>row.path.endsWith('/conversation-turns'));
  assert.equal(turnPosts().length,1,'the keyboard send posts one turn');
  assert.equal(turnPosts()[0].body.text,'Keyboard question');
  // APG tablist: roving tabindex, arrows/Home/End select and take focus.
  const tablist=page.getByRole('tablist',{name:'Discussion context'});
  assert.equal(await tablist.getByRole('tab').count(),4);
  await tablist.getByRole('tab',{name:'Results',exact:true}).focus();
  assert.equal(await page.evaluate(()=>document.activeElement?.getAttribute('aria-selected')),'true');
  assert.equal(await page.evaluate(()=>document.activeElement?.getAttribute('tabindex')),'0');
  await page.keyboard.press('ArrowRight');
  await page.waitForFunction(()=>document.activeElement?.id==='conversation-tab-sources');
  assert.equal(await page.locator('#conversation-tab-sources').getAttribute('aria-selected'),'true');
  assert.equal(await page.locator('#conversation-tab-sources').getAttribute('tabindex'),'0');
  assert.equal(await page.locator('#conversation-tab-results').getAttribute('tabindex'),'-1','only the selected tab is in the tab sequence');
  assert.equal(await page.getByRole('tabpanel').getAttribute('aria-labelledby'),'conversation-tab-sources','the panel follows the selected tab');
  const tabFocus=await page.locator('#conversation-tab-sources').evaluate(node=>getComputedStyle(node).outlineStyle);
  assert.notEqual(tabFocus,'none','tabs show a visible focus indicator');
  await page.keyboard.press('End');
  await page.waitForFunction(()=>document.activeElement?.id==='conversation-tab-metrics');
  await page.keyboard.press('ArrowRight');
  await page.waitForFunction(()=>document.activeElement?.id==='conversation-tab-results','ArrowRight wraps past the last tab');
  await page.keyboard.press('ArrowLeft');
  await page.waitForFunction(()=>document.activeElement?.id==='conversation-tab-metrics','ArrowLeft wraps before the first tab');
  await page.keyboard.press('Home');
  await page.waitForFunction(()=>document.activeElement?.id==='conversation-tab-results');
  // Mouse selection stays unchanged and decisions expose accessible names.
  await tablist.getByRole('tab',{name:'Decisions',exact:true}).click();
  const decisionsPanel=page.getByRole('tabpanel');
  await page.waitForFunction(()=>document.querySelector('[role="tabpanel"]')?.id==='conversation-panel-decisions');
  assert.equal(await decisionsPanel.getByRole('button',{name:'Approve',exact:true}).count(),1);
  assert.equal(await decisionsPanel.getByRole('button',{name:'Reject',exact:true}).count(),1);
  await tablist.getByRole('tab',{name:'Results',exact:true}).click();
  // Escape closes the discussion menu and returns focus to its summary trigger.
  const summary=page.locator('summary[aria-label="Discussion menu"]');
  await summary.focus();await page.keyboard.press('Enter');
  const details=page.locator('details.conversation-menu');
  assert.equal(await details.evaluate(node=>node.open),true,'Enter opens the discussion menu');
  await page.keyboard.press('Escape');
  assert.equal(await details.evaluate(node=>node.open),false,'Escape closes the discussion menu');
  assert.equal(await summary.evaluate(node=>document.activeElement===node),true,'focus returns to the menu trigger');
  // The native share dialog is modal, owns Escape, and returns focus to its trigger.
  await page.keyboard.press('Enter');
  const share=page.locator('.conversation-menu-panel').getByRole('button',{name:'Share discussion',exact:true});
  await share.focus();await page.keyboard.press('Enter');
  const dialog=page.getByRole('dialog',{name:'Share discussion',exact:true});
  await dialog.waitFor();
  assert.equal(await dialog.getAttribute('aria-modal'),'true','the share dialog is modal');
  assert.equal(await dialog.evaluate(node=>node.matches('dialog[open]')),true);
  await dialog.getByRole('heading',{name:'Share discussion',exact:true}).waitFor();
  await page.keyboard.press('Escape');
  await dialog.waitFor({state:'hidden'});
  assert.equal(await share.evaluate(node=>document.activeElement===node),true,'the share dialog returns focus to its trigger');
  await page.keyboard.press('Escape');
  assert.equal(await details.evaluate(node=>node.open),false);
  assert.equal(await summary.evaluate(node=>document.activeElement===node),true);
  // A failed preference keeps one announced copy: the visible transcript line is
  // presentation-only while the inline notice is the single live region.
  state.failPreferences=true;
  await page.keyboard.press('Enter');
  await page.getByRole('button',{name:'Pin discussion',exact:true}).click();
  const failure='Workspace discussions are unavailable. Your unsaved text is still here.';
  const inlineNotice=page.locator('p.conversation-inline-notice').filter({hasText:failure});
  await inlineNotice.waitFor();
  assert.equal(await inlineNotice.textContent(),failure);
  const announced=page.getByRole('status').filter({hasText:failure});
  assert.equal(await announced.count(),1,'exactly one live region announces the failure');
  assert.equal(await page.locator('.conversation-status').getAttribute('aria-hidden'),'true');
  assert.equal((await page.locator('.conversation-status').innerText()).trim(),failure,'the presentation copy stays visible');
  state.failPreferences=false;
  // Focus is never trapped: Tab/Shift+Tab leave and return to the composer.
  await composer.focus();
  await page.keyboard.press('Tab');
  assert.notEqual(await page.evaluate(()=>document.activeElement?.id),'conversation-message','Tab leaves the composer');
  await page.keyboard.press('Shift+Tab');
  assert.equal(await page.evaluate(()=>document.activeElement?.id),'conversation-message','Shift+Tab returns to the composer');
  await page.screenshot({path:shots+'/a11y-keyboard-desktop.png',fullPage:true});
  assert.deepEqual(errors,[]);
 }finally{await harness.close();}
});

test('turn metrics dashboard shows bounded project aggregates and fails closed',async()=>{
 const harness=await fixtureHarness({handler:standardApi()});
 try{
  const {page,state,requests,errors}=harness;
  await page.getByText('Here is the brief.',{exact:true}).waitFor();
  const tablist=page.getByRole('tablist',{name:'Discussion context'});
  await tablist.getByRole('tab',{name:'Turn metrics',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('[role="tabpanel"]')?.id==='conversation-panel-metrics');
  const panel=page.getByRole('tabpanel');
  const valueOf=async label=>(await page.locator('.conversation-metric-row').filter({hasText:label}).first()
    .locator('dd').textContent()).trim();
  await page.getByText('Total turns',{exact:true}).waitFor();
  assert.equal(await valueOf('Total turns'),'3');
  assert.equal(await valueOf('Completed'),'2');
  assert.equal(await valueOf('Median'),'900 ms');
  assert.equal(await valueOf('95th percentile'),'1.5 s');
  assert.equal(await valueOf('Slowest'),'2.1 s');
  assert.equal(await valueOf('Turns measured'),'3');
  assert.equal(await valueOf('Awaiting decision'),'1');
  assert.equal(await valueOf('Turns without a model answer'),'1');
  assert.equal(await valueOf('Unknown outcomes'),'1');
  assert.equal(await valueOf('Price unavailable'),'1');
  const reads=requests.filter(row=>row.path.endsWith('/conversation-turns/metrics'));
  assert.equal(reads.length,1,'the dashboard reads the bounded aggregate endpoint once per open');
  assert.match(reads[0].search,/window_days=7/);
  assert.equal(state.metricsReads,1);
  // Since the read is not repeated on render, content never leaks into the request.
  assert.equal(await panel.getByText('Here is the brief.',{exact:true}).count(),0);
  // A failed aggregate read is an honest notice, never invented zeros.
  state.metricsFail=true;
  await tablist.getByRole('tab',{name:'Results',exact:true}).click();
  await tablist.getByRole('tab',{name:'Turn metrics',exact:true}).click();
  await page.getByText('Turn metrics are unavailable. Try again later.',{exact:true}).waitFor();
  assert.equal(await page.getByText('Total turns',{exact:true}).count(),0);
  assert.equal(await panel.getByText('0',{exact:true}).count(),0,'no zero is rendered for an unverified read');
  assert.deepEqual(errors,[]);
 }finally{await harness.close();}
});

test('conversation studio reflows at the 200% zoom viewport and keeps zh-HK',async()=>{
 const harness=await fixtureHarness();
 try{
  const {page,errors}=harness;
  await page.getByText('Here is the brief.',{exact:true}).waitFor();
  // 200% of a 1280px screen is a 640 CSS-pixel viewport.
  await page.setViewportSize({width:640,height:900});
  const pageMetrics=()=>page.evaluate(()=>{const box=document.querySelector('.conversation-compose-box');
    const transcript=document.querySelector('.conversation-transcript');
    return {page:document.documentElement.scrollWidth,body:document.body.scrollWidth,
      composer:box?{scroll:box.scrollWidth,client:box.clientWidth}:null,
      transcript:transcript?{scroll:transcript.scrollWidth,client:transcript.clientWidth,
        overflowY:getComputedStyle(transcript).overflowY}:null};});
  let metrics=await pageMetrics();
  assert.ok(metrics.page<=640,`the document does not scroll sideways (${metrics.page}px)`);
  assert.ok(metrics.body<=640);
  assert.ok(metrics.transcript.scroll<=metrics.transcript.client,'the transcript does not overflow sideways');
  assert.equal(metrics.transcript.overflowY,'auto','the transcript scrolls vertically');
  assert.ok(metrics.composer.scroll<=metrics.composer.client,'the composer does not overflow sideways');
  const message=page.locator('#conversation-message');
  const send=page.locator('.conversation-send');
  await message.waitFor();
  assert.equal(await message.isVisible(),true);
  await message.fill('Zoom check');
  assert.equal(await send.isEnabled(),true,'the send action is reachable and enabled');
  await send.click();
  await page.getByText('Here is the follow-up.',{exact:true}).waitFor();
  metrics=await pageMetrics();
  assert.ok(metrics.page<=640,'the sent transcript still fits');
  // The drawer and context panel stay reachable at the zoomed viewport.
  const showDiscussions=page.getByRole('button',{name:'Show discussions',exact:true});
  await showDiscussions.click();
  await page.locator('.conversation-threads').waitFor();
  await page.keyboard.press('Escape');
  await page.waitForFunction(()=>document.activeElement?.getAttribute('aria-label')==='Show discussions');
  assert.equal(await showDiscussions.evaluate(node=>document.activeElement===node),true,'Escape returns focus to the drawer trigger');
  const context=page.getByRole('button',{name:'Details',exact:true});
  await context.click();
  const panel=page.locator('.conversation-panel');
  await panel.waitFor();
  const closePanel=page.getByRole('button',{name:'Close context panel',exact:true});
  await closePanel.waitFor();
  const panelMetrics=await panel.evaluate(node=>({scroll:node.scrollWidth,client:node.clientWidth}));
  assert.ok(panelMetrics.scroll<=panelMetrics.client,'the context panel does not overflow sideways');
  await closePanel.click();
  await panel.waitFor({state:'hidden'});
  await page.waitForFunction(()=>document.activeElement?.textContent?.trim()==='Details');
  assert.equal(await context.evaluate(node=>document.activeElement===node),true,'closing the panel returns focus to its opener');
  // Escape is the second close path and restores the same opener.
  await context.click();
  await panel.waitFor();
  await page.keyboard.press('Escape');
  await panel.waitFor({state:'hidden'});
  await page.waitForFunction(()=>document.activeElement?.textContent?.trim()==='Details');
  assert.equal(await context.evaluate(node=>document.activeElement===node),true,'Escape returns focus to the panel opener');
  await page.screenshot({path:shots+'/a11y-zoom-640-en.png',fullPage:true});
  // zh-HK keeps the same reflow and translated labels.
  await page.getByRole('button',{name:'Change language',exact:true}).click();
  await page.getByRole('textbox',{name:'向 BuyerOS 傳送訊息',exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'傳送訊息',exact:true}).count(),1,'the send action carries its zh-HK label');
  metrics=await pageMetrics();
  assert.ok(metrics.page<=640,'the zh-HK document does not scroll sideways');
  assert.ok(metrics.transcript.scroll<=metrics.transcript.client);
  assert.ok(metrics.composer.scroll<=metrics.composer.client);
  await page.getByRole('button',{name:'詳情',exact:true}).click();
  const zhPanel=page.locator('.conversation-panel');
  await zhPanel.waitFor();
  const zhPanelMetrics=await zhPanel.evaluate(node=>({scroll:node.scrollWidth,client:node.clientWidth}));
  assert.ok(zhPanelMetrics.scroll<=zhPanelMetrics.client,'the zh-HK context panel does not overflow sideways');
  await page.getByRole('button',{name:'關閉內容面板',exact:true}).click();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth)<=640,true);
  await page.screenshot({path:shots+'/a11y-zoom-640-zh.png',fullPage:true});
  assert.deepEqual(errors,[]);
 }finally{await harness.close();}
});

test('a 100-message transcript renders a bounded window and reveals history without losing live replies',async()=>{
 // Increment 3.3: 100 persisted messages are the server cap. Only the latest
 // bounded window mounts; each reveal is anchored and no request is made.
 const longThread=fixture.threadWith({messages:Array.from({length:100},(_,index)=>fixture.userRow({
  id:'e9000000-0000-4000-8000-'+String(index+1).padStart(12,'0'),seq:index+1,text:`Window message ${index+1}`}))});
 const baseApi=standardApi();
 const harness=await fixtureHarness({handler:async input=>{
  const {req,url,state}=input;
  if(req.method()==='GET'&&url.pathname.endsWith('/conversation-threads/'+threadId)){
   state.thread=state.thread??longThread;
   return {json:fixture.envelope(state.thread)};
  }
  return baseApi(input);
 }});
 try{
  const {page,errors,requests}=harness;
  const transcript=page.locator('.conversation-transcript');
  const messages=()=>transcript.locator('article.conversation-message');
  const partTexts=()=>transcript.locator('article.conversation-message .conversation-part-text').allTextContents();
  const waitForCount=expected=>page.waitForFunction(value=>document.querySelectorAll('.conversation-transcript article.conversation-message').length===value,expected);
  const showEarlier=page.getByRole('button',{name:'Show earlier messages',exact:true});
  await page.getByText('Window message 100',{exact:true}).waitFor();
  assert.equal(await messages().count(),25,'only the latest window is mounted initially');
  assert.equal(await page.getByText('Window message 76',{exact:true}).count(),1,'the window starts at the latest 25');
  assert.equal(await page.getByText('Window message 75',{exact:true}).count(),0,'the older 75 stay unmounted');
  await showEarlier.waitFor();
  assert.equal(await transcript.getByRole('button',{name:'Show earlier messages',exact:true}).count(),0,
   'the control sits outside the role=log live region');
  assert.equal(await transcript.getAttribute('role'),'log');
  // 320px: the control wraps without sideways overflow.
  await page.setViewportSize({width:320,height:900});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth)<=320,'the transcript window fits 320px');
  assert.equal(await showEarlier.isVisible(),true,'the control stays reachable at 320px');
  // Revealing earlier messages is in-memory and anchors the visible message
  // even when the reader has scrolled away from the tail.
  await transcript.evaluate(node=>{node.scrollTop=Math.max(0,node.scrollHeight-node.clientHeight-200);node.dispatchEvent(new Event('scroll'));});
  const before=await transcript.evaluate(node=>({top:node.scrollTop,height:node.scrollHeight,view:node.clientHeight}));
  const requestsBefore=requests.filter(item=>/\/conversation-(threads|turns)(\/|$)/.test(item.path)).length;
  await showEarlier.click();
  await waitForCount(50);
  const after=await transcript.evaluate(node=>({top:node.scrollTop,height:node.scrollHeight,view:node.clientHeight}));
  assert.ok(Math.abs((after.top-before.top)-(after.height-before.height))<=1,
   `revealing anchors the viewport (scroll ${before.top}->${after.top}, height ${before.height}->${after.height})`);
  assert.ok(after.top<after.height-after.view-100,'the anchored reader is not snapped to the tail');
  assert.equal(requests.filter(item=>/\/conversation-(threads|turns)(\/|$)/.test(item.path)).length,requestsBefore,
   'showing earlier messages makes no network request');
  let texts=await partTexts();
  assert.equal(texts.length,50,'one activation adds exactly one batch');
  assert.equal(new Set(texts).size,50,'revealed entries are exactly once');
  assert.equal(texts[0],'Window message 51');
  assert.equal(texts.at(-1),'Window message 100');
  // 200% zoom (640px CSS viewport): the next batch is still reachable.
  await page.setViewportSize({width:640,height:900});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth)<=640,'the window fits the zoom viewport');
  assert.equal(await showEarlier.isVisible(),true,'the control stays reachable at 200% zoom');
  await showEarlier.click();
  await waitForCount(75);
  // zh-HK: the remaining history reveals with the translated label, then the control goes.
  await page.getByRole('button',{name:'Change language',exact:true}).click();
  const zhShowEarlier=page.getByRole('button',{name:'顯示較早訊息',exact:true});
  await zhShowEarlier.waitFor();
  await zhShowEarlier.click();
  await waitForCount(100);
  assert.equal(await zhShowEarlier.count(),0,'the control disappears once everything is revealed');
  texts=await partTexts();
  assert.equal(texts.length,100,'the full reveal loses no entry');
  assert.equal(new Set(texts).size,100,'the full reveal duplicates no entry');
  assert.equal(texts[0],'Window message 1','the reveal keeps persisted order');
  assert.equal(texts.at(-1),'Window message 100');
  // Existing jump-to-latest semantics: only away from the tail, then it hides.
  await transcript.evaluate(node=>{node.scrollTop=0;node.dispatchEvent(new Event('scroll'));});
  const jump=page.getByRole('button',{name:'跳到最新',exact:true});
  await jump.waitFor();
  await jump.click();
  await page.waitForFunction(()=>{const node=document.querySelector('.conversation-transcript');
   return node&&node.scrollHeight-node.scrollTop-node.clientHeight<2;});
  assert.equal(await jump.count(),0,'jump-to-latest hides at the latest content');
  // A live reply still arrives and stays visible at the latest position.
  await page.locator('#conversation-message').fill('Live reply request');
  await page.locator('.conversation-send').click();
  await page.getByText('Here is the follow-up.',{exact:true}).waitFor();
  await waitForCount(102);
  assert.equal(await page.getByText('Window message 1',{exact:true}).count(),1,'the live entry does not displace revealed history');
  const liveVisible=await page.evaluate(()=>{
   const node=document.querySelector('.conversation-transcript');
   const target=[...node.querySelectorAll('.conversation-part-text')].find(item=>item.textContent==='Here is the follow-up.');
   if(!target)return false;
   const box=target.getBoundingClientRect(),scroll=node.getBoundingClientRect();
   return box.top>=scroll.top-1&&box.bottom<=scroll.bottom+1;
  });
  assert.equal(liveVisible,true,'the live reply is visible at the latest position');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth)<=640,'the zh-HK live state fits the zoom viewport');
  assert.deepEqual(errors,[]);
 }finally{await harness.close();}
});
