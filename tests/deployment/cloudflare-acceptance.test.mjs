import assert from 'node:assert/strict';
import {test} from 'node:test';
import {mkdtemp,writeFile,access,rmdir} from 'node:fs/promises';
import {resolve} from 'node:path';
import {validateAcceptanceOptions,summarizeJUnit} from '../../scripts/run-cloudflare-acceptance.mjs';

test('local acceptance rejects shared targets, preview activation and inherited credentials',()=>{
  const good={mode:'local',baseUrl:'http://localhost:5173',evidenceDir:'artifacts/cloudflare/acceptance'};
  assert.equal(validateAcceptanceOptions(good,{}).mode,'local');
  for(const option of [{...good,mode:'preview'},{...good,baseUrl:'https://buyer-os-nu.vercel.app'},{...good,evidenceDir:'../outside'},{...good,evidenceDir:process.platform==='win32'?'Z:/outside':'/outside'}]) assert.throws(()=>validateAcceptanceOptions(option,{}));
  for(const key of ['BUYEROS_TEST_DATABASE_URL','BUYEROS_REUSE_TEST_SERVER','CLOUDFLARE_API_TOKEN']) assert.throws(()=>validateAcceptanceOptions(good,{[key]:'forbidden'}));
});
test('acceptance counts actual executed cases and fails closed on empty, skipped or failed reports',()=>{
  assert.deepEqual(summarizeJUnit('<testsuites><testsuite tests="7" failures="0" errors="0" skipped="0"/></testsuites>'),{passed:7,failed:0,errors:0,skipped:0,total:7});
  for(const counts of ['tests="0" failures="0" errors="0" skipped="0"','tests="7" failures="1" errors="0" skipped="0"','tests="7" failures="0" errors="0" skipped="1"']) assert.throws(()=>summarizeJUnit(`<testsuite ${counts}/>`));
});

test('a new acceptance attempt invalidates old success and old JUnit before any command',async()=>{
  const {beginAcceptanceEvidence}=await import('../../scripts/run-cloudflare-acceptance.mjs');
  const dir=await mkdtemp(resolve('.sites-runtime/acceptance-evidence-check-'));
  const options={mode:'local',baseUrl:'http://localhost:5173',evidenceDir:dir};
  try {
    await writeFile(resolve(dir,'report.json'),'prior success');
    await writeFile(resolve(dir,'journey.xml'),'prior pass counts');
    await beginAcceptanceEvidence(options);
    await assert.rejects(access(resolve(dir,'report.json')));
    await assert.rejects(access(resolve(dir,'journey.xml')));
  } finally {
    const {rm}=await import('node:fs/promises');
    await rm(resolve(dir,'report.json'),{force:true});await rm(resolve(dir,'journey.xml'),{force:true});await rmdir(dir);
  }
});
