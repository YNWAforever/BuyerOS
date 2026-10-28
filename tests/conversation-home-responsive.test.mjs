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
const sampleContext=[{title:'Documents & outputs',items:[{id:'document:d1',label:'Offer document',title:'source'.repeat(40)+'.pdf',status:'parsing',path:'/app/discover/edit?document=d1'}]},{title:'Offer facts',items:[{id:'fact:f1',label:'Candidate offer fact',title:'product',detail:'內容'.repeat(250),status:'candidate',path:'/app/discover/edit'}]}];
for(const locale of ['en','zh-HK'])test(`thread and context fit 320–1440px in ${locale}`,async()=>{
 const {liveZh}=await import('../features/live/locale.ts');const t=value=>locale==='zh-HK'?(liveZh[value]||value):value;
 const browser=await chromium.launch({...(process.env.BUYEROS_CORE_CHROMIUM?{executablePath:process.env.BUYEROS_CORE_CHROMIUM}:{}),headless:true});
 try{
  const panel=LiveDiscussion({t,locale,thread:sampleThread,threads:[sampleThread],value:'',notice:'',context:sampleContext,navigate:()=>{},onTemplate:()=>{},onChange:()=>{},onSend:()=>{},onSource:()=>{},onRefresh:()=>{}});
  const nav=LiveNavigation({t,navigate:()=>{},pathname:'/app',authorized:true,projectKnown:true,canEdit:true,projectActive:true,canCreate:true,conversationHome:true});
  const frame=LiveFrame({t,pathname:'/app',navigation:nav,footer:null,header:null,children:panel,conversationHome:true});
  const page=await browser.newPage();await page.setContent('<style>'+css+readFileSync('features/live/discussion.css','utf8')+'</style>'+renderToStaticMarkup(frame));
  for(const width of [320,390,480,481,600,768,820,1023,1024,1440]){
   await page.setViewportSize({width,height:1000});const actual=await page.evaluate(()=>document.documentElement.scrollWidth);
   assert.ok(actual<=width,`${locale} thread viewport ${width}px overflows to ${actual}px`);
   assert.equal(await page.getByRole('textbox').count(),1);assert.equal(await page.getByRole('checkbox').count(),2);
  }
 }finally{await browser.close();}
});

test('hydrated Chromium continuity, scope isolation and local actions make zero requests',async()=>{
 const {createServer}=await import('vite');const {mkdirSync,writeFileSync,rmSync}=await import('node:fs');
 const {contextResponse,browserEntry,project,workspace,documentId,runId}=await import('./conversation-browser-fixture.mjs');
 const fixtureDir='work/conversation-browser';mkdirSync(fixtureDir,{recursive:true});writeFileSync(fixtureDir+'/entry.jsx',browserEntry);
 const server=await createServer({configFile:false,root,resolve:{alias:{'@':root}},server:{host:'127.0.0.1',port:0},appType:'custom'});
 server.middlewares.use((req,res,next)=>{if(req.url?.startsWith('/fixture')){res.setHeader('content-type','text/html');res.end('<html><head></head><body><div id="root"></div><script type="module" src="/work/conversation-browser/entry.jsx"></script></body></html>');}else next();});
 await server.listen();const origin=server.resolvedUrls.local[0];
 let browser;
 try{
  browser=await chromium.launch({...(process.env.BUYEROS_CORE_CHROMIUM?{executablePath:process.env.BUYEROS_CORE_CHROMIUM}:{}),headless:true});
  let holdReads=false;const heldReads=[];
  const page=await browser.newPage();page.setDefaultTimeout(30000);const errors=[],requests=[];page.on('console',message=>{if(message.type()==='error')writeFileSync('work/conversation-browser-console.log',message.text()+'\n',{flag:'a'});});page.on('requestfailed',request=>writeFileSync('work/conversation-browser-console.log',request.url()+' '+request.failure()?.errorText+'\n',{flag:'a'}));page.on('pageerror',error=>{errors.push(error.message);writeFileSync('work/conversation-browser-errors.json',JSON.stringify(errors));});
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
  await page.getByRole('checkbox').first().check();
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
  assert.deepEqual(errors,[]);writeFileSync('work/conversation-browser-network.json',JSON.stringify({initialReads,requests,errors},null,2));
 }finally{await browser?.close();await server.close();rmSync(fixtureDir,{recursive:true,force:true});}
});
