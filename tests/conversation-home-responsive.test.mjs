import test from 'node:test';
import assert from 'node:assert/strict';
import {registerHooks} from 'node:module';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {readFileSync,readdirSync} from 'node:fs';
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
for(const locale of ['en','zh-HK'])test(`thread and context fit 320–1440px in ${locale}`,async()=>{
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
  await page.goto(server.resolvedUrls.local[0]+'fixture');await page.getByText('project-evidence.pdf',{exact:false}).waitFor();
  await page.getByRole('textbox').fill('Start a local discussion');
  assert.equal(await page.getByRole('button',{name:'Ask BuyerOS',exact:true}).isDisabled(),true);
  await page.getByRole('button',{name:'Send',exact:true}).click();await page.getByLabel('Discussion messages',{exact:true}).waitFor();
  await page.getByRole('checkbox').first().click();await page.waitForFunction(()=>document.querySelectorAll('input[type=checkbox]')[0].checked);
  await page.getByRole('checkbox').nth(1).click();await page.waitForFunction(()=>document.querySelectorAll('input[type=checkbox]')[1].checked);
  await page.getByRole('textbox').fill('What should I review?');
  const ask=()=>page.getByRole('button',{name:'Ask BuyerOS',exact:true});
  await ask().focus();await page.keyboard.press('Enter');
  await page.getByText(reply.text,{exact:true}).waitFor();assert.equal(posts.length,1);
  assert.deepEqual(posts[0].body,{question:'What should I review?',source_ids:[documentRef.id,ref.id],language:'en'});
  assert.ok(posts.every(row=>row.path.endsWith('/conversation-reply')));
  let stored=await page.evaluate(()=>Object.values(localStorage).join(''));
  assert.doesNotMatch(stored,/PRIVATE_FACT_CONTENT|project-evidence.pdf|tool_calls/);
  await page.reload();await page.getByText(reply.text,{exact:true}).waitFor();
  const citations=page.getByLabel('Reply citations');
  await citations.getByRole('button',{name:'Approved offer fact',exact:true}).click();
  assert.equal(await page.evaluate(()=>window.lastDestination),`/app/overview?profile=${profileId}&workspace=a1000000-0000-4000-8000-000000000001&project=a2000000-0000-4000-8000-000000000001`);
  await page.getByRole('button',{name:'Home',exact:true}).click();await page.getByRole('region',{name:'Continue working',exact:true}).getByRole('button').click();
  await page.getByLabel('Reply citations').getByRole('button',{name:'Offer document',exact:true}).click();
  assert.match(await page.evaluate(()=>window.lastDestination),new RegExp(`/app/discover/edit\\?document=${documentId}`));
  await page.getByRole('button',{name:'Home',exact:true}).click();await page.getByRole('region',{name:'Continue working',exact:true}).getByRole('button').click();
  for(const state of ['unavailable','source','invalid']){
   mode=state;await page.getByRole('textbox').fill('Keep this question');await ask().click();
   await page.getByText(state==='unavailable'?'BuyerOS AI is unavailable. Your question is still here; you can use the guided step or try later.':state==='source'?'Selected sources are unavailable or not approved. Refresh project context and review your selection.':'The AI reply could not be verified. Review the selected sources and try again.',{exact:true}).waitFor();
   assert.equal(await page.getByRole('textbox').inputValue(),'Keep this question');
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

test('hydrated Chromium continuity, scope isolation and local actions make zero requests',async t=>{
 const {createServer}=await import('vite');const {mkdirSync,mkdtempSync,writeFileSync,rmSync}=await import('node:fs');
 const {contextResponse,browserEntry,project,workspace,documentId,runId}=await import('./conversation-browser-fixture.mjs');
 mkdirSync('work',{recursive:true});const fixtureDir=mkdtempSync('work/conversation-browser-');writeFileSync(fixtureDir+'/entry.jsx',browserEntry);
 // This custom HTML entry is invisible to Vite's default HTML scanner. Discovering
 // React/lucide on demand can invalidate an in-flight module with a 504 before
 // React mounts. Prebundle the complete dependency set; use a cold, private cache
 // so prior app builds or test runs cannot hide that startup regression.
 const server=await createServer({configFile:false,root,cacheDir:resolve(fixtureDir,'node_modules/.vite'),resolve:{alias:{'@':root}},
  optimizeDeps:{noDiscovery:true,include:['react','react-dom/client','react/jsx-runtime','react/jsx-dev-runtime','lucide-react']},
  server:{host:'127.0.0.1',port:0,watch:{ignored:['**/.sites-runtime/**','**/.venv/**','**/.vercel/**','**/dist/**']}},appType:'custom'});
 server.middlewares.use((req,res,next)=>{if(req.url?.startsWith('/fixture')){res.setHeader('content-type','text/html');res.end('<html><head></head><body><div id="root"></div><script type="module" src="/'+fixtureDir+'/entry.jsx"></script></body></html>');}else next();});
 await server.listen();const origin=server.resolvedUrls.local[0];
 let browser;
 try{
  browser=await chromium.launch({...(process.env.BUYEROS_CORE_CHROMIUM?{executablePath:process.env.BUYEROS_CORE_CHROMIUM}:{}),headless:true});
  let holdReads=false;const heldReads=[];
  const page=await browser.newPage();page.setDefaultTimeout(30000);const errors=[],requests=[],moduleFailures=[];
  page.on('console',message=>{if(message.type()==='error')t.diagnostic('Browser console: '+message.text());});
  page.on('requestfailed',request=>{const failure=request.url()+' '+request.failure()?.errorText;t.diagnostic(failure);if(request.resourceType()==='script')moduleFailures.push(failure);});
  page.on('response',response=>{if(response.request().resourceType()==='script'&&!response.ok()){const failure=response.status()+' '+response.url();moduleFailures.push(failure);t.diagnostic(failure);}});
  page.on('pageerror',error=>{errors.push(error.message);t.diagnostic(error.stack??error.message);});
  await page.route('**/v1/**',async route=>{
   if(holdReads)await new Promise(resolve=>heldReads.push(resolve));
   const req=route.request();requests.push({method:req.method(),url:req.url()});const data=contextResponse(new URL(req.url()));
   return route.fulfill({status:data?200:403,json:data?{data,data_mode:'live',request_id:'conversation-browser'}:{error:{code:'PERMISSION_DENIED',message:'denied'},request_id:'conversation-browser'}});
  });
  await page.addInitScript(()=>{window.discussionStorageEvents=[];for(const method of ['getItem','setItem']){const original=Storage.prototype[method];Storage.prototype[method]=function(key,...args){if(key.startsWith('buyeros.discussions'))window.discussionStorageEvents.push({method,key});return original.call(this,key,...args);};}});
  await page.goto(origin+'fixture?flag=off');await page.getByRole('button',{name:'Home',exact:true}).waitFor();
  assert.equal(await page.getByRole('textbox').count(),0);assert.equal(requests.length,0);assert.deepEqual(await page.evaluate(()=>window.discussionStorageEvents),[]);
  assert.deepEqual(await page.evaluate(()=>Object.keys(localStorage).filter(k=>k.startsWith('buyeros.discussions'))),[]);
  await page.goto(origin+'fixture');await page.getByText('project-evidence.pdf',{exact:false}).waitFor().catch(async error=>{writeFileSync('work/conversation-browser-error.html',await page.content());writeFileSync('work/conversation-browser-requests.json',JSON.stringify(requests,null,2));throw error;});
  const initialReads=requests.length;assert.ok(initialReads>=5);assert.ok(requests.every(req=>req.method==='GET'));
  const templates=['Guide my first project','Understand my documents','Research a market','Review & shortlist buyers','Check a company','Prepare a follow-up'];
  const destinations=[['Offer','/app/discover/edit'],['Offer','/app/discover/edit'],['Research runs','/app/runs'],['Buyers','/app/discover'],['Buyers','/app/discover'],['Drafts','/app/outreach']];
  for(const [index,name] of templates.entries()){
   await page.getByRole('button',{name:'Home',exact:true}).click();await page.getByRole('button',{name,exact:false}).click();
   await page.getByRole('textbox').fill('My next local step');await page.getByRole('button',{name:'Send',exact:true}).click();await page.getByText('My next local step',{exact:true}).waitFor();
   assert.match(await page.locator('#fixture-path').textContent(),/^\/app\/discussions\/local-/);
   const [label,path]=destinations[index];await page.locator('.live-discussion-thread').getByRole('button',{name:'Open in '+label,exact:true}).first().click();
   assert.equal(await page.evaluate(()=>window.lastDestination),path+'?workspace='+workspace+'&project='+project);
   await page.getByRole('button',{name:'Home',exact:true}).click();await page.getByRole('region',{name:'Continue working',exact:true}).getByRole('button').first().click();
  }
  assert.equal(requests.length,initialReads,'template, route and Send actions must not fetch');
  await page.getByRole('button',{name:'Change language',exact:true}).click();await page.getByText('只儲存於此裝置 · 不會共用',{exact:true}).waitFor();await page.getByRole('button',{name:'Change language',exact:true}).click();
  // The DOM gets real values, while selections only persist generic labels and IDs.
  await page.getByRole('checkbox').first().click();
  await page.waitForFunction(()=>document.querySelector('input[type=checkbox]').checked);
  const stored=await page.evaluate(()=>Object.fromEntries(Object.entries(localStorage).filter(([k])=>k.startsWith('buyeros.discussions'))));
  const serialized=JSON.stringify(stored);assert.ok(!serialized.includes('PRIVATE_FACT_CONTENT'));assert.ok(!serialized.includes('project-evidence.pdf'));assert.ok(serialized.includes(documentId));
  await page.reload();await page.getByText('My next local step',{exact:true}).waitFor();await page.getByText('project-evidence.pdf',{exact:false}).waitFor();assert.equal(await page.getByRole('checkbox').first().isChecked(),true);
  // Scope reads may occur here; actions on the loaded scope remain entirely local.
  await page.getByRole('button',{name:'Home',exact:true}).click();await page.getByRole('region',{name:'Continue working',exact:true}).waitFor();
  assert.equal(await page.getByRole('region',{name:'Continue working',exact:true}).getByRole('listitem').count(),6);
  await page.getByRole('combobox',{name:'Fixture project'}).selectOption('project-b');await page.getByText('No discussions in this project yet.',{exact:true}).waitFor();
  await page.getByRole('combobox',{name:'Fixture project'}).selectOption(project);await page.getByRole('region',{name:'Continue working',exact:true}).getByRole('listitem').first().waitFor();
  // Every source destination preserves record IDs; navigation callback supplies scope.
  await page.getByRole('region',{name:'Recent research runs',exact:true}).getByRole('button',{name:'Open source',exact:true}).click();
  assert.equal(await page.evaluate(()=>window.lastDestination),`/app/discover/${runId}?workspace=${workspace}&project=${project}`);
  await page.getByRole('button',{name:'Home',exact:true}).click();
  await page.getByRole('region',{name:'Documents & outputs',exact:true}).last().getByRole('button',{name:'Open source',exact:true}).first().click();
  assert.equal(await page.evaluate(()=>window.lastDestination),`/app/discover/edit?document=${documentId}&workspace=${workspace}&project=${project}`);
  await page.getByRole('button',{name:'Home',exact:true}).click();
  holdReads=true;await page.getByRole('button',{name:'Revoke offer access',exact:true}).click();
  await page.getByText('project-evidence.pdf',{exact:false}).waitFor({state:'hidden',timeout:2000});
  holdReads=false;heldReads.forEach(resolve=>resolve());
  await page.getByRole('region',{name:'Continue working',exact:true}).getByRole('button').first().click();
  await page.getByRole('button',{name:'Second actor',exact:true}).click();await page.getByText('This discussion is not saved for this account and project on this device.',{exact:true}).waitFor();
  assert.equal(await page.getByText('My next local step',{exact:true}).count(),0);
  await page.getByRole('button',{name:'Home',exact:true}).click();await page.getByText('No discussions in this project yet.',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Second workspace',exact:true}).click();await page.getByText('No discussions in this project yet.',{exact:true}).waitFor();
  assert.deepEqual(errors,[]);assert.deepEqual(moduleFailures,[],'fixture modules must load cleanly from a cold cache');writeFileSync('work/conversation-browser-network.json',JSON.stringify({initialReads,requests,errors},null,2));
  // Two real tabs begin from the same snapshot. The scope lock makes one save
  // win and the stale writer must keep its composer instead of erasing data.
  const tabs=await browser.newContext(),tabRequests=[];
  await tabs.route('**/v1/**',route=>{
   const req=route.request(),data=contextResponse(new URL(req.url()));tabRequests.push(req.method());
   return route.fulfill({status:data?200:403,json:data?{data,data_mode:'live',request_id:'multitab-fixture'}:{error:{code:'PERMISSION_DENIED'},request_id:'multitab-fixture'}});
  });
  const a=await tabs.newPage(),b=await tabs.newPage();
  for(const tab of [a,b]){await tab.goto(origin+'fixture');await tab.getByText('project-evidence.pdf',{exact:false}).waitFor();}
  const tabReadCount=tabRequests.length;
  await a.getByRole('textbox').fill('Question in tab A');await b.getByRole('textbox').fill('Question in tab B');
  await Promise.all([a.getByRole('button',{name:'Send',exact:true}).click(),b.getByRole('button',{name:'Send',exact:true}).click()]);
  const conflict='Saved discussions changed in another tab. Changes were not saved. Copy any unsaved work before reloading.';
  await Promise.any([a.getByText(conflict,{exact:true}).waitFor(),b.getByText(conflict,{exact:true}).waitFor()]);
  const winner=(await a.getByRole('textbox').inputValue())===''?a:b,loser=winner===a?b:a;
  const persisted=()=>winner.evaluate(()=>JSON.parse(Object.entries(localStorage).find(([key])=>key.startsWith('buyeros.discussions'))[1]));
  const firstSave=await persisted();assert.equal(firstSave.threads.length,1);
  assert.match(await loser.getByRole('textbox').inputValue(),/^Question in tab [AB]$/);
  assert.equal(tabRequests.length,tabReadCount,'simultaneous local saves must not fetch');
  await loser.reload();await loser.getByText('project-evidence.pdf',{exact:false}).waitFor();
  await loser.getByRole('region',{name:'Continue working',exact:true}).getByRole('button').click();
  await winner.getByRole('textbox').fill('Saved in the winner');await winner.getByRole('button',{name:'Send',exact:true}).click();
  await winner.getByText('Saved in the winner',{exact:true}).waitFor();
  await loser.getByRole('textbox').fill('Keep this unsaved message');await loser.getByRole('button',{name:'Send',exact:true}).click();
  await loser.getByText(conflict,{exact:true}).waitFor();
  assert.equal(await loser.getByRole('textbox').inputValue(),'Keep this unsaved message');
  await loser.getByRole('checkbox').first().click();
  await loser.waitForFunction(()=>!document.querySelector('input[type=checkbox]').checked);
  assert.deepEqual((await persisted()).threads[0].messages.map(row=>row.text),[firstSave.threads[0].messages[0].text,'Saved in the winner']);
  assert.deepEqual((await persisted()).threads[0].sources,[]);
  // A queued write must recheck its actor/project before running under the lock.
  await loser.reload();await loser.getByText('project-evidence.pdf',{exact:false}).waitFor();
  await winner.evaluate(()=>{window.fixtureLockHeld=false;void navigator.locks.request(Object.keys(localStorage).find(key=>key.startsWith('buyeros.discussions')),async()=>{window.fixtureLockHeld=true;await new Promise(resolve=>window.releaseFixtureLock=resolve);});});
  await winner.waitForFunction(()=>window.fixtureLockHeld);
  const beforeQueued=await persisted();
  await loser.getByRole('textbox').fill('Must not enter the old scope');await loser.getByRole('button',{name:'Send',exact:true}).click();
  await winner.waitForFunction(async()=> (await navigator.locks.query()).pending.length>0);
  await loser.getByRole('combobox',{name:'Fixture project'}).selectOption('project-b');
  await loser.getByText('This discussion is not saved for this account and project on this device.',{exact:true}).waitFor();
  await winner.evaluate(()=>window.releaseFixtureLock());
  await winner.waitForFunction(async()=> (await navigator.locks.query()).pending.length===0&&(await navigator.locks.query()).held.length===0);
  assert.deepEqual(await persisted(),beforeQueued);
  // Unsupported lock capability must not fall back to unsafe persistent writes.
  const unlocked=await tabs.newPage();await unlocked.addInitScript(()=>Object.defineProperty(navigator,'locks',{value:undefined}));
  await unlocked.goto(origin+'fixture');await unlocked.getByText('project-evidence.pdf',{exact:false}).waitFor();
  await unlocked.getByRole('textbox').fill('Memory only');await unlocked.getByRole('button',{name:'Send',exact:true}).click();
  await unlocked.getByLabel('Discussion messages',{exact:true}).getByText('Memory only',{exact:true}).waitFor();
  await unlocked.getByText('Local storage is unavailable. Discussions are kept only in this tab.',{exact:true}).waitFor();
  assert.deepEqual(await persisted(),beforeQueued);assert.ok(tabRequests.every(method=>method==='GET'));
  await tabs.close();
 }finally{await browser?.close();await server.close();rmSync(fixtureDir,{recursive:true,force:true});}
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
  await page.goto(server.resolvedUrls.local[0]+'fixture');await page.getByText('project-evidence.pdf',{exact:false}).waitFor();
  await page.addStyleTag({content:css+readFileSync('features/live/discussion.css','utf8')});
  await page.getByRole('textbox').fill('Research these approved sources');await page.getByRole('button',{name:'Send',exact:true}).click();
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
  await page.reload();await page.getByText(runId,{exact:true}).waitFor();await page.locator('.live-conversation-research').getByText('partial',{exact:true}).waitFor();
  await page.getByRole('checkbox').nth(1).click();await page.getByRole('textbox').fill('Which source supports this?');await page.getByRole('button',{name:'Ask BuyerOS',exact:true}).click();
  await page.getByText('PRIVATE_LIVE_MODEL_FACT_BODY',{exact:true}).waitFor();
  assert.doesNotMatch(await page.evaluate(()=>Object.values(localStorage).join('')),/PRIVATE_LIVE_MODEL_FACT_BODY|PRIVATE_BUYER_BODY|PRIVATE_FACT_CONTENT/);
  const count=posts.length;await page.reload();await page.getByText(runId,{exact:true}).waitFor();assert.equal(await page.getByText('PRIVATE_LIVE_MODEL_FACT_BODY',{exact:true}).count(),0);assert.equal(posts.length,count);
  await page.goto(server.resolvedUrls.local[0]+'fixture?flag=off');await page.getByRole('button',{name:'Operations',exact:true}).waitFor();assert.equal(await propose().count(),0);assert.equal(posts.length,count);
  assert.deepEqual(errors,[]);
 }finally{await browser?.close();await server.close();rmSync(dir,{recursive:true,force:true});}
});

test('Stage 3 confirmed import retries once, shares by keyboard, restores and preserves stale text',async()=>{
 const {createServer}=await import('vite');const {mkdirSync,mkdtempSync,writeFileSync,rmSync}=await import('node:fs');
 const {contextResponse,browserEntry}=await import('./conversation-browser-fixture.mjs');
 mkdirSync('work',{recursive:true});const dir=mkdtempSync('work/conversation-server-browser-');writeFileSync(dir+'/entry.jsx',browserEntry);
 const server=await createServer({configFile:false,root,cacheDir:resolve(dir,'node_modules/.vite'),resolve:{alias:{'@':root}},optimizeDeps:{noDiscovery:true,include:['react','react-dom/client','react/jsx-runtime','react/jsx-dev-runtime','lucide-react']},server:{host:'127.0.0.1',port:0,watch:{ignored:['**/.sites-runtime/**','**/.venv/**','**/.vercel/**','**/dist/**']}},appType:'custom'});
 server.middlewares.use((req,res,next)=>{if(req.url?.startsWith('/fixture')){res.setHeader('content-type','text/html');res.end('<html><head><style>'+readFileSync('features/live/discussion.css','utf8')+'</style></head><body><div id="root"></div><script type="module" src="/'+dir+'/entry.jsx"></script></body></html>');}else next();});
 await server.listen();let browser;
 try{
  browser=await chromium.launch({...(process.env.BUYEROS_CORE_CHROMIUM?{executablePath:process.env.BUYEROS_CORE_CHROMIUM}:{}),headless:true});
  const page=await browser.newPage(),posts=[],errors=[];page.on('pageerror',error=>errors.push(error.message));
  const id='12345678-1234-4123-8123-123456789012',member={member_id:'22345678-1234-4123-8123-123456789012',display_name:'Synthetic colleague'};
  let row=null,grants=[],uncertain=true,stale=false,access='owner',forbidden=false;
  await page.route('**/v1/**',async route=>{
   const req=route.request(),url=new URL(req.url()),path=url.pathname,method=req.method();
   const ok=data=>route.fulfill({json:{data,data_mode:'live',request_id:'stage3-synthetic'}});
   if(!path.includes('/conversation-threads'))return ok(contextResponse(url));
   if(method==='GET'){
    if(path.endsWith('/conversation-threads'))return ok({items:row?[{...row,access}]:[],offset:0,limit:50,total:row?1:0});
    if(forbidden)return route.fulfill({status:404,json:{code:'NOT_FOUND',message:'discussion not found'}});
    if(path.endsWith('/share-recipients'))return ok({items:[member],offset:0,limit:25});
    if(path.endsWith('/shares'))return ok({items:grants,version:row.version});
    return ok({...row,access});
   }
   posts.push({path,method,body:req.postData()?req.postDataJSON():null,key:req.headers()['idempotency-key'],version:req.headers()['x-buyeros-if-match']});
   if(path.endsWith('/conversation-threads')){
    row??={id,templateId:'custom',title:'Synthetic workspace note',createdAt:1,updatedAt:2,messages:[{id:'m1',text:'Synthetic workspace note'}],sources:[],runs:[],version:1,access:'owner',shareCount:0};
    if(uncertain){uncertain=false;return route.fulfill({status:503,json:{code:'UNAVAILABLE',message:'uncertain'}});}return ok(row);
   }
   if(path.endsWith('/messages')){
    if(stale)return route.fulfill({status:409,json:{code:'STALE_REVISION',message:'changed'}});
    row={...row,version:row.version+1,messages:[...row.messages,{id:'m2',text:req.postDataJSON().text}]};return ok(row);
   }
   if(path.includes('/shares/')){
    grants=method==='DELETE'?[]:[{...member,role:req.postDataJSON().role,active:true}];row={...row,version:row.version+1,shareCount:grants.length};return ok(row);
   }
   throw new Error('unexpected thread write '+path);
  });
  await page.goto(server.resolvedUrls.local[0]+'fixture');await page.getByText('project-evidence.pdf',{exact:false}).waitFor();
  await page.getByRole('textbox').fill('Synthetic workspace note');await page.getByRole('button',{name:'Send',exact:true}).click();
  await page.getByLabel('Discussion messages',{exact:true}).waitFor();assert.equal(posts.length,0,'local notes never auto-upload');
  await page.getByRole('button',{name:'Save to workspace',exact:true}).click();assert.equal(posts.length,0,'opening confirmation cannot import');
  await page.getByRole('button',{name:'Confirm workspace save',exact:true}).click();await page.getByText('Workspace discussions are unavailable. Your unsaved text is still here.',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Confirm workspace save',exact:true}).click();await page.getByRole('button',{name:'Open workspace discussion',exact:true}).waitFor();
  assert.equal(posts.length,2);assert.equal(posts[0].key,posts[1].key);assert.deepEqual(posts[0].body,{confirmed:true,template_id:'custom',title:'Synthetic workspace note',messages:[{text:'Synthetic workspace note'}],sources:[],runs:[]});
  assert.match(await page.evaluate(()=>Object.values(localStorage).join('')),/Synthetic workspace note/);
  await page.getByRole('button',{name:'Open workspace discussion',exact:true}).click();await page.getByText('Saved to this workspace · visible to you and people you share with',{exact:true}).waitFor();
  await page.reload();await page.getByRole('button',{name:'Share discussion',exact:true}).waitFor();
  await page.getByRole('button',{name:'Share discussion',exact:true}).focus();await page.keyboard.press('Enter');
  await page.getByRole('dialog',{name:'Share discussion',exact:true}).waitFor();
  for(const width of [320,390,480,600,768,820,1023,1024,1440]){
   await page.setViewportSize({width,height:1000});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth)<=width,`share dialog overflows ${width}`);
  }
  await page.keyboard.press('Escape');await page.getByRole('button',{name:'Change language',exact:true}).click();
  await page.getByRole('button',{name:'共用討論',exact:true}).focus();await page.keyboard.press('Enter');
  await page.getByRole('dialog',{name:'共用討論',exact:true}).waitFor();
  for(const width of [320,390,480,600,768,820,1023,1024,1440]){
   await page.setViewportSize({width,height:1000});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth)<=width,`zh-HK share dialog overflows ${width}`);
  }
  await page.keyboard.press('Escape');await page.getByRole('button',{name:'Change language',exact:true}).click();await page.getByRole('button',{name:'Share discussion',exact:true}).click();
  await page.getByLabel('Find workspace member').fill('Synthetic');await page.getByRole('button',{name:'Search members',exact:true}).click();
  await page.getByLabel('Share role',{exact:true}).selectOption('editor');await page.getByRole('button',{name:'Share with member',exact:true}).click();await page.getByRole('button',{name:'Make viewer',exact:true}).waitFor();
  await page.getByRole('button',{name:'Make viewer',exact:true}).click();await page.getByRole('button',{name:'Make editor',exact:true}).waitFor();
  await page.getByRole('button',{name:'Revoke access',exact:true}).click();await page.getByRole('button',{name:'Make editor',exact:true}).waitFor({state:'detached'});
  await page.keyboard.press('Escape');assert.equal(await page.getByRole('button',{name:'Share discussion',exact:true}).evaluate(node=>document.activeElement===node),true);
  stale=true;await page.getByLabel('Discussion message',{exact:true}).fill('Keep this unsaved text');await page.getByRole('button',{name:'Send',exact:true}).click();
  await page.getByText('This discussion changed. Copy any unsaved text before reloading.',{exact:true}).waitFor();assert.equal(await page.getByLabel('Discussion message',{exact:true}).inputValue(),'Keep this unsaved text');
  access='viewer';stale=false;await page.reload();await page.getByText('Shared with you',{exact:false}).waitFor();
  assert.equal(await page.getByLabel('Discussion message',{exact:true}).isDisabled(),true);assert.equal(await page.getByRole('button',{name:'Ask BuyerOS',exact:true}).isDisabled(),true);assert.equal(await page.getByRole('button',{name:'Propose research',exact:true}).count(),0);assert.equal(await page.getByRole('button',{name:'Share discussion',exact:true}).count(),0);
  forbidden=true;await page.reload();await page.getByText('This workspace discussion was not found or is no longer shared with you.',{exact:true}).first().waitFor();assert.equal(await page.getByLabel('Discussion messages',{exact:true}).count(),0);
  const before=posts.length;await page.goto(server.resolvedUrls.local[0]+'fixture?flag=off');await page.getByRole('button',{name:'Operations',exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'Save to workspace',exact:true}).count(),0);assert.equal(posts.length,before);
  assert.deepEqual(errors,[]);
 }finally{await browser?.close();await server.close();rmSync(dir,{recursive:true,force:true});}
});

