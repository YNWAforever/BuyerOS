/** Server configuration only. Expected values come from the reviewed environment target;
 * they are independent bindings, never inferred from a callback, token or request host. */
export interface NeonConfig {readonly authUrl:string;readonly publicOrigin:string;readonly cookieSecret:string}
type Environment=Record<string,string|undefined>;
function invalid():never {throw new Error('Neon server configuration is unavailable');}
function required(env:Environment,name:string):string {
  const value=env[name];if(typeof value!=='string'||!value||value!==value.trim()||/[\u0000-\u001f\u007f]/.test(value))return invalid();return value;
}
function url(value:string):URL {
  let result:URL;try{result=new URL(value);}catch{return invalid();}
  if(result.username||result.password||result.search||result.hash)return invalid();return result;
}
export function loadNeonConfig(env:Environment):NeonConfig {
  if(typeof window!=='undefined')return invalid();
  const environment=required(env,'BUYEROS_NEON_ENVIRONMENT');
  if(!['local','preview','production'].includes(environment))return invalid();
  if(environment==='local'){
    if(!['development','test'].includes(env.NODE_ENV??'')||env.VERCEL_ENV&&env.VERCEL_ENV!=='development')return invalid();
  }else{
    if(env.NODE_ENV!=='production'||env.VERCEL_ENV&&env.VERCEL_ENV!==environment)return invalid();
  }
  if(Object.entries(env).some(([name,value])=>name.startsWith('BUYEROS_NEON_FIXTURE')&&value&&value!=='0')||
    env.BUYEROS_NEON_TEST_EMAIL||env.BUYEROS_NEON_TEST_PASSWORD)return invalid();
  const authUrl=required(env,'BUYEROS_NEON_AUTH_URL'),publicOrigin=required(env,'BUYEROS_PUBLIC_ORIGIN'),cookieSecret=required(env,'BUYEROS_NEON_COOKIE_SECRET');
  if(authUrl!==required(env,'BUYEROS_NEON_EXPECTED_AUTH_URL')||publicOrigin!==required(env,'BUYEROS_NEON_EXPECTED_PUBLIC_ORIGIN'))return invalid();
  const auth=url(authUrl),origin=url(publicOrigin);
  if(auth.protocol!=='https:'||!auth.hostname.endsWith('.neon.tech')||auth.port||auth.pathname==='/'||auth.href!==authUrl)return invalid();
  if(origin.origin!==publicOrigin||origin.pathname!=='/'||origin.port&&environment!=='local')return invalid();
  if(origin.protocol!=='https:'&&!(environment==='local'&&origin.protocol==='http:'&&['localhost','127.0.0.1','[::1]'].includes(origin.hostname)))return invalid();
  if(cookieSecret.length<32||cookieSecret.length>8192)return invalid();
  return Object.freeze({authUrl,publicOrigin,cookieSecret});
}
