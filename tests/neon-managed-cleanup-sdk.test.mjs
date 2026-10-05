import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFileSync,readdirSync,writeFileSync,mkdirSync,existsSync} from 'node:fs';
import {join} from 'node:path';
import {createAuthClient} from '@neondatabase/auth';
import {executionFixture,listen} from './fixtures/neon-execution/fixture.mjs';
import {RealRunJournal} from '../scripts/neon-real-preflight.mjs';
import {createFixtureExecutionBoundary,createFixtureExecutionGateway} from '../scripts/neon-execution-boundary.mjs';
const cleanup=await import('../scripts/neon-managed-cleanup-sdk.mjs').catch(e=>{if(e.code!=='ERR_MODULE_NOT_FOUND')throw e;return {};});
const nonce='n'.repeat(43),cookie='fictional-cleanup-admin=owned';
const options={headers:{'x-n00-owner':nonce,cookie},retry:0,redirect:'manual'};
const query=id=>({filterField:'id',filterValue:id,filterOperator:'eq',limit:1,offset:0});
let capture=0;
async function wire(t,mode='normal'){
 const f=await executionFixture(async(req,res,{identity,model})=>{
  const url=new URL(req.url,'http://127.0.0.1');
  if(!url.pathname.startsWith('/fixture/auth/admin/'))return;
  assert.equal(model.hits.length,model.journal.snapshot().requests.filter(r=>r.operationId.startsWith('execution-http-')).length);
  assert.equal(model.journal.snapshot().requests.at(-1).outcome,'pending');
  res.setHeader('Content-Type','application/json');res.setHeader('Cache-Control','no-store');
  if(req.headers.cookie!==cookie){res.statusCode=403;res.end('{"code":"FORBIDDEN"}');return true;}
  const resource=model.resources.get('identity');
  if(url.pathname==='/fixture/auth/admin/list-users'){
   assert.equal(req.method,'GET');assert.deepEqual(Object.fromEntries(url.searchParams),Object.fromEntries(Object.entries(query(identity.id)).map(([k,v])=>[k,String(v)])));
   model.reads++;
   if(mode==='read-500'){res.statusCode=500;res.end('{"code":"INTERNAL_SERVER_ERROR"}');return true;}
   if(mode==='generic-404'){res.statusCode=404;res.end('{"code":"NOT_FOUND"}');return true;}
   const user={id:identity.id,name:'Fictional cleanup',email:'cleanup@fixture.invalid',emailVerified:false,role:'user',createdAt:identity.createdAt,updatedAt:identity.createdAt};
   if(mode==='foreign-id')user.id='other-user';
   if(mode==='foreign-created')user.createdAt=new Date(Date.parse(identity.createdAt)-1000).toISOString();
   const users=resource.exists?[user]:[],total=users.length;
   res.end(JSON.stringify(mode==='malformed'?{users:[],total:1,limit:1,offset:0}:mode==='post-delete-malformed'&&!resource.exists?{users:[],total:0}:{users,total,limit:1,offset:0}));return true;
  }
  if(url.pathname==='/fixture/auth/admin/remove-user'){
   assert.equal(req.method,'POST');let body='';for await(const c of req)body+=c;
   assert.deepEqual(JSON.parse(body),{userId:identity.id});model.removes++;
   if(mode==='reject-500'){res.statusCode=500;res.end('{"code":"INTERNAL_SERVER_ERROR"}');return true;}
   if(mode!=='lingering')resource.exists=false;
   if(mode==='commit-lost'){req.socket.destroy();return true;}
   res.end(JSON.stringify({success:mode!=='bad-success'}));return true;
  }
 });
 f.model.journal=f.journal;f.model.reads=0;f.model.removes=0;
 f.journal.bindIdentity(f.identity);
 f.execution=createFixtureExecutionBoundary({backend:f.backend,journal:f.journal});
 f.gateway=createFixtureExecutionGateway({execution:f.execution,nonce});f.servers.push(f.gateway);
 f.sdk=createAuthClient(await listen(f.gateway)+'/sdk/auth');
 t.after(async()=>{const records=f.journal.snapshot().requests;const receipts=records.map(r=>r.evidenceRef&&existsSync(join(f.root,r.evidenceRef))?JSON.parse(readFileSync(join(f.root,r.evidenceRef),'utf8')):null);const cleaned=await f.cleanup();const dir='test-results/neon-managed-cleanup-sdk/http-captures';mkdirSync(dir,{recursive:true});writeFileSync(join(dir,String(++capture).padStart(3,'0')+'.json'),JSON.stringify({case:t.name,fixture_only:true,external_requests:0,records,receipts,hits:f.model.hits,removes:f.model.removes,reads:f.model.reads,cleaned},null,2)+'\n');});
 return f;
}
async function run(f,extra={}){assert.equal(typeof cleanup.runFixtureManagedIdentityCleanup,'function','native SDK cleanup not wired');return cleanup.runFixtureManagedIdentityCleanup({execution:f.execution,journal:f.journal,gateway:f.gateway,nonce,sessionCookie:cookie,...extra});}

