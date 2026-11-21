/** Server configuration only. Expected values come from the reviewed environment target;
 * they are independent bindings, never inferred from a callback, token or request host. */
export interface NeonConfig {readonly authUrl:string;readonly publicOrigin:string;readonly cookieSecret:string;readonly stagedOrigin?:string;readonly qaPreviewOrigin?:string}
type Environment=Record<string,string|undefined>;
function invalid():never {throw new Error('Neon server configuration is unavailable');}
function required(env:Environment,name:string):string {
  const value=env[name];if(typeof value!=='string'||!value||value!==value.trim()||/[\u0000-\u001f\u007f]/.test(value))return invalid();return value;
}
function url(value:string):URL {
  let result:URL;try{result=new URL(value);}catch{return invalid();}
  if(result.username||result.password||result.search||result.hash)return invalid();return result;
}
const sourceSha=/^[0-9a-f]{40}$/,vercelHost=/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.vercel\.app$/;
const repo=/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/,repoId=/^[0-9]+$/,branch=/^[A-Za-z0-9._/-]{1,255}$/;
const projectId=/^prj_[A-Za-z0-9]+$/,teamId=/^team_[A-Za-z0-9]+$/;
function branchSafe(value:string):boolean {
  return branch.test(value)&&value.split('/').every(part=>part!==''&&part!=='.'&&part!=='..');
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
  let stagedOrigin:string|undefined,qaPreviewOrigin:string|undefined;
  const staging=env.BUYEROS_NEON_STAGED_ORIGIN_ENABLED;
  if(staging!==undefined&&staging!=='0'){
    if(staging!=='1'||environment!=='production'||env.NODE_ENV!=='production'||env.VERCEL_ENV!=='production'
      ||!sourceSha.test(env.BUYEROS_RUNTIME_SOURCE_SHA??''))return invalid();
    // Only the platform-injected deployment hostname is trusted. Never derive
    // this allowlist from Host, forwarded headers, or a request URL.
    const hostname=required(env,'VERCEL_URL');
    if(!vercelHost.test(hostname))return invalid();
    stagedOrigin='https://'+hostname;
  }
  const preview=env.BUYEROS_NEON_QA_PREVIEW_ORIGIN_ENABLED;
  if(preview!==undefined&&preview!==''&&preview!=='0'){
    // Narrow preview-only opt-in. Production staging keeps its original flag and
    // the two allowlists cannot be enabled together.
    if(preview!=='1'||environment!=='preview'||env.NODE_ENV!=='production'||env.VERCEL_ENV!=='preview'||stagedOrigin)return invalid();
    const expectedProject=required(env,'BUYEROS_QA_PREVIEW_PROJECT_ID');
    const expectedRepo=required(env,'BUYEROS_QA_PREVIEW_REPO');
    const expectedRepoId=required(env,'BUYEROS_QA_PREVIEW_REPO_ID');
    const expectedBranch=required(env,'BUYEROS_QA_PREVIEW_BRANCH');
    const expectedSource=required(env,'BUYEROS_RUNTIME_SOURCE_SHA');
    if(!projectId.test(expectedProject)||!repo.test(expectedRepo)||!repoId.test(expectedRepoId)
      ||!branchSafe(expectedBranch)||!sourceSha.test(expectedSource))return invalid();
    const [repoOwner,repoName]=expectedRepo.split('/');
    // These are platform-injected deployment facts, not request-host guesses.
    if(env.VERCEL_PROJECT_ID!==expectedProject||env.VERCEL_GIT_PROVIDER!=='github'
      ||env.VERCEL_GIT_REPO_OWNER!==repoOwner||env.VERCEL_GIT_REPO_SLUG!==repoName
      ||env.VERCEL_GIT_REPO_ID!==expectedRepoId||env.VERCEL_GIT_COMMIT_REF!==expectedBranch
      ||env.VERCEL_GIT_COMMIT_SHA!==expectedSource)return invalid();
    const expectedTeam=env.BUYEROS_QA_PREVIEW_TEAM_ID;
    if(expectedTeam!==undefined&&expectedTeam!==''&&(expectedTeam!==expectedTeam.trim()||!teamId.test(expectedTeam)||env.VERCEL_TEAM_ID!==expectedTeam))return invalid();
    const hostname=required(env,'VERCEL_URL');
    if(!vercelHost.test(hostname))return invalid();
    // Optional independent binding: when a deployment already knows the exact
    // immutable host, it must match the platform-injected VERCEL_URL exactly.
    const expectedOrigin=env.BUYEROS_QA_PREVIEW_EXPECTED_ORIGIN;
    if(expectedOrigin!==undefined&&expectedOrigin!==''&&expectedOrigin!=='https://'+hostname)return invalid();
    qaPreviewOrigin='https://'+hostname;
  }
  return Object.freeze({authUrl,publicOrigin,cookieSecret,...(stagedOrigin?{stagedOrigin}:{}),...(qaPreviewOrigin?{qaPreviewOrigin}:{})});
}
