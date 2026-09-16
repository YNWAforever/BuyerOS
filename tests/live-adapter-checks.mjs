import assert from 'node:assert/strict';
import {loadModule} from './ts-loader.mjs';

let checks=0;
// Async by necessity: several checks await a deferred response. A sync harness would let those
// assertions run after the summary and turn a failure into an unhandled rejection.
async function test(name,fn){await fn();checks++;console.log('PASS '+name);}
const mode=await loadModule('services/live/mode.ts');

await test('apiBaseUrl absent or blank resolves to demo',()=>{
  assert.equal(mode.resolveMode(undefined),'demo');
  assert.equal(mode.resolveMode(null),'demo');
  assert.equal(mode.resolveMode(''),'demo');
  assert.equal(mode.resolveMode('   '),'demo');
});

await test('a configured apiBaseUrl resolves to live',()=>{
  assert.equal(mode.resolveMode('https://api.example.test'),'live');
});

await test('demo mode makes every section available, live mode does not',()=>{
  const sections=['overview','discovery','lists','outreach','results','settings'];
  for(const s of sections)assert.equal(mode.availabilityFor('demo',s),'available');
  assert.equal(mode.availabilityFor('live','overview'),'available');
  for(const s of ['discovery','lists','outreach','results'])assert.equal(mode.availabilityFor('live',s),'unavailable');
});

await test('live without a ready session reports not_configured, never available',()=>{
  assert.equal(mode.availabilityFor('live','overview',false),'not_configured');
  assert.equal(mode.availabilityFor('live','overview',true),'available');
});

await test('unavailable and not_configured are distinct states',()=>{
  assert.notEqual(mode.availabilityFor('live','outreach'),mode.availabilityFor('live','overview',false));
});

const map=await loadModule('services/live/mapping.ts');

await test('workspaces map to the narrow model',()=>{
  const payload={items:[{id:'ws-1',name:'Acme',roles:['viewer'],data_mode:'live'}],offset:0,limit:1,total:1};
  assert.deepEqual(map.toWorkspaces(payload),[{id:'ws-1',name:'Acme',roles:['viewer']}]);
});

await test('projects map to the narrow model',()=>{
  const payload={items:[{id:'p-1',name:'Sensors',status:'active'}],offset:0,limit:1,total:1};
  assert.deepEqual(map.toProjects(payload),[{id:'p-1',name:'Sensors',status:'active'}]);
});

await test('icp versions map approved_at to approvedAt and keep the hash',()=>{
  const payload={items:[{id:'i-1',number:2,content_hash:'sha256:aa',status:'approved',approved_at:'2026-09-01T00:00:00Z'}],offset:0,limit:1,total:1};
  assert.deepEqual(map.toIcpVersions(payload),[{id:'i-1',number:2,contentHash:'sha256:aa',status:'approved',approvedAt:'2026-09-01T00:00:00Z'}]);
});

await test('buyers map to the narrow model and keep a null note as null',()=>{
  const payload={items:[{id:'b-1',name:'Example GmbH',note:null}],offset:0,limit:1,total:1};
  assert.deepEqual(map.toBuyers(payload),[{id:'b-1',name:'Example GmbH',note:null}]);
});

await test('a missing required field raises instead of becoming an empty value',()=>{
  assert.throws(()=>map.toBuyers({items:[{id:'b-1',note:null}],offset:0,limit:1,total:1}),map.MapError);
  assert.throws(()=>map.toWorkspaces({items:[{name:'no id'}]}),map.MapError);
  assert.throws(()=>map.toBuyers({items:null}),map.MapError);
  assert.throws(()=>map.toBuyers(undefined),map.MapError);
});

await test('an empty page is empty, not an error',()=>{
  assert.deepEqual(map.toBuyers({items:[],offset:0,limit:0,total:0}),[]);
});

console.log(`${checks} live adapter checks passed`);
