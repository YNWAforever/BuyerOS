import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {test} from 'node:test';
import {fingerprintCurrent} from '../services/live/approval-fingerprint.ts';

const vectors=JSON.parse(await readFile(new URL('../services/generated/approval-golden-vectors.json',import.meta.url),'utf8'));
for(const vector of vectors.filter(row=>row.serializer_version==='approval-cjson-v2')){
  test('TypeScript approval fingerprint matches '+vector.name,async()=>{
    assert.equal(await fingerprintCurrent(vector.context),vector.digest);
    await assert.rejects(fingerprintCurrent({...vector.context,display_locale:'zh-HK'}),/schema/);
  });
}
