import assert from 'node:assert/strict';
import {test} from 'node:test';
import {mkdtempSync,readFileSync,writeFileSync,mkdirSync,rmSync,rmdirSync,realpathSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve,relative} from 'node:path';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {validateRealTarget,realRuntimeEnvironment,realBuildEnvironment,RealRunJournal,cleanupTargets} from '../scripts/neon-real-preflight.mjs';
const start='2026-10-04T02:00:00.000Z',now=Date.parse(start)+60_000;
const approval='fixture-only-authorization-reference';
function target() {return {
 schemaVersion:1,proposal:'buyeros-neon-auth-n00-20261004',sourceSha:'d48cba24ce6f2afc8b792ba1f65e5b93239902cc',
 projectId:'isolated-auth-12345678',branchId:'br-isolated-12345678',authId:'auth-isolated-12345678',
 orgId:'org-soft-sunset-25251479',name:'buyeros-neon-auth-n00-20261004',regionId:'aws-ap-southeast-1',
 creationMode:'new-empty',createdAt:start,expiresAt:'2026-10-04T04:00:00.000Z',
 readback:{projectId:'isolated-auth-12345678',branchId:'br-isolated-12345678',authId:'auth-isolated-12345678',orgId:'org-soft-sunset-25251479',name:'buyeros-neon-auth-n00-20261004',regionId:'aws-ap-southeast-1',observedAt:start,subscription:'free_v3',emailDeliveryEnabled:false,emailPasswordEnabled:false,emailHooksEnabled:false,methods:['google'],trustedOrigins:['http://localhost:44890']},
 auth:{baseUrl:'https://n00-auth.fixture.invalid/neondb/auth',issuer:'https://n00-auth.fixture.invalid',audience:'explicit-n00-audience',jwksUrl:'https://n00-auth.fixture.invalid/neondb/auth/.well-known/jwks.json',algorithm:'EdDSA',keyType:'OKP',curve:'Ed25519'}
};}
function scratch(t) {const root=mkdtempSync(join(tmpdir(),'buyeros-n00-real-'));t.after(()=>{assert.equal(realpathSync(root),resolve(root));assert.ok(relative(resolve(tmpdir()),root).startsWith('buyeros-n00-real-'));rmSync(root,{recursive:true,force:true});});return root;}
function journal(t) {const root=scratch(t);return {root,run:RealRunJournal.create(root,{approvalReference:approval,approvedAt:'2026-10-04T01:59:00.000Z'})};}
function bound(t) {const pair=journal(t);pair.run.bindTarget(target(),now);return pair;}

test('real target requires observed exact identifiers and explicit Ed25519 trust',()=>{
 const value=validateRealTarget(target(),now);assert.equal(value.projectId,target().projectId);
 assert.match(value.fingerprint,/^[a-f0-9]{64}$/);assert.equal(value.auth.audience,'explicit-n00-audience');
});
test('template has null target and trust values and check denies it without a network call',()=>{
 const result=spawnSync(process.execPath,['scripts/neon-real-preflight.mjs','check','docs/buyeros/runbooks/neon-auth-n00-real-target.template.json'],{encoding:'utf8'});
 assert.equal(result.status,1);assert.match(result.stderr,/N00_REAL_TARGET_REQUIRED/);assert.equal(result.stdout,'');
 const blank=JSON.parse(readFileSync('docs/buyeros/runbooks/neon-auth-n00-real-target.template.json','utf8'));
 for(const key of ['projectId','branchId','authId'])assert.equal(blank[key],null);
 for(const key of ['baseUrl','issuer','audience','jwksUrl'])assert.equal(blank.auth[key],null);
});
for(const [label,mutate] of [
 ['production project',v=>{v.projectId='nameless-bar-15324691';v.readback.projectId=v.projectId;}],
 ['existing Cloudflare preview',v=>{v.projectId='rapid-night-21766635';v.readback.projectId=v.projectId;}],
 ['different owner',v=>{v.orgId='org-unapproved';v.readback.orgId=v.orgId;}],
 ['cloned data',v=>{v.creationMode='cloned';}],
 ['unmatched branch readback',v=>{v.readback.branchId='br-different';}],
 ['missing audience',v=>{v.auth.audience=null;}],
 ['Auth0 RSA algorithm',v=>{v.auth.algorithm='RS256';}],
 ['wrong key curve',v=>{v.auth.curve='Ed448';}],
 ['email enabled',v=>{v.readback.emailDeliveryEnabled=true;}],
 ['email registration',v=>{v.readback.emailPasswordEnabled=true;}],
 ['email hook',v=>{v.readback.emailHooksEnabled=true;}],
 ['paid plan',v=>{v.readback.subscription='scale';}],
 ['wildcard trusted domain',v=>{v.readback.trustedOrigins.push('https://*.vercel.app');}],
 ['unknown config or DSN',v=>{v.DATABASE_URL='postgresql://fictional.invalid/forbidden';}],
 ['credential URL',v=>{v.auth.baseUrl='https://user:password@n00-auth.fixture.invalid/auth';}],
 ['loopback masquerading as real',v=>{v.auth.baseUrl='http://127.0.0.1:44891/fixture/auth';}],
 ['unreviewed JWKS host',v=>{v.auth.jwksUrl='https://unreviewed.fixture.invalid/jwks';}],
 ['extended expiry',v=>{v.expiresAt='2026-10-04T05:00:00.000Z';}],
 ['future creation',v=>{v.createdAt='2026-10-05T02:00:00.000Z';}],
])test('real preflight denies '+label,()=>{const value=target();mutate(value);assert.throws(()=>validateRealTarget(value,now));});