test('native pinned SDK exact-id lookup reaches owned HTTP with a durable reconciliation reservation',async t=>{
 const f=await wire(t);const response=await f.sdk.admin.listUsers({query:query(f.identity.id),fetchOptions:options});
 assert.equal(response.error,null);assert.equal(response.data.users[0].id,f.identity.id);assert.equal(f.model.reads,1);assert.equal(f.journal.snapshot().requests[0].purpose,'reconcile');
});
test('native SDK removal uses the twenty-request cleanup reserve after 180 auth checks',async t=>{
 const f=await wire(t);for(let i=0;i<180;i++){f.journal.reserveRequest('auth','earlier-'+i);f.journal.settleRequest('earlier-'+i,'accepted','historical-fixture.json');}
 const response=await f.sdk.admin.removeUser({userId:f.identity.id,fetchOptions:options});assert.equal(response.error,null);assert.equal(response.data.success,true);assert.equal(f.model.removes,1);assert.equal(f.journal.snapshot().requests.at(-1).purpose,'cleanup');
});
test('native SDK refuses a different identity before reserving or dispatching HTTP',async t=>{
 const f=await wire(t);for(const call of [()=>f.sdk.admin.listUsers({query:query('foreign-user'),fetchOptions:options}),()=>f.sdk.admin.removeUser({userId:'foreign-user',fetchOptions:options})]){await assert.rejects(call(),e=>e.status===403);}
 assert.equal(f.model.hits.length,0);assert.equal(f.journal.snapshot().requests.length,0);
});
test('fresh ownership, exact identity and native SDK absence complete only the owned identity cleanup',async t=>{
 const f=await wire(t),r=await run(f);assert.equal(r.complete,true);assert.equal(r.absent_identity,true);assert.equal(r.fixture_only,true);assert.equal(r.external_verified,false);assert.equal(f.model.removes,1);assert.equal(f.model.reads,2);assert.deepEqual(f.journal.snapshot().requests.map(v=>v.purpose),['reconcile','reconcile','cleanup','reconcile']);assert.ok(f.model.resources.get('auth').exists&&f.model.resources.get('project').exists);assert.equal(f.journal.snapshot().identity.id,f.identity.id);
});
for(const mode of ['read-500','generic-404','foreign-id','foreign-created','malformed'])test(mode+' read cannot authorize removal or claim absence',async t=>{
 const f=await wire(t,mode),r=await run(f);assert.equal(r.complete,false);assert.equal(r.absent_identity,false);assert.equal(f.model.removes,0);
});
for(const mode of ['lingering','bad-success','post-delete-malformed'])test(mode+' removal response cannot claim confirmed absence',async t=>{
 const f=await wire(t,mode),r=await run(f);assert.equal(r.complete,false);assert.equal(r.absent_identity,false);assert.equal(f.model.removes,1);
});
test('committed removal with lost response is not replayed; restart confirms exact absence through the SDK',async t=>{
 const f=await wire(t,'commit-lost'),first=await run(f);assert.equal(first.complete,false);assert.equal(f.model.removes,1);assert.equal(f.journal.snapshot().requests.at(-1).outcome,'unknown');
 const resumed=new RealRunJournal(f.root),execution=createFixtureExecutionBoundary({backend:f.backend,journal:resumed}),gateway=createFixtureExecutionGateway({execution,nonce});f.servers.push(gateway);await listen(gateway);
 const second=await run(f,{journal:resumed,execution,gateway});assert.equal(second.complete,true);assert.equal(second.absent_identity,true);assert.equal(f.model.removes,1);assert.equal(resumed.snapshot().requests.filter(r=>r.outcome==='unknown').length,1);
});
test('unknown removal still present after restart retains hold and never resends',async t=>{
 const f=await wire(t,'reject-500');assert.equal((await run(f)).complete,false);assert.equal(f.model.removes,1);
 const r=await run(f);assert.equal(r.complete,false);assert.equal(r.blocked,'held-remove');assert.equal(f.model.removes,1);
});
test('an expired target may consume cleanup/reconciliation reserve but cannot send new auth checks',async t=>{
 const f=await wire(t),late=Date.parse(f.target.expiresAt)+1;f.execution=createFixtureExecutionBoundary({backend:f.backend,journal:f.journal,now:()=>late});f.gateway=createFixtureExecutionGateway({execution:f.execution,nonce});f.servers.push(f.gateway);await listen(f.gateway);
 // Fresh readbacks are evaluated at real wall time; accounting alone uses the expired clock.
 assert.equal((await run(f)).complete,true);await assert.rejects(f.execution.dispatch({channel:'sdk',path:'/fixture/auth/token',method:'GET'}),/EXPIRED/);
});
test('admin authentication failure cannot be interpreted as an empty identity set',async t=>{
 const f=await wire(t),r=await run(f,{sessionCookie:'fictional-cleanup-admin=unprivileged'});assert.equal(r.complete,false);assert.equal(f.model.removes,0);
});
test('gateway, journal and owner must all be the same branded owned context',async t=>{
 const f=await wire(t),other=await wire(t);
 for(const extra of [{nonce:'w'.repeat(43)},{gateway:other.gateway},{journal:other.journal},{execution:{}},{sessionCookie:'real-session=not-allowed'}])await assert.rejects(run(f,extra),/N00_/);
 assert.equal(f.model.hits.length,0);assert.equal(other.model.hits.length,0);
});
test('changed project readback stops before native identity lookup',async t=>{
 const f=await wire(t);f.model.readbackPatch={projectId:'foreign-project'};await assert.rejects(run(f),/N00_/);assert.equal(f.model.reads,0);assert.equal(f.model.removes,0);
});
test('no email linking, role writes, impersonation, create-user or unrestricted query enters the boundary',async t=>{
 const f=await wire(t);
 for(const path of ['/fixture/auth/admin/create-user','/fixture/auth/admin/set-role','/fixture/auth/admin/list-users?searchValue=cleanup@fixture.invalid','/fixture/auth/admin/list-users?'+new URLSearchParams({...query(f.identity.id),offset:1}),'https://auth.neon.tech/auth/admin/list-users'])await assert.rejects(f.execution.dispatch({channel:'sdk',method:'GET',path}));
 assert.equal(f.model.hits.length,0);
});
test('durable receipts do not persist fixture session headers or identity payloads',async t=>{
 const f=await wire(t);assert.equal((await run(f)).complete,true);const receipts=readdirSync(f.root).filter(n=>n.startsWith('execution-http')).map(n=>readFileSync(join(f.root,n),'utf8')).join('\n');assert.doesNotMatch(receipts,/fictional-cleanup-admin|cleanup@fixture.invalid|"users"|"role"/);
});


