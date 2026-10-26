import assert from 'node:assert/strict';
import {test} from 'node:test';
import {existsSync} from 'node:fs';
import {loadModule} from './ts-loader.mjs';

const fixturePath=new URL('./e2e/fixtures/neon-fixture-protocol.mjs',import.meta.url);
test('owned workbench fixture exposes the Neon email/cookie protocol and restores its matching actor',async()=>{
  assert.ok(existsSync(fixturePath),'owned Neon workbench protocol must replace the removed OIDC fixture');
  const {createNeonFixtureProtocol,neonFixtureEnvironment}=await import(fixturePath.href);
  const {loadPublicAuth}=await loadModule('lib/auth/public-auth.ts');
  const {createNeonAuthAdapter}=await loadModule('services/live/neon-auth.ts');
  const config=loadPublicAuth({...neonFixtureEnvironment,NODE_ENV:'test'});
  assert.equal(config.provider,'neon');
  const fixture=createNeonFixtureProtocol({subject:'fixture-reviewer',accessToken:'fixture-reviewer'});
  const entries=new Map(),location={origin:'http://localhost:5173',href:'http://localhost:5173/app',assign(url){this.href=new URL(url,this.origin).href;}};
  let cookie='',calls=[];
  const env={location,storage:{getItem:key=>entries.get(key)??null,setItem:(key,value)=>entries.set(key,value),removeItem:key=>entries.delete(key)},crypto:globalThis.crypto,now:Date.now,
    fetch:async(path,init)=>{calls.push(path);const response=await fixture.respond(new Request(new URL(path,location.origin),{...init,headers:{...init.headers,cookie}}));assert.ok(response,'all auth requests stay synthetic');const set=response.headers.get('set-cookie');if(set)cookie=set.split(';')[0];return response;}};
  const auth=createNeonAuthAdapter(config.config,env);
  await auth.initialize();assert.equal(auth.subject(),'');
  await auth.signIn('/app?workspace=A&project=P');await auth.signInEmail(fixture.email,fixture.password);
  await auth.completeCallback();assert.equal(auth.subject(),'fixture-reviewer');
  const jwt=await auth.getAccessToken();assert.equal(JSON.parse(Buffer.from(jwt.split('.')[1],'base64url')).sub,'fixture-reviewer');
  assert.equal(fixture.apiBearer(jwt),'fixture-reviewer');assert.equal(fixture.apiBearer(jwt+'other'),null);
  assert.equal(auth.returnPath(),'/app?workspace=A&project=P');
  const reload=createNeonAuthAdapter(config.config,env);await reload.initialize();assert.equal(reload.subject(),'fixture-reviewer');
  assert.ok(calls.includes('/api/auth/sign-in/email'));assert.ok(calls.includes('/api/auth/token'));
  assert.doesNotMatch(JSON.stringify([...entries]),/synthetic-only|fixture-reviewer/);
  await reload.signOut();const signedOut=createNeonAuthAdapter(config.config,env);await signedOut.initialize();assert.equal(signedOut.subject(),'');
});

test('synthetic workbench protocol refuses foreign origins and invalid credentials',async()=>{
  assert.ok(existsSync(fixturePath),'owned Neon workbench protocol must exist');
  const {createNeonFixtureProtocol}=await import(fixturePath.href),fixture=createNeonFixtureProtocol();
  await assert.rejects(fixture.respond(new Request('https://production.example/api/auth/get-session')),/owned/);
  const response=fixture.respond(new Request('http://localhost:5173/api/auth/sign-in/email',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'real@example.com',password:'real',callbackURL:'http://localhost:5173/auth/callback?state=owned'})}));
  assert.equal((await response).status,401);
});
