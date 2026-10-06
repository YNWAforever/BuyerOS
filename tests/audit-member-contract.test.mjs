import test from 'node:test';
import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';
const {SessionScope}=await loadModule('services/live/session.ts');
const {createOperationClient}=await loadModule('services/live/operations.ts');
const {LiveCancelled}=await loadModule('services/live/client.ts');
function fixture(){
 const session=new SessionScope({mode:'live',actor:'canonical-user',workspace:'workspace-a'});session.setToken('memory-only');
 const calls=[];const api=createOperationClient({request:async r=>{calls.push(r);return {items:[],offset:20,limit:20,total:0};}});
 const capture=session.captureWriteContext();const ctx={...capture,getToken:async()=>session.token(),isCurrent:()=>session.isCurrent(capture.identity)};
 return {session,calls,api,ctx};
}
test('U06 generated member operation carries literal search and bounded page query',async()=>{
 const {api,calls,ctx}=fixture();await api.requestOperation('listMemberships',{path:{workspace_id:'workspace-a'},query:{offset:20,limit:20,q:'Alex %_繁中'}},ctx);
 const url=new URL(calls[0].path,'http://fixture.test');assert.equal(url.pathname,'/v1/workspaces/workspace-a/memberships');assert.equal(url.searchParams.get('q'),'Alex %_繁中');assert.equal(url.searchParams.get('offset'),'20');assert.equal(calls[0].token,'memory-only');
});
test('S06 generated eligible lookup and scope context reject foreign and A-B-A responses',async()=>{
 const {api,calls,ctx,session}=fixture();await api.requestOperation('listEligibleAssignees',{path:{workspace_id:'workspace-a'},query:{q:'member',offset:0,limit:20}},ctx);
 assert.match(calls[0].path,/eligible-assignees/);await assert.rejects(api.requestOperation('listEligibleAssignees',{path:{workspace_id:'workspace-b'}},ctx),LiveCancelled);
 session.next({workspace:'workspace-b'});session.next({workspace:'workspace-a'});await assert.rejects(api.requestOperation('listMemberships',{path:{workspace_id:'workspace-a'}},ctx),LiveCancelled);assert.equal(calls.length,1);
});