test('expiry blocks new runtime configuration while exact cleanup remains available',t=>{
 const {run}=bound(t),expired=Date.parse(target().expiresAt)+1;
 assert.throws(()=>realRuntimeEnvironment({},target(),'r'.repeat(43),expired),/EXPIRED/);
 assert.throws(()=>run.reserveRequest('auth','after-expiry',expired),/EXPIRED/);
 const readback={...target().readback,observedAt:new Date(expired).toISOString()};
 assert.deepEqual(cleanupTargets(run.snapshot(),readback,expired).map(v=>v.kind),['auth','project']);
 assert.equal(run.reserveRequest('cleanup','cleanup-expired',expired).sequence,1);
});
test('runtime secrets and explicit trust never enter build env or inherit DB/provider config',()=>{
 const parent={PATH:'fictional-path',DATABASE_URL:'forbidden',NEON_AUTH_COOKIE_SECRET:'inherited-forbidden',BUYEROS_AUTH0_ISSUER:'forbidden',OPENAI_API_KEY:'forbidden'};
 const runtime=realRuntimeEnvironment(parent,target(),'s'.repeat(43),now),build=realBuildEnvironment({...parent,...runtime});
 assert.equal(runtime.NEON_AUTH_BASE_URL,target().auth.baseUrl);assert.equal(runtime.NEON_AUTH_COOKIE_SECRET,'s'.repeat(43));assert.equal(runtime.N00_AUTH_ISSUER,target().auth.issuer);assert.equal(runtime.N00_AUTH_AUDIENCE,target().auth.audience);assert.equal(runtime.N00_AUTH_JWKS_URL,target().auth.jwksUrl);
 for(const key of ['DATABASE_URL','BUYEROS_AUTH0_ISSUER','OPENAI_API_KEY'])assert.equal(key in runtime,false);
 for(const key of ['NEON_AUTH_BASE_URL','NEON_AUTH_COOKIE_SECRET','N00_AUTH_ISSUER','N00_AUTH_AUDIENCE','N00_AUTH_JWKS_URL'])assert.equal(key in build,false);
 assert.equal(build.PATH,'fictional-path');assert.throws(()=>realRuntimeEnvironment(parent,target(),'too-short',now));
});
test('journal cannot be created without an explicit authorization reference or overwrite an earlier run',t=>{
 const root=scratch(t);assert.throws(()=>RealRunJournal.create(root,{approvedAt:start}),/AUTHORIZATION/);
 RealRunJournal.create(root,{approvalReference:approval,approvedAt:start});assert.throws(()=>RealRunJournal.create(root,{approvalReference:approval,approvedAt:start}));
});
test('setup before target creation and failed requests consume the same persistent budget',t=>{
 const {root,run}=journal(t);run.reserveRequest('setup','read-quota',now-120_000);run.settleRequest('read-quota','unknown','fixture-readback.json');
 const restarted=new RealRunJournal(root);restarted.bindTarget(target(),now);
 assert.equal(restarted.reserveRequest('auth','login',now).sequence,2);
 assert.equal(run.snapshot().requests.length,2);assert.throws(()=>restarted.reserveRequest('auth','login',now),/RECONCILE/);
 assert.throws(()=>restarted.reserveRequest('setup','read-quota',now),/RECONCILE/);
 assert.equal(restarted.reserveRequest('reconcile','read-quota-result',now).sequence,3);
});
test('lost response is reserved before execution, survives restart and cannot be blindly retried',t=>{
 const {root,run}=bound(t);run.reserveRequest('auth','commit-login',now);
 const recovered=new RealRunJournal(root);assert.equal(recovered.snapshot().requests[0].outcome,'pending');
 assert.throws(()=>recovered.reserveRequest('auth','commit-login',now),/RECONCILE/);
 recovered.settleRequest('commit-login','unknown','fixture-transport-error.json');
 assert.equal(recovered.snapshot().requests.length,1);assert.throws(()=>recovered.reserveRequest('auth','commit-login',now),/RECONCILE/);
});
test('180 probes reserve 20 cleanup/reconcile checks and hard cap is 200 including errors',t=>{
 const {root,run}=bound(t);for(let i=0;i<180;i++)run.reserveRequest('auth','probe-'+i,now);
 assert.throws(()=>run.reserveRequest('auth','probe-over-limit',now),/BUDGET/);
 const restarted=new RealRunJournal(root);for(let i=0;i<20;i++)restarted.reserveRequest(i%2?'cleanup':'reconcile','cleanup-'+i,now);
 assert.equal(run.snapshot().requests.length,200);assert.throws(()=>run.reserveRequest('cleanup','cleanup-over-limit',now),/BUDGET/);
});
test('target binding is immutable across process restarts and IDs cannot be repointed',t=>{
 const {root,run}=bound(t);new RealRunJournal(root).bindTarget(target(),now);
 const changed=target();changed.projectId='isolated-other-12345678';changed.readback.projectId=changed.projectId;
 assert.throws(()=>run.bindTarget(changed,now),/BOUND_TARGET/);assert.equal(run.snapshot().target.projectId,target().projectId);
});
test('two build reservations are bounded to 20 minutes and remain consumed on restart',t=>{
 const {root,run}=bound(t);const first=run.reserveBuild('portable',now);assert.equal(Date.parse(first.deadline)-now,20*60_000);
 new RealRunJournal(root).reserveBuild('vercel',now);assert.throws(()=>run.reserveBuild('portable',now),/BUILD_BUDGET/);
});
test('cleanup needs fresh matching readback and may select only one bound test identity',t=>{
 const {run}=bound(t);run.bindIdentity({id:'test-user-1234',authId:target().authId,projectId:target().projectId,createdAt:new Date(now).toISOString()},now);
 const fresh={...target().readback,observedAt:new Date(now).toISOString()};const actions=cleanupTargets(run.snapshot(),fresh,now);
 assert.deepEqual(actions.map(v=>[v.kind,v.id]),[['identity','test-user-1234'],['auth',target().authId],['project',target().projectId]]);
 assert.throws(()=>cleanupTargets(run.snapshot(),{...fresh,projectId:'nameless-bar-15324691'},now));
 assert.throws(()=>cleanupTargets(run.snapshot(),fresh,now+5*60_000+1),/READBACK/);
 assert.throws(()=>run.bindIdentity({id:'second-user',authId:target().authId,projectId:target().projectId,createdAt:start},now));
});
test('unknown outcomes and suspicious operation metadata do not leak bearer, query or credential data to journal',t=>{
 const {root,run}=bound(t);assert.throws(()=>run.reserveRequest('auth','https://host/?token=secret',now));
 assert.throws(()=>run.reserveRequest('auth','Bearer secret',now));run.reserveRequest('auth','safe-id',now);
 assert.throws(()=>run.settleRequest('safe-id','accepted','https://host/?token=secret'));
 const bytes=readFileSync(join(root,'journal.json'),'utf8');assert.doesNotMatch(bytes,/Bearer|password|token=|COOKIE_SECRET/);
});
test('a concurrent writer or corrupt journal fails closed without resetting counters',t=>{
 const {root,run}=bound(t);run.reserveRequest('auth','before-lock',now);mkdirSync(join(root,'journal.lock'));
 assert.throws(()=>run.reserveRequest('auth','during-lock',now),/BUSY/);assert.equal(run.snapshot().requests.length,1);
 rmdirSync(join(root,'journal.lock'));writeFileSync(join(root,'journal.json'),'{broken');assert.throws(()=>new RealRunJournal(root).snapshot());
});
test('ledger tampering with limits or target fingerprint fails before cleanup or a new reservation',t=>{
 const {root,run}=bound(t);const path=join(root,'journal.json'),original=readFileSync(path,'utf8'),data=JSON.parse(original);
 data.limit=201;writeFileSync(path,JSON.stringify(data));assert.throws(()=>run.reserveRequest('auth','tamper-limit',now));
 writeFileSync(path,original);const changed=JSON.parse(original);changed.target.projectId='nameless-bar-15324691';writeFileSync(path,JSON.stringify(changed));assert.throws(()=>cleanupTargets(run.snapshot(),target().readback,now));
 assert.equal(createHash('sha256').update(readFileSync(path)).digest('hex').length,64);
});

