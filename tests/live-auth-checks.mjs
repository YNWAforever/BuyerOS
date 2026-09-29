import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';
const {SessionScope}=await loadModule('services/live/session.ts');
const {createAuthAdapter, normalizeReturnPath}=await loadModule('services/live/auth.ts');
let n=0;
async function check(name,fn){await fn(); console.log('PASS '+name); n++;}
await check('scope snapshot stable until change and observer sees each generation',()=>{
 const s=new SessionScope({mode:'live'}), snap=s.getSnapshot(); let notices=0;
 const stop=s.subscribe(()=>notices++);
 assert.equal(s.getSnapshot(),snap);
 const first=s.next({actor:'actor',workspace:'A'});
 assert.notEqual(s.getSnapshot(),snap);
 s.next({workspace:'B'}); s.next({workspace:'A'});
 assert.equal(s.isCurrent(first.identity),false); assert.equal(notices,3);
 stop(); s.next({workspace:'C'}); assert.equal(notices,3);
});
await check('write context is captured and unauthenticated writes fail closed',()=>{
 const s=new SessionScope({mode:'live'});
 assert.throws(()=>s.captureWriteContext());
 s.setToken('private-token'); s.next({actor:'actor',workspace:'A',project:'P'});
 const ctx=s.captureWriteContext(); assert.equal(ctx.workspace,'A');
 assert.equal(JSON.stringify(ctx).includes('private-token'),false);
 s.next({workspace:'B',project:null}); assert.equal(ctx.signal.aborted,true);
 assert.equal(s.isCurrent(ctx.identity),false);
});
await check('OIDC return path rejects off-origin redirects',()=>{
 assert.equal(normalizeReturnPath('/app?workspace=A'),'/app?workspace=A');
 for(const value of ['https://evil.test','//evil.test','/\\evil','/auth/callback?code=x']) assert.equal(normalizeReturnPath(value),'/app');
});
await check('public auth config never accepts client secret or non-HTTPS issuer',()=>{
 assert.throws(()=>createAuthAdapter({issuer:'http://evil.test',clientId:'id',audience:'api'}));
 assert.throws(()=>createAuthAdapter({issuer:'https://issuer.test',clientId:'id',audience:'api',clientSecret:'secret'}));
});
console.log(`${n} live auth checks passed`);

