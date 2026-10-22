import test from 'node:test';
import assert from 'node:assert/strict';
import {validateSyntheticReturn,fulfillSyntheticRedirect,closeSyntheticRedirectServer} from './e2e/fixtures/synthetic-oidc-redirect.mjs';
const callback='http://localhost:5173/auth/callback?code=workbench-fixture&state=synthetic-state-only';
test('synthetic return admits only the existing callback/logout contract',()=>{
 assert.equal(validateSyntheticReturn(callback),callback);
 assert.equal(validateSyntheticReturn('http://localhost:5173/app'),'http://localhost:5173/app');
});
test('synthetic return rejects foreign origin, paths, missing/duplicate state and userinfo',()=>{
 for(const raw of [callback.replace('localhost','example.test'),callback.replace(':5173',':5174'),
  callback.replace('/auth/callback','/auth/callback/extra'),callback+'&state=other',
  callback.replace('state=synthetic-state-only','state='),callback+'&extra=1',callback+'#fragment',
  callback.replace('http://','http://synthetic@'),'http://localhost:5173/app?state=synthetic']){
   assert.throws(()=>validateSyntheticReturn(raw),/Synthetic return target refused/);
 }
});
test('wrong issuer is refused before navigation or TLS generation',async()=>{
 let navigated=false;
 const route={request:()=>({url:()=> 'https://foreign.example.test/authorize',method:()=> 'GET'}),
   continue:()=>{navigated=true;},fulfill:()=>{navigated=true;}};
 await assert.rejects(fulfillSyntheticRedirect({},route,callback),/Synthetic issuer request refused/);
 assert.equal(navigated,false);
 await closeSyntheticRedirectServer();
});
