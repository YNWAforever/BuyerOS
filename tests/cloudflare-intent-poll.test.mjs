import assert from 'node:assert/strict';
import test from 'node:test';
import {awaitCloudflareIntent} from './e2e/fixtures/cloudflare-stack.ts';

const run='a1000000-0000-4000-8000-000000000001';
const project='a2000000-0000-4000-8000-000000000001';
const job='a3000000-0000-4000-8000-000000000001';

for(const draftJob of [undefined,job]){
  test(`Cloudflare ${draftJob?'draft':'research'} waits for completion and numeric platform receipt`,async t=>{
    const reports=[
      {status:'running',platform_receipts:1},
      {status:'completed',platform_receipts:0},
      {status:'completed',platform_receipts:'1'},
      {status:'completed',platform_receipts:1},
    ].map(row=>({transport:'actual-local-cloudflare',...row}));
    const requests=[];
    t.mock.method(globalThis,'fetch',async url=>{
      requests.push(String(url));
      assert.ok(reports.length,'unexpected extra poll');
      return {ok:true,json:async()=>reports.shift()};
    });
    const result=await awaitCloudflareIntent(run,project,draftJob);
    assert.equal(requests.length,4);
    assert.equal(JSON.parse(result.stdout).platform_receipts,1);
    for(const request of requests){
      const url=new URL(request);
      assert.equal(url.origin,'http://127.0.0.1:8000');
      assert.equal(url.pathname,`/fixture/cloudflare/state/${project}/${run}`);
      assert.equal(url.searchParams.get('draft_job_id'),draftJob??null);
    }
  });
}
