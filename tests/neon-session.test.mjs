import test from 'node:test';
import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';
const {createLiveClient,LiveCancelled}=await loadModule('services/live/client.ts');
const {SessionScope}=await loadModule('services/live/session.ts');
const {normalizeReturnPath}=await loadModule('services/live/auth.ts');
const trustedSocialInitOrigin='https://ep-owned.neonauth.us-east-2.aws.neon.tech';
const trustedSocialInitPath='/neondb/auth/sign-in/social/init';
const adapter=async env=>(await loadModule('services/live/neon-auth.ts')).createNeonAuthAdapter({authPath:'/api/auth',socialInitOrigin:trustedSocialInitOrigin,socialInitPath:trustedSocialInitPath},env);
const deferred=()=>{let resolve;return {promise:new Promise(r=>resolve=r),resolve};};
const jwt=(sub='neon-user',exp=2000)=>['eyJhbGciOiJFZERTQSJ9',Buffer.from(JSON.stringify({sub,exp})).toString('base64url'),'synthetic-signature'].join('.');
function environment(){
 const entries=new Map(),sent=[],listeners=new Set();let clock=1_000_000;
 const location={origin:'https://app.example.test',href:'https://app.example.test/app',assign(url){this.href=new URL(url,this.origin).href;}};
 const env={location,storage:{getItem:k=>entries.get(k)??null,setItem:(k,v)=>entries.set(k,v),removeItem:k=>entries.delete(k)},crypto,now:()=>clock,
 channel:{postMessage:e=>sent.push(e),subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn);}},fetch:async(url,init)=>{
  assert.equal(init.credentials,'same-origin');assert.equal(init.cache,'no-store');
  if(String(url)==='/api/auth/get-session')return Response.json({session:{id:'session'},user:{id:'neon-user'}});
  if(String(url)==='/api/auth/token')return Response.json({token:jwt()});
  if(String(url)==='/api/auth/sign-out')return Response.json({success:true});
  throw Error('Offline test refuses '+url);
 }};
 return {env,entries,sent,emit:e=>{for(const fn of listeners)fn(e);},clock:v=>clock=v};
}
test('C11 cookie hydration initializes one session without persisting or broadcasting tokens',async()=>{
 const h=environment(),auth=await adapter(h.env);let calls=0;const fetch=h.env.fetch;h.env.fetch=async(...a)=>{calls++;return fetch(...a);};
 await Promise.all(Array.from({length:20},()=>auth.initialize()));
 assert.equal(calls,2);assert.equal(auth.subject(),'neon-user');assert.equal(await auth.getAccessToken(),jwt());
 assert.equal(h.entries.size,0);assert.equal(h.sent.length,0);
});
test('C11 twenty rejected requests share one renewal and keep each original body and intent',async()=>{
 const h=environment(),auth=await adapter(h.env);await auth.initialize();let refreshCalls=0;const wait=deferred();
 h.env.fetch=async(url)=>{assert.equal(url,'/api/auth/token');refreshCalls++;await wait.promise;return Response.json({token:jwt('neon-user',2100)});};
 const observations=[],accepted=new Map();let runCount=0,outboxCount=0;
 const client=createLiveClient(async(url,init)=>{
  observations.push({url,body:init.body,key:init.headers['Idempotency-Key'],auth:init.headers.Authorization,match:init.headers['X-BuyerOS-If-Match']});
  if(init.headers.Authorization===`Bearer ${jwt()}`)return Response.json({code:'UNAUTHORIZED'},{status:401});
  if(!accepted.has(init.headers['Idempotency-Key'])){accepted.set(init.headers['Idempotency-Key'],init.body);if(init.headers['Idempotency-Key']==='intent-0'){runCount++;outboxCount++;}}
  return Response.json({data_mode:'live',request_id:'observed-request',data:{accepted:true}});
 },'',{refresh:(token)=>auth.refreshAccessToken(token),isCurrent:()=>true,onUnauthorized:()=>auth.invalidate()});
 const bodies=Array.from({length:20},(_,i)=>({index:i,payload:'original'}));
 const requests=bodies.map((body,i)=>client.request({path:'/v1/research',method:'POST',token:jwt(),scope:'A',body,idempotencyKey:`intent-${i}`,ifMatch:'"7"'}));
 await new Promise(r=>setTimeout(r,0));bodies.forEach(body=>body.payload='mutated after send');wait.resolve();await Promise.all(requests);
 assert.equal(refreshCalls,1);assert.equal(runCount,1);assert.equal(outboxCount,1);assert.equal(observations.length,40);
 for(const original of observations.slice(0,20)){const retry=observations.find(x=>x.key===original.key&&x.auth!==original.auth);assert.equal(retry.body,original.body);assert.equal(original.match,'"7"');assert.equal(retry.match,original.match);}
});
test('C11 an already renewed rejected token never starts a second renewal',async()=>{
 const h=environment(),auth=await adapter(h.env);await auth.initialize();let calls=0;
 h.env.fetch=async()=>{calls++;return Response.json({token:jwt('neon-user',2100)});};
 await auth.refreshAccessToken(jwt());await auth.refreshAccessToken(jwt());assert.equal(calls,1);
});
test('C11 logout invalidates pending hydration and cannot restore the old session',async()=>{
 const h=environment(),auth=await adapter(h.env),wait=deferred();
 h.env.fetch=async(url)=>{if(url==='/api/auth/get-session'){await wait.promise;return Response.json({session:{},user:{id:'neon-user'}});}return Response.json({success:true});};
 const result=auth.initialize().then(()=>false,()=>true);await auth.signOut();wait.resolve();assert.equal(await result,true);
 assert.equal(auth.subject(),'');assert.equal(auth.expiresAt(),0);await assert.rejects(auth.getAccessToken());
 assert.deepEqual(h.sent,[{type:'logout'}]);assert.equal(h.env.location.href,'https://app.example.test/app');
});
test('C11 cross-tab logout clears token, scope, polling controller and rejects late renewal',async()=>{
 const h=environment(),auth=await adapter(h.env),session=new SessionScope({mode:'live'});await auth.initialize();
 session.setToken(await auth.getAccessToken());session.next({actor:auth.subject(),workspace:'A',project:'P'});
 auth.subscribeInvalidated(()=>session.setToken(undefined));const old=session.captureWriteContext(),wait=deferred();
 h.env.fetch=async()=>{await wait.promise;return Response.json({token:jwt('neon-user',2100)});};
 const renewal=auth.refreshAccessToken(jwt()).then(()=>false,()=>true);h.emit({type:'logout'});wait.resolve();assert.equal(await renewal,true);
 assert.equal(old.signal.aborted,true);assert.equal(session.getSnapshot().authenticated,false);assert.equal(session.current().workspace,null);
 assert.equal(auth.subject(),'');assert.deepEqual(h.sent,[]);
});
test('C11 cross-tab data containing a token is ignored rather than imported',async()=>{
 const h=environment(),auth=await adapter(h.env);await auth.initialize();h.emit({type:'logout',token:jwt('other')});
 assert.equal(auth.subject(),'neon-user');assert.equal(await auth.getAccessToken(),jwt());
});
test('C11 absent cookie session is unauthenticated; provider outage is an error',async()=>{
 const h=environment();h.env.fetch=async()=>Response.json(null);const auth=await adapter(h.env);await auth.initialize();assert.equal(auth.subject(),'');
 const failed=environment();failed.env.fetch=async()=>Response.json({code:'UNAVAILABLE'},{status:503});await assert.rejects((await adapter(failed.env)).initialize());
});
test('C11 token metadata cannot change the cookie-authenticated subject',async()=>{
 const h=environment();h.env.fetch=async url=>String(url).endsWith('/get-session')?Response.json({session:{},user:{id:'neon-user'}}):Response.json({token:jwt('other')});
 const auth=await adapter(h.env);await assert.rejects(auth.initialize());assert.equal(auth.subject(),'');
});
test('C11 one renewal failure clears authentication and emits only invalidated',async()=>{
 const h=environment(),auth=await adapter(h.env);await auth.initialize();h.env.fetch=async()=>Response.json({code:'UNAUTHORIZED'},{status:401});
 await assert.rejects(auth.refreshAccessToken(jwt()));assert.equal(auth.subject(),'');assert.deepEqual(h.sent,[{type:'invalidated'}]);
});
test('C11 callback consumes a bounded transaction once and retains deep link',async()=>{
 const h=environment(),auth=await adapter(h.env),path='/app/outreach?workspace=A&project=P&locale=zh-HK';
 await auth.signIn(path);const tx=JSON.parse([...h.entries.values()][0]);assert.equal(tx.returnPath,path);assert.equal(Object.keys(tx).sort().join(','),'createdAt,returnPath,state');
 h.env.location.href=`https://app.example.test/auth/callback?state=${tx.state}`;await auth.completeCallback();assert.equal(auth.returnPath(),path);assert.equal(h.entries.size,0);
 await assert.rejects(auth.completeCallback());assert.equal(h.entries.size,0);
});
test('C11 foreign, stale or missing callback state cannot hydrate cookies',async()=>{
 for(const kind of ['foreign','stale','missing']){const h=environment(),auth=await adapter(h.env);await auth.signIn('/app');const tx=JSON.parse([...h.entries.values()][0]);
 h.env.location.href=`https://app.example.test/auth/callback${kind==='missing'?'':`?state=${kind==='foreign'?'foreign':tx.state}`}`;if(kind==='stale')h.clock(1_700_000);let calls=0;h.env.fetch=async()=>{calls++;throw Error('must not fetch');};
 await assert.rejects(auth.completeCallback());assert.equal(calls,0);}
});
for(const value of ['/app/../auth/callback','/app/%2e%2e/auth/callback','/app/%5cevil','/app\n','/application','//evil.test'])test('C11 same-site app return path refuses '+JSON.stringify(value),()=>assert.equal(normalizeReturnPath(value),'/app'));
test('C11 scope switch cancels a pending 401 renewal without retry or restoring state',async()=>{
 const session=new SessionScope({mode:'live'});session.setToken('old');session.next({actor:'user',workspace:'A'});const identity=session.identity(),wait=deferred();let fetches=0;
 const client=createLiveClient(async()=>{fetches++;return Response.json({code:'UNAUTHORIZED'},{status:401});},'',{refresh:async()=>{await wait.promise;return 'new';},isCurrent:scope=>session.isCurrent(scope)});
 const result=client.request({path:'/v1/workspaces/A',token:'old',scope:identity}).catch(e=>e);await new Promise(r=>setTimeout(r,0));session.next({workspace:'B'});wait.resolve();
 assert.ok(await result instanceof LiveCancelled);assert.equal(fetches,1);assert.equal(session.token(),'old');assert.equal(session.current().workspace,'B');
});
test('C11 only an authenticated explicit 401 is retried once; second 401 recovers login',async()=>{
 let fetches=0,refreshes=0,invalidations=0;const client=createLiveClient(async()=>{fetches++;return Response.json({code:'UNAUTHORIZED'},{status:401});},'',{refresh:async()=>{refreshes++;return 'new';},isCurrent:()=>true,onUnauthorized:()=>invalidations++});
 await assert.rejects(client.request({path:'/v1/research',method:'POST',token:'old',scope:'A',idempotencyKey:'same',body:{}}),e=>e.status===401);
 assert.equal(fetches,2);assert.equal(refreshes,1);assert.equal(invalidations,1);
 await assert.rejects(client.request({path:'/v1/read',scope:'A'}));assert.equal(fetches,3);assert.equal(refreshes,1);
});
for(const status of [202,403,409,503,'network'])test('C11 accepted/unknown/error '+status+' never refreshes or replays intent',async()=>{
 let calls=0,refreshes=0;const client=createLiveClient(async()=>{calls++;if(status==='network')throw Error('connection lost');return Response.json(status===202?{data_mode:'live',request_id:'r',data:{id:'accepted'}}:{code:'REJECTED'},{status:status==='network'?500:status});},'',{refresh:async()=>{refreshes++;return 'new';},isCurrent:()=>true});
 const request=client.request({path:'/v1/research',method:'POST',token:'old',scope:'A',body:{},idempotencyKey:'same'});if(status===202)assert.equal((await request).id,'accepted');else await assert.rejects(request);
 assert.equal(calls,1);assert.equal(refreshes,0);
});

