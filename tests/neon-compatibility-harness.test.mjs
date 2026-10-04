import assert from 'node:assert/strict';
import {test} from 'node:test';
import {assertLoopbackUrl,assertSourcePath,isBuildSource} from '../scripts/neon-compatibility-harness.mjs';
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
