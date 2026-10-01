// Actual local Worker/Queue/Workflow. No DB, Auth0, provider or R2 credentials.
import {createRequire} from 'node:module';
import {createServer} from 'node:http';
import {mkdir, mkdtemp} from 'node:fs/promises';
import {resolve} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';

if (process.env.BUYEROS_TEST_DATABASE_URL || process.env.CLOUDFLARE_API_TOKEN) {
  throw new Error('local Cloudflare acceptance forbids inherited DB/account credentials');
}
const require=createRequire(import.meta.url);
const wrangler=require('wrangler');
const dependencies=createRequire(require.resolve('wrangler/package.json'));
const {Miniflare,convertV4MiniflareOptions}=dependencies('miniflare');
const esbuild=dependencies('esbuild');
const response=await fetch('http://127.0.0.1:8000/fixture/cloudflare/context');
if (!response.ok) throw new Error('owned fixture context missing');
const context=await response.json();
if (context.fixture_only!==true || context.origin!=='http://127.0.0.1:8000' || !Number.isSafeInteger(context.epoch)) {
  throw new Error('refusing nonfixture target');
}
await mkdir(resolve('.sites-runtime'),{recursive:true});
const workspace=await mkdtemp(resolve('.sites-runtime/cloudflare-acceptance-'));
await esbuild.build({entryPoints:['services/cloudflare-jobs/src/index.ts'],bundle:true,format:'esm',
  platform:'browser',external:['cloudflare:*','node:*'],outfile:resolve(workspace,'controller.js')});
process.env.WORKER_CURRENT_SECRET='fictional-cf05-secret-32-bytes-only';
const {workerOptions}=wrangler.unstable_getMiniflareWorkerOptions('services/cloudflare-jobs/wrangler.jsonc');
const options={...workerOptions,rootPath:workspace,modulesRoot:workspace,name:'buyeros-jobs',modules:true,scriptPath:resolve(workspace,'controller.js'),
  port:0,host:'127.0.0.1',cf:false,
  resourcePersistencePath:resolve(workspace,'state'),
  bindings:{...workerOptions.bindings,EXECUTION_ENABLED:'true',RUNTIME_EPOCH:String(context.epoch),LOCAL_TEST_MODE:'true',
    WORKER_API_ORIGIN:context.origin,WORKER_API_ALLOWED_ORIGINS:JSON.stringify([context.origin]),
    WORKER_CURRENT_KEY_ID:'fictional-key',WORKER_CURRENT_SECRET:'fictional-cf05-secret-32-bytes-only'}};
// esbuild has resolved all project modules into this sole ESM module.
// Wrangler's raw file-discovery rules do not apply to the bundled fixture.
delete options.modulesRules;
let mf=new Miniflare(convertV4MiniflareOptions(options));
await mf.ready;
let worker=await mf.getWorker();
let stopped=false, restarting=false, ticks=0, failures=0, restarts=0, pendingTick=Promise.resolve();
const server=createServer(async(request,res)=>{
  if(request.method==='POST' && request.url==='/fixture/stop' && request.headers['x-buyeros-fixture']==='local-only'){
    await stop();res.writeHead(200);res.end('fixture stopped');return;
  }
  if(request.method==='POST' && request.url==='/fixture/restart'){
    if(request.headers['x-buyeros-fixture']!=='local-only' || restarting){res.writeHead(403);res.end();return;}
    restarting=true;
    try{await pendingTick;await mf.dispose();mf=new Miniflare(convertV4MiniflareOptions(options));
      await mf.ready;worker=await mf.getWorker();restarts+=1;
    }catch{res.writeHead(500);res.end('fixture restart failed');return;}
    finally{restarting=false;}
  } else if(request.method!=='GET' || request.url!=='/health'){res.writeHead(404);res.end();return;}
  res.writeHead(200,{'Content-Type':'application/json'});
  res.end(JSON.stringify({fixture_only:true,transport:'actual-local-cloudflare',ticks,failures,restarts,scheduled_interval_ms:1000}));
});
server.listen(8788,'127.0.0.1');
const controller=(async()=>{
  while (!stopped) {
    if(restarting){await delay(50);continue;}
    try {pendingTick=worker.scheduled({cron:'* * * * *'});await pendingTick;ticks+=1;}
    catch {failures+=1;console.error('Fixture scheduled tick failed');}
    await delay(1000);
  }
})();
async function stop(){if(stopped)return;stopped=true;server.close();await controller;await mf.dispose();}
process.once('SIGINT',()=>void stop());process.once('SIGTERM',()=>void stop());
console.log('Actual local Cloudflare fixture ready; accelerated1s Cron, fictional machine key, no cloud resources.');