test('C11 provider binding holds initializing until cookie hydration and never restores after scope change',async()=>{
 const {bindAuthSession}=await loadModule('services/live/auth-session.ts');
 const session=new SessionScope({mode:'live'}),h=environment(),wait=deferred();h.env.fetch=async url=>{await wait.promise;return String(url).endsWith('/token')?Response.json({token:jwt()}):Response.json({session:{},user:{id:'neon-user'}});};
 const auth=await adapter(h.env),binding=bindAuthSession(session,auth,createLiveClient());
 assert.equal(session.getSnapshot().authenticated,false);session.next({workspace:'B'});wait.resolve();await assert.rejects(binding.ready);
 assert.equal(session.current().actor,'');assert.equal(session.current().workspace,'B');binding.dispose();
});
test('C11 scope clear captures dirty buffer before token/actor/project disappear',()=>{
 const session=new SessionScope({mode:'live'});session.setToken('old');session.next({actor:'user',workspace:'A',project:'P'});let captured;
 session.subscribeBeforeClear(()=>{captured={scope:session.current(),token:session.token()};});session.setToken(undefined);
 assert.deepEqual(captured.scope,{mode:'live',actor:'user',workspace:'A',project:'P'});assert.equal(captured.token,'old');assert.equal(session.current().actor,'');
});
test('C11 a cancelled or failed dirty transition cannot sign out; changed scopes cannot proceed',async()=>{
 const session=new SessionScope({mode:'live'});session.setToken('old');session.next({actor:'user',workspace:'A'});let actions=0;
 const stop=session.registerTransitionGuard(async()=>false);assert.equal(await session.transition(async()=>actions++),false);assert.equal(actions,0);stop();
 const wait=deferred(),stop2=session.registerTransitionGuard(async proceed=>{await wait.promise;await proceed();return true;});
 const transition=session.transition(async()=>actions++).catch(e=>e);session.next({workspace:'B'});wait.resolve();assert.ok(await transition instanceof LiveCancelled);assert.equal(actions,0);stop2();
});
test('C11 retained draft requires exact authenticated actor, workspace, project and draft after server read',async()=>{
 const {DraftRecovery}=await loadModule('services/live/draft-recovery.ts'),h=environment(),recovery=new DraftRecovery(h.env.storage);
 const buffer={actor:'user',workspace:'A',project:'P',draftId:'draft',revisionId:'r1',version:3,subject:'Unsaved subject',body:'Unsaved text',language:'en'};
 assert.equal(recovery.hasRetained(),false);
 recovery.retain(buffer);const afterReload=new DraftRecovery(h.env.storage);
 assert.equal(recovery.hasRetained(),true);assert.equal(afterReload.hasRetained(),true);
 for(const changed of [{actor:'other'},{workspace:'B'},{project:'Q'},{draftId:'other'}])assert.equal(afterReload.find({...buffer,...changed}),null);
 assert.deepEqual(afterReload.find(buffer),buffer);assert.deepEqual(afterReload.find({...buffer,version:4,revisionId:'r2'}),buffer);
 assert.equal([...h.entries.values()].some(value=>value.includes(jwt())),false);afterReload.forget(buffer);assert.equal(afterReload.find(buffer),null);assert.equal(afterReload.hasRetained(),false);
});
test('C11 OAuth verifier is forwarded only to cookie exchange and never saved or broadcast',async()=>{
 const h=environment(),auth=await adapter(h.env);await auth.signIn('/app');const tx=JSON.parse([...h.entries.values()][0]);
 h.env.location.href=`https://app.example.test/auth/callback?state=${tx.state}&neon_auth_session_verifier=opaque-verifier`;const urls=[];
 h.env.fetch=async url=>{urls.push(url);return String(url).startsWith('/api/auth/get-session')?Response.json({session:{},user:{id:'neon-user'}}):Response.json({token:jwt()});};
 await auth.completeCallback();assert.deepEqual(urls,['/api/auth/get-session?neon_auth_session_verifier=opaque-verifier','/api/auth/token']);assert.equal(h.entries.size,0);assert.equal(h.sent.length,0);
});
test('C11 cookie sign-in email uses validated same-origin callback and does not retain password',async()=>{
 const h=environment(),auth=await adapter(h.env);await auth.signIn('/app?workspace=A');let call;
 h.env.fetch=async(url,init)=>{call={url,body:JSON.parse(init.body),credentials:init.credentials};return Response.json({redirect:false,user:{id:'neon-user'},token:'opaque-cookie'});};
 await auth.signInEmail(' synthetic@example.test ','private-password');assert.equal(call.url,'/api/auth/sign-in/email');assert.equal(call.body.email,'synthetic@example.test');assert.equal(call.credentials,'same-origin');
 const callback=new URL(call.body.callbackURL);assert.equal(callback.origin,h.env.location.origin);assert.equal(callback.pathname,'/auth/callback');assert.ok(callback.searchParams.get('state'));
 assert.equal([...h.entries.values()].some(value=>value.includes('private-password')),false);assert.equal(h.sent.length,0);
});
test('C11 write without an intent key is not automatically replayed on 401',async()=>{
 let calls=0,refresh=0;const client=createLiveClient(async()=>{calls++;return Response.json({code:'UNAUTHORIZED'},{status:401});},'',{refresh:async()=>{refresh++;return 'new';},isCurrent:()=>true});
 await assert.rejects(client.request({path:'/v1/write',method:'POST',token:'old',scope:'A',body:{}}));assert.equal(calls,1);assert.equal(refresh,0);
});