for(const runFailure of [503,409,404])test(`Stage 3 thread save failures preserve paid work and permission context (run save ${runFailure})`,async()=>{
 const {createServer}=await import('vite');const {mkdirSync,mkdtempSync,writeFileSync,rmSync}=await import('node:fs');
 const {contextResponse,browserEntry,workspace,project,profileId,factId}=await import('./conversation-browser-fixture.mjs');
 mkdirSync('work',{recursive:true});const dir=mkdtempSync('work/conversation-server-recovery-');
 writeFileSync(dir+'/entry.jsx',browserEntry.replace('Revoke offer access</button>','Revoke offer access</button><button onClick={()=>setOfferAccess(true)}>Restore offer access</button>'));
 const server=await createServer({configFile:false,root,cacheDir:resolve(dir,'node_modules/.vite'),resolve:{alias:{'@':root}},optimizeDeps:{noDiscovery:true,include:['react','react-dom/client','react/jsx-runtime','react/jsx-dev-runtime','lucide-react']},server:{host:'127.0.0.1',port:0,watch:{ignored:['**/.sites-runtime/**','**/.venv/**','**/.vercel/**','**/dist/**']}},appType:'custom'});
 server.middlewares.use((req,res,next)=>{if(req.url?.startsWith('/fixture')){res.setHeader('content-type','text/html');res.end('<html><body><div id="root"></div><script type="module" src="/'+dir+'/entry.jsx"></script></body></html>');}else next();});
 await server.listen();let browser;
 try{
  browser=await chromium.launch({...(process.env.BUYEROS_CORE_CHROMIUM?{executablePath:process.env.BUYEROS_CORE_CHROMIUM}:{}),headless:true});
  const page=await browser.newPage(),posts=[],errors=[],heldReads=[];page.on('pageerror',error=>errors.push(error.message));
  const id='12345678-1234-4123-8123-123456789012',runId='b4000000-0000-4000-8000-000000000001';
  const ref={id:`fact:profile:${profileId}:${factId}`,label:'Approved offer fact',locator:{surface:'profile',id:profileId}};
  const answer='PRIVATE_ACCEPTED_AI_REPLY';let failNote=true,holdContext=false,holdNote=false,releaseNote,noteStarted,holdCheck=false,releaseCheck,checkStarted;
  let row={id,templateId:'custom',title:'Synthetic recovery',createdAt:1,updatedAt:2,messages:[{id:'m1',text:'Synthetic note'}],sources:[{id:ref.id,label:ref.label}],runs:[],version:1,access:'owner',shareCount:0};
  await page.route('**/v1/**',async route=>{
   const req=route.request(),url=new URL(req.url()),path=url.pathname,method=req.method();
   const ok=data=>route.fulfill({json:{data,data_mode:'live',request_id:'stage3-recovery'}});
   if(method==='POST'){
    posts.push({path,body:req.postDataJSON(),key:req.headers()['idempotency-key']});
    if(path.endsWith('/conversation-reply'))return ok({status:'needs_review',fixture:false,text:answer,citations:[ref]});
    if(path.includes('/conversation-threads/')){
     if(path.endsWith('/runs'))return route.fulfill({status:runFailure,json:{code:runFailure===409?'STALE_REVISION':runFailure===404?'NOT_FOUND':'UNAVAILABLE',message:'not saved'}});
     if(failNote)return route.fulfill({status:503,json:{code:'UNAVAILABLE',message:'not saved'}});
     if(holdNote)await new Promise(resolve=>{releaseNote=resolve;noteStarted();});
     row={...row,version:row.version+1,messages:[...row.messages,{id:'m'+(row.messages.length+1),text:req.postDataJSON().text}]};return ok(row);
    }
    return ok({id:runId,workspace_id:workspace,project_id:project,status:'queued'});
   }
   if(method==='PATCH'&&path.endsWith('/'+id)){row={...row,title:req.postDataJSON().title,version:row.version+1};return ok(row);}
   if(path.includes('/conversation-threads')){
    if(holdCheck&&path.endsWith('/'+id))await new Promise(resolve=>{releaseCheck=resolve;checkStarted();});
    return ok(path.endsWith('/conversation-threads')?{items:[row],total:1,offset:0,limit:50}:row);
   }
   if(holdContext)await new Promise(resolve=>heldReads.push(resolve));
   if(path.endsWith('/budgets'))return ok({items:[['workspace',workspace,'all'],['project',project,'all'],['category',project,'discovery']].map(([scope,scope_id,category])=>({workspace_id:workspace,scope,scope_id,category,period_start:'2026-01-01T00:00:00Z',period_end:'2099-01-01T00:00:00Z',remaining:{amount:'1.000000',currency:'USD'},effective_state:'active'})),offset:0,limit:100,total:3});
   if(path.includes('pilot-budget'))return ok({id:null,workspace_id:workspace,project_id:project,remaining:null,currency:'USD'});
   let data=contextResponse(url);if(path.endsWith('/icp-versions')&&url.searchParams.get('limit')==='100')data={...data,limit:100};return ok(data);
  });
  await page.goto(server.resolvedUrls.local[0]+'fixture?route='+encodeURIComponent('/app/discussions/s/'+id));
  await page.getByText('project-evidence.pdf',{exact:false}).waitFor();
  const composer=page.getByLabel('Discussion message',{exact:true}),ask=page.getByRole('button',{name:'Ask BuyerOS',exact:true});
  await composer.fill('Keep my accepted question');await ask.evaluate(button=>{button.click();button.click();});
  await page.getByText('Workspace discussions are unavailable. Your unsaved text is still here.',{exact:true}).waitFor();
  assert.equal(await composer.inputValue(),'Keep my accepted question');
  if(runFailure===503){
   await page.getByRole('button',{name:'Home',exact:true}).first().click();
   await page.getByRole('region',{name:'Continue working',exact:true}).getByRole('button',{name:/Synthetic recovery/}).click();
   await composer.fill('Keep my accepted question');
  }
  failNote=false;await ask.evaluate(button=>{button.click();button.click();});
  await page.waitForFunction(()=>document.querySelector('#discussion-message').value==='');
  await page.getByText(answer,{exact:true}).waitFor();
  assert.equal(posts.filter(post=>post.path.endsWith('/conversation-reply')).length,1,'retrying the note save must reuse the accepted AI answer');
  const notes=posts.filter(post=>post.path.endsWith('/messages'));assert.equal(notes.length,2);assert.equal(notes[0].key,notes[1].key);
  failNote=true;await composer.fill('Retain my answer across a rename');await ask.click();
  await page.getByText('Workspace discussions are unavailable. Your unsaved text is still here.',{exact:true}).waitFor();
  await page.getByLabel('Discussion title',{exact:true}).fill('Renamed recovery');
  await page.getByRole('button',{name:'Rename discussion',exact:true}).click();
  await page.getByText('Renamed recovery',{exact:true}).waitFor();
  failNote=false;await ask.click();
  await page.waitForFunction(()=>document.querySelector('#discussion-message').value==='');
  assert.equal(posts.filter(post=>post.path.endsWith('/conversation-reply')).length,2,'a title save must not discard an accepted answer and charge a note retry again');
  if(runFailure===503){
   const questions=['First unsaved paid answer','Second unsaved paid answer'];
   failNote=true;
   for(const question of questions){
    await composer.fill(question);await ask.click();
    await page.getByText('Workspace discussions are unavailable. Your unsaved text is still here.',{exact:true}).waitFor();
   }
   failNote=false;
   for(const question of questions){
    await composer.fill(question);await ask.click();
    await page.waitForFunction(()=>document.querySelector('#discussion-message').value==='');
   }
   assert.equal(posts.filter(post=>post.path.endsWith('/conversation-reply')).length,4,'another accepted question must not replace earlier unsaved paid work');
  }
  await page.getByRole('button',{name:'Propose research',exact:true}).click();
  await page.getByRole('button',{name:'Confirm and start research',exact:true}).click();
  await page.getByRole('dialog',{name:'Confirm paid research'}).waitFor({state:'hidden'});
  await page.getByText('Research was accepted, but its reference could not be saved. Open Research runs.',{exact:true}).waitFor({timeout:3000});
  assert.equal(posts.filter(post=>post.path.endsWith('/runs')&&!post.path.includes('/conversation-threads/')).length,1);
  assert.equal(await page.getByRole('button',{name:'Confirm and start research',exact:true}).count(),0,'accepted research must require a new proposal before another paid action');
  assert.doesNotMatch(JSON.stringify(posts.filter(post=>post.path.includes('/conversation-threads/'))),/PRIVATE_ACCEPTED_AI_REPLY|PRIVATE_FACT_CONTENT|project-evidence\.pdf/);
  assert.deepEqual(await page.evaluate(()=>Object.keys(localStorage)),[],'server threads and live replies stay out of localStorage');
  if(runFailure===503){
   // The paid answer arrives before permission loss; its delayed note response
   // must not restore it after the permission effect has aborted the request.
   await page.getByRole('button',{name:'Rename discussion',exact:true}).click();
   await page.getByText(answer,{exact:true}).waitFor({state:'hidden'});
   holdNote=true;const noteReceived=new Promise(resolve=>noteStarted=resolve);
   await composer.fill('Discard this delayed reply after permission loss');await ask.click();await noteReceived;
   holdContext=true;await page.getByRole('button',{name:'Revoke offer access',exact:true}).click();
   await page.getByText('project-evidence.pdf',{exact:false}).waitFor({state:'hidden'});
   releaseNote();holdNote=false;
   await page.waitForFunction(()=>document.querySelector('#discussion-message')&&Array.from(document.querySelectorAll('button')).find(button=>button.textContent==='Ask BuyerOS')?.disabled);
   assert.equal(await page.getByText('project-evidence.pdf',{exact:false}).count(),0,'permission loss hides previous context before pending reads finish');
   assert.equal(await page.getByText('PRIVATE_FACT_CONTENT',{exact:true}).count(),0);
   holdContext=false;heldReads.splice(0).forEach(resolve=>resolve());
   await page.getByRole('button',{name:'Restore offer access',exact:true}).click();
   await page.getByText('project-evidence.pdf',{exact:false}).waitFor();
   assert.equal(await page.getByText(answer,{exact:true}).count(),0,'an aborted in-flight answer cannot reappear after permission restoration');
   assert.equal(await composer.inputValue(),'Discard this delayed reply after permission loss');
   await page.reload();await composer.waitFor();
   const paidCount=posts.filter(post=>post.path.endsWith('/conversation-reply')).length;
   holdCheck=true;const checkReceived=new Promise(resolve=>checkStarted=resolve);
   await composer.fill('Leave before the paid request');await ask.click();await checkReceived;
   await page.getByRole('button',{name:'Home',exact:true}).first().click();
   await page.getByRole('region',{name:'Continue working',exact:true}).waitFor();
   holdCheck=false;const response=page.waitForResponse(result=>new URL(result.url()).pathname.endsWith('/'+id));releaseCheck();await response;
   await page.getByRole('region',{name:'Continue working',exact:true}).getByRole('button',{name:/Renamed recovery/}).click();
   await composer.waitFor();
   assert.equal(posts.filter(post=>post.path.endsWith('/conversation-reply')).length,paidCount,'unmount during the ACL recheck cannot launch a paid request');
   assert.equal(await composer.inputValue(),'');
   for(const exit of ['permission','thread']){
    await page.getByRole('button',{name:'Propose research',exact:true}).click();
    holdCheck=true;const confirmCheck=new Promise(resolve=>checkStarted=resolve);
    await page.getByRole('button',{name:'Confirm and start research',exact:true}).click();await confirmCheck;
    // Simulate an external permission update or route change while the modal
    // is waiting for its ACL response, before any paid admission has started.
    await page.getByRole('button',{name:exit==='permission'?'Revoke offer access':'Home',exact:true}).first().evaluate(button=>button.click());
    await page.getByRole('dialog',{name:'Confirm paid research'}).waitFor({state:'hidden'});
    holdCheck=false;const checked=page.waitForResponse(result=>new URL(result.url()).pathname.endsWith('/'+id));releaseCheck();await (await checked).finished();
    if(exit==='permission')await page.getByRole('button',{name:'Restore offer access',exact:true}).click();
    else await page.getByRole('region',{name:'Continue working',exact:true}).getByRole('button',{name:/Renamed recovery/}).click();
    await page.getByText('project-evidence.pdf',{exact:false}).waitFor();
    await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
    assert.equal(posts.filter(post=>post.path.endsWith('/runs')&&!post.path.includes('/conversation-threads/')).length,1,`${exit} unmount during the research ACL recheck must not start paid research`);
   }
  }else await page.getByText(runFailure===409?'This discussion changed. Copy any unsaved text before reloading.':'This workspace discussion was not found or is no longer shared with you.',{exact:true}).first().waitFor();
  heldReads.splice(0).forEach(resolve=>resolve());assert.deepEqual(errors,[]);
 }finally{await browser?.close();await server.close();rmSync(dir,{recursive:true,force:true});}
});