const config={issuer:'https://issuer.test/',clientId:'public-client',audience:'buyer-api'};
const keys=await crypto.subtle.generateKey({name:'RSASSA-PKCS1-v1_5',modulusLength:2048,publicExponent:new Uint8Array([1,0,1]),hash:'SHA-256'},true,['sign','verify']);
const publicKey={...(await crypto.subtle.exportKey('jwk',keys.publicKey)),kid:'test-key',use:'sig'};
function b64(value){return Buffer.from(typeof value==='string'?value:JSON.stringify(value)).toString('base64url');}
async function idToken(nonce){
 const header=b64({alg:'RS256',kid:'test-key'}), body=b64({iss:config.issuer,aud:config.clientId,sub:'oidc-user',exp:Math.floor(Date.now()/1000)+3600,nonce});
 const payload=`${header}.${body}`;
 const sig=await crypto.subtle.sign('RSASSA-PKCS1-v1_5',keys.privateKey,new TextEncoder().encode(payload));
 return `${payload}.${Buffer.from(sig).toString('base64url')}`;
}
function harness(){
 const entries=new Map();let clock=Date.now(), expectedNonce='', access='test-access';
 const location={origin:'http://localhost:5173',href:'http://localhost:5173/app',assign(url){this.href=url;}};
 const env={location,storage:{getItem:key=>entries.get(key)??null,setItem:(key,value)=>entries.set(key,value),removeItem:key=>entries.delete(key)},crypto,now:()=>clock,
  fetch:async (url,init)=>{
   const target=String(url);
   if(target.endsWith('/.well-known/jwks.json'))return {ok:true,json:async()=>({keys:[publicKey]})};
   if(target.endsWith('/oauth/token')){
    assert.equal(init.method,'POST');
    assert.equal(init.body.get('grant_type'),'authorization_code');
    assert.equal(init.body.get('client_secret'),null);
    assert.equal(init.body.get('code_verifier'),JSON.parse(entries.get('saved-tx')).verifier);
    return {ok:true,json:async()=>({access_token:access,id_token:await idToken(expectedNonce),expires_in:120})};
   }
   throw Error('Unexpected request '+target);
  }};
 return {env,entries,location,setNonce:value=>expectedNonce=value,advance:value=>clock+=value,setAccess:value=>access=value};
}
await check('PKCE callback verifies state, nonce and signature, holds only access token in memory',async()=>{
 const h=harness(), adapter=createAuthAdapter(config,h.env);
 await adapter.signIn('/app?workspace=A');
 const authorize=new URL(h.location.href), tx=JSON.parse(h.entries.get('buyeros-oidc-transaction'));
 assert.equal(authorize.searchParams.get('code_challenge_method'),'S256');
 assert.equal(authorize.searchParams.get('client_secret'),null);
 const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(tx.verifier));
 assert.equal(authorize.searchParams.get('code_challenge'),Buffer.from(digest).toString('base64url'));
 h.entries.set('saved-tx',JSON.stringify(tx));h.setNonce(tx.nonce);
 h.location.href=`http://localhost:5173/auth/callback?code=one-use&state=${tx.state}`;
 await adapter.completeCallback();
 assert.equal(adapter.subject(),'oidc-user');assert.equal(adapter.returnPath(),'/app?workspace=A');
 assert.equal(await adapter.getAccessToken(),'test-access');
 assert.equal(h.entries.has('buyeros-oidc-transaction'),false);
 assert.equal([...h.entries.values()].some(value=>value.includes('test-access')),false);
 h.advance(91_000); await assert.rejects(()=>adapter.getAccessToken(),/expired/);
});
await check('callback rejects mismatched state and cannot replay transaction',async()=>{
 const h=harness(), adapter=createAuthAdapter(config,h.env);await adapter.signIn('/app');
 h.location.href='http://localhost:5173/auth/callback?code=one-use&state=wrong';
 await assert.rejects(()=>adapter.completeCallback(),/state mismatch/);
 assert.equal(h.entries.has('buyeros-oidc-transaction'),false);
 await assert.rejects(()=>adapter.getAccessToken(),/expired/);
});
await check('callback rejects wrong nonce even with signed ID token',async()=>{
 const h=harness(), adapter=createAuthAdapter(config,h.env);await adapter.signIn('/app');
 const tx=JSON.parse(h.entries.get('buyeros-oidc-transaction'));
 h.entries.set('saved-tx',JSON.stringify(tx));h.setNonce('wrong-nonce');
 h.location.href=`http://localhost:5173/auth/callback?code=one-use&state=${tx.state}`;
 await assert.rejects(()=>adapter.completeCallback(),/identity mismatch/);
 await assert.rejects(()=>adapter.getAccessToken(),/expired/);
});
await check('logout drops the token and uses an allowlisted origin return URL',async()=>{
 const h=harness(), adapter=createAuthAdapter(config,h.env);await adapter.signIn('/app');
 const tx=JSON.parse(h.entries.get('buyeros-oidc-transaction'));
 h.entries.set('saved-tx',JSON.stringify(tx));h.setNonce(tx.nonce);
 h.location.href=`http://localhost:5173/auth/callback?code=one-use&state=${tx.state}`;
 await adapter.completeCallback();await adapter.signOut();
 await assert.rejects(()=>adapter.getAccessToken(),/expired/);
 const url=new URL(h.location.href);assert.equal(url.pathname,'/v2/logout');
 assert.equal(url.searchParams.get('returnTo'),'http://localhost:5173/app');
 assert.equal(url.searchParams.get('access_token'),null);
});
console.log(`${n} live auth checks passed including OIDC crypto`);