test('C11 callback cannot restore a captured identity after logout or scope change',async()=>{
 const {completeSessionCallback}=await loadModule('services/live/auth-session.ts');
 for(const change of ['logout','scope']){const session=new SessionScope({mode:'live'});session.setToken('old');session.next({actor:'old-user',workspace:'A',project:'P'});const wait=deferred();
 const auth={completeCallback:async()=>wait.promise,getAccessToken:async()=>jwt(),subject:()=> 'neon-user',returnPath:()=>'/app?workspace=A'};
 const result=completeSessionCallback(auth,session).catch(e=>e);if(change==='logout')session.setToken(undefined);else session.next({workspace:'B'});wait.resolve();
 assert.ok(await result instanceof LiveCancelled);assert.equal(session.current().actor,change==='logout'?'':'old-user');assert.equal(session.current().workspace,change==='logout'?null:'B');}
});
test('C11 recovery capacity or storage failure keeps every dirty buffer in memory without eviction',async()=>{
 const {DraftRecovery}=await loadModule('services/live/draft-recovery.ts');const recovery=new DraftRecovery({getItem:()=>null,setItem(){throw Error('quota');},removeItem(){}});
 for(let i=0;i<10;i++){const buffer={actor:'user',workspace:'A',project:'P',draftId:'draft-'+i,revisionId:'r1',version:1,subject:'subject',body:'private text '+i,language:'en'};assert.equal(recovery.retain(buffer),false);}
 for(let i=0;i<10;i++)assert.equal(recovery.find({actor:'user',workspace:'A',project:'P',draftId:'draft-'+i}).body,'private text '+i);
});
test('C11 explicit public provider config cannot reveal secrets or fall back from invalid Neon to Auth0',async()=>{
 const {loadPublicAuth}=await loadModule('lib/auth/public-auth.ts'),url='https://ep-owned.neonauth.us-east-2.aws.neon.tech/neondb/auth';
 const env={NODE_ENV:'production',VERCEL_ENV:'preview',BUYEROS_AUTH_PROVIDER:'neon',BUYEROS_NEON_AUTH_ROUTE_ENABLED:'1',BUYEROS_NEON_ENVIRONMENT:'preview',BUYEROS_NEON_AUTH_URL:url,BUYEROS_NEON_EXPECTED_AUTH_URL:url,BUYEROS_PUBLIC_ORIGIN:'https://app.example.test',BUYEROS_NEON_EXPECTED_PUBLIC_ORIGIN:'https://app.example.test',BUYEROS_NEON_COOKIE_SECRET:'PRIVATE_CANARY_DO_NOT_SERIALIZE_'.repeat(2),BUYEROS_AUTH0_ISSUER:'https://legacy.example.test/',BUYEROS_AUTH0_CLIENT_ID:'legacy',BUYEROS_AUTH0_AUDIENCE:'legacy'};
 assert.deepEqual(loadPublicAuth(env),{provider:'neon',config:{authPath:'/api/auth',socialInitOrigin:'https://ep-owned.neonauth.us-east-2.aws.neon.tech',socialInitPath:'/neondb/auth/sign-in/social/init'}});
 for(const wrong of [{BUYEROS_NEON_AUTH_ROUTE_ENABLED:'0'},{BUYEROS_NEON_EXPECTED_AUTH_URL:'https://other.neon.tech/auth'},{BUYEROS_AUTH_PROVIDER:'unknown'}]){const value=loadPublicAuth({...env,...wrong});assert.equal(value.provider,'unavailable');assert.doesNotMatch(JSON.stringify(value),/PRIVATE_CANARY|legacy/);}
 assert.equal(loadPublicAuth({...env,BUYEROS_AUTH_PROVIDER:undefined}).provider,'neon');
 assert.equal(loadPublicAuth({...env,BUYEROS_AUTH_PROVIDER:''}).provider,'neon');
 const abandoned=loadPublicAuth({...env,BUYEROS_AUTH_PROVIDER:'auth0',BUYEROS_AUTH0_ISSUER:'https://dev-oaug20cdxqqgn1s8.us.auth0.com/',BUYEROS_AUTH0_CLIENT_ID:'public',BUYEROS_AUTH0_AUDIENCE:'https://buyer-os-nu.vercel.app/v1'});
 assert.equal(abandoned.provider,'unavailable');
 assert.doesNotMatch(JSON.stringify(abandoned),/auth0\.com|public|buyer-os-nu/);
});

