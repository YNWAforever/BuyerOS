import assert from 'node:assert/strict';
import {test} from 'node:test';
import {resolve} from 'node:path';
import {validateBuiltUiFixture,safeStaticPath} from '../../scripts/serve-built-ui-fixture.mjs';

test('built UI fixture refuses inherited databases, credentials and nonfixture API targets',()=>{
  const env={BUYEROS_STRICT_INTEGRATION:'1'};
  const context={fixture_only:true,origin:'http://127.0.0.1:8000',issuer:'urn:buyeros:e2e'};
  assert.doesNotThrow(()=>validateBuiltUiFixture(env,context));
  for(const extra of [{BUYEROS_TEST_DATABASE_URL:'postgresql://localhost/shared'},{CLOUDFLARE_API_TOKEN:'unrelated-token'},{BUYEROS_REUSE_TEST_SERVER:'1'}]){
    assert.throws(()=>validateBuiltUiFixture({...env,...extra},context));
  }
  for(const change of [{fixture_only:false},{origin:'https://production.example'},{issuer:'https://real-issuer.example'}]){
    assert.throws(()=>validateBuiltUiFixture(env,{...context,...change}));
  }
});

test('built UI static assets cannot escape their emitted public directory',()=>{
  const root=resolve('.vercel/output/static');
  assert.equal(safeStaticPath(root,'/assets/app.js'),resolve(root,'assets/app.js'));
  for(const path of ['/../secrets','/%2e%2e/.env','/C:/Windows/config','/%5c..%5c.env','/%ZZ']){
    assert.throws(()=>safeStaticPath(root,path));
  }
});
