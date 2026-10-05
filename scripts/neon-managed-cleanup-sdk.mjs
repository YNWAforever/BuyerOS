/** Native pinned SDK cleanup rehearsal against a branded owned loopback only.
 * No real provider URL, automatic admin grant or BuyerOS identity/role mutation. */
import {createAuthClient} from '@neondatabase/auth';
import {cleanupTargets} from './neon-real-preflight.mjs';
import {ownedFixtureSdkUrl} from './neon-execution-boundary.mjs';
function need(value,code){if(!value)throw new Error('N00_MANAGED_CLEANUP_'+code);}
export async function runFixtureManagedIdentityCleanup({execution,journal,gateway,nonce,sessionCookie,now=Date.now}){
 const url=ownedFixtureSdkUrl({gateway,execution,journal,nonce});
 need(typeof sessionCookie==='string'&&/^fictional-cleanup-admin=[a-z-]+$/.test(sessionCookie),'FIXTURE_SESSION');
 const state=journal.snapshot(),identity=state.identity;need(identity?.id.startsWith('fictional-execution-'),'BOUND_IDENTITY');
 const receipts=[];
 const result=(complete,blocked=null)=>({complete,blocked,absent_identity:complete,receipts,fixture_only:true,external_verified:false});
 const fresh=await execution.dispatch({channel:'control',method:'GET',path:'/fixture/control/target',body:''});receipts.push(fresh.evidenceRef);
 need(fresh.outcome==='accepted'&&fresh.status===200,'OWNERSHIP_READBACK');
 let target;try{target=JSON.parse(fresh.body);}catch{throw new Error('N00_MANAGED_CLEANUP_OWNERSHIP_READBACK');}
 need(cleanupTargets(state,target,now()).some(v=>v.kind==='identity'&&v.id===identity.id),'BOUND_IDENTITY');
 const client=createAuthClient(url),fetchOptions={headers:{'x-n00-owner':nonce,cookie:sessionCookie},retry:0,redirect:'manual'};
 async function call(method,input){const before=journal.snapshot().requests.length;try{return await method(input);}catch{return null;}finally{receipts.push(...journal.snapshot().requests.slice(before).map(v=>v.evidenceRef).filter(Boolean));}}
 async function exists(){
  const response=await call(input=>client.admin.listUsers(input),{query:{filterField:'id',filterValue:identity.id,filterOperator:'eq',limit:1,offset:0},fetchOptions});
  const data=response?.data;
  if(response?.error||!data||!Array.isArray(data.users)||![0,1].includes(data.total)||data.users.length!==data.total||data.limit!==1||data.offset!==0)return null;
  if(data.total===0)return false;
  const user=data.users[0],created=user?.createdAt instanceof Date?user.createdAt.toISOString():user?.createdAt;
  return user?.id===identity.id&&created===identity.createdAt?true:null;
 }
 const before=await exists();if(before===null)return result(false,'identity-readback-unconfirmed');if(before===false)return result(true);
 const request={channel:'sdk',method:'POST',path:'/fixture/auth/admin/remove-user',body:JSON.stringify({userId:identity.id})};
 if(execution.holds(request))return result(false,'held-remove');
 const removed=await call(input=>client.admin.removeUser(input),{userId:identity.id,fetchOptions});
 if(removed?.error||removed?.data?.success!==true)return result(false,'remove-result-unconfirmed');
 if(await exists()!==false)return result(false,'absence-unconfirmed');return result(true);
}