test('C11 multipart retry freezes fields and intent without changing the original browser boundary',async()=>{
 const form=new FormData();form.append('name','original');const wait=deferred(),observed=[];let calls=0;
 const client=createLiveClient(async(url,init)=>{observed.push({body:init.body,fields:[...init.body.entries()],key:init.headers['Idempotency-Key'],type:init.headers['Content-Type']});calls++;return calls===1?Response.json({code:'UNAUTHORIZED'},{status:401}):Response.json({data_mode:'live',request_id:'r',data:{ok:true}});},'',{refresh:async()=>{await wait.promise;return 'new';},isCurrent:()=>true});
 const request=client.request({path:'/v1/upload',method:'POST',token:'old',scope:'A',formData:form,idempotencyKey:'upload-intent'});await new Promise(r=>setTimeout(r,0));form.set('name','changed');wait.resolve();await request;
 assert.equal(observed[0].body,form);assert.deepEqual(observed[1].fields,observed[0].fields);assert.equal(observed[0].key,observed[1].key);assert.equal(observed[0].type,undefined);assert.equal(observed[1].type,undefined);
});

test('C11 a callback consumer that unmounted cannot publish even with the same scope generation',async()=>{
 const {completeSessionCallback}=await loadModule('services/live/auth-session.ts'),session=new SessionScope({mode:'live'}),wait=deferred();let active=true;
 const auth={completeCallback:async()=>wait.promise,getAccessToken:async()=>jwt(),subject:()=> 'neon-user',returnPath:()=>'/app'};
 const result=completeSessionCallback(auth,session,()=>active).catch(e=>e);active=false;wait.resolve();assert.ok(await result instanceof LiveCancelled);assert.equal(session.current().actor,'');assert.equal(session.token(),undefined);
});

