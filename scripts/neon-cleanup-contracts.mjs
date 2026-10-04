/** Unarmed Neon control-plane cleanup request/readback preparation.
 * No network, credentials, authorization grant or deletion executor lives here.
 * Managed Better Auth identity cleanup remains unverified; never assume the
 * documented users_sync endpoint deletes a Managed Better Auth identity. */
import {RealRunJournal} from './neon-real-preflight.mjs';
const API='https://console.neon.tech/api/v2';
const FRESH_MS=300000;
function need(value,code){if(!value)throw new Error('N00_CLEANUP_'+code);}
function object(value){return value!==null&&typeof value==='object'&&!Array.isArray(value);}
function time(value){
 need(typeof value==='string'&&/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,3})?Z$/.test(value),'TIME');
 const stamp=Date.parse(value);need(Number.isFinite(stamp),'TIME');
 // Reject rollover dates while accepting provider RFC3339 seconds or fractions.
 need(new Date(stamp).toISOString().slice(0,19)===value.slice(0,19),'TIME');return stamp;
}
function read(value,url,target,now){
 const keys=['method','url','status','body','receivedAt'];
 need(object(value)&&Object.keys(value).length===keys.length&&keys.every(k=>Object.hasOwn(value,k)),'READBACK');
 need(value.method==='GET'&&value.url===url&&value.status===200&&object(value.body),'READBACK');
 const received=time(value.receivedAt);need(received>=time(target.createdAt)&&received<=now&&now-received<=FRESH_MS,'FRESH_READBACK');
 return value.body;
}
export function planNeonCleanup({journal,projectRead,authRead,now=Date.now()}){
 need(journal instanceof RealRunJournal&&Number.isFinite(now),'JOURNAL');
 const state=journal.snapshot(),target=state.target;need(target,'BOUND_TARGET');
 need(/^[a-z0-9-]{1,60}$/.test(target.projectId)&&/^[a-z0-9-]{1,60}$/.test(target.branchId),'RESOURCE_ID');
 const projectUrl=API+'/projects/'+target.projectId,authUrl=projectUrl+'/branches/'+target.branchId+'/auth';
 const project=read(projectRead,projectUrl,target,now).project;
 need(object(project)&&project.id===target.projectId&&project.name===target.name&&project.region_id===target.regionId&&
  project.platform_id==='aws'&&project.owner_id===target.orgId&&(!Object.hasOwn(project,'org_id')||project.org_id===target.orgId),'PROJECT_READBACK');
 need(time(project.created_at)===time(target.createdAt),'PROJECT_READBACK');
 const auth=read(authRead,authUrl,target,now);
 need(auth.auth_provider==='better_auth'&&auth.auth_provider_project_id===target.authId&&auth.branch_id===target.branchId&&
  auth.owned_by==='neon'&&auth.jwks_url===target.auth.jwksUrl&&auth.base_url===target.auth.baseUrl,'AUTH_READBACK');
 const authCreated=time(auth.created_at);need(authCreated>=time(target.createdAt)&&authCreated<=time(authRead.receivedAt),'AUTH_READBACK');
 const identityBlocked=state.identity!==null;
 const unresolved=state.requests.some(request=>['pending','unknown'].includes(request.outcome));
 const deletionBlocked=identityBlocked||unresolved;
 return {
  schema_version:1,target_fingerprint:target.fingerprint,
  external_authorized:false,external_verified:false,execution_enabled:false,
  blocked:unresolved?'unresolved-request-reconciliation-required':identityBlocked?'managed-identity-cleanup-contract-unverified':'external-transport-and-authority-required',
  identity_erasure_verified:false,project_recovery_window_days:7,
  resources:[
   {kind:'auth',id:target.authId,read:{method:'GET',url:authUrl},delete:deletionBlocked?null:{method:'DELETE',url:authUrl,body:'{"delete_data":false}'}},
   {kind:'project',id:target.projectId,read:{method:'GET',url:projectUrl},delete:deletionBlocked?null:{method:'DELETE',url:projectUrl,body:''}}
  ],
  requirements:['fresh-authenticated-provider-readbacks','counted-contained-provider-transport','specific-target-and-identity-authorization',
   'managed-identity-removal-and-exact-absence-contract','unknown-write-reconciliation','fresh-post-delete-absence-readback'],
 };
}
