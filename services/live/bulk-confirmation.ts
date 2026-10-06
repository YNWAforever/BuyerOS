import type {components} from '@/services/generated/buyeros-api';
import type {ReviewSelection} from './buyer-selection';
import {ActionIntent} from './action-intent';
import {scopeKey,type SessionScope} from './session';

type Outcome=components['schemas']['BulkResult']|components['schemas']['AsyncJob'];
export interface BulkConfirmationInput {
 actor:string;workspace:string;project:string;operation:string;
 selection:ReviewSelection;ownerMembershipId:string|null;reason:string;
}
function normalized(input:BulkConfirmationInput):BulkConfirmationInput {
 const selection:ReviewSelection=input.selection.kind==='explicit'
  ?{kind:'explicit',buyers:input.selection.buyers.map(row=>({id:row.id,version:row.version})).sort((a,b)=>a.id.localeCompare(b.id)||a.version-b.version)}
  :{kind:'snapshot',snapshot_id:input.selection.snapshot_id,excluded_ids:[...input.selection.excluded_ids].sort()};
 return {actor:input.actor,workspace:input.workspace,project:input.project,operation:input.operation,
  selection,ownerMembershipId:input.ownerMembershipId,reason:input.reason.trim()};
}
/** Page offsets, bearer tokens and scope generations are not business intent. */
export function bulkConfirmationFingerprint(input:BulkConfirmationInput):string {return JSON.stringify(normalized(input));}
export function freezeBulkAssignment(input:BulkConfirmationInput,count?:number){
 const value=normalized(input),selection=value.selection;
 if(selection.kind==='explicit'){selection.buyers.forEach(Object.freeze);Object.freeze(selection.buyers);}
 else Object.freeze(selection.excluded_ids);
 Object.freeze(selection);
 const body:components['schemas']['OwnerAssignRequest']=Object.freeze({selection,owner_membership_id:value.ownerMembershipId,reason:value.reason});
 return Object.freeze({count:count??(selection.kind==='explicit'?selection.buyers.length:0),actor:value.actor,workspace:value.workspace,project:value.project,fingerprint:bulkConfirmationFingerprint(value),body});
}
export type FrozenBulkAssignment=ReturnType<typeof freezeBulkAssignment>;
class Recovery {
 readonly intent=new ActionIntent<Outcome>();
 private value:FrozenBulkAssignment|null=null;
 get pending(){return this.value;}
 begin(preview:FrozenBulkAssignment){
  if(this.value&&this.value.fingerprint!==preview.fingerprint)throw new Error('Resolve the pending assignment before changing its intent');
  this.value=preview;
 }
 clear(){this.value=null;}
}
// Memory only: a route/scope round trip cannot create a fresh key for an unknown write.
// Never store bearer tokens, identities or buyer payloads in browser persistence.
const recovery=new WeakMap<SessionScope,Map<string,Recovery>>();
export function assignmentRecovery(session:SessionScope):Recovery {
 let scopes=recovery.get(session);if(!scopes){scopes=new Map();recovery.set(session,scopes);}
 const key=scopeKey(session.current());let item=scopes.get(key);
 if(!item){item=new Recovery();scopes.set(key,item);}
 return item;
}
