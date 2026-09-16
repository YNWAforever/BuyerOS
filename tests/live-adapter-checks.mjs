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

console.log(`${checks} live adapter checks passed`);