test('C11 failed provider logout remains invalidated on reload despite an old valid cookie',async()=>{
 const h=environment(),auth=await adapter(h.env);await auth.initialize();h.env.fetch=async()=>Response.json({code:'UNAVAILABLE'},{status:503});await assert.rejects(auth.signOut());
 let calls=0;h.env.fetch=async url=>{calls++;return String(url).endsWith('/get-session')?Response.json({session:{},user:{id:'neon-user'}}):Response.json({token:jwt()});};
 const reloaded=await adapter(h.env);await reloaded.initialize();assert.equal(reloaded.subject(),'');assert.equal(calls,0);assert.equal(JSON.stringify([...h.entries.values()]).includes(jwt()),false);
});
test('C11 received cross-tab invalidation persists through reload without a token marker',async()=>{
 const h=environment(),auth=await adapter(h.env);await auth.initialize();h.emit({type:'logout'});const reloaded=await adapter(h.env);await reloaded.initialize();assert.equal(reloaded.subject(),'');assert.equal(JSON.stringify([...h.entries.values()]).includes(jwt()),false);
});

test('account email is visible only after a matching session token and never persisted or broadcast',async()=>{
 const h=environment(),auth=await adapter(h.env),wait=deferred();
 h.env.fetch=async url=>String(url).endsWith('/get-session')
  ?Response.json({session:{},user:{id:'neon-user',email:'buyer@example.test'}})
  :(await wait.promise,Response.json({token:jwt()}));
 const pending=auth.initialize();await new Promise(r=>setTimeout(r,0));
 assert.equal(auth.accountEmail?.(),'');wait.resolve();await pending;
 assert.equal(auth.accountEmail?.(),'buyer@example.test');assert.equal(h.entries.size,0);assert.deepEqual(h.sent,[]);
 h.emit({type:'logout'});assert.equal(auth.accountEmail?.(),'');
 assert.doesNotMatch(JSON.stringify([...h.entries,...h.sent]),/buyer@example\.test/);
});

