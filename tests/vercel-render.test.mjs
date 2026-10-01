import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {test} from 'node:test';
import {pathToFileURL} from 'node:url';

// Exercise the emitted function: a successful Vite build alone missed a
// Linux-only CommonJS interop failure while importing the workspace chunk.
const entry = process.env.BUYEROS_VERCEL_FUNCTION_ENTRY
  ? pathToFileURL(resolve(process.env.BUYEROS_VERCEL_FUNCTION_ENTRY))
  : new URL('../.vercel/output/functions/__server.func/index.mjs', import.meta.url);
process.env.NODE_ENV = 'production';
const {default: handler} = await import(entry.href);

for (const path of ['/', '/app', '/auth/callback']) {
  test(`the built Vercel function renders ${path} without a workspace import failure`, async () => {
    const response = await handler.fetch(new Request(`https://app.test${path}`, {
      headers: {Accept: 'text/html'},
    }), {waitUntil() {}});
    const html = await response.text();
    assert.equal(response.status, 200, `${path} initial HTML status`);
    assert.match(response.headers.get('content-type') ?? '', /^text\/html/);
    assert.equal(html.includes('id="__next_error__"'), false, 'SSR error shell');
    assert.match(html, /FIMMICK BuyerOS/);
  });
}
