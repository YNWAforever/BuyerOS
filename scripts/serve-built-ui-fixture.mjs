/** Serve the actual emitted Vercel function/assets against an owned fictional API. */
import {createServer} from 'node:http';
import {stat} from 'node:fs/promises';
import {createReadStream} from 'node:fs';
import {Readable} from 'node:stream';
import {pipeline} from 'node:stream/promises';
import {resolve,relative,isAbsolute,sep,extname} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

export function validateBuiltUiFixture(env,context){
  if(env.BUYEROS_STRICT_INTEGRATION!=='1') throw new Error('strict owned fixture required');
  for(const name of ['BUYEROS_TEST_DATABASE_URL','BUYEROS_DATABASE_URL','BUYEROS_EXECUTION_DATABASE_URL','BUYEROS_RUNTIME_ADMIN_DATABASE_URL','DATABASE_URL','CLOUDFLARE_API_TOKEN','BUYEROS_REUSE_TEST_SERVER']){
    if(env[name]) throw new Error(`unset inherited ${name}`);
  }
  if(context?.fixture_only!==true || context.origin!=='http://127.0.0.1:8000' || context.issuer!=='urn:buyeros:e2e'){
    throw new Error('owned fictional API proof required');
  }
}
export function safeStaticPath(root,path){
  const decoded=decodeURIComponent(path);
  if(!decoded.startsWith('/') || decoded.includes('\\') || decoded.includes(':') || decoded.split('/').includes('..')) throw new Error('invalid static path');
  const target=resolve(root,`.${decoded}`),inside=relative(root,target);
  if(isAbsolute(inside) || inside==='..' || inside.startsWith(`..${sep}`)) throw new Error('static path escaped');
  return target;
}

export async function serveBuiltUiFixture(){
  const proof=await fetch('http://127.0.0.1:8000/fixture/frontend',{signal:AbortSignal.timeout(10_000)});
  if(!proof.ok) throw new Error('owned API not available');
  validateBuiltUiFixture(process.env,await proof.json());
  process.env.NODE_ENV='production';
  // Local analogue of the calling app's runtime-only Vercel service binding.
  process.env.BUYEROS_INTERNAL_API_URL='http://127.0.0.1:8000';
  const root=resolve('.vercel/output/static');
  const entry=resolve('.vercel/output/functions/__server.func/index.mjs');
  const {default:handler}=await import(pathToFileURL(entry).href);
  if(typeof handler.fetch!=='function') throw new Error('emitted Vercel fetch handler missing');
  const pending=new Set();
  const waitUntil=promise=>{pending.add(promise);void promise.catch(()=>{}).finally(()=>pending.delete(promise));};
  const types={'.js':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.ico':'image/x-icon','.woff2':'font/woff2','.html':'text/html','.txt':'text/plain'};
  const server=createServer(async(req,res)=>{
    const abort=new AbortController();
    res.once('close',()=>{if(!res.writableEnded) abort.abort();});
    try{
      const path=(req.url??'/').split('?')[0],file=safeStaticPath(root,path);
      const metadata=await stat(file).catch(error=>{if(error.code==='ENOENT'||error.code==='ENOTDIR') return null;throw error;});
      if(metadata?.isFile() && ['GET','HEAD'].includes(req.method??'GET')){
        res.writeHead(200,{'content-type':types[extname(file)]??'application/octet-stream','content-length':metadata.size});
        if(req.method==='HEAD') res.end();else await pipeline(createReadStream(file),res);
        return;
      }
      const headers=new Headers();
      for(const [name,value] of Object.entries(req.headers)) if(value!==undefined) headers.set(name,Array.isArray(value)?value.join(','):value);
      const body=['GET','HEAD'].includes(req.method??'GET')?undefined:Readable.toWeb(req);
      const response=await handler.fetch(new Request(`http://localhost:5173${req.url??'/'}`,{method:req.method,headers,body,duplex:'half',signal:abort.signal}),{waitUntil});
      res.writeHead(response.status,Object.fromEntries(response.headers));
      if(response.body && req.method!=='HEAD') await pipeline(Readable.fromWeb(response.body),res);else res.end();
    }catch(error){
      console.error('built fixture request failed:',error.name);
      if(!res.headersSent){res.writeHead(500,{'content-type':'text/plain'});res.end('Built fixture request failed');}else res.destroy();
    }
  });
  await new Promise((done,reject)=>{server.once('error',reject);server.listen(5173,'127.0.0.1',done);});
  return server;
}
if(process.argv[1] && resolve(process.argv[1])===fileURLToPath(import.meta.url)) await serveBuiltUiFixture();
