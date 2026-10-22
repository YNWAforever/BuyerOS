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

for (const path of ['/', '/app', '/auth/sign-in', '/auth/callback']) {
  test(`the built Vercel function renders ${path} without a workspace import failure`, async () => {
    let response = await handler.fetch(new Request(`https://app.test${path}`, {
      headers: {Accept: 'text/html'},
    }), {waitUntil() {}});
    if (path === '/') {
      assert.equal(response.status, 307, 'root redirects to the canonical business layout');
      const location = new URL(response.headers.get('location'), 'https://app.test');
      assert.equal(location.href, 'https://app.test/app', 'root redirect stays at the exact app origin and path');
      response = await handler.fetch(new Request(location, {headers: {Accept: 'text/html'}}), {waitUntil() {}});
    }
    const html = await response.text();
    assert.equal(response.status, 200, `${path} initial HTML status`);
    assert.match(response.headers.get('content-type') ?? '', /^text\/html/);
    assert.equal(html.includes('id="__next_error__"'), false, 'SSR error shell');
    assert.match(html, /FIMMICK BuyerOS/);
    if(path!=='/auth/callback'){
      const localeControl=html.match(/<select\b[^>]*aria-label="Language"[^>]*>/)?.[0];
      assert.ok(localeControl,'initial app HTML exposes the language choice');
      assert.match(localeControl,/\bdisabled(?:=|[ >])/,
        'language must wait for hydration; an early native change has no React handler and is lost on sign-in');
    }
  });
}
