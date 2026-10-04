/** Managed OAuth model with a fictional user and Ed25519 keys; no real identity.
 * All auth paths are served behind createCountedAuthProxy. */
import {randomBytes,generateKeyPairSync,sign,createHmac} from 'node:crypto';
import {createOwnedAuthServer} from './neon-counted-proxy.mjs';
export function createFlowFixture(manifest) {
 const {privateKey,publicKey}=generateKeyPairSync('ed25519'),kid='fictional-flow-key';
 const jwk={...publicKey.export({format:'jwk'}),kid,alg:'EdDSA',use:'sig'};
 const stamp=new Date().toISOString(),user={id:'fictional-flow-user',name:'Fictional flow',email:'flow@fixture.invalid',emailVerified:false,createdAt:stamp,updatedAt:stamp};
 const session={id:'fictional-flow-session',userId:user.id,token:randomBytes(24).toString('base64url'),createdAt:stamp,updatedAt:stamp,expiresAt:new Date(Date.now()+3600000).toISOString()};
 let authenticated=false,rejectSignOutRedirect=false;const flows=new Map(),verifiers=new Map(),appOrigin='http://localhost:44890';
 const challengeName='__Secure-neon-auth.session_challenge';
 const sessionCookie=(value,maxAge=3600)=>'__Secure-neon-auth.session_token='+value+'; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age='+maxAge;
 const challengeCookie=(value,maxAge=300)=>challengeName+'='+value+'; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age='+maxAge;
 const value=(header,name)=>(header??'').split(';').map(v=>v.trim()).find(v=>v.startsWith(name+'='))?.slice(name.length+1);
 function token(kind='valid') {
  const now=Math.floor(Date.now()/1000),header={alg:kind==='wrong-algorithm'?'HS256':'EdDSA',kid:kind==='unknown-kid'?'fictional-unknown':kid,typ:'JWT'};
  const claims={sub:user.id,iss:kind==='wrong-issuer'?'https://wrong.fixture.invalid':manifest.auth.issuer,aud:kind==='wrong-audience'?'different':manifest.auth.audience,iat:now,exp:kind==='expired'?now-120:now+900};
  if(kind==='array-audience')claims.aud=[claims.aud];
  const message=[header,claims].map(v=>Buffer.from(JSON.stringify(v)).toString('base64url')).join('.');
  return message+'.'+(kind==='wrong-algorithm'?createHmac('sha256','fictional').update(message).digest():sign(null,Buffer.from(message),privateKey)).toString('base64url');
 }
 const server=createOwnedAuthServer(async(req,res)=>{
  const url=new URL(req.url,'http://127.0.0.1:44894'),path=url.pathname,active=authenticated&&value(req.headers.cookie,'__Secure-neon-auth.session_token')===session.token;
  res.setHeader('Content-Type','application/json');res.setHeader('Cache-Control','no-store');
  const fail=()=>{res.statusCode=401;res.end('{"code":"FICTIONAL_FLOW_REFUSED"}');};
  if(path==='/fixture/auth/jwks'){res.end(JSON.stringify({keys:[jwk]}));return;}
  if(path==='/fixture-token'){res.end(JSON.stringify({token:token(url.searchParams.get('kind')??'valid')}));return;}
  if(path==='/fixture/auth/sign-in/social'&&req.method==='POST'){
   let body='';for await(const chunk of req)body+=chunk;let input,callback;try{input=JSON.parse(body);callback=new URL(input.callbackURL);}catch{fail();return;}
   if(input.provider!=='google'||callback.origin!==appOrigin||callback.pathname!=='/compat/return'||req.headers.origin!==appOrigin||req.headers['x-neon-auth-middleware']!=='true'||flows.size>=50){fail();return;}
   const state=randomBytes(24).toString('base64url'),challenge=randomBytes(24).toString('base64url');
   flows.set(state,{challenge,callback:callback.href,expires:Date.now()+300000});authenticated=false;
   res.setHeader('Set-Cookie',challengeCookie(challenge));res.end(JSON.stringify({redirect:true,url:'http://127.0.0.1:44891/fixture/auth/callback/google?state='+state}));return;
  }
  if(path==='/fixture/auth/callback/google'){
   const state=url.searchParams.get('state'),flow=flows.get(state);flows.delete(state);if(!flow||flow.expires<=Date.now()){fail();return;}
   const verifier=randomBytes(24).toString('base64url');verifiers.set(verifier,flow);const callback=new URL(flow.callback);callback.searchParams.set('neon_auth_session_verifier',verifier);
   res.statusCode=302;res.setHeader('Location',callback.href);res.end();return;
  }
  if(path==='/fixture/auth/get-session'){
   if(url.searchParams.has('neon_auth_session_verifier')){
    const verifier=url.searchParams.get('neon_auth_session_verifier'),flow=verifiers.get(verifier);
    if(!flow||flow.expires<=Date.now()||value(req.headers.cookie,challengeName)!==flow.challenge||req.headers.origin!==appOrigin||req.headers['x-neon-auth-middleware']!=='true'){fail();return;}
    verifiers.delete(verifier);authenticated=true;res.setHeader('Set-Cookie',[sessionCookie(session.token),challengeCookie('',0)]);res.setHeader('set-auth-jwt',token());res.end(JSON.stringify({session,user}));return;
   }
   if(active)res.setHeader('set-auth-jwt',token());res.end(JSON.stringify(active?{session,user}:null));return;
  }
  if(path==='/fixture/auth/token'){if(!active){fail();return;}res.end(JSON.stringify({token:token()}));return;}
  if(path==='/fixture/auth/sign-out'&&req.method==='POST'){authenticated=false;if(rejectSignOutRedirect){rejectSignOutRedirect=false;res.statusCode=302;res.setHeader('Location','https://unapproved.fixture.invalid/committed-sign-out');res.end();return;}res.setHeader('Set-Cookie',sessionCookie('',0));res.end('{"success":true}');return;}
  res.statusCode=404;res.end('{"fixture_only":true}');
 });
 // This one-shot local fault never accepts an external target or creates identity.
 server.refuseNextSignOutRedirect=()=>{rejectSignOutRedirect=true;};
 return server;
}
