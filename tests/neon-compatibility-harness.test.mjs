import assert from 'node:assert/strict';
import {test} from 'node:test';
import {resolve} from 'node:path';
import {assertLoopbackUrl,assertSourcePath,isBuildSource,fixtureChildEnvironment,assertSeedMetadata,staticAssetPath,compatibilityViteConfig,assertProtocolStorage} from '../scripts/neon-compatibility-harness.mjs';
for(const value of ['https://auth.neon.tech/neondb/auth','http://127.0.0.1.evil.test/auth','http://user:password@localhost:44891/auth','http://0.0.0.0:44891/auth']) {
 test(`N00 rejects a non-owned upstream: ${value}`,()=>assert.throws(()=>assertLoopbackUrl(value)));
}
test('N00 accepts the loopback fixture base path',()=>assert.equal(assertLoopbackUrl('http://127.0.0.1:44891/fixture/auth').pathname,'/fixture/auth'));
for(const value of ['../.env','a/../../secret','/secret','C:/secret','a/.env.production','a\\.env.local','node_modules/secret','test-results/secret','app/../secret']) {
 test(`N00 source inventory rejects unsafe input: ${value}`,()=>assert.throws(()=>assertSourcePath(value)));
}
test('N00 source inventory accepts a source file',()=>assert.equal(assertSourcePath('app/page.tsx'),'app/page.tsx'));

test('N00 build includes BuyerOS frontend services and generated types',()=>{for(const path of ['services/live/mode.ts','services/generated/api-types.ts'])assert.equal(isBuildSource(path),true);});
test('N00 build excludes Python/services and historical evidence',()=>{for(const path of ['services/api/.env','services/worker/run.py','docs/private.txt','tests/fixtures/private.ts'])assert.equal(isBuildSource(path),false);});

test('N00 child env excludes inherited DB/Auth/provider variables',()=>{const env=fixtureChildEnvironment({PATH:'fictional-path',DATABASE_URL:'forbidden',BUYEROS_TEST_DATABASE_URL:'forbidden',BUYEROS_AUTH0_ISSUER:'forbidden',NEON_AUTH_COOKIE_SECRET:'forbidden',OPENAI_API_KEY:'forbidden'});assert.equal(env.PATH,'fictional-path');assert.equal(env.BUYEROS_STRICT_INTEGRATION,'1');for(const key of ['DATABASE_URL','BUYEROS_TEST_DATABASE_URL','BUYEROS_AUTH0_ISSUER','NEON_AUTH_COOKIE_SECRET','OPENAI_API_KEY'])assert.equal(key in env,false);});
test('N00 cache seed requires matching declared owner',()=>{assert.doesNotThrow(()=>assertSeedMetadata('buyeros-audit-ui-deps-052d6a686de9','052d6a686de9',{'buyeros.audit.owner':'052d6a686de9'}));assert.throws(()=>assertSeedMetadata('buyeros-audit-ui-deps-052d6a686de9','052d6a686de9',{'buyeros.audit.owner':'someone-else'}));assert.throws(()=>assertSeedMetadata('shared-production-cache','052d6a686de9',{'buyeros.audit.owner':'052d6a686de9'}));});

test('N00 emitted static assets stay within the output static directory',()=>{assert.equal(staticAssetPath(resolve('fixture-static'),'/_next/static/chunks/client.js'),resolve('fixture-static/_next/static/chunks/client.js'));for(const path of ['/../private','/%2e%2e/private','/a%5cprivate','/a:private'])assert.throws(()=>staticAssetPath('/fixture-static',path));});

test('N00 registers Vinext public fetch entry as the Nitro RSC service without changing production config',()=>{const input="plugins: [(await import(\"nitro/vite\")).nitro({ vercel: { functions: { maxDuration: 90 } } })]";const output=compatibilityViteConfig(input);assert.match(output,/services: \{ rsc: \{ entry: \"\.\/lib\/neon-compatibility\/rsc-service\.ts\"/);assert.match(output,/maxDuration: 90/);assert.throws(()=>compatibilityViteConfig('different build interface'));assert.throws(()=>compatibilityViteConfig(input+input));});

test('N00 storage permits only canonical locale prefs and refuses tokens or credential fields',()=>{assert.doesNotThrow(()=>assertProtocolStorage([]));assert.doesNotThrow(()=>assertProtocolStorage([['buyeros-prefs-v1','{"locale":"en"}']]));assert.doesNotThrow(()=>assertProtocolStorage([['buyeros-prefs-v1','{"locale":"zh-HK"}']]));for(const entries of [[['token','fictional']], [['buyeros-prefs-v1','{"locale":"en","token":"fictional"}']], [['buyeros-prefs-v1','{"locale":"fictional-session"}']], [['buyeros-prefs-v1','{"locale":"credential","locale":"en"}']]])assert.throws(()=>assertProtocolStorage(entries));});
