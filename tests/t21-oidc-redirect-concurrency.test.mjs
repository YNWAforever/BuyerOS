import test from 'node:test';
import assert from 'node:assert/strict';
import {Server} from 'node:net';
import {fulfillSyntheticRedirect,closeSyntheticRedirectServer} from './e2e/fixtures/synthetic-oidc-redirect.mjs';
test('owned loopback redirect initialization is single-flight and cleanup closes its one listener',async t=>{
 const prior=process.env.T21_SYNTHETIC_TLS;process.env.T21_SYNTHETIC_TLS='1';
 const listeners=new Set(),original=Server.prototype.listen,urls=[];
 t.mock.method(Server.prototype,'listen',function(...args){
   assert.equal(args[0],0);assert.equal(args[1],'127.0.0.1');listeners.add(this);
   return original.apply(this,args);
 });
 const context={browser:()=>({browserType:()=>({name:()=> 'webkit'})}),route:async()=>{}};
 const page={context:()=>context};
 const route=()=>({request:()=>({url:()=> 'https://oidc.buyeros.test/authorize',method:()=> 'GET'}),
   continue:async({url})=>{urls.push(url);}});
 try{
   await Promise.all([fulfillSyntheticRedirect(page,route(),'http://localhost:5173/auth/callback?code=workbench-fixture&state=synthetic-one'),
     fulfillSyntheticRedirect(page,route(),'http://localhost:5173/auth/callback?code=research-fixture&state=synthetic-two')]);
   assert.equal(listeners.size,1,'two overlapping handoffs must not create an untracked TLS listener');
   assert.equal(new Set(urls.map(url=>new URL(url).origin)).size,1);
   await closeSyntheticRedirectServer();
   assert.equal([...listeners].some(server=>server.listening),false);
 }finally{
   await closeSyntheticRedirectServer();
   for(const listener of listeners)if(listener.listening){
     listener.closeAllConnections?.();await new Promise((resolve,reject)=>listener.close(error=>error?reject(error):resolve()));
   }
   if(prior===undefined)delete process.env.T21_SYNTHETIC_TLS;else process.env.T21_SYNTHETIC_TLS=prior;
 }
});
