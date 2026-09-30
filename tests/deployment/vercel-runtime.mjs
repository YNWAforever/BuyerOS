import assert from 'node:assert/strict';
import {test} from 'node:test';

// Run explicitly after a deployment. This suite makes anonymous GET requests
// only; it never acquires a token, writes data or calls a provider.
const configuredUrl = process.env.BUYEROS_VERCEL_VERIFY_URL;
assert.ok(configuredUrl, 'Set BUYEROS_VERCEL_VERIFY_URL to the deployment origin');
const origin = new URL(configuredUrl);
assert.equal(origin.username + origin.password + origin.search + origin.hash, '');
assert.equal(origin.pathname, '/');
assert.ok(origin.protocol === 'https:' ||
  (origin.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(origin.hostname)));

for (const path of ['/', '/app', '/auth/callback']) {
  test(`${path} renders initial application HTML without relying on browser recovery`, async () => {
    const response = await fetch(new URL(path, origin), {
      redirect: 'manual', signal: AbortSignal.timeout(30_000),
      headers: {Accept: 'text/html'},
    });
    assert.equal(response.status, 200, `${path} HTTP status`);
    assert.match(response.headers.get('content-type') ?? '', /^text\/html/);
    const html = await response.text();
    assert.equal(html.includes('id="__next_error__"'), false, 'SSR error shell');
    assert.match(html, /FIMMICK BuyerOS/);
  });
}

test('the public API proxy reaches FastAPI and rejects an anonymous request', async () => {
  const response = await fetch(new URL('/v1/workspaces', origin), {
    redirect: 'manual', signal: AbortSignal.timeout(30_000),
  });
  assert.equal(response.status, 401);
  assert.equal((await response.json()).code, 'UNAUTHENTICATED');
});
