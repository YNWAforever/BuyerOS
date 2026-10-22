import test,{before,after} from 'node:test';
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {resolve} from 'node:path';
import {createServer as createViteServer} from 'vite';
import react from '@vitejs/plugin-react';
import ts from 'typescript';
import {chromium,expect} from '@playwright/test';

// Actual React components, session and HTTP client; only Auth context/navigation
// are replaced. All API responses below are fictional and confined to this server.
const context=`
import {useSyncExternalStore} from 'react';
import {SessionScope} from '/services/live/session.ts';
import {createLiveClient} from '/services/live/client.ts';
export const session=new SessionScope({mode:'live',actor:'synthetic',workspace:'workspace-a',project:'project-a'});
session.setToken('synthetic-component-only');
const client=createLiveClient(fetch,location.origin);
export const useWorkspaceSession=()=>({session,client});
export const useSessionSnapshot=()=>useSyncExternalStore(session.subscribe,session.getSnapshot,session.getSnapshot);
`;
const entry=`
import React,{useState} from 'react';
import {createRoot} from 'react-dom/client';
import {session} from 'virtual:owner-context';
import {LeadProgressPanel} from '/features/live/lead-workflow/progress-panel.tsx';
import {LiveOperations} from '/features/live/operations.tsx';
import {useOwnerDirectory} from '/features/live/lead-workflow/owner-directory.tsx';
function Probe({config}){
 const directory=useOwnerDirectory(config.member,config.canAssign);
 return <><output data-testid="projection">{JSON.stringify({items:directory.items.map(x=>x.display_name),own:directory.ownUserId,foreign:directory.name('user-a'),error:directory.error})}</output><button onClick={directory.retry}>Retry probe</button></>;
}
function App(){
 const [config,setConfig]=useState({canAssign:false,member:'member-a',mode:'queue'});
 window.configureOwnerFixture=next=>{if(next.workspace)session.next({workspace:next.workspace,project:'project-a'});setConfig(current=>({...current,...next}));};
 return config.mode==='probe'?<Probe config={config}/>:<>
  <LeadProgressPanel mode="queue" locale="en" canAssign={config.canAssign} ownMembershipId={config.member}/>
  {config.mode==='outage'&&<LiveOperations workspace="workspace-a" project="project-a" isAdmin={false} onOpenBuyers={()=>{}} t={x=>x}/>}
 </>;
}
createRoot(document.getElementById('root')).render(<App/>);
`;
let vite,server,browser,origin;
before(async()=>{
 const modules={'virtual:owner-context':context,'virtual:owner-entry':ts.transpileModule(entry,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText,
  'virtual:owner-navigation':'export const useSearchParams=()=>new URLSearchParams(); export const useRouter=()=>({push(){}});',
  'virtual:owner-link':"import React from 'react'; export default function Link({prefetch,...props}){return React.createElement('a',props)}",
  'virtual:owner-inactive-panels':'export const LeadEvidencePanel=()=>null;export const LeadCasePanel=()=>null;'};
 const plugin={name:'owned-directory-fixture',enforce:'pre',
  resolveId(id,importer){if(importer?.endsWith('/lead-workflow/progress-panel.tsx')&&['./evidence-panel','./case-panel'].includes(id))return '\0virtual:owner-inactive-panels';if(id==='/__owner_entry.tsx')return '\0virtual:owner-entry';if(Object.hasOwn(modules,id))return '\0'+id;},
  load(id){if(id.startsWith('\0'))return modules[id.slice(1)];}};
 vite=await createViteServer({root:process.cwd(),configFile:false,envDir:false,envFile:false,
  appType:'custom',plugins:[plugin,react()],logLevel:'error',
  resolve:{alias:[{find:'@/features/providers/workspace-session',replacement:'virtual:owner-context'},
   {find:'next/navigation',replacement:'virtual:owner-navigation'},{find:'next/link',replacement:'virtual:owner-link'},
   {find:'@',replacement:resolve('.')} ]},
  server:{middlewareMode:true,hmr:false},optimizeDeps:{noDiscovery:true,include:['react','react-dom/client','react/jsx-dev-runtime','react/jsx-runtime']}});
 server=createServer((req,res)=>{
  if(req.url==='/')void vite.transformIndexHtml('/','<div id="root"></div><script type="module" src="/__owner_entry.tsx"></script>').then(html=>{res.setHeader('Content-Type','text/html');res.end(html);}).catch(error=>{res.statusCode=500;res.end(error.name);});
  else vite.middlewares(req,res);
 });
 await new Promise((done,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',done);});
 origin='http://127.0.0.1:'+server.address().port;
 browser=await chromium.launch({headless:true});
}, {timeout:120_000});
after(async()=>{await browser?.close();await vite?.close();if(server)await new Promise(done=>server.close(done));});

async function fixture(config={},options={}){
 const context=await browser.newContext(),page=await context.newPage(),calls=[],errors=[];
 page.setDefaultTimeout(15_000);page.setDefaultNavigationTimeout(90_000);
 const state={deny:false,hold:null,...options};
 page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/*',async route=>{
  const url=new URL(route.request().url());
  if(url.origin!==origin)return route.abort();
  if(!url.pathname.startsWith('/v1/'))return route.continue();
  calls.push(url.pathname+url.search);
  const reply=(data,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(status===200?{data_mode:'live',request_id:'synthetic-read',data}:data)}).catch(()=>{});
  if(url.pathname.endsWith('/eligible-assignees')){
   if(state.hold)await state.hold;
   if(state.deny)return reply({code:'PERMISSION_DENIED',message:'synthetic role refusal',request_id:'synthetic-directory-denied'},403);
   const suffix=url.pathname.includes('workspace-b')?'b':'a';
   return reply({items:[{membership_id:'member-'+suffix,user_id:'user-'+suffix,display_name:suffix==='a'?'Alpha Owner':'Beta Owner',version:1}],total:1,offset:0,limit:20});
  }
  if(url.pathname.endsWith('/lead-workflow'))return reply({items:[],total:0,offset:0,limit:20,as_of:'2026-10-22T00:00:00Z',metrics:{company_cards:0,priority_companies:0,qualified_people_companies:0,direct_channel_companies:0,reviewed_preparation_companies:0}});
  if(url.pathname.endsWith('/capabilities'))return reply({items:[]});
  if(url.pathname.endsWith('/jobs')){
   if(url.searchParams.get('status')==='failed')return reply({code:'FIXTURE_OUTAGE',message:'synthetic jobs outage',request_id:'22222222-2222-4222-8222-222222222222',retryable:true},503);
   return reply({items:[],total:0,offset:0,limit:20});
  }
  if(url.pathname.endsWith('/projects/project-a'))return reply({code:'FIXTURE_OUTAGE',message:'synthetic project outage',request_id:'22222222-2222-4222-8222-222222222222',retryable:true},503);
  errors.push('Unexpected API path: '+url.pathname);return route.abort();
 });
 await page.goto(origin,{waitUntil:'domcontentloaded'});await page.waitForFunction(()=>typeof window.configureOwnerFixture==='function');
 await page.evaluate(config=>window.configureOwnerFixture(config),config);
 return {page,context,calls,errors,state,close:()=>context.close(),directoryCalls:()=>calls.filter(x=>x.includes('/eligible-assignees'))};
}
async function projection(page){return JSON.parse(await page.getByTestId('projection').textContent());}

test('reviewer/viewer outage keeps request evidence without unauthorized directory reads',async()=>{
 const f=await fixture({mode:'outage',canAssign:false},{deny:true});
 try{
  const queue=f.page.getByRole('region',{name:'Work queue',exact:true});
  await expect(queue).toContainText('Profile approval: Unavailable');await expect(queue).toContainText('Failed jobs: Unavailable');
  await f.page.waitForLoadState('networkidle');
  assert.deepEqual(f.directoryCalls(),[]);
  await expect(f.page.getByRole('alert')).toHaveCount(1);
  await expect(f.page.getByRole('alert')).toContainText('Request ID: 22222222-2222-4222-8222-222222222222');
  await expect(queue).not.toContainText('Loading');assert.deepEqual(f.errors,[]);
 }finally{await f.close();}
});
test('authorized operator/admin resolves named owners and its own identity',async()=>{
 const f=await fixture({canAssign:true});
 try{await expect(f.page.getByRole('option').filter({hasText:'Alpha Owner'})).toHaveCount(1);assert.ok(f.directoryCalls().length>0);await expect(f.page.getByRole('option',{name:'Mine',exact:true})).toBeEnabled();assert.deepEqual(f.errors,[]);}finally{await f.close();}
});
test('permission loss hides previously readable owner projection and identity',async()=>{
 const f=await fixture({canAssign:true,mode:'probe'});
 try{await expect.poll(async()=> (await projection(f.page)).own).toBe('user-a');const count=f.directoryCalls().length;
  await f.page.evaluate(()=>window.configureOwnerFixture({canAssign:false}));
  await expect.poll(()=>projection(f.page)).toEqual({items:[],own:null,foreign:null,error:''});assert.equal(f.directoryCalls().length,count);
 }finally{await f.close();}
});
test('a real server refusal remains visible for an authorized directory request',async()=>{
 const f=await fixture({canAssign:true},{deny:true});
 try{await expect(f.page.getByRole('alert')).toContainText('Request ID: synthetic-directory-denied');await expect(f.page.getByRole('alert')).toContainText('You do not have permission');assert.ok(f.directoryCalls().length>0);await expect(f.page.getByText('Loading members…',{exact:true})).toHaveCount(0);}finally{await f.close();}
});
test('workspace change never exposes another workspace cached member name',async()=>{
 const f=await fixture({canAssign:true,mode:'probe'});
 try{await expect.poll(async()=> (await projection(f.page)).own).toBe('user-a');
  await f.page.evaluate(()=>window.configureOwnerFixture({workspace:'workspace-b',member:'member-b'}));
  await expect.poll(async()=> (await projection(f.page)).own).toBe('user-b');
  assert.deepEqual(await projection(f.page),{items:['Beta Owner'],own:'user-b',foreign:null,error:''});
 }finally{await f.close();}
});
