import test from 'node:test';
import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';

const {SessionScope}=await loadModule('services/live/session.ts');
const {LiveError}=await loadModule('services/live/client.ts');
const {loadDiscussionContext}=await loadModule('services/live/discussion-context.ts');
const ids={workspace:'a0000000-0000-4000-8000-000000000001',project:'b0000000-0000-4000-8000-000000000001',
  document:'c0000000-0000-4000-8000-000000000001',profile:'d0000000-0000-4000-8000-000000000001',
  fact:'e0000000-0000-4000-8000-000000000001',run:'f0000000-0000-4000-8000-000000000001'};
const at='2026-10-28T12:00:00Z';
const entity=id=>({id,workspace_id:ids.workspace,version:1,created_at:at,updated_at:at,data_mode:'live'});
const fact=(patch={})=>({id:ids.fact,field:'product',value:'Private project offer',provenance:'user_entered',approved:true,...patch});
const document=(patch={})=>({...entity(ids.document),project_id:ids.project,filename:'Offer.pdf',media_type:'application/pdf',
  sha256:null,status:'ready',fact_candidates:[fact({source_document_id:ids.document})],...patch});
const project=(patch={})=>({...entity(ids.project),name:'Project',company_name:'Company',offer:'Offer',website:null,
  markets:['GB'],language_preferences:['en'],status:'active',offer_revision:2,active_icp_version_id:ids.profile,sender_identity:null,...patch});
const profile=(patch={})=>({...entity(ids.profile),project_id:ids.project,number:1,basis_offer_revision:2,
  basis_status:'current',is_current:true,content_hash:`sha256:${'a'.repeat(64)}`,status:'approved',approved_by:'reviewer',approved_at:at,
  offer_document_ids:[],offer_facts:[fact()],requirements:[],markets:['GB'],buyer_types:['distributor'],languages:['en'],desired_roles:[],...patch});
const money={amount:'0.000000',currency:'USD'};
const run=(patch={})=>({...entity(ids.run),project_id:ids.project,icp_version_id:ids.profile,status:'running',stage:'discovery',
  raw_count:0,company_count:100,assessed_count:0,last_event_sequence:0,max_cost:money,spent:money,reserved:money,
  limits:{query_rounds:3,max_results:100,max_pages:10,max_page_bytes:2000000,max_duration_seconds:1800,max_model_tokens:100000,provider_concurrency:4,max_queries_per_run:12},attempt:1,...patch});
const page=(items,limit=20,total=items.length,offset=0)=>({items,limit,total,offset});
const usage=(query,patch={})=>({workspace_id:ids.workspace,project_id:ids.project,from:query.get('from'),to:query.get('to'),as_of:at,
  categories:[],total_settled:money,total_reserved:money,remaining:money,accepted_company_count:4,eligible_contactable_company_count:2,
  cost_per_accepted_company:money,cost_per_contactable_accepted_company:money,denominator_definition:'Committed accepted project companies',includes_partial_runs:true,...patch});
function context(overrides={}){
  const session=new SessionScope({mode:'live',actor:'actor',workspace:ids.workspace,project:ids.project});
  session.setToken('memory-token');
  const calls=[];
  const client={request:async request=>{
    calls.push(request);
    assert.equal(request.method,'GET','context may only perform GET requests');
    assert.equal(request.token,'memory-token');
    const url=new URL(request.path,'https://api.example.test');
    const root=`/v1/workspaces/${ids.workspace}/projects/${ids.project}`;
    const route=url.pathname===root?'project':url.pathname===`${root}/offer-documents`?'documents':
      url.pathname===`${root}/icp-versions`?'profiles':url.pathname===`${root}/runs`?'runs':url.pathname===`${root}/usage`?'usage':null;
    assert.ok(route,`unexpected context read: ${request.path}`);
    if(Object.hasOwn(overrides,route))return overrides[route](request,url);
    if(route==='project')return project();
    if(route==='documents')return page([document()]);
    if(route==='profiles')return page([profile()]);
    if(route==='runs')return page([run()],10);
    return usage(url.searchParams);
  }};
  return {session,client,calls};
}
const options=patch=>({enabled:true,canViewOffer:true,canViewResults:true,signal:new AbortController().signal,...patch});
const load=(ctx,patch)=>loadDiscussionContext(ctx.client,ctx.session,options(patch));
const section=(sections,title)=>sections.find(row=>row.title===title);
const settle=()=>new Promise(resolve=>setImmediate(resolve));

test('disabled context performs no reads and returns no project data',async()=>{
  const ctx=context();
  assert.deepEqual(await load(ctx,{enabled:false}),[]);
  assert.equal(ctx.calls.length,0);
});

for(const scope of [{mode:'demo'},{actor:''},{workspace:null},{project:null}])test(`context refuses incomplete live scope ${JSON.stringify(scope)}`,async()=>{
  const ctx=context();ctx.session.next(scope);
  assert.deepEqual(await load(ctx),[]);
  assert.equal(ctx.calls.length,0);
});

