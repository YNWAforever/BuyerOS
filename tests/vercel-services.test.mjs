import assert from 'node:assert/strict';
import {existsSync, readFileSync} from 'node:fs';
import {test} from 'node:test';

test('Vercel exposes only the app and binds its API call to the internal API service', () => {
  const path = new URL('../vercel.json', import.meta.url);
  assert.equal(existsSync(path), true, 'root vercel.json must exist');
  const configuration = JSON.parse(readFileSync(path, 'utf8'));
  assert.deepEqual(Object.keys(configuration.services).sort(), ['api', 'app']);
  assert.equal(configuration.services.app.root, '.');
  assert.equal(configuration.services.app.framework, 'nitro');
  assert.equal('outputDirectory' in configuration.services.app, false);
  assert.deepEqual(configuration.services.app.bindings, [
    {type: 'service', service: 'api', format: 'url', env: 'BUYEROS_INTERNAL_API_URL'},
  ]);
  assert.equal(configuration.services.api.root, 'services/api');
  assert.equal(configuration.services.api.framework, 'fastapi');
  assert.equal(configuration.services.api.entrypoint, 'buyeros_api.api.vercel:app');
  assert.deepEqual(configuration.rewrites, [
    {source: '/(.*)', destination: {service: 'app'}},
  ]);
});

test('the app proxy forwards the bearer and original API path to the bound service', async () => {
  const {GET} = await import('../app/v1/[...path]/route.ts');
  const previousUrl = process.env.BUYEROS_INTERNAL_API_URL;
  const previousFetch = globalThis.fetch;
  process.env.BUYEROS_INTERNAL_API_URL = 'https://internal-api.test/base/';
  let called = 0;
  globalThis.fetch = async (input, init) => {
    called++;
    assert.equal(String(input), 'https://internal-api.test/base/v1/workspaces/abc?offset=2');
    assert.equal(new Headers(init.headers).get('Authorization'), 'Bearer fixture-access');
    assert.equal(new Headers(init.headers).get('Cookie'), null);
    assert.equal(new Headers(init.headers).get('x-vercel-protection-bypass'), null);
    return new Response(JSON.stringify({data_mode: 'live', data: {items: []}}), {
      status: 200,
      headers: {'Content-Type': 'application/json', 'X-Request-ID': 'fixture-request'},
    });
  };
  try {
    const response = await GET(new Request('https://app.test/v1/workspaces/abc?offset=2', {
      headers: {Authorization: 'Bearer fixture-access', Cookie: 'session=do-not-forward', 'x-vercel-protection-bypass': 'fictional-preview-bypass-only'},
    }));
    assert.equal(called, 1);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get('X-Request-ID'), 'fixture-request');
    assert.deepEqual(await response.json(), {data_mode: 'live', data: {items: []}});
  } finally {
    globalThis.fetch = previousFetch;
    if (previousUrl === undefined) delete process.env.BUYEROS_INTERNAL_API_URL;
    else process.env.BUYEROS_INTERNAL_API_URL = previousUrl;
  }
});

test('the app proxy fails closed when the binding is absent', async () => {
  const {GET} = await import('../app/v1/[...path]/route.ts');
  const previousUrl = process.env.BUYEROS_INTERNAL_API_URL;
  delete process.env.BUYEROS_INTERNAL_API_URL;
  try {
    const response = await GET(new Request('https://app.test/v1/workspaces'));
    assert.equal(response.status, 503);
    assert.equal((await response.json()).code, 'SERVICE_UNAVAILABLE');
  } finally {
    if (previousUrl !== undefined) process.env.BUYEROS_INTERNAL_API_URL = previousUrl;
  }
});

test('the app proxy streams writes and preserves API conflicts without forwarding cookies', async () => {
  const {PATCH} = await import('../app/v1/[...path]/route.ts');
  const previousUrl = process.env.BUYEROS_INTERNAL_API_URL;
  const previousFetch = globalThis.fetch;
  process.env.BUYEROS_INTERNAL_API_URL = 'https://internal-api.test/';
  globalThis.fetch = async (input, init) => {
    assert.equal(String(input), 'https://internal-api.test/v1/projects/p1');
    assert.equal(init.method, 'PATCH');
    assert.equal(new Headers(init.headers).get('If-Match'), 'version-2');
    assert.equal(new Headers(init.headers).get('Idempotency-Key'), 'edit-123');
    assert.equal(new Headers(init.headers).get('Cookie'), null);
    assert.equal(new Headers(init.headers).get('x-vercel-protection-bypass'), null);
    assert.equal(await new Response(init.body).text(), '{"name":"Revised"}');
    return Response.json({code: 'VERSION_CONFLICT', request_id: 'req-1'},
      {status: 409, headers: {'X-Request-ID': 'req-1'}});
  };
  try {
    const response = await PATCH(new Request('https://app.test/v1/projects/p1', {
      method: 'PATCH', body: JSON.stringify({name: 'Revised'}),
      headers: {'Content-Type': 'application/json', 'If-Match': 'version-2',
        'Idempotency-Key': 'edit-123', Cookie: 'session=do-not-forward', 'x-vercel-protection-bypass': 'fictional-preview-bypass-only'},
    }));
    assert.equal(response.status, 409);
    assert.equal(response.headers.get('Cache-Control'), 'private, no-store');
    assert.equal(response.headers.get('X-Request-ID'), 'req-1');
    assert.equal((await response.json()).code, 'VERSION_CONFLICT');
  } finally {
    globalThis.fetch = previousFetch;
    if (previousUrl === undefined) delete process.env.BUYEROS_INTERNAL_API_URL;
    else process.env.BUYEROS_INTERNAL_API_URL = previousUrl;
  }
});

test('FastAPI redirects stay on the public app path', async () => {
  const {GET} = await import('../app/v1/[...path]/route.ts');
  const previousUrl = process.env.BUYEROS_INTERNAL_API_URL;
  const previousFetch = globalThis.fetch;
  process.env.BUYEROS_INTERNAL_API_URL = 'https://internal-api.test/base/';
  globalThis.fetch = async (input, init) => {
    assert.equal(String(input), 'https://internal-api.test/base/v1/workspaces/');
    assert.equal(init.redirect, 'manual');
    return new Response(null, {status: 307,
      headers: {Location: 'https://internal-api.test/base/v1/workspaces'}});
  };
  try {
    const response = await GET(new Request('https://app.test/v1/workspaces/'));
    assert.equal(response.status, 307);
    assert.equal(response.headers.get('Location'), '/v1/workspaces');
  } finally {
    globalThis.fetch = previousFetch;
    if (previousUrl === undefined) delete process.env.BUYEROS_INTERNAL_API_URL;
    else process.env.BUYEROS_INTERNAL_API_URL = previousUrl;
  }
});
