import test from 'node:test';
import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';
const {createNeonAuthAdapter}=await loadModule('services/live/neon-auth.ts');
function fixture(){
 const entries=new Map(),calls=[],location={origin:'https://app.example.test',href:'https://app.example.test/auth/sign-in?state=old-link',assign(url){this.href=new URL(url,this.origin).href;}};
 const env={location,crypto,now:()=>1_000_000,storage:{getItem:k=>entries.get(k)??null,setItem:(k,v)=>entries.set(k,v),removeItem:k=>entries.delete(k)},fetch:async(url,init)=>{calls.push({url,...init,body:JSON.parse(init.body)});return Response.json({token:null,user:{id:'synthetic'}});}};
 const auth=createNeonAuthAdapter({authPath:'/api/auth',socialInitOrigin:'https://ep-fixture.neonauth.us-east-2.aws.neon.tech',socialInitPath:'/neondb/auth/sign-in/social/init'},env);
 return {auth,env,entries,calls,location};
}
test('unverified signup stays on code entry even when the provider creates a cookie session',async()=>{
 const f=fixture();f.env.fetch=async()=>Response.json({token:'fixture-session',user:{emailVerified:false}});
 assert.equal(await f.auth.signUpEmail('Buyer','buyer@example.test','fixture-password'),'verify-email');
 assert.equal(f.entries.size,0);assert.equal(f.location.href,'https://app.example.test/auth/sign-in?state=old-link');
});
test('email code verification posts only the email and code without storing either',async()=>{
 const f=fixture();await f.auth.verifyEmailCode(' buyer@example.test ',' 123456 ');
 assert.equal(f.calls[0].url,'/api/auth/email-otp/verify-email');
 assert.deepEqual(f.calls[0].body,{email:'buyer@example.test',otp:'123456'});
 assert.equal(f.entries.size,0);assert.equal(f.auth.subject(),'');
});
test('malformed verification codes never reach the provider',async()=>{
 const f=fixture();for(const code of ['', '12345', '1234567', 'abcdef'])await assert.rejects(f.auth.verifyEmailCode('buyer@example.test',code));
 assert.equal(f.calls.length,0);
});
test('direct or expired sign-in creates a fresh local transaction; callback still rejects foreign state',async()=>{
 for(const stored of [null,'invalid JSON',JSON.stringify({state:crypto.randomUUID(),returnPath:'/app?workspace=old',createdAt:1})]){
  const f=fixture();if(stored)f.entries.set('buyeros-neon-return',stored);
  await f.auth.signInEmail('buyer@example.test','synthetic-password');
  const tx=JSON.parse(f.entries.get('buyeros-neon-return'));
  assert.equal(tx.returnPath,'/app');assert.notEqual(tx.state,'old-link');assert.equal(f.calls.length,1);
  assert.equal(f.calls[0].body.callbackURL,`https://app.example.test/auth/callback?state=${tx.state}`);
  f.location.href='https://app.example.test/auth/callback?state=foreign';
  await assert.rejects(f.auth.completeCallback());assert.equal(f.calls.length,1);
 }
});
test('registration uses the auth owner only and waits for email verification without storing credentials',async()=>{
 const f=fixture();assert.equal(await f.auth.signUpEmail(' New buyer ',' buyer@example.test ','synthetic-password'),'verify-email');
 assert.equal(f.calls[0].url,'/api/auth/sign-up/email');
 assert.deepEqual(f.calls[0].body,{name:'New buyer',email:'buyer@example.test',password:'synthetic-password',callbackURL:'https://app.example.test/auth/sign-in?verified=1'});
 assert.equal(f.entries.size,0);assert.equal(f.auth.subject(),'');
 assert.equal(f.calls[0].credentials,'same-origin');assert.equal(f.calls[0].redirect,'error');
});
test('auto-session registration uses a fresh bounded callback without granting membership',async()=>{
 const f=fixture();f.env.fetch=async()=>Response.json({token:'ephemeral-provider-token'});
 assert.equal(await f.auth.signUpEmail('Buyer','buyer@example.test','synthetic-password'),'signed-in');
 assert.match(f.location.href,/\/auth\/callback\?state=/);assert.equal(f.auth.subject(),'');
 assert.doesNotMatch(JSON.stringify([...f.entries]),/synthetic-password|provider-token|buyer@example/);
});
test('password recovery works without a sign-in transaction and fixes the redirect origin',async()=>{
 const f=fixture();await f.auth.requestPasswordReset(' buyer@example.test ');
 assert.equal(f.calls[0].url,'/api/auth/request-password-reset');
 assert.deepEqual(f.calls[0].body,{email:'buyer@example.test',redirectTo:'https://app.example.test/auth/reset-password'});
 assert.equal(f.entries.size,0);assert.equal(f.calls.length,1);
});
test('reset posts a token once, clears local authentication, and never persists the token/password',async()=>{
 const f=fixture();await f.auth.resetPassword('synthetic-reset-token','synthetic-new-password');
 assert.equal(f.calls[0].url,'/api/auth/reset-password');
 assert.deepEqual(f.calls[0].body,{token:'synthetic-reset-token',newPassword:'synthetic-new-password'});
 assert.doesNotMatch(JSON.stringify([...f.entries]),/synthetic-reset-token|synthetic-new-password/);
 assert.equal(f.auth.subject(),'');
});
test('invalid reset and registration inputs never reach the provider',async()=>{
 const f=fixture();
 await assert.rejects(f.auth.resetPassword('', 'synthetic-password'));
 await assert.rejects(f.auth.resetPassword('token', 'short'));
 await assert.rejects(f.auth.signUpEmail('', 'buyer@example.test','synthetic-password'));
 await assert.rejects(f.auth.requestPasswordReset('not an email'));
 assert.equal(f.calls.length,0);
});
test('verification resend uses a stable sign-in destination, never a cross-tab callback state',async()=>{
 const f=fixture();await f.auth.sendVerificationEmail('buyer@example.test');
 assert.deepEqual(f.calls[0].body,{email:'buyer@example.test',callbackURL:'https://app.example.test/auth/sign-in?verified=1'});
 assert.equal(f.calls[0].url,'/api/auth/send-verification-email');assert.equal(f.entries.size,0);
});
