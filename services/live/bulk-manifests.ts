import type {components} from '@/services/generated/buyeros-api';
import type {SessionScope} from './session';
import {scopeKey} from './session';
import type {LiveClient} from './client';
import {buyerOperationContext} from './buyers';
import {createOperationClient} from './operations';
import {ActionIntent} from './action-intent';
export type Manifest=components['schemas']['BulkManifest'];
export type ManifestBody=components['schemas']['BulkManifestCreate'];
export type ManifestResult=components['schemas']['BulkResult']|components['schemas']['AsyncJob'];
export interface ManifestRecovery {body:ManifestBody|null;preview:ActionIntent<Manifest>;execute:ActionIntent<ManifestResult>}
function freezeBody<T>(value:T):T{
 if(value&&typeof value==='object'){for(const child of Object.values(value))freezeBody(child);Object.freeze(value);}return value;
}
const recoveries=new WeakMap<SessionScope,Map<string,ManifestRecovery>>();
export function manifestRecovery(session:SessionScope):ManifestRecovery{
 let records=recoveries.get(session);if(!records){records=new Map();recoveries.set(session,records);}
 const id=scopeKey(session.current());let record=records.get(id);
 if(!record){record={body:null,preview:new ActionIntent(),execute:new ActionIntent()};records.set(id,record);}return record;
}
export async function previewManifest(client:LiveClient,session:SessionScope,body:ManifestBody):Promise<Manifest>{
 const ctx=buyerOperationContext(session),record=manifestRecovery(session);
 record.body??=freezeBody(structuredClone(body));const frozen=record.body;
 return record.preview.run(JSON.stringify({scope:scopeKey(session.current()),body:frozen}),key=>createOperationClient(client).requestOperation('previewBulkManifest',{
  path:{workspace_id:ctx.workspace,project_id:ctx.project!},header:{'Idempotency-Key':key},body:frozen},ctx));
}
export async function readManifest(client:LiveClient,session:SessionScope,id:string):Promise<Manifest>{
 const ctx=buyerOperationContext(session);return createOperationClient(client).requestOperation('getBulkManifest',{
  path:{workspace_id:ctx.workspace,project_id:ctx.project!,manifest_id:id}},ctx);
}
export async function executeManifest(client:LiveClient,session:SessionScope,manifest:Manifest):Promise<ManifestResult>{
 const ctx=buyerOperationContext(session),body={digest:manifest.digest,confirmation:true as const};
 return manifestRecovery(session).execute.run(JSON.stringify({scope:scopeKey(session.current()),manifest:manifest.id,version:manifest.version,body}),key=>createOperationClient(client).requestOperation('executeBulkManifest',{
  path:{workspace_id:ctx.workspace,project_id:ctx.project!,manifest_id:manifest.id},header:{'Idempotency-Key':key,'If-Match':`"${manifest.version}"`},body},ctx));
}
export function startNewManifest(session:SessionScope){const records=recoveries.get(session);records?.delete(scopeKey(session.current()));}
