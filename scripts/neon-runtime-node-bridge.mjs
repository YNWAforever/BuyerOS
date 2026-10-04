/** Local built-output bridge only; no deployment or provider transport. */
import {createServer} from 'node:http';
import {existsSync,readFileSync,statSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {staticAssetPath} from './neon-compatibility-harness.mjs';
import {installProbeFetchGuard} from './neon-runtime-probe.mjs';
if(process.env.N00_RUNTIME_PROBE_MODE!=='fixture')throw new Error('N00_PROBE_DISABLED');
process.env.NODE_ENV='production';installProbeFetchGuard();
const output=resolve('test-results/neon-runtime-built-dispatcher/vercel/.vercel/output');
const {default:handler}=await import(pathToFileURL(resolve(output,'functions/__server.func/index.mjs')).href);
const server=createServer(async(req,res)=>{try{
 const pathname=new URL(req.url,'http://localhost:44900').pathname;
 if(['GET','HEAD'].includes(req.method)&&pathname!=='/'){
  const file=staticAssetPath(resolve(output,'static'),pathname);
  if(existsSync(file)&&statSync(file).isFile()){
   res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'application/octet-stream');res.end(req.method==='HEAD'?undefined:readFileSync(file));return;
  }
 }
 const body=[];for await(const chunk of req)body.push(chunk);
 const request=new Request(`http://localhost:44900${req.url}`,{method:req.method,headers:req.headers,...(!['GET','HEAD'].includes(req.method)?{body:Buffer.concat(body)}:{})});
 const response=await handler.fetch(request,{waitUntil(){}});
 res.statusCode=response.status;for(const [key,value]of response.headers)if(key!=='set-cookie')res.setHeader(key,value);
 const cookies=response.headers.getSetCookie();if(cookies.length)res.setHeader('Set-Cookie',cookies);
 res.end(Buffer.from(await response.arrayBuffer()));
 }catch{res.statusCode=500;res.end('N00_BUILT_BRIDGE_FAILED');}});
await new Promise((ok,bad)=>{server.once('error',bad);server.listen(44900,'127.0.0.1',ok);});
process.on('SIGTERM',()=>{server.closeAllConnections();server.close(()=>process.exit(0));});
