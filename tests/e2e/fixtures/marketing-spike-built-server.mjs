// Local adapter for the actual emitted Nitro/Vercel function; no fixture DB or
// provider service. Browser tests intercept synthetic Neon cookie endpoints.
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {resolve, sep, extname} from 'node:path';
import {pathToFileURL} from 'node:url';
import {neonFixtureEnvironmentFor} from './neon-fixture-protocol.mjs';

const port = 5193;
const origin = `http://127.0.0.1:${port}`;
Object.assign(process.env,neonFixtureEnvironmentFor(origin),{NODE_ENV:'test'});
const staticRoot = resolve('.vercel/output/static');
const {default: built} = await import(pathToFileURL(resolve('.vercel/output/functions/__server.func/index.mjs')).href);
globalThis.fetch = async () => {throw Error('Marketing spike server forbids upstream network');};
const mime = {'.js': 'application/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.json': 'application/json'};
const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url, origin);
    const filename = resolve(staticRoot, '.' + decodeURIComponent(url.pathname));
    let response;
    if (filename.startsWith(staticRoot + sep)) {
      try {
        const content = await readFile(filename);
        response = new Response(content, {headers: {'content-type': mime[extname(filename)] ?? 'application/octet-stream'}});
      } catch (error) {if (!['ENOENT', 'EISDIR', 'ENOTDIR'].includes(error.code)) throw error;}
    }
    if (!response) {
      const chunks = [];
      for await (const chunk of req) chunks.push(chunk);
      const headers = new Headers();
      for (const [key, value] of Object.entries(req.headers)) if (value) headers.set(key, Array.isArray(value) ? value.join(',') : value);
      const request = new Request(url, {method: req.method, headers,
        ...(!['GET', 'HEAD'].includes(req.method) ? {body: Buffer.concat(chunks)} : {}),
      });
      response = await built.fetch(request, {waitUntil() {}});
    }
    res.statusCode = response.status;
    for (const [key, value] of response.headers) if (key !== 'set-cookie') res.setHeader(key, value);
    if (response.headers.getSetCookie().length) res.setHeader('set-cookie', response.headers.getSetCookie());
    res.end(Buffer.from(await response.arrayBuffer()));
  } catch (error) {
    console.error(error);
    res.writeHead(500); res.end('Local built-output adapter failure');
  }
});
server.listen(port, '127.0.0.1', () => console.log(`Local built spike ${origin}`));
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => server.close(() => process.exit(0)));