test('signed-out and already-aborted context perform no reads',async()=>{
  const ctx=context();ctx.session.setToken(undefined);
  assert.deepEqual(await load(ctx),[]);assert.equal(ctx.calls.length,0);
  const current=context(),own=new AbortController();own.abort();
  assert.deepEqual(await load(current,{signal:own.signal}),[]);assert.equal(current.calls.length,0);
});

test('permission gates perform zero offer or results reads',async()=>{
  const ctx=context(),sections=await load(ctx,{canViewOffer:false,canViewResults:false});
  assert.deepEqual(sections.map(row=>row.title),['Recent research runs']);
  assert.equal(ctx.calls.length,1);
  assert.match(ctx.calls[0].path,/\/runs\?offset=0&limit=10$/);
});

test('context uses bounded existing GETs and preserves authoritative status and candidate provenance',async()=>{
  const ctx=context(),sections=await load(ctx);
  assert.equal(ctx.calls.length,5);
  const docs=section(sections,'Documents & outputs'),facts=section(sections,'Offer facts');
  assert.deepEqual(docs.items,[{id:`document:${ids.document}`,label:'Offer document',title:'Offer.pdf',status:'ready',
    path:`/app/discover/edit?document=${ids.document}#offer-documents`}]);
  assert.deepEqual(facts.items.map(row=>[row.label,row.status]),[
    ['Approved offer fact','approved'],['Candidate offer fact','candidate']]);
  assert.equal(new Set(facts.items.map(row=>row.id)).size,2,'fact IDs include the source version/document');
  assert.equal(facts.items[0].detail,'Private project offer');
  assert.equal(facts.items[0].path,`/app/overview?profile=${ids.profile}`);
  assert.equal(facts.items[1].path,`/app/discover/edit?document=${ids.document}#offer-documents`);
  const runs=section(sections,'Recent research runs');
  assert.equal(runs.items[0].status,'running','a high company count must not imply completion');
  assert.equal(runs.items[0].path,`/app/discover/${ids.run}`);
  const summary=section(sections,'Results summary').items[0];
  assert.equal(summary.id,`results:${ids.project}`);
  assert.equal(summary.path,'/app/results');
  assert.match(summary.detail,/4 \/ 2/);
  const url=new URL(ctx.calls.find(call=>call.path.includes('/usage?')).path,'https://api.example.test');
  const from=new Date(url.searchParams.get('from')),to=new Date(url.searchParams.get('to'));
  assert.equal(from.getUTCDate(),1);assert.equal(from.getUTCHours(),0);assert.equal(to.getUTCDate(),1);
  assert.equal(to.getUTCFullYear()*12+to.getUTCMonth()-from.getUTCFullYear()*12-from.getUTCMonth(),1);
});

for(const patch of [{status:'saved'},{status:'superseded'},{is_current:false},{basis_status:'stale'},
  {basis_status:'unknown'},{basis_offer_revision:1},{offer_facts:[fact({approved:false})]},
  {offer_facts:[fact({provenance:'model_inference'})]}])test(`only current reviewer-approved profile facts are approved ${JSON.stringify(patch)}`,async()=>{
  const ctx=context({profiles:()=>page([profile(patch)])});
  const facts=section(await load(ctx),'Offer facts');
  assert.equal(facts.items.some(row=>row.status==='approved'),false);
  assert.equal(facts.items.some(row=>row.status==='candidate'),true);
});

test('an approved profile outside the active project pointer cannot supply approved facts',async()=>{
  const ctx=context({project:()=>project({active_icp_version_id:null})});
  assert.equal(section(await load(ctx),'Offer facts').items.some(row=>row.status==='approved'),false);
});

test('only ready documents expose candidate facts',async()=>{
  const ctx=context({documents:()=>page([document({status:'parsing'})])});
  assert.equal(section(await load(ctx),'Offer facts').items.some(row=>row.status==='candidate'),false);
});

test('403 and 503 fail the affected section closed with honest generic notices',async()=>{
  const ctx=context({documents:()=>{throw new LiveError('secret denied body','DENIED',403,'secret-request',false);},
    usage:()=>{throw new LiveError('secret provider body','FAILED',503,'secret-request',true);}});
  const sections=await load(ctx);
  for(const title of ['Documents & outputs','Offer facts']){
    assert.deepEqual(section(sections,title).items,[]);
    assert.match(section(sections,title).notice,/Access denied/);
  }
  assert.deepEqual(section(sections,'Results summary').items,[]);
  assert.match(section(sections,'Results summary').notice,/temporarily unavailable/);
  assert.equal(section(sections,'Recent research runs').items.length,1);
  assert.doesNotMatch(JSON.stringify(sections),/secret|Private project offer/);
});

