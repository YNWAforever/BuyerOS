import test from 'node:test';
import assert from 'node:assert/strict';
const authUrl='https://ep-c61-preview.neonauth.us-east-2.aws.neon.tech/neondb/auth';
const origin='https://c61-preview.example.test';
const configured=()=>({NODE_ENV:'production',VERCEL_ENV:'preview',BUYEROS_NEON_ENVIRONMENT:'preview',BUYEROS_NEON_AUTH_URL:authUrl,BUYEROS_NEON_EXPECTED_AUTH_URL:authUrl,BUYEROS_PUBLIC_ORIGIN:origin,BUYEROS_NEON_EXPECTED_PUBLIC_ORIGIN:origin,BUYEROS_NEON_COOKIE_SECRET:'C61_ONLY_SYNTHETIC_COOKIE_CANARY_'.repeat(2)});
const load=async()=> (await import('../lib/auth/neon-config.ts')).loadNeonConfig;
test('C61-08 exact preview binding returns only server configuration without changing env',async()=>{
 const env=configured(),before={...env},config=(await load())(env);assert.deepEqual(config,{authUrl,publicOrigin:origin,cookieSecret:env.BUYEROS_NEON_COOKIE_SECRET});assert.deepEqual(env,before);
});
for(const name of ['BUYEROS_NEON_ENVIRONMENT','BUYEROS_NEON_AUTH_URL','BUYEROS_NEON_EXPECTED_AUTH_URL','BUYEROS_PUBLIC_ORIGIN','BUYEROS_NEON_EXPECTED_PUBLIC_ORIGIN','BUYEROS_NEON_COOKIE_SECRET'])test(`C61-08 missing ${name} fails closed without echoing secrets`,async()=>{
 const env=configured();delete env[name];const fn=await load();assert.throws(()=>fn(env),error=> !String(error).includes(env.BUYEROS_NEON_COOKIE_SECRET||'CANARY_NEVER_SENT')&&!String(error).includes(authUrl));
});
for(const [name,change] of Object.entries({
 wrong_branch:{BUYEROS_NEON_AUTH_URL:authUrl.replace('preview','production')},wrong_origin:{BUYEROS_PUBLIC_ORIGIN:'https://other.example.test'},preview_to_production:{BUYEROS_NEON_ENVIRONMENT:'production'},unknown_environment:{BUYEROS_NEON_ENVIRONMENT:'staging'},
 short_secret:{BUYEROS_NEON_COOKIE_SECRET:'too-short'},url_credentials:{BUYEROS_NEON_AUTH_URL:'https://synthetic:synthetic@'+new URL(authUrl).host+'/neondb/auth'},auth_query:{BUYEROS_NEON_AUTH_URL:authUrl+'?branch=other'},insecure_auth:{BUYEROS_NEON_AUTH_URL:authUrl.replace('https:','http:')},
 insecure_preview_origin:{BUYEROS_PUBLIC_ORIGIN:'http://preview.example.test',BUYEROS_NEON_EXPECTED_PUBLIC_ORIGIN:'http://preview.example.test'},origin_path:{BUYEROS_PUBLIC_ORIGIN:origin+'/app',BUYEROS_NEON_EXPECTED_PUBLIC_ORIGIN:origin+'/app'},fixture_trust:{BUYEROS_NEON_FIXTURE_MODE:'1'},test_credentials:{BUYEROS_NEON_TEST_EMAIL:'fictional@example.test'},
}))test(`C61-08 ${name} is refused before SDK initialization`,async()=>{const fn=await load();assert.throws(()=>fn({...configured(),...change}));});
test('C61-08 production has an independent exact manifest and no preview fallback',async()=>{
 const env={...configured(),VERCEL_ENV:'production',BUYEROS_NEON_ENVIRONMENT:'production',BUYEROS_NEON_AUTH_URL:authUrl.replace('preview','production'),BUYEROS_NEON_EXPECTED_AUTH_URL:authUrl.replace('preview','production'),BUYEROS_PUBLIC_ORIGIN:'https://buyeros.example.test',BUYEROS_NEON_EXPECTED_PUBLIC_ORIGIN:'https://buyeros.example.test'};
 const fn=await load();assert.equal(fn(env).authUrl,env.BUYEROS_NEON_AUTH_URL);delete env.BUYEROS_NEON_AUTH_URL;assert.throws(()=>fn(env));
});
test('C61-08 explicit local public origin permits loopback only and keeps remote auth HTTPS',async()=>{
 const env={...configured(),NODE_ENV:'development',BUYEROS_NEON_ENVIRONMENT:'local',BUYEROS_PUBLIC_ORIGIN:'http://localhost:5173',BUYEROS_NEON_EXPECTED_PUBLIC_ORIGIN:'http://localhost:5173'};delete env.VERCEL_ENV;
 const fn=await load();assert.equal(fn(env).publicOrigin,'http://localhost:5173');assert.throws(()=>fn({...env,BUYEROS_NEON_AUTH_URL:'http://localhost:8001/auth',BUYEROS_NEON_EXPECTED_AUTH_URL:'http://localhost:8001/auth'}));assert.throws(()=>fn({...env,NODE_ENV:'production'}));
});
