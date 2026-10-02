// Read-only acceptance for the explicitly approved existing production deployment.
// Sends four bounded GET requests. Uses no user credentials or database connection.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';

const origin = 'https://buyer-os-nu.vercel.app';
const source = '41810627540dd52c4567f853ae65d51e2bb6365d';
const deployment = JSON.parse(readFileSync(new URL('./t30-production-deployment-4181062-20261001.json', import.meta.url), 'utf8'));
assert.equal(deployment.source_sha, source);
assert.equal(deployment.ready_state, 'READY');
assert.equal(deployment.target, 'production');
assert.equal(deployment.production_alias, origin);

const checks = [];
async function check(name, path, validate, headers = {}) {
  const started = performance.now();
  const row = { name, method: 'GET', path };
  try {
    const response = await fetch(new URL(path, origin), {
      method: 'GET', redirect: 'manual', cache: 'no-store',
      headers, signal: AbortSignal.timeout(30_000),
    });
    const body = await response.text();
    row.status = response.status;
    row.content_type = response.headers.get('content-type');
    row.bytes = Buffer.byteLength(body);
    row.body_sha256 = createHash('sha256').update(body).digest('hex');
    validate(response, body, row);
    row.passed = true;
  } catch (error) {
    row.passed = false;
    row.failure = error.message;
  }
  row.duration_ms = Math.round(performance.now() - started);
  checks.push(row);
}

await check('production root initial HTML', '/', (response, body) => {
  assert.equal(response.status, 200, 'root must serve HTTP200 without redirect');
  assert.match(response.headers.get('content-type') ?? '', /text\/html/);
  assert.ok(body.includes('FIMMICK BuyerOS'), 'expected application title absent');
});
await check('app HTML and public Auth0 bootstrap', '/app', (response, body, row) => {
  assert.equal(response.status, 200, 'app must serve HTTP200 without redirect');
  assert.match(response.headers.get('content-type') ?? '', /text\/html/);
  assert.ok(body.includes('https://dev-oaug20cdxqqgn1s8.us.auth0.com'), 'public issuer absent');
  assert.ok(body.includes('iVnUZbP4JsjRAJAHob1qmTSlZ0rgZU1R'), 'public SPA client ID absent');
  assert.ok(body.includes('https://buyer-os-nu.vercel.app/v1'), 'API audience absent');
  row.public_auth0_bootstrap_present = true;
});
function rejectedBearer(expectedMessage) {
  return (response, body, row) => {
    assert.equal(response.status, 401, 'anonymous/invalid bearer must be rejected');
    assert.match(response.headers.get('content-type') ?? '', /application\/json/);
    const payload = JSON.parse(body);
    assert.equal(payload.code, 'UNAUTHENTICATED');
    assert.equal(payload.message, expectedMessage);
    assert.equal(payload.retryable, false);
    assert.ok(typeof payload.request_id === 'string' && payload.request_id.length > 0);
    assert.ok(!Object.hasOwn(payload, 'data'), 'auth failure must not expose data rows');
    row.error_code = payload.code;
    row.request_id = payload.request_id;
  };
}
await check('anonymous same-origin API rejection', '/v1/workspaces', rejectedBearer('missing bearer token'));
await check('malformed bearer rejection', '/v1/workspaces', rejectedBearer('token rejected'), { Authorization: 'Bearer not-a-jwt' });

const passed = checks.filter(row => row.passed).length;
const result = {
  observed_at_utc: new Date().toISOString(), origin, source_sha: source,
  deployment_id: deployment.id, command: 'node artifacts/t30-production-acceptance-4181062-20261001.mjs',
  passed, failed: checks.length - passed, skipped: 0, checks,
  scope: 'Actual anonymous production HTTP and public bootstrap checks only. No authenticated UI, database write, live provider, external worker, delivery or complete staff journey verification.',
};
writeFileSync(new URL('./t30-production-acceptance-4181062-20261001.json', import.meta.url), `${JSON.stringify(result, null, 2)}\n`);
console.log(JSON.stringify(result, null, 2));
if (result.failed) process.exitCode = 1;