for(const [index,[route,value,title]] of [
  ['documents',page([document({workspace_id:'foreign'})]),'Documents & outputs'],
  ['documents',page([document({project_id:'foreign'})]),'Offer facts'],
  ['documents',page([document({fact_candidates:{}})]),'Offer facts'],
  ['documents',page([document({fact_candidates:null})]),'Documents & outputs'],
  ['project',project({workspace_id:'foreign'}),'Offer facts'],
  ['project',project({id:'foreign'}),'Offer facts'],
  ['profiles',page([profile({workspace_id:'foreign'})]),'Offer facts'],
  ['profiles',page([profile({project_id:'foreign'})]),'Offer facts'],
  ['profiles',page([profile({offer_facts:[fact({value:42})]})]),'Offer facts'],
  ['profiles',page([profile({approved_by:{actor:'reviewer'}})]),'Offer facts'],
  ['profiles',page([profile({approved_at:'yesterday'})]),'Offer facts'],
  ['runs',page([run({project_id:'foreign'})],10),'Recent research runs'],
  ['runs',page([run({status:'complete-ish'})],10),'Recent research runs'],
  ['runs',{items:{},offset:0,limit:10,total:0},'Recent research runs'],
].entries())test(`malformed or foreign ${route} response cannot expose section ${title} (case ${index+1})`,async()=>{
  const ctx=context({[route]:()=>value}),result=section(await load(ctx),title);
  assert.deepEqual(result.items,[]);assert.match(result.notice,/could not be verified/);
});

test('usage must match the project, workspace and requested UTC period and have valid counts',async()=>{
  for(const patch of [{project_id:'foreign'},{workspace_id:'foreign'},{from:at},{accepted_company_count:-1},
    {eligible_contactable_company_count:5},{accepted_company_count:'4'}]){
    const ctx=context({usage:(_request,url)=>usage(url.searchParams,patch)});
    const summary=section(await load(ctx),'Results summary');
    assert.deepEqual(summary.items,[]);assert.match(summary.notice,/could not be verified/);
  }
});

test('bounded document and run pages honestly disclose omitted context',async()=>{
  const docs=Array.from({length:20},(_,i)=>document({id:`c0000000-0000-4000-8000-${String(i+1).padStart(12,'0')}`,fact_candidates:[]}));
  const runs=Array.from({length:10},(_,i)=>run({id:`f0000000-0000-4000-8000-${String(i+1).padStart(12,'0')}`}));
  const ctx=context({documents:()=>page(docs,20,500),runs:()=>page(runs,10,1000)});
  const sections=await load(ctx);
  assert.equal(section(sections,'Documents & outputs').items.length,20);
  assert.match(section(sections,'Documents & outputs').notice,/recent|shown/i);
  assert.equal(section(sections,'Recent research runs').items.length,10);
  assert.match(section(sections,'Recent research runs').notice,/recent|shown/i);
  assert.equal(ctx.calls.length,5,'large totals must not cause a page crawl');
});

test('profile history uses a bounded head and tail and never claims full offer coverage',async()=>{
  const row=i=>profile({id:`d0000000-0000-4000-8000-${String(i+10).padStart(12,'0')}`,number:i+1,status:'saved',is_current:false,offer_facts:[]});
  const ctx=context({profiles:(_request,url)=>{
    const offset=Number(url.searchParams.get('offset'));
    assert.ok([0,180].includes(offset),'only head/tail reads are allowed');
    const items=Array.from({length:20},(_,i)=>row(offset+i));
    if(offset===180){
      items[5]=profile({number:186});
      items[19]=row(199);items[19].offer_facts=[fact({value:'Unapproved latest value'})];
    }
    return page(items,20,200,offset);
  }});
  const sections=await load(ctx),facts=section(sections,'Offer facts');
  assert.equal(ctx.calls.filter(call=>call.path.includes('/icp-versions?')).length,2);
  assert.equal(facts.items.some(row=>row.status==='approved'),true);
  assert.equal(facts.items.find(row=>row.detail==='Unapproved latest value').status,'candidate');
  assert.match(facts.notice,/shown|partial/i);
});

test('a changed profile history between bounded pages fails offer facts closed',async()=>{
  const ctx=context({profiles:(_request,url)=>{
    const offset=Number(url.searchParams.get('offset'));
    const items=Array.from({length:20},(_,i)=>profile({id:`d0000000-0000-4000-8000-${String(offset+i+1).padStart(12,'0')}`}));
    return page(items,20,offset===0?100:101,offset);
  }});
  const facts=section(await load(ctx),'Offer facts');
  assert.deepEqual(facts.items,[]);assert.match(facts.notice,/could not be verified/);
});

for(const action of ['abort','A-B-A','sign-out'])test(`${action} discards all delayed context and aborts its read signals`,async()=>{
  let release;
  const held=new Promise(resolve=>{release=resolve;});
  const ctx=context({documents:()=>held}),own=new AbortController();
  const pending=load(ctx,{signal:own.signal});
  await settle();
  if(action==='abort')own.abort();
  else if(action==='sign-out')ctx.session.setToken(undefined);
  else{ctx.session.next({project:'other'});ctx.session.next({project:ids.project});}
  assert.ok(ctx.calls.every(call=>call.signal.aborted));
  release(page([document()]));
  assert.deepEqual(await pending,[]);
});
