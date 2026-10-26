import {loadNeonConfig} from './neon-config';
import type {PublicNeonConfig} from '../../services/live/neon-auth';
export type PublicAuth = {provider:'neon';config:PublicNeonConfig} | {provider:'unavailable';message:string};
const auth0Disabled='Auth0 sign-in is disabled. An administrator needs to finish Neon sign-in setup before anyone can sign in.';
/** Server selects Neon only. Auth0 settings never become a public redirect target. */
export function loadPublicAuth(env:Record<string,string|undefined>):PublicAuth {
  const provider=env.BUYEROS_AUTH_PROVIDER||'neon';
  if(provider==='auth0')return {provider:'unavailable',message:auth0Disabled};
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
