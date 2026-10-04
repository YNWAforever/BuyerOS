import assert from 'node:assert/strict';
import {test} from 'node:test';
import {spawnSync} from 'node:child_process';
import {realRuntimeEnvironment,realBuildEnvironment} from '../scripts/neon-real-preflight.mjs';
import {readRealRuntimeConfiguration,createRealAuthRuntime} from '../scripts/neon-real-runtime.mjs';
// Synthetic unit metadata only; no provider readback/authorization/account/network.
const start='2026-10-04T02:00:00.000Z',clock=Date.parse(start)+60_000,secret='fictional-runtime-secret-'.padEnd(43,'x');
function target(){return {schemaVersion:1,proposal:'buyeros-neon-auth-n00-20261004',sourceSha:'535e12bc49588eadb4e4ce0c75f748489868e084',projectId:'unit-runtime-12345678',branchId:'br-runtime-12345678',authId:'auth-runtime-12345678',orgId:'org-soft-sunset-25251479',name:'buyeros-neon-auth-n00-20261004',regionId:'aws-ap-southeast-1',creationMode:'new-empty',createdAt:start,expiresAt:'2026-10-04T04:00:00.000Z',readback:{projectId:'unit-runtime-12345678',branchId:'br-runtime-12345678',authId:'auth-runtime-12345678',orgId:'org-soft-sunset-25251479',name:'buyeros-neon-auth-n00-20261004',regionId:'aws-ap-southeast-1',observedAt:start,subscription:'free_v3',emailDeliveryEnabled:false,emailPasswordEnabled:false,emailHooksEnabled:false,methods:['google'],trustedOrigins:['http://localhost:44890']},auth:{baseUrl:'https://runtime.fixture.invalid/neondb/auth',issuer:'https://explicit-issuer.fixture.invalid',audience:'runtime-unit-audience',jwksUrl:'https://runtime.fixture.invalid/neondb/auth/jwks',algorithm:'EdDSA',keyType:'OKP',curve:'Ed25519'}};}
function environment(value=target()){return {...realRuntimeEnvironment({},value,secret,clock),N00_REAL_TARGET_JSON:JSON.stringify(value)};}
function boundary(options={}){let constructed=0,observed;const instance={fixtureOnly:true};const runtime=createRealAuthRuntime({readEnvironment:()=>environment(),now:()=>clock,createAuth:configuration=>{constructed++;observed=configuration;return instance;},...options});return {runtime,instance,count:()=>constructed,configuration:()=>observed};}