test('failed identity validation never exposes another account email',async()=>{
 const h=environment(),auth=await adapter(h.env);
 h.env.fetch=async url=>String(url).endsWith('/get-session')
  ?Response.json({session:{},user:{id:'neon-user',email:'buyer@example.test'}})
  :Response.json({token:jwt('other')});
 await assert.rejects(auth.initialize());assert.equal(auth.accountEmail?.(),'');
});

test('missing or malformed account email does not prevent valid session authentication',async()=>{
 for(const email of [undefined,{},'buyer\n@example.test','x'.repeat(321)]){
  const h=environment(),auth=await adapter(h.env);
  h.env.fetch=async url=>String(url).endsWith('/get-session')
   ?Response.json({session:{},user:{id:'neon-user',email}}):Response.json({token:jwt()});
  await auth.initialize();assert.equal(auth.subject(),'neon-user');assert.equal(auth.accountEmail?.(),'');
 }
});

test('Google sign-in always offers account selection and preserves the provider transaction',async()=>{
 for(const [existing,expected] of [[null,'select_account'],['consent','consent select_account'],['none','select_account'],['consent select_account','consent select_account']]){
  const h=environment(),auth=await adapter(h.env);await auth.signIn('/app?workspace=A');
  const tx=JSON.parse(h.entries.get('buyeros-neon-return'));
  const providerUrl=new URL('https://accounts.google.com/o/oauth2/v2/auth?client_id=fixture-client&response_type=code&scope=openid+email&state=opaque-provider-state&nonce=opaque-provider-nonce&code_challenge=opaque-pkce&redirect_uri=https%3A%2F%2Fprovider.example.test%2Fcallback');
  if(existing)providerUrl.searchParams.set('prompt',existing);
  h.env.fetch=async(url,init)=>{
   assert.equal(url,'/api/auth/sign-in/social');
   assert.deepEqual(JSON.parse(init.body),{provider:'google',callbackURL:`https://app.example.test/auth/callback?state=${tx.state}`,disableRedirect:true});
   return Response.json({url:providerUrl.href});
  };
  await auth.signInGoogle();const redirect=new URL(h.env.location.href);
  assert.equal(redirect.searchParams.get('prompt'),expected);
  redirect.searchParams.delete('prompt');providerUrl.searchParams.delete('prompt');
  assert.equal(redirect.href,providerUrl.href);
  assert.equal(h.entries.get('buyeros-neon-return'),JSON.stringify(tx));
 }
});

test('Google sign-in accepts the exact trusted branch social-init URL without changing its opaque token',async()=>{
 const h=environment(),auth=await adapter(h.env);await auth.signIn('/app');
 const returned=`${trustedSocialInitOrigin}${trustedSocialInitPath}?token=synthetic-opaque-token`;
 h.env.fetch=async(url,init)=>{
  assert.equal(url,'/api/auth/sign-in/social');
  assert.equal(JSON.parse(init.body).provider,'google');
  return Response.json({redirect:false,url:returned});
 };
 await auth.signInGoogle();
 assert.equal(h.env.location.href,returned);
});

