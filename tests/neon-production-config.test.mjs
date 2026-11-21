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
const previewHost='buyeros-qa-abc123-team.vercel.app',previewOrigin='https://'+previewHost,previewSource='a'.repeat(40);
const previewConfigured=()=>({...configured(),VERCEL_ENV:'preview',BUYEROS_NEON_ENVIRONMENT:'preview',
 BUYEROS_NEON_QA_PREVIEW_ORIGIN_ENABLED:'1',VERCEL_URL:previewHost,
 BUYEROS_QA_PREVIEW_PROJECT_ID:'prj_qa',BUYEROS_QA_PREVIEW_TEAM_ID:'team_qa',
 BUYEROS_QA_PREVIEW_REPO:'YNWAforever/BuyerOS',BUYEROS_QA_PREVIEW_REPO_ID:'123456789',
 BUYEROS_QA_PREVIEW_BRANCH:'codex/qa-preview',BUYEROS_RUNTIME_SOURCE_SHA:previewSource,
 BUYEROS_QA_PREVIEW_EXPECTED_ORIGIN:previewOrigin,
 VERCEL_PROJECT_ID:'prj_qa',VERCEL_TEAM_ID:'team_qa',VERCEL_GIT_PROVIDER:'github',
 VERCEL_GIT_REPO_OWNER:'YNWAforever',VERCEL_GIT_REPO_SLUG:'BuyerOS',VERCEL_GIT_REPO_ID:'123456789',
 VERCEL_GIT_COMMIT_REF:'codex/qa-preview',VERCEL_GIT_COMMIT_SHA:previewSource});
test('QA preview origin is a narrow preview-only allowlist bound to platform deployment metadata',async()=>{
 const fn=await load(),env=previewConfigured(),config=fn(env);
 assert.equal(config.publicOrigin,origin);assert.equal(config.qaPreviewOrigin,previewOrigin);
 assert.equal(config.stagedOrigin,undefined);
 const optional=fn({...env,BUYEROS_QA_PREVIEW_EXPECTED_ORIGIN:undefined,BUYEROS_QA_PREVIEW_TEAM_ID:undefined,VERCEL_TEAM_ID:undefined});
 assert.equal(optional.qaPreviewOrigin,previewOrigin);
 const injectedEmpty=fn({...env,BUYEROS_QA_PREVIEW_TEAM_ID:'',BUYEROS_QA_PREVIEW_EXPECTED_ORIGIN:'',VERCEL_TEAM_ID:undefined});
 assert.equal(injectedEmpty.qaPreviewOrigin,previewOrigin);
});
for(const [fault,change] of Object.entries({
 invalid_flag:{BUYEROS_NEON_QA_PREVIEW_ORIGIN_ENABLED:'true'},production_environment:{BUYEROS_NEON_ENVIRONMENT:'production'},
 production_vercel:{VERCEL_ENV:'production'},
 missing_project:{BUYEROS_QA_PREVIEW_PROJECT_ID:undefined},wrong_project:{VERCEL_PROJECT_ID:'prj_other'},
 wrong_team:{VERCEL_TEAM_ID:'team_other'},
 missing_repo:{BUYEROS_QA_PREVIEW_REPO:undefined},wrong_repo_owner:{VERCEL_GIT_REPO_OWNER:'evil'},
 wrong_repo_slug:{VERCEL_GIT_REPO_SLUG:'Other'},missing_repo_id:{BUYEROS_QA_PREVIEW_REPO_ID:undefined},
 wrong_repo_id:{VERCEL_GIT_REPO_ID:'987654321'},missing_branch:{BUYEROS_QA_PREVIEW_BRANCH:undefined},
 wrong_branch:{VERCEL_GIT_COMMIT_REF:'main'},unsafe_branch:{BUYEROS_QA_PREVIEW_BRANCH:'codex/../main'},
 missing_source:{BUYEROS_RUNTIME_SOURCE_SHA:undefined},wrong_source:{VERCEL_GIT_COMMIT_SHA:'b'.repeat(40)},
 wrong_provider:{VERCEL_GIT_PROVIDER:'gitlab'},wrong_expected_origin:{BUYEROS_QA_PREVIEW_EXPECTED_ORIGIN:'https://other.vercel.app'},
 staging_and_preview:{BUYEROS_NEON_STAGED_ORIGIN_ENABLED:'1'},
}))test(`QA preview origin refuses ${fault}`,async()=>{const fn=await load();assert.throws(()=>fn({...previewConfigured(),...change}));});
for(const [fault,change] of Object.entries({
 scheme:{VERCEL_URL:'https://'+previewHost},port:{VERCEL_URL:previewHost+':443'},path:{VERCEL_URL:previewHost+'/path'},
 suffix:{VERCEL_URL:previewHost+'.evil.test'},underscore:{VERCEL_URL:'buyeros_qa.vercel.app'},empty:{VERCEL_URL:''},
}))test(`QA preview origin refuses an invalid platform VERCEL_URL: ${fault}`,async()=>{const fn=await load();assert.throws(()=>fn({...previewConfigured(),...change}));});
test('QA preview origin is off unless explicitly enabled and empty platform flags stay closed',async()=>{
 const fn=await load(),off=fn({...previewConfigured(),BUYEROS_NEON_QA_PREVIEW_ORIGIN_ENABLED:undefined});
 assert.equal(off.qaPreviewOrigin,undefined);
 assert.equal(fn({...previewConfigured(),BUYEROS_NEON_QA_PREVIEW_ORIGIN_ENABLED:''}).qaPreviewOrigin,undefined);
});
test('QA preview origin does not change the existing production staging behavior',async()=>{
 const staging={...configured(),VERCEL_ENV:'production',BUYEROS_NEON_ENVIRONMENT:'production',
  BUYEROS_NEON_AUTH_URL:authUrl.replace('preview','production'),BUYEROS_NEON_EXPECTED_AUTH_URL:authUrl.replace('preview','production'),
  BUYEROS_PUBLIC_ORIGIN:'https://buyeros.example.test',BUYEROS_NEON_EXPECTED_PUBLIC_ORIGIN:'https://buyeros.example.test',
  BUYEROS_NEON_STAGED_ORIGIN_ENABLED:'1',BUYEROS_RUNTIME_SOURCE_SHA:previewSource,VERCEL_URL:previewHost};
 const config=(await load())(staging);
 assert.equal(config.publicOrigin,'https://buyeros.example.test');assert.equal(config.stagedOrigin,previewOrigin);assert.equal(config.qaPreviewOrigin,undefined);
});
