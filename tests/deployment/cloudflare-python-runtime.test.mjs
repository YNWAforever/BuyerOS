import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

test('CF00 reports measured local feasibility separately from hosted Vercel evidence', () => {
  const report = JSON.parse(readFileSync('artifacts/cloudflare/CF00-runtime-matrix.json', 'utf8'));
  assert.equal(report.environment, 'local');
  assert.match(report.source_sha, /^[0-9a-f]{40}$/);
  assert.equal(report.local_feasible, true);
  assert.equal(report.hosted_feasible, false);
  for (const name of ['vercel_api_bundle', 'vercel_app_90s', 'vercel_api_90s', 'preview_protection']) {
    const record = report.records.find(row => row.check === name);
    assert.equal(record.state, 'not_run', name);
  }
  const parser = report.records.find(row => row.check === 'pdf_timeout');
  assert.equal(parser.details.timeout_seconds, 8);
  assert.equal(parser.details.child_killed, true);
  assert.equal(report.records.filter(row => row.state === 'failed').length, 0);
});