test('accepted remove without absence remains held on another attempt',async t=>{
 const f=await wire(t,'lingering');assert.equal((await run(f)).blocked,'absence-unconfirmed');assert.equal((await run(f)).blocked,'held-remove');assert.equal(f.model.removes,1);
});
test('duplicate or extended query and body fields cannot broaden exact-id cleanup',async t=>{
 const f=await wire(t),base='/fixture/auth/admin/list-users?'+new URLSearchParams(query(f.identity.id));
 for(const path of [base+'&filterValue=other',base+'&searchValue=cleanup@fixture.invalid',base.replace('offset=0','offset=1')])await assert.rejects(f.execution.dispatch({channel:'sdk',method:'GET',path}),/IDENTITY_LOOKUP/);
 for(const body of ['{"userId":"fictional-execution-identity","role":"admin"}','{"userId":123}','not-json'])await assert.rejects(f.execution.dispatch({channel:'sdk',method:'POST',path:'/fixture/auth/admin/remove-user',body}),/OWNED_IDENTITY/);
 assert.equal(f.model.hits.length,0);assert.equal(f.journal.snapshot().requests.length,0);
});
test('cleanup also stops at the hard total of two hundred physical requests',async t=>{
 const f=await wire(t);for(let i=0;i<200;i++){const purpose=i<180?'auth':'reconcile';f.journal.reserveRequest(purpose,'earlier-'+i);f.journal.settleRequest('earlier-'+i,'accepted','historical-fixture.json');}
 await assert.rejects(run(f),/BUDGET/);assert.equal(f.model.hits.length,0);assert.equal(f.journal.snapshot().requests.length,200);
});
