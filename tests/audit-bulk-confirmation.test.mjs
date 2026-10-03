import test from 'node:test';
import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';
const {bulkConfirmationFingerprint,freezeBulkAssignment,assignmentRecovery}=await loadModule('services/live/bulk-confirmation.ts');
const {SessionScope}=await loadModule('services/live/session.ts');
const input={actor:'user-a',workspace:'workspace-a',project:'project-a',operation:'assignBuyerOwners',selection:{kind:'explicit',buyers:[{id:'b',version:2},{id:'a',version:1}]},ownerMembershipId:'member-a',reason:' rotation '};
test('B02 confirmation is stable for row ordering but binds every material field',()=>{
 const hash=bulkConfirmationFingerprint(input);
 assert.equal(hash,bulkConfirmationFingerprint({...input,reason:'rotation',selection:{kind:'explicit',buyers:[...input.selection.buyers].reverse()}}));
 for(const change of [{actor:'other'},{workspace:'other'},{project:'other'},{operation:'reviewBuyers'},{ownerMembershipId:null},{reason:'different'}, {selection:{kind:'explicit',buyers:[{id:'a',version:2},{id:'b',version:2}]}},{selection:{kind:'explicit',buyers:[...input.selection.buyers,{id:'c',version:1}]}}])assert.notEqual(hash,bulkConfirmationFingerprint({...input,...change}));
});
test('B02 snapshot confirmation binds snapshot identity and normalized exclusions',()=>{
 const choice={...input,selection:{kind:'snapshot',snapshot_id:'snapshot-a',excluded_ids:['b','a']}};
 assert.equal(bulkConfirmationFingerprint(choice),bulkConfirmationFingerprint({...choice,selection:{...choice.selection,excluded_ids:['a','b']}}));
 for(const selection of [{...choice.selection,snapshot_id:'other'},{...choice.selection,excluded_ids:['a']}])assert.notEqual(bulkConfirmationFingerprint(choice),bulkConfirmationFingerprint({...choice,selection}));
});
test('B03 frozen payload preserves confirmed rows and trimmed audit reason',()=>{
 const source=structuredClone(input),frozen=freezeBulkAssignment(source);source.selection.buyers[0].version=90;source.reason='new';
 assert.deepEqual(frozen.body,{selection:{kind:'explicit',buyers:[{id:'a',version:1},{id:'b',version:2}]},owner_membership_id:'member-a',reason:'rotation'});
 assert.throws(()=>{frozen.body.selection.buyers[0].version=99;},TypeError);
});
test('B16 unknown assignment survives route remount and token renewal with the same key',async()=>{
 const session=new SessionScope({mode:'live',actor:input.actor,workspace:input.workspace,project:input.project});session.setToken('first');
 const record=assignmentRecovery(session);record.begin(freezeBulkAssignment(input));let key;
 await assert.rejects(record.intent.run(record.pending.fingerprint,async k=>{key=k;throw Error('lost committed response');}));
 session.setToken('renewed');assert.equal(assignmentRecovery(session),record);
 session.next({project:'project-b'});assert.notEqual(assignmentRecovery(session),record);session.next({project:input.project});assert.equal(assignmentRecovery(session),record);
 await record.intent.run(record.pending.fingerprint,async k=>assert.equal(k,key));
});

test('B16 an unresolved assignment cannot be replaced with a materially different intent',()=>{
 const session=new SessionScope({mode:'live',actor:input.actor,workspace:input.workspace,project:input.project});session.setToken('memory-only');const record=assignmentRecovery(session);
 record.begin(freezeBulkAssignment(input));assert.throws(()=>record.begin(freezeBulkAssignment({...input,reason:'different'})),/Resolve the pending assignment/);
 assert.equal(record.pending.body.reason,'rotation');record.clear();record.begin(freezeBulkAssignment({...input,reason:'different'}));assert.equal(record.pending.body.reason,'different');
});
