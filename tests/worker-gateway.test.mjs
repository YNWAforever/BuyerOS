import assert from 'node:assert/strict';
import test from 'node:test';
import {POST} from '../app/v1/[...path]/route.ts';

test('test_internal_headers_forward_only_on_allowlisted_paths', async () => {
  const oldBinding = process.env.BUYEROS_INTERNAL_API_URL;
  const oldFetch = globalThis.fetch;
  process.env.BUYEROS_INTERNAL_API_URL = 'https://api.fixture/';
  try {
    for (const path of ['/v1/internal/worker/claim', '/v1/internal/worker/step',
      '/v1/internal/worker/status', '/v1/internal/worker/publication', '/v1/internal/worker/maintenance',
      '/v1/workspaces', '/v1/internal/worker/claim/', '/v1/internal/worker/other']) {
      globalThis.fetch = async (target, options) => {
        const allowed = /^\/v1\/internal\/worker\/(claim|step|status|publication|maintenance)$/.test(path);
        for (const name of ['key-id', 'timestamp', 'nonce', 'signature']) {
          assert.equal(new Headers(options.headers).get(`x-buyeros-worker-${name}`), allowed ? 'fixture' : null);
        }
        assert.equal(await new Response(options.body).text(), '{"v":1}');
        assert.equal(options.redirect, 'manual');
        assert.equal(new URL(target).pathname, path);
        return Response.json({ok: true});
      };
      const headers = {'content-type': 'application/json'};
      for (const name of ['key-id', 'timestamp', 'nonce', 'signature']) headers[`x-buyeros-worker-${name}`] = 'fixture';
      const response = await POST(new Request(`https://app.fixture${path}`, {method: 'POST', headers, body: '{"v":1}'}));
      assert.equal(response.status, 200);
    }
  } finally {
    globalThis.fetch = oldFetch;
    if (oldBinding === undefined) delete process.env.BUYEROS_INTERNAL_API_URL;
    else process.env.BUYEROS_INTERNAL_API_URL = oldBinding;
  }
});
