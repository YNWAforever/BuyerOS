import {loadNeonConfig} from './neon-config';
import type {AuthConfig} from '../../services/live/auth';
import type {PublicNeonConfig} from '../../services/live/neon-auth';
export type PublicAuth = {provider:'auth0';config:AuthConfig|null} | {provider:'neon';config:PublicNeonConfig} | {provider:'unavailable';message:string};
/** Server selects one explicit provider. Only public config crosses the RSC boundary. */
export function loadPublicAuth(env:Record<string,string|undefined>):PublicAuth {
  const provider=env.BUYEROS_AUTH_PROVIDER??'auth0';
  if(provider==='auth0')return {provider,config:env.BUYEROS_AUTH0_ISSUER&&env.BUYEROS_AUTH0_CLIENT_ID&&env.BUYEROS_AUTH0_AUDIENCE
    ?{issuer:env.BUYEROS_AUTH0_ISSUER,clientId:env.BUYEROS_AUTH0_CLIENT_ID,audience:env.BUYEROS_AUTH0_AUDIENCE}:null};
  if(provider==='neon'){
    try {
      if(env.BUYEROS_NEON_AUTH_ROUTE_ENABLED!=='1')throw Error('closed');
      const auth=loadNeonConfig(env),base=new URL(auth.authUrl);
      return {provider,config:{
        authPath:'/api/auth',
        socialInitOrigin:base.origin,
        socialInitPath:base.pathname.replace(/\/+$/,'')+'/sign-in/social/init',
      }};
    }
    catch {return {provider:'unavailable',message:'Neon sign-in configuration is unavailable. Ask an administrator to restore sign-in.'};}
  }
  return {provider:'unavailable',message:'Sign-in provider configuration is unavailable. Ask an administrator to restore sign-in.'};
}
