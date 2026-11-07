import {registerHooks} from 'node:module';
registerHooks({resolve(specifier,context,next){if(specifier==='./neon-config'&&context.parentURL?.endsWith('/lib/auth/neon-boundary.ts'))return next(new URL('./neon-config.ts',context.parentURL).href,context);return next(specifier,context);}});
import test from 'node:test';import assert from 'node:assert/strict';
const origin='https://c61-preview.example.test',authUrl='https://ep-c61-preview.neonauth.us-east-2.aws.neon.tech/neondb/auth';
const env=()=>({NODE_ENV:'production',VERCEL_ENV:'preview',BUYEROS_NEON_ENVIRONMENT:'preview',BUYEROS_NEON_AUTH_ROUTE_ENABLED:'1',BUYEROS_NEON_AUTH_URL:authUrl,BUYEROS_NEON_EXPECTED_AUTH_URL:authUrl,BUYEROS_PUBLIC_ORIGIN:origin,BUYEROS_NEON_EXPECTED_PUBLIC_ORIGIN:origin,BUYEROS_NEON_COOKIE_SECRET:'C61_ONLY_SYNTHETIC_COOKIE_CANARY_'.repeat(2)});
const context={params:Promise.resolve({path:['sign-in','email']})};
const load=async()=> (await import('../lib/auth/neon-boundary.ts')).neonAuthHandlers;
const stagedOrigin='https://buyeros-candidate123-owned.vercel.app';
const stagedEnv=()=>({...env(),VERCEL_ENV:'production',BUYEROS_NEON_ENVIRONMENT:'production',
 BUYEROS_NEON_STAGED_ORIGIN_ENABLED:'1',BUYEROS_RUNTIME_SOURCE_SHA:'a'.repeat(40),VERCEL_URL:new URL(stagedOrigin).hostname});

test('protected staged auth accepts only exact deployment and canonical same-origin requests',async()=>{
 let calls=0;const handler=async()=>{calls++;return new Response('owned synthetic SDK');};
 const route=(await load())(stagedEnv,()=>({GET:handler,POST:handler}));
 for(const target of [origin,stagedOrigin]){
  assert.equal((await route.GET(new Request(target+'/api/auth/get-session'),context)).status,200);
  assert.equal((await route.POST(new Request(target+'/api/auth/sign-in/email',{method:'POST',headers:{origin:target}}),context)).status,200);
 }
 assert.equal(calls,4);
});

test('protected staged auth rejects spoofed hosts, sibling deployments and cross-origin requests before SDK',async()=>{
 let initialized=0;const route=(await load())(stagedEnv,()=>{initialized++;throw Error('must not initialize');});
 for(const request of [
  new Request('https://evil.example/api/auth/get-session',{headers:{host:new URL(stagedOrigin).host,'x-forwarded-host':new URL(stagedOrigin).host}}),
  new Request('https://buyeros-other-owned.vercel.app/api/auth/get-session'),
  new Request(stagedOrigin+'/api/auth/get-session',{headers:{origin}}),
  new Request(origin+'/api/auth/get-session',{headers:{origin:stagedOrigin}}),
  new Request(stagedOrigin+'/api/auth/sign-in/email',{method:'POST',headers:{origin}}),
  new Request(origin+'/api/auth/sign-in/email',{method:'POST',headers:{origin:stagedOrigin}}),
  new Request(stagedOrigin+'/api/auth/sign-in/email',{method:'POST'}),
  new Request(stagedOrigin+'/api/auth/get-session',{headers:{origin:'null'}}),
 ])assert.equal((await route[request.method](request,context)).status,403);
 assert.equal(initialized,0);
});

