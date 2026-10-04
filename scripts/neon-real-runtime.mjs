/** N00 real-only runtime preparation; no HTTP/provider/identity/DB activity.
 * Import/factory creation reads no environment. Call only in an owned server
 * runtime after separately authorized target/readbacks and counted transport. */
import {createHash} from 'node:crypto';
import {validateRealTarget} from './neon-real-target.mjs';
const REQUIRED=['N00_REAL_TARGET_JSON','N00_TARGET_FINGERPRINT','NEON_AUTH_BASE_URL','NEON_AUTH_COOKIE_SECRET','N00_AUTH_ISSUER','N00_AUTH_AUDIENCE','N00_AUTH_JWKS_URL','N00_AUTH_ALGORITHM'];
function need(value,code){if(!value)throw new Error('N00_REAL_RUNTIME_'+code);}
export function readRealRuntimeConfiguration(env,now=Date.now()){
 need(env&&REQUIRED.every(key=>typeof env[key]==='string'&&env[key].length),'REQUIRED');
 need(env.N00_REAL_TARGET_JSON.length<=16*1024,'MANIFEST');let manifest;
 try{manifest=JSON.parse(env.N00_REAL_TARGET_JSON);}catch{throw new Error('N00_REAL_RUNTIME_MANIFEST');}
 const target=validateRealTarget(manifest,now);
 const tuple={NEON_AUTH_BASE_URL:target.auth.baseUrl,N00_AUTH_ISSUER:target.auth.issuer,N00_AUTH_AUDIENCE:target.auth.audience,N00_AUTH_JWKS_URL:target.auth.jwksUrl,N00_AUTH_ALGORITHM:'EdDSA',N00_TARGET_FINGERPRINT:target.fingerprint};
 need(Object.entries(tuple).every(([key,value])=>env[key]===value),'MISMATCH');
 if(!/^[a-zA-Z0-9_-]{43,128}$/.test(env.NEON_AUTH_COOKIE_SECRET))throw new Error('N00_REAL_COOKIE_SECRET');
 const cookies=Object.freeze({secret:env.NEON_AUTH_COOKIE_SECRET,sameSite:'lax',sessionDataTtl:300});
 return Object.freeze({sdk:Object.freeze({baseUrl:target.auth.baseUrl,cookies}),trust:Object.freeze({issuer:target.auth.issuer,audience:target.auth.audience,jwksUrl:target.auth.jwksUrl,algorithm:'EdDSA',keyType:'OKP',curve:'Ed25519'}),fingerprint:target.fingerprint,expiresAt:target.expiresAt,projectId:target.projectId,branchId:target.branchId,authId:target.authId});
}
export function createRealAuthRuntime({readEnvironment,createAuth,now=Date.now}){
 need(typeof readEnvironment==='function'&&typeof createAuth==='function'&&typeof now==='function','FACTORY');
 let instance,boundKey;
 function context(){
  const value=readRealRuntimeConfiguration(readEnvironment(),now());
  const key=createHash('sha256').update(value.fingerprint+'\0'+value.sdk.cookies.secret).digest('hex');
  need(!boundKey||boundKey===key,'CONTEXT_CHANGED');return {value,key};
 }
 return Object.freeze({
  getAuth(){
   const {value,key}=context();
   if(instance===undefined){try{instance=createAuth(value.sdk);need(instance!==undefined,'SDK_INIT');}catch{throw new Error('N00_REAL_RUNTIME_SDK_INIT');}boundKey=key;}
   return instance;
  },
  describe(){const {value}=context();return Object.freeze({fingerprint:value.fingerprint,expiresAt:value.expiresAt,projectId:value.projectId,branchId:value.branchId,authId:value.authId,trust:value.trust,external_verified:false});}
 });
}
