import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';

test('native API budget applies to the resolved Python entrypoint inside its service',()=>{
  const config=JSON.parse(readFileSync('vercel.json','utf8'));
  assert.equal(config.services.api.functions['buyeros_api/api/vercel.py'].maxDuration,90);
  assert.equal('functions' in config,false);
});
test('the actual emitted Nitro gateway carries the ninety-second budget',()=>{
  const output=JSON.parse(readFileSync('.vercel/output/functions/__server.func/.vc-config.json','utf8'));
  assert.equal(output.maxDuration,90);
});
test('the isolated preview controller has distinct private resources and execution off',()=>{
  const config=JSON.parse(readFileSync('services/cloudflare-jobs/wrangler.jsonc','utf8'));
  const preview=config.env.preview;
  assert.equal(preview.name,'buyeros-jobs-preview');
  assert.equal(preview.workers_dev,false);assert.equal(preview.preview_urls,false);
  assert.equal(preview.vars.EXECUTION_ENABLED,'false');assert.equal(preview.vars.LOCAL_TEST_MODE,'false');
  assert.equal(preview.queues.consumers[0].queue,'buyeros-jobs-preview');
  assert.equal(preview.queues.consumers[0].dead_letter_queue,'buyeros-jobs-preview-dlq');
  assert.equal(preview.workflows[0].name,'buyeros-job-preview');
  assert.equal(config.vars.EXECUTION_ENABLED,'false');
});