for(const [fault,change] of Object.entries({
 missing_flag:{BUYEROS_NEON_STAGED_ORIGIN_ENABLED:undefined},disabled:{BUYEROS_NEON_STAGED_ORIGIN_ENABLED:'0'},
 invalid_flag:{BUYEROS_NEON_STAGED_ORIGIN_ENABLED:'true'},missing_source:{BUYEROS_RUNTIME_SOURCE_SHA:undefined},
 invalid_source:{BUYEROS_RUNTIME_SOURCE_SHA:'g'.repeat(40)},short_source:{BUYEROS_RUNTIME_SOURCE_SHA:'abc123'},
 development:{NODE_ENV:'development'},preview:{VERCEL_ENV:'preview'},missing_platform:{VERCEL_ENV:undefined},
 wrong_neon_environment:{BUYEROS_NEON_ENVIRONMENT:'preview'},missing_hostname:{VERCEL_URL:undefined},
 url_instead_of_hostname:{VERCEL_URL:stagedOrigin},hostname_port:{VERCEL_URL:'owned.vercel.app:443'},
 hostname_path:{VERCEL_URL:'owned.vercel.app/path'},hostname_suffix:{VERCEL_URL:'owned.vercel.app.evil.test'},
 nested_hostname:{VERCEL_URL:'extra.owned.vercel.app'},hostname_credentials:{VERCEL_URL:'user@owned.vercel.app'},
 invalid_label:{VERCEL_URL:'-owned.vercel.app'},oversized_label:{VERCEL_URL:'a'.repeat(64)+'.vercel.app'},
}))test(`protected staged auth refuses ${fault} without SDK access`,async()=>{
 let initialized=0;const route=(await load())(()=>({...stagedEnv(),...change}),()=>{initialized++;throw Error('must not initialize');});
 const result=await route.GET(new Request(stagedOrigin+'/api/auth/get-session'),context);
 assert.equal(result.status,['missing_flag','disabled'].includes(fault)?403:503);assert.equal(initialized,0);
});
test('C61-08 disabled auth route does not initialize SDK or replace Auth0',async()=>{let initialized=0;const route=(await load())(()=>({...env(),BUYEROS_NEON_AUTH_ROUTE_ENABLED:'0'}),()=>{initialized++;throw Error('must not initialize');});const r=await route.GET(new Request(origin+'/api/auth/get-session'),context);assert.equal(r.status,503);assert.equal(initialized,0);assert.equal(r.headers.get('cache-control'),'no-store');});
test('C61-08 incomplete config fails closed without provider call or secret details',async()=>{let initialized=0;const value=env();delete value.BUYEROS_NEON_EXPECTED_AUTH_URL;const route=(await load())(()=>value,()=>{initialized++;throw Error('must not initialize');});const r=await route.GET(new Request(origin+'/api/auth/get-session'),context);assert.equal(r.status,503);assert.equal(initialized,0);assert.doesNotMatch(await r.text(),/CANARY|neon.tech/);});
test('C61-08 exact POST delegates to public SDK with Lax host cookies and preserves redirect cookies',async()=>{let observed;const route=(await load())(env,config=>{observed=config;return {GET:async()=>new Response('unused'),POST:async request=>{assert.equal(request.headers.get('cookie'),'auth-session=synthetic');const headers=new Headers({location:origin+'/app'});headers.append('set-cookie','one=synthetic; HttpOnly; SameSite=Lax; Path=/');headers.append('set-cookie','two=synthetic; HttpOnly; SameSite=Lax; Path=/');return new Response(null,{status:302,headers});}};});const r=await route.POST(new Request(origin+'/api/auth/sign-in/email',{method:'POST',headers:{origin,cookie:'auth-session=synthetic'},body:'{}'}),context);assert.equal(r.status,302);assert.equal(r.headers.get('location'),origin+'/app');assert.equal(r.headers.getSetCookie().length,2);assert.equal(r.headers.get('cache-control'),'no-store');assert.deepEqual(observed,{baseUrl:authUrl,cookies:{secret:env().BUYEROS_NEON_COOKIE_SECRET,sameSite:'lax',sessionDataTtl:300},logLevel:'silent'});});
test('C61-08 foreign origin, absent POST origin and wrong request host never call SDK',async()=>{let called=0;const route=(await load())(env,()=>{called++;throw Error('must not initialize');});for(const request of [new Request(origin+'/api/auth/sign-in/email',{method:'POST'}),new Request(origin+'/api/auth/sign-in/email',{method:'POST',headers:{origin:'https://foreign.example.test'}}),new Request('https://foreign.example.test/api/auth/get-session'),new Request(origin+'/api/auth/get-session',{headers:{origin:'null'}})]){const r=await route[request.method](request,context);assert.equal(r.status,403);}assert.equal(called,0);});
test('C61-08 auth wrapper cannot relay business API cookies',async()=>{let called=0;const route=(await load())(env,()=>{called++;throw Error('must not initialize');});const r=await route.GET(new Request(origin+'/v1/workspaces',{headers:{cookie:'auth-session=synthetic'}}),context);assert.equal(r.status,404);assert.equal(called,0);});
test('C61-08 SDK failure remains 503 and configuration change rebuilds only its own server instance',async()=>{let count=0,value=env();const route=(await load())(()=>value,()=>{count++;return {GET:async()=>{throw Error('CANARY private provider diagnostics');},POST:async()=>new Response('unused')};});for(let i=0;i<2;i++){const r=await route.GET(new Request(origin+'/api/auth/get-session'),context);assert.equal(r.status,503);assert.doesNotMatch(await r.text(),/CANARY/);}assert.equal(count,1);value={...value,BUYEROS_NEON_COOKIE_SECRET:'C61_OTHER_SYNTHETIC_SECRET_'.repeat(2)};await route.GET(new Request(origin+'/api/auth/get-session'),context);assert.equal(count,2);});