test('Google sign-in rejects untrusted social-init redirects before navigation',async()=>{
 const base=`${trustedSocialInitOrigin}${trustedSocialInitPath}`;
 const candidates=[
  `https://ep-other.neonauth.us-east-2.aws.neon.tech${trustedSocialInitPath}?token=synthetic`,
  `https://ep-owned.neonauth.us-east-2.aws.neon.tech.evil.test${trustedSocialInitPath}?token=synthetic`,
  `http://ep-owned.neonauth.us-east-2.aws.neon.tech${trustedSocialInitPath}?token=synthetic`,
  `https://synthetic-user@ep-owned.neonauth.us-east-2.aws.neon.tech${trustedSocialInitPath}?token=synthetic`,
  `https://ep-owned.neonauth.us-east-2.aws.neon.tech:8443${trustedSocialInitPath}?token=synthetic`,
  `${base}/extra?token=synthetic`,
  `${base}/?token=synthetic`,
  `${base}?token=synthetic#fragment`,
  `${base}/%2e%2e/init?token=synthetic`,
  `${base}?token=`,
  `${base}?token=%20%20`,
  `${base}?token=opaque${String.fromCharCode(32)}value`,
  `${base}?token=first&token=second`,
  `${base}?token=opaque${String.fromCharCode(0)}value`,
  `${base}?token=opaque&extra=synthetic`,
  `${base}?%74oken=synthetic`,
  'https://accounts.google.com/o/oauth2/v2/auth?state=synthetic#fragment',
  'http://accounts.google.com/o/oauth2/v2/auth?state=synthetic',
  'https://synthetic-user@accounts.google.com/o/oauth2/v2/auth?state=synthetic',
  'https://accounts.google.com:8443/o/oauth2/v2/auth?state=synthetic',
 ];
 for(const returned of candidates){
  const h=environment(),auth=await adapter(h.env);await auth.signIn('/app');
  const before=h.env.location.href;
  h.env.fetch=async()=>Response.json({url:returned});
  await assert.rejects(auth.signInGoogle(),error=>{
   assert.equal(error.message,'Invalid Google redirect');
   assert.doesNotMatch(error.message,/synthetic|first|second/);
   return true;
  },`accepted synthetic redirect ${returned}`);
  assert.equal(h.env.location.href,before);
 }
});

test('T21-01 failed social transport exposes only a bounded category, status and UUID correlation',async()=>{
 const {neonSignInDiagnostic}=await loadModule('services/live/neon-auth.ts');
 for(const requestId of ['12345678-1234-4234-8234-123456789abc','synthetic-opaque-header-not-a-correlation']){
  const h=environment(),auth=await adapter(h.env);await auth.signIn('/app');
  h.env.fetch=async()=>Response.json({message:'synthetic-private-response-must-not-be-shown'},{status:503,headers:{'x-request-id':requestId}});
  let captured;try{await auth.signInGoogle();}catch(error){captured=error;}
  assert.deepEqual(neonSignInDiagnostic(captured),{category:'service_response',http_status:503,
   request_id:requestId.startsWith('1234')?requestId:null,reason:'service'});
  assert.doesNotMatch(JSON.stringify(neonSignInDiagnostic(captured)),/opaque|private-response/);
 }
});