test('runtime env carries the validated complete manifest, and build env drops it with all trust/secrets',()=>{
 const value=target(),runtime=realRuntimeEnvironment({},value,secret,clock);assert.equal(typeof runtime.N00_REAL_TARGET_JSON,'string');assert.deepEqual(JSON.parse(runtime.N00_REAL_TARGET_JSON),value);
 const build=realBuildEnvironment(runtime);assert.equal(Object.keys(build).some(k=>k.startsWith('N00_')||k.startsWith('NEON_AUTH_')),false);
});
test('explicit issuer is kept independent from Auth base URL and actual SDK cookie options are returned',()=>{
 const result=readRealRuntimeConfiguration(environment(),clock);
 assert.deepEqual(result.sdk,{baseUrl:'https://runtime.fixture.invalid/neondb/auth',cookies:{secret,sameSite:'lax',sessionDataTtl:300}});
 assert.deepEqual(result.trust,{issuer:'https://explicit-issuer.fixture.invalid',audience:'runtime-unit-audience',jwksUrl:'https://runtime.fixture.invalid/neondb/auth/jwks',algorithm:'EdDSA',keyType:'OKP',curve:'Ed25519'});
 assert.equal(result.expiresAt,'2026-10-04T04:00:00.000Z');assert.match(result.fingerprint,/^[a-f0-9]{64}$/);
});
for(const key of ['N00_REAL_TARGET_JSON','N00_TARGET_FINGERPRINT','NEON_AUTH_BASE_URL','NEON_AUTH_COOKIE_SECRET','N00_AUTH_ISSUER','N00_AUTH_AUDIENCE','N00_AUTH_JWKS_URL','N00_AUTH_ALGORITHM'])test('runtime missing '+key+' refuses SDK construction without fallback',()=>{
 const env=environment();delete env[key];const b=boundary({readEnvironment:()=>env});assert.throws(()=>b.runtime.getAuth(),/N00_REAL_RUNTIME_REQUIRED/);assert.equal(b.count(),0);
});
for(const [key,value] of [['NEON_AUTH_BASE_URL','https://different.fixture.invalid/auth'],['N00_AUTH_ISSUER','https://different-issuer.fixture.invalid'],['N00_AUTH_AUDIENCE','different-audience'],['N00_AUTH_JWKS_URL','https://different.fixture.invalid/jwks'],['N00_AUTH_ALGORITHM','RS256'],['N00_TARGET_FINGERPRINT','0'.repeat(64)]])test('runtime drift '+key+' refuses initialization',()=>{
 const env=environment();env[key]=value;const b=boundary({readEnvironment:()=>env});assert.throws(()=>b.runtime.getAuth(),/N00_REAL_RUNTIME_MISMATCH/);assert.equal(b.count(),0);
});
test('malformed manifest error cannot echo secret or input data',()=>{
 const env=environment();env.N00_REAL_TARGET_JSON='{'+secret;assert.throws(()=>readRealRuntimeConfiguration(env,clock),{message:'N00_REAL_RUNTIME_MANIFEST'});
});
test('oversize manifest refuses parsing rather than consuming an unbounded runtime input',()=>{
 const env=environment();env.N00_REAL_TARGET_JSON=' '.repeat(16*1024+1);assert.throws(()=>readRealRuntimeConfiguration(env,clock),/N00_REAL_RUNTIME_MANIFEST/);
});
test('runtime reuses full target validation and rejects production IDs',()=>{
 const value=target();value.projectId='nameless-bar-15324691';value.readback.projectId=value.projectId;const env=environment();env.N00_REAL_TARGET_JSON=JSON.stringify(value);assert.throws(()=>readRealRuntimeConfiguration(env,clock),/N00_REAL_NEW_EMPTY_TARGET/);
});
test('module/runtime creation consumes no env or SDK initialization at build time',()=>{
 let reads=0;const b=boundary({readEnvironment:()=>{reads++;throw new Error('build must not read runtime env');}});assert.equal(reads,0);assert.equal(b.count(),0);
});
test('request initialization revalidates but caches one SDK instance for exact same context',()=>{
 const b=boundary();assert.equal(b.runtime.getAuth(),b.instance);assert.equal(b.runtime.getAuth(),b.instance);assert.equal(b.count(),1);assert.equal(b.configuration().cookies.secret,secret);
});
test('cached SDK cannot bypass the two-hour target expiry',()=>{
 let current=clock;const b=boundary({now:()=>current});b.runtime.getAuth();current=Date.parse('2026-10-04T04:00:00.000Z');assert.throws(()=>b.runtime.getAuth(),/N00_REAL_EXPIRED/);assert.equal(b.count(),1);
});
test('changed target cannot reuse or silently replace an already bound SDK context',()=>{
 let env=environment();const b=boundary({readEnvironment:()=>env});b.runtime.getAuth();const value=target();value.auth.audience='another-approved-unit-audience';env=environment(value);assert.throws(()=>b.runtime.getAuth(),/N00_REAL_RUNTIME_CONTEXT_CHANGED/);assert.equal(b.count(),1);
});
test('changed cookie secret requires a new owned runtime rather than silent context replacement',()=>{
 const env=environment();const b=boundary({readEnvironment:()=>env});b.runtime.getAuth();env.NEON_AUTH_COOKIE_SECRET='replacement-unit-secret-'.padEnd(43,'z');assert.throws(()=>b.runtime.getAuth(),/N00_REAL_RUNTIME_CONTEXT_CHANGED/);assert.equal(b.count(),1);
});
test('fresher matching readback does not change the bound target/SDK intent',()=>{
 let env=environment();const b=boundary({readEnvironment:()=>env});b.runtime.getAuth();const value=target();value.readback.observedAt='2026-10-04T02:00:30.000Z';env=environment(value);assert.equal(b.runtime.getAuth(),b.instance);assert.equal(b.count(),1);
});
test('SDK constructor errors are redacted and cannot disclose runtime cookie secret',()=>{
 const b=boundary({createAuth:()=>{throw new Error(secret);}});assert.throws(()=>b.runtime.getAuth(),{message:'N00_REAL_RUNTIME_SDK_INIT'});
});
test('runtime description contains only target/trust context and no cookie secret',()=>{
 const b=boundary(),description=b.runtime.describe();assert.equal(b.count(),0);assert.equal(description.projectId,'unit-runtime-12345678');assert.equal(description.authId,'auth-runtime-12345678');assert.equal(description.expiresAt,'2026-10-04T04:00:00.000Z');assert.equal(description.external_verified,false);assert.doesNotMatch(JSON.stringify(description),/fictional-runtime-secret|cookies|NEON_AUTH_COOKIE_SECRET/);
});
test('returned runtime config cannot be mutated to change the validated SDK/trust tuple',()=>{
 const c=readRealRuntimeConfiguration(environment(),clock);assert.throws(()=>{c.sdk.baseUrl='https://other.fixture.invalid';},TypeError);assert.throws(()=>{c.sdk.cookies.secret='changed';},TypeError);assert.throws(()=>{c.trust.algorithm='HS256';},TypeError);
});
test('separate build-environment Node process imports the runtime module without secret/init',()=>{
 const code="import {createRealAuthRuntime} from './scripts/neon-real-runtime.mjs';let initialized=0;const runtime=createRealAuthRuntime({readEnvironment:()=>process.env,createAuth:()=>{initialized++;return {};}});let error;try{runtime.getAuth();}catch(e){error=e.message;}console.log(JSON.stringify({initialized,error}));";
 const env=realBuildEnvironment({...process.env,...environment()});const result=spawnSync(process.execPath,['--input-type=module','-e',code],{env,encoding:'utf8',timeout:5000});assert.equal(result.status,0,result.stderr);assert.deepEqual(JSON.parse(result.stdout),{initialized:0,error:'N00_REAL_RUNTIME_REQUIRED'});assert.doesNotMatch(result.stdout+result.stderr,new RegExp(secret));
});

test('runtime consumer independently refuses an invalid cookie secret',()=>{const env=environment();env.NEON_AUTH_COOKIE_SECRET='too-short';assert.throws(()=>readRealRuntimeConfiguration(env,clock),/N00_REAL_COOKIE_SECRET/);});
