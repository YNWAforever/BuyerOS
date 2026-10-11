// Unpatched public SDK transport with a process-wide deny-by-default mock.
// Synthetic protocol inputs only; no real Neon account/session acceptance.
import {registerHooks} from 'node:module';
import test from 'node:test';
import assert from 'node:assert/strict';
// Node ESM needs explicit extensions for the same unmodified Next.js files
// that production bundlers resolve through their framework module aliases.
registerHooks({resolve(specifier,context,next){
 if(specifier==='./neon-config'&&context.parentURL?.endsWith('/lib/auth/neon-boundary.ts'))return next(new URL('./neon-config.ts',context.parentURL).href,context);
 if(specifier==='next/headers'||specifier==='next/server')return next(specifier+'.js',context);
 return next(specifier,context);
}});
const origin='https://c61-sdk.example.test',authUrl='https://ep-c61-sdk.neonauth.us-east-2.aws.neon.tech/neondb/auth';
const cookieSecret='C61_ONLY_OFFLINE_SDK_COOKIE_CANARY_'.repeat(2);
const environment=()=>({NODE_ENV:'production',VERCEL_ENV:'preview',BUYEROS_NEON_ENVIRONMENT:'preview',BUYEROS_NEON_AUTH_ROUTE_ENABLED:'1',BUYEROS_NEON_AUTH_URL:authUrl,BUYEROS_NEON_EXPECTED_AUTH_URL:authUrl,BUYEROS_PUBLIC_ORIGIN:origin,BUYEROS_NEON_EXPECTED_PUBLIC_ORIGIN:origin,BUYEROS_NEON_COOKIE_SECRET:cookieSecret});
let transport=async()=>{throw Error('Offline SDK test refuses every unconfigured fetch');};
globalThis.fetch=(...args)=>transport(...args); // Never restored: dedicated test process cannot use real network.
const {createNeonAuth}=await import('@neondatabase/auth/next/server');
const {neonAuthHandlers}=await import('../lib/auth/neon-boundary.ts');
const route=()=>neonAuthHandlers(environment,config=>createNeonAuth(config).handler());
const context=path=>({params:Promise.resolve({path:path.split('/')})});
const sessionData={session:{id:'offline-session',token:'offline-opaque-session',userId:'offline-user',expiresAt:'2030-01-01T00:00:00.000Z',createdAt:'2026-10-01T00:00:00.000Z',updatedAt:'2026-10-01T00:00:00.000Z',ipAddress:null,userAgent:null},user:{id:'offline-user',name:'Synthetic SDK user',email:'synthetic@example.test',emailVerified:true,image:null,createdAt:'2026-10-01T00:00:00.000Z',updatedAt:'2026-10-01T00:00:00.000Z'}};

test('C61-08 public SDK creates protected host session cookies and uses the actual signed cache',async()=>{
 let calls=0;
 transport=async(url,options)=>{assert.equal(String(url),authUrl+'/get-session');assert.equal(options.method??'GET','GET');calls++;const headers=new Headers({'content-type':'application/json'});if(calls===1)headers.append('set-cookie','__Secure-neon-auth.session_token=offline-opaque-session; Path=/; HttpOnly; Secure; SameSite=Lax');else assert.equal(options.headers.Cookie,'__Secure-neon-auth.session_token=offline-opaque-session');return new Response(JSON.stringify(sessionData),{status:200,headers});};
 const handlers=route(),first=await handlers.GET(new Request(origin+'/api/auth/get-session'),context('get-session'));
 assert.equal(first.status,200);assert.equal(first.headers.get('cache-control'),'no-store');assert.equal((await first.clone().json()).user.id,sessionData.user.id);
 const cookies=first.headers.getSetCookie();assert.ok(cookies.length>=2);
 for(const cookie of cookies){assert.match(cookie,/HttpOnly/i);assert.match(cookie,/SameSite=Lax/i);assert.match(cookie,/Path=\//i);assert.match(cookie,/Secure/i);assert.doesNotMatch(cookie,/Domain=/i);assert.ok(!cookie.includes(cookieSecret));}
 const header=cookies.map(value=>value.split(';')[0]).join('; ');
 const cached=await handlers.GET(new Request(origin+'/api/auth/get-session',{headers:{cookie:header}}),context('get-session'));
 assert.equal(cached.status,200);assert.equal((await cached.json()).user.id,sessionData.user.id);assert.equal(calls,2);
});

test('C61-08 public SDK preserves the OAuth redirect URL and cookies through the route wrapper',async()=>{
 let calls=0;
 transport=async(url,options)=>{assert.equal(String(url),authUrl+'/sign-in/social');assert.equal(options.method,'POST');assert.equal(JSON.parse(options.body).provider,'google');calls++;const headers=new Headers({'content-type':'application/json'});headers.append('set-cookie','__Secure-neon-auth.session_challenge=offline-social-challenge; Path=/; HttpOnly; Secure; SameSite=Lax');return new Response(JSON.stringify({redirect:true,url:'https://accounts.google.com/o/oauth2/v2/auth?state=offline'}),{status:200,headers});};
 const result=await route().POST(new Request(origin+'/api/auth/sign-in/social',{method:'POST',headers:{origin,'content-type':'application/json'},body:JSON.stringify({provider:'google',callbackURL:origin+'/app'})}),context('sign-in/social'));
 assert.equal(result.status,200);assert.deepEqual(await result.json(),{redirect:true,url:'https://accounts.google.com/o/oauth2/v2/auth?state=offline'});assert.ok(result.headers.getSetCookie().length>0);assert.equal(result.headers.get('cache-control'),'no-store');assert.equal(calls,1);
});

test('C61-08 public SDK provider 503 remains an unavailable response with no fictional session',async()=>{
 let calls=0;
 transport=async(url)=>{assert.equal(String(url),authUrl+'/get-session');calls++;return Response.json({code:'OFFLINE_PROVIDER_UNAVAILABLE'},{status:503});};
 const result=await route().GET(new Request(origin+'/api/auth/get-session'),context('get-session'));
 assert.equal(result.status,503);assert.equal(result.headers.get('cache-control'),'no-store');assert.equal(result.headers.getSetCookie().length,0);assert.equal(calls,1);assert.doesNotMatch(await result.text(),/offline-user|CANARY/);
});
