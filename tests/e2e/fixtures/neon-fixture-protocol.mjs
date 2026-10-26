// Browser-test protocol only. These values never reach a provider or authorize the API.
import {randomUUID} from 'node:crypto';
export const fixtureOrigin='http://localhost:5173';
export const fixtureOrigins=[fixtureOrigin,'http://127.0.0.1:5193','http://127.0.0.1:5195'];
const provider='https://ep-owned-browser.neonauth.us-east-2.aws.neon.tech/neondb/auth';
export const neonFixtureEnvironment={
  BUYEROS_AUTH_PROVIDER:'neon',BUYEROS_NEON_AUTH_ROUTE_ENABLED:'1',BUYEROS_NEON_ENVIRONMENT:'local',
  BUYEROS_NEON_AUTH_URL:provider,BUYEROS_NEON_EXPECTED_AUTH_URL:provider,
  BUYEROS_PUBLIC_ORIGIN:fixtureOrigin,BUYEROS_NEON_EXPECTED_PUBLIC_ORIGIN:fixtureOrigin,
  BUYEROS_NEON_COOKIE_SECRET:'OWNED_SYNTHETIC_COOKIE_SECRET_ONLY_'.repeat(2),
  BUYEROS_NEON_TEST_EMAIL:'',BUYEROS_NEON_TEST_PASSWORD:'',VERCEL_ENV:'development',
};
export function neonFixtureEnvironmentFor(origin){
  if(!fixtureOrigins.includes(origin))throw Error('owned loopback Neon fixture required');
  return {...neonFixtureEnvironment,BUYEROS_PUBLIC_ORIGIN:origin,BUYEROS_NEON_EXPECTED_PUBLIC_ORIGIN:origin};
}

export function createNeonFixtureProtocol({subject='fixture-reviewer',accessToken=subject,tokenSubject=subject,expiresInSeconds=900,origin=fixtureOrigin}={}){
  if(!fixtureOrigins.includes(origin))throw Error('owned loopback Neon fixture required');
  if(!/^[\w-]{1,255}$/.test(subject)||!accessToken||accessToken.length>255)throw Error('owned synthetic fixture actor required');
  const email=`${subject}@example.test`,password='synthetic-only',sessionCookie=`owned-neon-${randomUUID()}`;
  const encode=value=>Buffer.from(JSON.stringify(value)).toString('base64url');
  // The browser reads metadata only. This intentionally unsigned JWT is translated
  // to an existing fictional bearer before the owned API sees the request.
  const token=`${encode({alg:'none',typ:'JWT'})}.${encode({iss:'urn:buyeros:e2e',sub:tokenSubject,exp:Math.floor(Date.now()/1000)+expiresInSeconds,jti:randomUUID()})}.owned-fixture-only`;
  const user={id:subject,email,name:'Owned synthetic fixture',emailVerified:true};
  const response=(body,status=200,headers={})=>Response.json(body,{status,headers:{'cache-control':'no-store',...headers}});
  async function respond(request){
    const url=new URL(request.url);
    if(url.origin!==origin)throw Error('owned loopback Neon fixture required');
    const signedIn=(request.headers.get('cookie')??'').split(';').some(value=>value.trim()===`buyeros-owned-neon-fixture=${sessionCookie}`);
    switch(url.pathname){
      case '/api/auth/get-session':return response(signedIn?{session:{id:sessionCookie,userId:subject},user}:null);
      case '/api/auth/token':return signedIn?response({token}):response({code:'UNAUTHORIZED'},401);
      case '/api/auth/sign-in/email':{
        if(request.method!=='POST')return response({code:'METHOD_NOT_ALLOWED'},405);
        const body=await request.json();
        if(body.email!==email||body.password!==password)return response({code:'INVALID_CREDENTIALS'},401);
        const callback=new URL(body.callbackURL);
        if(callback.origin!==origin||callback.pathname!=='/auth/callback'||!callback.searchParams.get('state'))throw Error('owned callback required');
        return response({redirect:false,user},200,{'set-cookie':`buyeros-owned-neon-fixture=${sessionCookie}; Path=/; HttpOnly; SameSite=Lax`});
      }
      case '/api/auth/sign-out':return response({success:true},200,{'set-cookie':'buyeros-owned-neon-fixture=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0'});
      default:throw Error('unsupported owned Neon fixture protocol');
    }
  }
  return {email,password,token,respond,apiBearer:value=>value===token?accessToken:null};
}