test('persisted settled results need evidence and probe reservations cannot exceed the original expiry',t=>{
 const {root,run}=bound(t),path=join(root,'journal.json');run.reserveRequest('auth','probe',now);const original=readFileSync(path,'utf8');
 const settled=JSON.parse(original);settled.requests[0].outcome='accepted';writeFileSync(path,JSON.stringify(settled));assert.throws(()=>run.snapshot(),/JOURNAL_REQUEST/);
 const expired=JSON.parse(original);expired.requests[0].reservedAt=target().expiresAt;writeFileSync(path,JSON.stringify(expired));assert.throws(()=>run.snapshot(),/EXPIRED/);
});
test('build deadline cannot exceed resource TTL and persisted build sequence cannot be forged',t=>{
 const {root,run}=bound(t),path=join(root,'journal.json');const late=Date.parse(target().expiresAt)-60_000;
 assert.equal(run.reserveBuild('portable',late).deadline,target().expiresAt);const original=readFileSync(path,'utf8');
 const forged=JSON.parse(original);forged.builds[0].sequence=2;writeFileSync(path,JSON.stringify(forged));assert.throws(()=>run.snapshot(),/BUILD_SCOPE/);
 const extended=JSON.parse(original);extended.builds[0].deadline='2026-10-04T04:01:00.000Z';writeFileSync(path,JSON.stringify(extended));assert.throws(()=>run.snapshot(),/BUILD_TIMEOUT/);
});

test('an actual terminated Node process leaves its reservation consumed and the next process sees it',t=>{
 const {root,run}=bound(t);
 const script="import {RealRunJournal} from './scripts/neon-real-preflight.mjs';const run=new RealRunJournal(process.argv[1]);run.reserveRequest('auth','terminated-response',Date.parse('2026-10-04T02:01:00.000Z'));process.exit(17);";
 const stopped=spawnSync(process.execPath,['--input-type=module','-e',script,root],{encoding:'utf8'});assert.equal(stopped.status,17);assert.equal(stopped.stderr,'');
 const recover="import {RealRunJournal} from './scripts/neon-real-preflight.mjs';const run=new RealRunJournal(process.argv[1]);try{run.reserveRequest('auth','terminated-response',Date.parse('2026-10-04T02:01:00.000Z'));process.exitCode=99;}catch(error){if(error.message!=='N00_REAL_RECONCILE_BEFORE_RETRY')throw error;}console.log(run.snapshot().requests.length);";
 const resumed=spawnSync(process.execPath,['--input-type=module','-e',recover,root],{encoding:'utf8'});assert.equal(resumed.status,0);assert.equal(resumed.stdout.trim(),'1');assert.equal(run.snapshot().requests[0].outcome,'pending');
});
