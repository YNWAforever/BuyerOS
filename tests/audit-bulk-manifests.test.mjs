import test from 'node:test';
import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';
const {SessionScope}=await loadModule('services/live/session.ts');
const {createLiveClient}=await loadModule('services/live/client.ts');
const {previewManifest,executeManifest,manifestRecovery,startNewManifest}=await loadModule('services/live/bulk-manifests.ts');
const body={operation:'assignBuyerOwners',filters:{q:'Fixture'},excluded_ids:['buyer-a'],target:{owner_membership_id:'member-a'},reason:'confirmed reason'};
function session(){const s=new SessionScope({mode:'live',actor:'actor-a',workspace:'workspace-a',project:'project-a'});s.setToken('first');return s;}
const ok=data=>new Response(JSON.stringify({data,data_mode:'live',request_id:'fixture'}),{status:201,headers:{'Content-Type':'application/json'}});

test('B15 pending body is immutable and retry/token renewal uses same frozen body/key',async()=>{
 const s=session(),calls=[],source=structuredClone(body);let fail=true;
 const client=createLiveClient(async(path,init)=>{calls.push({path,init});if(fail)throw Error('lost committed response');return ok({id:'manifest-a'});});
 await assert.rejects(previewManifest(client,s,source));source.target.owner_membership_id='other';source.filters.q='changed';
 assert.throws(()=>{manifestRecovery(s).body.target.owner_membership_id='other';},TypeError);
 s.setToken('renewed');fail=false;await previewManifest(client,s,body);
 assert.equal(calls[0].init.headers['Idempotency-Key'],calls[1].init.headers['Idempotency-Key']);assert.equal(calls[0].init.body,calls[1].init.body);assert.equal(calls[1].init.headers.Authorization,'Bearer renewed');
});
test('B16 A-B-A keeps actor intent while stale response is cancelled; other actor/scope are independent',async()=>{
 const s=session(),record=manifestRecovery(s);let finish;const client=createLiveClient(()=>new Promise(resolve=>finish=()=>resolve(ok({id:'old'}))));
 const pending=previewManifest(client,s,body);await new Promise(r=>setImmediate(r));s.next({project:'other'});assert.notEqual(manifestRecovery(s),record);s.next({project:'project-a'});assert.equal(manifestRecovery(s),record);finish();await assert.rejects(pending,/scope|cancel/i);
 s.next({actor:'actor-b'});assert.notEqual(manifestRecovery(s),record);
});
test('B15 execution binds exact manifest/version/digest and retains key on unknown acceptance',async()=>{
 const s=session(),manifest={id:'manifest-a',version:1,digest:'a'.repeat(64)},calls=[];let fail=true;
 const client=createLiveClient(async(path,init)=>{calls.push({path,init});if(fail)throw Error('unknown 202');return ok({kind:'bulk_mutation',id:'job-a'});});
 await assert.rejects(executeManifest(client,s,manifest));s.setToken('renewed');fail=false;await executeManifest(client,s,manifest);
 assert.equal(calls[0].init.headers['Idempotency-Key'],calls[1].init.headers['Idempotency-Key']);assert.equal(calls[0].init.headers['If-Match'],'"1"');assert.deepEqual(JSON.parse(calls[1].init.body),{digest:manifest.digest,confirmation:true});assert.match(calls[1].path,/manifest-a\/execute$/);
 const before=manifestRecovery(s);startNewManifest(s);assert.notEqual(manifestRecovery(s),before);
});
