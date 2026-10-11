// Actual local Vercel deployment output, without any auth account or provider.
import test from 'node:test';
import assert from 'node:assert/strict';
for(const key of Object.keys(process.env))if(key.startsWith('BUYEROS_NEON_'))delete process.env[key];
let calls=0;
globalThis.fetch=async()=>{calls++;throw Error('Built auth gate test forbids network');};
const {default:built}=await import('../.vercel/output/functions/__server.func/index.mjs');
const origin='https://c61-built.example.test';
const request=(method='GET',headers={})=>built.fetch(new Request(origin+'/api/auth/get-session',{method,headers}));
test('C61-08 actual built auth route defaults closed without cookies or a provider request',async()=>{
 for(const method of ['GET','POST']){const response=await request(method);assert.equal(response.status,503);assert.equal(response.headers.get('cache-control'),'no-store');assert.equal(response.headers.getSetCookie().length,0);assert.deepEqual(await response.json(),{code:'AUTH_UNAVAILABLE'});}
 assert.equal(calls,0);
});
test('C61-08 actual built enabled route refuses incomplete deployment config',async()=>{
 process.env.BUYEROS_NEON_AUTH_ROUTE_ENABLED='1';
 const response=await request();assert.equal(response.status,503);assert.equal(calls,0);assert.deepEqual(await response.json(),{code:'AUTH_UNAVAILABLE'});
});
test('C61-08 actual built route rejects foreign origin before provider access',async()=>{
 const url='https://ep-c61-built.neonauth.us-east-2.aws.neon.tech/neondb/auth';
 Object.assign(process.env,{NODE_ENV:'production',VERCEL_ENV:'preview',BUYEROS_NEON_ENVIRONMENT:'preview',BUYEROS_NEON_AUTH_URL:url,BUYEROS_NEON_EXPECTED_AUTH_URL:url,BUYEROS_PUBLIC_ORIGIN:origin,BUYEROS_NEON_EXPECTED_PUBLIC_ORIGIN:origin,BUYEROS_NEON_COOKIE_SECRET:'C61_BUILT_PRIVATE_OFFLINE_ONLY_'.repeat(2)});
 const response=await request('POST',{origin:'https://foreign.example.test'});assert.equal(response.status,403);assert.equal(response.headers.getSetCookie().length,0);assert.equal(calls,0);assert.deepEqual(await response.json(),{code:'AUTH_FORBIDDEN'});
});
