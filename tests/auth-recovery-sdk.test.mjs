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
for (const [path,body] of [
 ['email-otp/verify-email',{email:'synthetic@example.test',otp:'123456'}],
 ['sign-up/email',{name:'Synthetic',email:'synthetic@example.test',password:'synthetic-password',callbackURL:origin+'/auth/sign-in?verified=1'}],
 ['request-password-reset',{email:'synthetic@example.test',redirectTo:origin+'/auth/reset-password'}],
 ['reset-password',{token:'synthetic-reset-token',newPassword:'synthetic-new-password'}],
 ['send-verification-email',{email:'synthetic@example.test',callbackURL:origin+'/auth/sign-in?verified=1'}],
]) test(`installed SDK forwards ${path} without changing the payload or origin boundary`,async()=>{
 let calls=0;
 transport=async(url,options)=>{calls++;assert.equal(String(url),authUrl+'/'+path);assert.equal(options.method,'POST');assert.deepEqual(JSON.parse(options.body),body);return Response.json({status:true});};
 const handlers=route();
 const request=source=>new Request(origin+'/api/auth/'+path,{method:'POST',headers:{origin:source,'content-type':'application/json'},body:JSON.stringify(body)});
 const result=await handlers.POST(request(origin),context(path));
 assert.equal(result.status,200);assert.equal(result.headers.get('cache-control'),'no-store');assert.equal(calls,1);
 const rejected=await handlers.POST(request('https://foreign.example.test'),context(path));
 assert.equal(rejected.status,403);assert.equal(calls,1);
});
