import test from 'node:test';
import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';
const {readLatestProfile}=await loadModule('services/live/profile-read.ts');
const {SessionScope}=await loadModule('services/live/session.ts');
function session(){const value=new SessionScope({mode:'live',actor:'actor',workspace:'ws',project:'project'});value.setToken('fixture-only');return value;}
function row(number){return {id:`icp-${number}`,project_id:'project',number};}
function client(fn){return {request:fn};}

test('Q09 latest101 uses only head1/tail1 generated reads, never downloads all history',async()=>{
 const calls=[];const value=await readLatestProfile(client(async input=>{const q=new URL(input.path,'http://fixture.test').searchParams;const offset=Number(q.get('offset'));calls.push({offset,limit:q.get('limit'),token:input.token});return {items:[row(offset+1)],offset,limit:1,total:101};}),session(),'project',new AbortController().signal);
 assert.equal(value.number,101);assert.deepEqual(calls,[{offset:0,limit:'1',token:'fixture-only'},{offset:100,limit:'1',token:'fixture-only'}]);
});
test('Q09 empty and single ICP use one read; malformed/foreign pages fail closed',async()=>{
 for(const total of [0,1]){let calls=0;const value=await readLatestProfile(client(async()=>{calls++;return {items:total?[row(1)]:[],offset:0,limit:1,total};}),session(),'project',new AbortController().signal);assert.equal(calls,1);assert.equal(value?.number??null,total?1:null);}
 for(const page of [{items:[{...row(1),project_id:'foreign'}],offset:0,limit:1,total:1},{items:[row(1),row(2)],offset:0,limit:1,total:2},{items:[],offset:1,limit:1,total:0}])await assert.rejects(readLatestProfile(client(async()=>page),session(),'project',new AbortController().signal),/Invalid profile metadata/);
});
test('Q09 concurrent appended history is unavailable rather than a falsely latest profile',async()=>{
 let calls=0;await assert.rejects(readLatestProfile(client(async()=>++calls===1?{items:[row(1)],offset:0,limit:1,total:2}:{items:[row(2)],offset:1,limit:1,total:3}),session(),'project',new AbortController().signal),/history changed/);assert.equal(calls,2);
});
test('Q09 A-B-A rejects a late metadata response and token renewal alone keeps the context',async()=>{
 const scope=session();let release;const pending=readLatestProfile(client(()=>new Promise(resolve=>{release=resolve;})),scope,'project',new AbortController().signal);while(!release)await Promise.resolve();scope.next({project:'other'});scope.next({project:'project'});release({items:[row(1)],offset:0,limit:1,total:1});await assert.rejects(pending,/scope changed/);
 const stable=session();const value=await readLatestProfile(client(async()=>{stable.setToken('renewed');return {items:[row(1)],offset:0,limit:1,total:1};}),stable,'project',new AbortController().signal);assert.equal(value.number,1);
});
