/** Local fictional IPC worker only. Parent/broker/browser/provider egress is NOT contained. */
import {execFile,spawn} from 'node:child_process';
import {randomBytes} from 'node:crypto';
import {createInterface} from 'node:readline';
import {readFileSync,lstatSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {fixtureChildEnvironment} from './neon-compatibility-harness.mjs';
import {assertFixtureExecutionBoundary} from './neon-execution-boundary.mjs';
const LABEL='buyeros.n00.native.owner',CONTEXT='desktop-linux',PORT=38479;
const readbackRetries=new WeakMap();
function need(value,code){if(!value)throw new Error('N00_NATIVE_'+code);}
const sinkSource=`import {createServer} from 'node:http';let hits=0;createServer((req,res)=>{if(req.url.startsWith('/native/'))hits++;res.setHeader('Content-Type','application/json');res.end(JSON.stringify({hits,fixture_only:true}));}).listen(${PORT},'0.0.0.0');`;
const metricsSource=`fetch('http://127.0.0.1:${PORT}/metrics',{signal:AbortSignal.timeout(1000)}).then(r=>r.text()).then(s=>process.stdout.write(s)).catch(()=>process.exitCode=1)`;
const workerPath=fileURLToPath(new URL('./neon-native-worker.mjs',import.meta.url));
function docker(args,env){return new Promise((ok,bad)=>execFile('docker',['--context',CONTEXT,...args],{env,encoding:'utf8',timeout:20000,maxBuffer:1048576,windowsHide:true},(error,stdout,stderr)=>{if(error){const failure=new Error('N00_NATIVE_DOCKER_FAILED');failure.absent=(args[0]==='inspect'||args[0]==='network'&&args[1]==='inspect')&&stderr.includes(args.at(-1))&&/No such (object|container|network)|network .* not found/i.test(stderr);failure.operation=args.slice(0,2).join(' ');failure.exit=error.code;failure.killed=error.killed;failure.detail=stderr.slice(0,512);bad(failure);}else ok(stdout.trim());}));}
async function inspect(kind,id,env){const args=kind==='network'?['network','inspect',id]:['inspect',id];let data;try{data=await docker(args,env);}catch(e){if(!e.killed||e.detail)throw e;readbackRetries.set(env,(readbackRetries.get(env)??0)+1);data=await docker(args,env);}return JSON.parse(data)[0];}
async function absent(kind,id,env){try{await inspect(kind,id,env);return false;}catch(e){if(e.absent)return true;throw e;}}
function verifyContainer(value,owner){need(value.Config?.Labels?.[LABEL]===owner&&value.Id?.match(/^[a-f0-9]{64}$/),'OWNERSHIP');need(value.HostConfig.ReadonlyRootfs&&value.Config.User==='node'&&value.HostConfig.CapDrop?.includes('ALL')&&!Object.keys(value.HostConfig.PortBindings??{}).length,'CONTAINER_POLICY');}
function pipeWorker(name,cfg,env,dispatch){return new Promise((ok,bad)=>{
 const child=spawn('docker',['--context',CONTEXT,'start','-a','-i',name],{env,stdio:['pipe','pipe','pipe'],windowsHide:true});let size=0,complete,nextIndex=0,failed=false,failureReason=null;
 const fail=reason=>{if(failed)return;failed=true;failureReason=reason?.message??String(reason??'worker transport');child.kill();};
 const timer=setTimeout(()=>fail('worker deadline'),15000);child.stderr.resume();child.stdout.on('data',chunk=>{size+=chunk.length;if(size>1048576)fail();});
 const lines=createInterface({input:child.stdout,crlfDelay:Infinity});let work=Promise.resolve();
 lines.on('line',line=>{work=work.then(async()=>{if(failed)return;need(line.length<=65536,'PIPE_LIMIT');const item=JSON.parse(line);
  if(item.type==='request'){need(item.index===nextIndex&&nextIndex<cfg.requests.length&&JSON.stringify(item.request)===JSON.stringify(cfg.requests[nextIndex]),'PIPE_CONTEXT');nextIndex++;let value;try{value=await dispatch(item.request);}catch(e){value={error:e.message?.startsWith('N00_')?e.message:'N00_NATIVE_DISPATCH_FAILED'};}child.stdin.write(JSON.stringify({type:'receipt',index:item.index,value})+'\n');}
  else if(item.type==='complete'){need(!complete&&nextIndex===cfg.requests.length&&item.environment_clean===true,'PIPE_COMPLETE');complete=item;child.stdin.end();}
  else throw new Error('N00_NATIVE_WORKER_REFUSED:'+item.stage+':'+item.error_name);
 }).catch(fail);});
 child.once('error',fail);child.once('close',async code=>{await work;clearTimeout(timer);lines.close();if(!failed&&code===0&&complete)ok(complete);else {const e=new Error('N00_NATIVE_WORKER_FAILED');e.reason=failureReason;e.exit=code;e.complete=!!complete;e.requests=nextIndex;bad(e);}});
 child.stdin.on('error',e=>{if(!complete)fail(e);});child.stdin.write(JSON.stringify(cfg)+'\n');
});}
export async function runFixtureNativeSession({execution,journal,requests,parentEnvironment=process.env}){
 assertFixtureExecutionBoundary(execution,journal);need(Array.isArray(requests)&&requests.length<=8,'REQUESTS');
 need(JSON.stringify(requests).length<=32768&&requests.every(r=>r&&r.channel==='cli'&&['GET','HEAD','POST'].includes(r.method)&&typeof r.path==='string'&&r.path.startsWith('/fixture/auth/')&&!r.path.includes('admin/')),'REQUESTS');
 need(lstatSync(workerPath).isFile()&&!lstatSync(workerPath).isSymbolicLink(),'WORKER');const source=readFileSync(workerPath,'utf8');need(source.length<32768,'WORKER');
 const env=fixtureChildEnvironment(parentEnvironment),owner=randomBytes(6).toString('hex'),prefix='buyeros-n00-native-'+owner,networkName=prefix+'-net',containers=[],attempted=[];let networkId,result,networkAttempted=false,originalError;
 const fingerprint=journal.snapshot().target.fingerprint;
 const cleanup={complete:false,containers_absent:[],network_absent:false,fixture_only:true};
 try {
  const endpoint=JSON.parse(await docker(['context','inspect',CONTEXT],env))[0].Endpoints.docker.Host;need(/^npipe:\/.*dockerDesktopLinuxEngine$/.test(endpoint),'LOCAL_DOCKER');
  const image=JSON.parse(await docker(['image','inspect','node:22-bookworm-slim'],env))[0];need(/^sha256:[a-f0-9]{64}$/.test(image.Id),'CACHED_IMAGE');
  networkAttempted=true;networkId=await docker(['network','create','--internal','--label',LABEL+'='+owner,networkName],env);const network=await inspect('network',networkId,env);need(network.Internal&&network.Labels?.[LABEL]===owner&&network.Id===networkId,'NETWORK_POLICY');
  const common=['--label',LABEL+'='+owner,'--read-only','--user','node','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','64','--memory','128m','--cpus','1','--env','BUYEROS_STRICT_INTEGRATION=1'];
  const create=async(name,mode,worker)=>{attempted.push(name);const id=await docker(['create','--pull=never','--name',name,...common,'--network',mode,...(worker?['-i']:[]),image.Id,'node','--input-type=module','-e',worker?source:sinkSource],env);containers.push(id);const info=await inspect('container',id,env);verifyContainer(info,owner);return {id,info};};
  const sink=await create(prefix+'-sink',networkName,false);await docker(['start',sink.id],env);const sinkInfo=await inspect('container',sink.id,env);const address=sinkInfo.NetworkSettings.Networks[networkName];need(address?.NetworkID===networkId&&/^\d+\.\d+\.\d+\.\d+$/.test(address.IPAddress),'OWNED_SINK');
  let ready=false;for(let i=0;i<5;i++){try{await docker(['exec',sink.id,'node','-e',metricsSource],env);ready=true;break;}catch{await new Promise(ok=>setTimeout(ok,50));}}need(ready,'SINK_READY');
  const cfg={probeHost:address.IPAddress,probePort:PORT,requests:[]},control=await create(prefix+'-control',networkName,true);
  const positive=await pipeWorker(control.id,cfg,env,()=>{throw new Error('N00_NATIVE_CONTROL_RPC');});need(Object.values(positive.probes).every(Boolean),'POSITIVE_CONTROL');
  const baseline=JSON.parse(await docker(['exec',sink.id,'node','-e',metricsSource],env));need(baseline.hits===3,'POSITIVE_CONTROL');
  const worker=await create(prefix+'-worker','none',true);
  const value=await pipeWorker(worker.id,{...cfg,requests},env,async request=>{assertFixtureExecutionBoundary(execution,journal);need(journal.snapshot().target.fingerprint===fingerprint,'BOUND_TARGET');return execution.dispatch(request);});
  const metrics=JSON.parse(await docker(['exec',sink.id,'node','-e',metricsSource],env));
  result={fixture_only:true,external_verified:false,parent_os_contained:false,browser_os_contained:false,arbitrary_provider_cli_contained:false,environment_clean:value.environment_clean,runtime_environment_names:value.environment_names,receipts:value.receipts,probes:value.probes,direct_http_requests:metrics.hits-baseline.hits,positive_control:{http_requests:baseline.hits,native_tcp_connected:positive.probes.tcp_connected},worker_policy:{network:worker.info.HostConfig.NetworkMode,read_only:worker.info.HostConfig.ReadonlyRootfs,user:worker.info.Config.User,cap_drop:worker.info.HostConfig.CapDrop,pids_limit:worker.info.HostConfig.PidsLimit,memory:worker.info.HostConfig.Memory,nano_cpus:worker.info.HostConfig.NanoCpus,published_ports:Object.keys(worker.info.HostConfig.PortBindings??{}).length,mounts:worker.info.Mounts.length,environment_names:worker.info.Config.Env.map(s=>s.split('=')[0])},image_id:image.Id,owner,resource_ids:{containers:[...containers],network:networkId},cleanup};
 }catch(error){originalError=error;throw error;}finally {
  const failures=[];for(const name of attempted){try{const v=await inspect('container',name,env);verifyContainer(v,owner);if(!containers.includes(v.Id))containers.push(v.Id);}catch(e){if(!e.absent)failures.push({resource:name,operation:e.operation,detail:e.detail});}}
  if(networkAttempted&&!networkId){try{const v=await inspect('network',networkName,env);need(v.Labels?.[LABEL]===owner&&v.Internal,'OWNERSHIP');networkId=v.Id;}catch(e){if(!e.absent)failures.push({resource:networkName,operation:e.operation,detail:e.detail});}}for(const id of [...containers].reverse()){try{const value=await inspect('container',id,env);verifyContainer(value,owner);await docker(['rm','-f',id],env);need(await absent('container',id,env),'CLEANUP_ABSENCE');cleanup.containers_absent.push(id);}catch(e){failures.push({resource:id,operation:e.operation,detail:e.detail});}}
  if(networkId){try{const value=await inspect('network',networkId,env);need(value.Labels?.[LABEL]===owner&&value.Id===networkId&&value.Internal,'OWNERSHIP');await docker(['network','rm',networkId],env);need(await absent('network',networkId,env),'CLEANUP_ABSENCE');cleanup.network_absent=true;}catch(e){failures.push({resource:networkId,operation:e.operation,detail:e.detail});}}
  cleanup.inspect_retries=readbackRetries.get(env)??0;cleanup.complete=failures.length===0&&cleanup.containers_absent.length===containers.length&&(!networkId||cleanup.network_absent);if(!cleanup.complete){const error=new Error('N00_NATIVE_CLEANUP_FAILED');error.failures=failures;error.original=originalError?.operation;throw error;}
 }
 return result;
}