test('sign-in failures name what failed and never copy the provider body',async()=>{
 const {neonSignInDiagnostic}=await loadModule('services/live/neon-auth.ts');
 const {describeSignInFailure,signInFailureCopy,signInReasons,signInFailureMessage}=await loadModule('services/live/sign-in-failure.ts');
 for(const reason of signInReasons){
  const row=signInFailureCopy[reason];
  assert.match(row.en,/^Sign-in failed\./);
  assert.match(row['zh-HK'],/登入失敗/);
  assert.notEqual(row.en,row['zh-HK']);
  assert.equal(signInFailureMessage(reason,'en'),row.en);
  assert.equal(signInFailureMessage(reason,'zh-HK'),row['zh-HK']);
  if(reason==='callback'||reason==='session')assert.match(row.en,/Sign-in failed\. Please start again\./);
 }
 const cases=[
  [401,{code:'INVALID_PASSWORD',message:'synthetic-private-response'},'wrong_password'],
  [401,{code:'USER_NOT_FOUND',message:'opaque-email'},'unknown_email'],
  [401,{code:'USER_EMAIL_NOT_FOUND',message:'opaque'},'unknown_email'],
  [401,{code:'INVALID_CREDENTIALS',message:'opaque'},'credentials'],
  [401,{code:'INVALID_EMAIL_OR_PASSWORD',message:'opaque'},'credentials'],
  [401,{message:'opaque-unspecified'},'credentials'],
  [400,{code:'INVALID_EMAIL',message:'opaque'},'invalid_email'],
  [400,{message:'not-a-code'},'validation'],
  [422,{code:'PASSWORD_TOO_SHORT',message:'opaque'},'validation'],
  [403,{code:'AUTH_FORBIDDEN',message:'opaque'},'forbidden'],
  [404,{message:'opaque'},'service'],
  [429,{message:'opaque'},'rate_limited'],
  [503,{code:'not-allow-listed',message:'synthetic-private-response'},'service'],
  [401,{code:'EMAIL_NOT_VERIFIED',message:'opaque'},'unverified_email'],
  [401,{code:'CREDENTIAL_ACCOUNT_NOT_FOUND',message:'opaque'},'social_only'],
 ];
 for(const [status,body,reason] of cases){
  const h=environment(),auth=await adapter(h.env);await auth.signIn('/app');
  h.env.fetch=async()=>Response.json(body,{status});
  let captured;try{await auth.signInEmail('synthetic@example.test','secret-value');}catch(error){captured=error;}
  const diagnostic=neonSignInDiagnostic(captured);
  assert.equal(diagnostic.reason,reason,JSON.stringify(body));
  assert.equal(describeSignInFailure(captured),reason);
  assert.equal(diagnostic.category,'service_response');
  assert.equal(diagnostic.http_status,status);
  const encoded=JSON.stringify(diagnostic)+signInFailureCopy[reason].en+signInFailureCopy[reason]['zh-HK'];
  assert.doesNotMatch(encoded,/opaque|private-response|secret-value|not-allow-listed/);
 }
 const network=environment(),networkAuth=await adapter(network.env);await networkAuth.signIn('/app');
 network.env.fetch=async()=>{throw new TypeError('Failed to fetch');};
 let networkError;try{await networkAuth.signInEmail('synthetic@example.test','secret-value');}catch(error){networkError=error;}
 assert.equal(neonSignInDiagnostic(networkError).reason,'network');
 assert.equal(neonSignInDiagnostic(networkError).category,'session_or_transport');
 let validationError;try{await (await adapter(environment().env)).signInEmail('   ','x');}catch(error){validationError=error;}
 assert.equal(describeSignInFailure(validationError),'validation');
 assert.equal(describeSignInFailure(new Error('Invalid Google redirect')),'google_redirect');
 assert.equal(neonSignInDiagnostic(new Error('Invalid Google redirect')).category,'redirect_validation');
 assert.equal(describeSignInFailure(new Error('Start sign-in again')),'stale_transaction');
 assert.equal(describeSignInFailure(new Error('OIDC state mismatch')),'callback');
 assert.equal(describeSignInFailure(new Error('OIDC keys unavailable')),'service');
 assert.equal(describeSignInFailure(new Error('OIDC token exchange failed'),'callback'),'service');
 assert.equal(describeSignInFailure(new Error('Sign-in did not create a session')),'session');
});

test('callback and Google HTTP failures never use credential-form copy',async()=>{
 const {describeSignInFailure,reasonForHttp,signInFailureMessage}=await loadModule('services/live/sign-in-failure.ts');
 const cases=[
  [400,'INVALID_EMAIL','session','google_sign_in'],
  [401,'INVALID_PASSWORD','session','google_sign_in'],
  [401,'USER_NOT_FOUND','session','google_sign_in'],
  [401,'INVALID_CREDENTIALS','session','google_sign_in'],
  [401,'INVALID_EMAIL_OR_PASSWORD','session','google_sign_in'],
  [401,null,'session','google_sign_in'],
  [422,'PASSWORD_TOO_SHORT','session','google_sign_in'],
  [422,'PASSWORD_TOO_LONG','session','google_sign_in'],
  [401,'EMAIL_NOT_VERIFIED','session','google_sign_in'],
  [401,'CREDENTIAL_ACCOUNT_NOT_FOUND','session','google_sign_in'],
  [404,null,'session','google_sign_in'],
  [503,'INVALID_PASSWORD','service','service'],
  [503,'FAILED_TO_CREATE_SESSION','service','service'],
  [429,null,'rate_limited','rate_limited'],
  [403,'AUTH_FORBIDDEN','forbidden','forbidden'],
 ];
 for(const context of ['callback','google']){
  for(const [status,code,callbackReason,googleReason] of cases){
   const h=environment(),auth=await adapter(h.env);await auth.signIn('/app');
   if(context==='callback'){
    const tx=JSON.parse(h.entries.get('buyeros-neon-return'));
    h.env.location.href=`https://app.example.test/auth/callback?state=${tx.state}`;
   }
   h.env.fetch=async()=>Response.json({code,message:'synthetic-private-response'},{status});
   let captured;
   try{await (context==='callback'?auth.completeCallback():auth.signInGoogle());}catch(error){captured=error;}
   const reason=describeSignInFailure(captured,context);
   const expected=context==='google'?googleReason:callbackReason;
   assert.equal(reason,expected,`${context} HTTP ${status} ${code}`);
   assert.equal(reasonForHttp(status,code,context),expected);
   for(const locale of ['en','zh-HK']){
    const copy=signInFailureMessage(reason,locale);
    assert.doesNotMatch(copy,/password|email above|密碼|上方電郵|synthetic-private-response/i);
   }
  }
  for(const error of [new Error('Start sign-in again'),new Error('Sign-in did not create a session')]){
   for(const locale of ['en','zh-HK']){
    assert.doesNotMatch(signInFailureMessage(describeSignInFailure(error,context),locale),/password|密碼/i);
   }
  }
 }
});
