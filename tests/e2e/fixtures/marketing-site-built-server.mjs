// Serve actual emitted Vercel output locally, with external fetches denied.
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {resolve, sep, extname} from 'node:path';
import {pathToFileURL} from 'node:url';
import {gzipSync} from 'node:zlib';
import {neonFixtureEnvironmentFor} from './neon-fixture-protocol.mjs';
const origin = 'http://127.0.0.1:5195', staticRoot = resolve('.vercel/output/static');
Object.assign(process.env,neonFixtureEnvironmentFor(origin),{NODE_ENV:'test',BUYEROS_NEON_AUTH_ROUTE_ENABLED:'0'});
const nativeFetch = globalThis.fetch;
globalThis.fetch = async (input, init) => {
  const url = new URL(typeof input === 'string' || input instanceof URL ? input : input.url);
  if (process.env.MARKETING_SYNTHETIC_MODE === '1' && url.origin === process.env.MARKETING_API_ORIGIN && url.hostname === '127.0.0.1' && ['/marketing/leads', '/marketing/leads/challenge'].includes(url.pathname)) return nativeFetch(input, init);
  throw Error('Local marketing server refuses unexpected upstream fetch');
};
const {default: built} = await import(pathToFileURL(resolve('.vercel/output/functions/__server.func/index.mjs')).href);
const mime = {'.js':'application/javascript','.css':'text/css','.png':'image/png','.svg':'image/svg+xml','.woff2':'font/woff2','.json':'application/json'};
const server = createServer(async (req,res) => {
  try {
    const url = new URL(req.url,origin), file = resolve(staticRoot,'.'+decodeURIComponent(url.pathname));let response;
    if (file.startsWith(staticRoot+sep)) try {response = new Response(await readFile(file),{headers:{'content-type':mime[extname(file)]??'application/octet-stream'}});} catch (error) {if (!['ENOENT','EISDIR','ENOTDIR'].includes(error.code)) throw error;}
    if (!response) {
      const chunks=[];for await (const chunk of req) chunks.push(chunk);
      const headers=new Headers();for(const[key,value]of Object.entries(req.headers))if(value)headers.set(key,Array.isArray(value)?value.join(','):value);
      response=await built.fetch(new Request(url,{method:req.method,headers,...(!['GET','HEAD'].includes(req.method)?{body:Buffer.concat(chunks)}:{})}),{waitUntil(){}});
    }
    res.statusCode=response.status;for(const[key,value]of response.headers)if(key!=='set-cookie')res.setHeader(key,value);
    if(response.headers.getSetCookie().length)res.setHeader('set-cookie',response.headers.getSetCookie());
    // Mirror the emitted Vercel immutable-asset header and normal HTTP compression.
    // The baseline uncompressed Lighthouse report is retained separately.
    if(url.pathname.startsWith('/_next/static/'))res.setHeader('Cache-Control','public, max-age=31536000, immutable');
    let body=Buffer.from(await response.arrayBuffer());
    if(/\bgzip\b/.test(req.headers['accept-encoding']??'') && /^(text\/|application\/(javascript|json))/.test(response.headers.get('content-type')??'')){
      body=gzipSync(body);res.setHeader('Content-Encoding','gzip');res.setHeader('Vary','Accept-Encoding');res.removeHeader('Content-Length');
    }
    res.end(body);
  } catch (error) {console.error(error);res.writeHead(500);res.end('Local built-output adapter failure');}
});
server.listen(5195,'127.0.0.1');
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>server.close(()=>process.exit(0)));
