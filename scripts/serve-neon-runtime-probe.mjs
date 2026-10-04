/** Fictional metadata only, runtime env after build; private vars never become evidence. */
import {createServer} from 'node:http';
import {randomBytes,createHash} from 'node:crypto';
import {execFileSync,execFile,spawn} from 'node:child_process';
import {existsSync,readFileSync,writeFileSync,appendFileSync,mkdirSync,mkdtempSync,readdirSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {resolve,join} from 'node:path';
import {realRuntimeEnvironment} from './neon-real-preflight.mjs';
import {fixtureChildEnvironment} from './neon-compatibility-harness.mjs';
import {removeOwnedRuntimeRoot} from './neon-runtime-cleanup.mjs';
const target=process.env.BUYEROS_N00_TARGET,scenario=process.env.BUYEROS_N00_PROBE_SCENARIO??'valid',runId=process.env.BUYEROS_N00_RUN_ID;
if(!['portable','vercel'].includes(target)||!['valid','missing','mismatch','expired'].includes(scenario)||!/^[a-f0-9]{12}$/.test(runId??''))throw new Error('N00_PROBE_SCOPE');
const area=resolve('test-results/neon-runtime-built'),compiledArea=resolve('test-results/neon-runtime-built-dispatcher'),inputs=JSON.parse(readFileSync(join(compiledArea,'build-inputs.json'),'utf8'));
if(inputs.profile!=='runtime-probe-dispatcher')throw new Error('N00_PROBE_BUILD_PROFILE');
mkdirSync(join(area,'runs'),{recursive:true});
const folder=join(area,'runs',`${target}-${scenario}-${runId}`);mkdirSync(folder,{recursive:false});
const root=mkdtempSync(join(tmpdir(),'buyeros-n00-runtime-'));
const ownership={fixture_only:true,target,scenario,runId,pid:process.pid,private_root:root};
writeFileSync(join(root,'owner.json'),JSON.stringify(ownership)+'\n',{flag:'wx',mode:0o600});
writeFileSync(join(folder,'runtime.json'),JSON.stringify(ownership)+'\n',{flag:'wx'});
const now=Date.now(),created=scenario==='expired'?now-2*60*60_000-60_000:now,stamp=new Date(created).toISOString();
const scope={projectId:'fictional-probe-project-'+runId,branchId:'fictional-probe-branch-'+runId,authId:'fictional-probe-auth-'+runId,orgId:'org-soft-sunset-25251479',name:'buyeros-neon-auth-n00-20261004',regionId:'aws-ap-southeast-1'};
const manifest={schemaVersion:1,proposal:scope.name,sourceSha:inputs.base,...scope,creationMode:'new-empty',createdAt:stamp,expiresAt:new Date(created+2*60*60_000).toISOString(),
 readback:{...scope,observedAt:stamp,subscription:'free_v3',emailDeliveryEnabled:false,emailPasswordEnabled:false,emailHooksEnabled:false,methods:['google'],trustedOrigins:['http://localhost:44890']},
 auth:{baseUrl:`https://${runId}.fixture.invalid/auth`,issuer:`https://${runId}.fixture.invalid`,audience:'fictional-probe-audience-'+runId,jwksUrl:`https://${runId}.fixture.invalid/auth/jwks`,algorithm:'EdDSA',keyType:'OKP',curve:'Ed25519'}};
const secret=randomBytes(32).toString('base64url');
let childEnv=scenario==='missing'?fixtureChildEnvironment(process.env):realRuntimeEnvironment(process.env,manifest,secret,created);
if(scenario==='mismatch')childEnv.N00_AUTH_AUDIENCE='fictional-probe-mismatched';
childEnv={...childEnv,N00_RUNTIME_PROBE_MODE:'fixture'};
// Scan emitted text before injection; only exact fresh runtime values, never print them.
let scanned=0,leaks=0;
function scan(folder){for(const entry of readdirSync(folder,{withFileTypes:true})){const path=join(folder,entry.name);if(entry.isDirectory())scan(path);else if(entry.isFile()&&/\.(?:[cm]?js|json|html|css|map)$/.test(entry.name)){const text=readFileSync(path,'utf8');scanned++;for(const value of [secret,manifest.auth.baseUrl,scope.projectId,scope.branchId,scope.authId])if(text.includes(value))leaks++;}}}
scan(join(compiledArea,target));writeFileSync(join(folder,'runtime-value-leak-check.json'),JSON.stringify({fixture_only:true,emitted_text_files:scanned,exact_runtime_value_matches:leaks,cookie_secret_checked:true})+'\n');
if(leaks)throw new Error('N00_PROBE_BUILD_VALUE_LEAK');
const runtimeVars=Object.fromEntries(Object.entries(childEnv).filter(([key])=>key.startsWith('N00_')||key.startsWith('NEON_AUTH_')));
writeFileSync(join(folder,'configuration.json'),JSON.stringify({fixture_only:true,external_verified:false,compiled_source_sha:inputs.base,runner_head:execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim(),scenario,
 manifest:scenario==='missing'?null:manifest,keys:Object.keys(runtimeVars),cookie_secret_sha256:createHash('sha256').update(secret).digest('hex'),environment_injected_after_build:true},null,2)+'\n');
const children=[];let stopping=false,control;
function capture(stream){let buffer='';stream.on('data',data=>{buffer+=data.toString();const lines=buffer.split('\n');buffer=lines.pop();for(const line of lines)appendFileSync(join(folder,'runtime-output.log'),line.replaceAll(secret,'[REDACTED]')+'\n');});stream.on('end',()=>{if(buffer)appendFileSync(join(folder,'runtime-output.log'),buffer.replaceAll(secret,'[REDACTED]'));});}
function launch(args){const child=spawn(process.execPath,args,{env:childEnv,windowsHide:true,stdio:['ignore','pipe','pipe']});children.push(child);writeFileSync(join(folder,'children.json'),JSON.stringify({fixture_only:true,pids:children.map(item=>item.pid)})+'\n');capture(child.stdout);capture(child.stderr);child.once('error',()=>stop(1));child.once('exit',code=>{if(!stopping)stop(code??1);});}
async function stop(code=0){
 if(stopping)return;stopping=true;let cleanupPhase='owned-children';const deadline=Date.now()+18000;
 control?.closeAllConnections();control?.close();
 const results=await Promise.all(children.map(child=>new Promise(ok=>{
  if(child.exitCode!==null||!child.pid){ok({pid:child.pid,already_exited:true});return;}
  if(process.platform==='win32')execFile('taskkill',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,timeout:15000},error=>ok({pid:child.pid,command_exit:error?(error.code??'TASKKILL_FAILED'):0}));
  else{child.once('exit',()=>ok({pid:child.pid,terminated:true}));child.kill();setTimeout(()=>ok({pid:child.pid,terminated:child.exitCode!==null}),5000).unref();}
 })));
 try{
  while(true){
   for(let i=0;i<children.length;i++){const child=children[i];try{process.kill(child.pid,0);results[i].process_absent=false;}catch(error){if(error.code!=='ESRCH')throw error;results[i].process_absent=true;}}
   if(results.every(item=>item.process_absent)||Date.now()>=deadline)break;await new Promise(ok=>setTimeout(ok,100));
  }
  writeFileSync(join(folder,'child-cleanup.json'),JSON.stringify({fixture_only:true,children:results})+'\n');
  if(results.some(item=>!item.process_absent))throw new Error('N00_PROBE_CHILD_STILL_RUNNING');
  cleanupPhase='owned-root-removal';const removal=await removeOwnedRuntimeRoot(root,ownership);
  writeFileSync(join(folder,'cleanup.json'),JSON.stringify({fixture_only:true,private_root_removed:!existsSync(root),runtime_configuration_removed:true,owned_children_absent:true,owned_root_removal:removal,external_resources:0})+'\n');
 }catch(error){writeFileSync(join(folder,'cleanup-failure.json'),JSON.stringify({fixture_only:true,phase:cleanupPhase,code:/^N00_/.test(error.message)?error.message:'N00_PROBE_CLEANUP_FAILED',native_code:error.code??null,errno:error.errno??null,syscall:error.syscall??null})+'\n');code=1;}
 process.exit(code);
}
process.on('SIGTERM',()=>stop());process.on('SIGINT',()=>stop());
try{
 control=createServer((req,res)=>{if(req.method!=='POST'||req.url!=='/n00-runtime-stop'||req.headers['x-n00-owner']!==runId){res.statusCode=403;res.end();return;}res.setHeader('Content-Type','application/json');res.end('{"fixture_only":true}');setTimeout(()=>stop(),25);});
 await new Promise((ok,bad)=>{control.once('error',bad);control.listen(44901,'127.0.0.1',ok);});
 if(target==='portable'){
  const buildRoot=resolve(compiledArea,'portable/dist'),original=JSON.parse(readFileSync(join(buildRoot,'server/wrangler.json'),'utf8'));
  const config={...original,main:join(buildRoot,'server/index.js'),assets:{...original.assets,directory:join(buildRoot,'client')},vars:runtimeVars};
  const configPath=join(root,'wrangler.json');writeFileSync(configPath,JSON.stringify(config),{flag:'wx',mode:0o600});
  launch(['node_modules/wrangler/bin/wrangler.js','dev','--local','--config',configPath,'--ip','127.0.0.1','--port','44900','--persist-to',join(root,'state'),'--inspector-port','0']);
 }else launch(['scripts/neon-runtime-node-bridge.mjs']);
 // Own readiness failures: Windows Playwright startup termination bypasses signal handlers.
 const deadline=Date.now()+20000;let ready=false,lastStatus=null;
 while(Date.now()<deadline&&!stopping){try{lastStatus=(await fetch('http://127.0.0.1:44900/',{signal:AbortSignal.timeout(1000)})).status;if(lastStatus===200){ready=true;break;}}catch{}await new Promise(ok=>setTimeout(ok,100));}
 writeFileSync(join(folder,'readiness.json'),JSON.stringify({fixture_only:true,ready,lastStatus})+'\n');if(!ready)await stop(1);
}catch{await stop(1);throw new Error('N00_PROBE_START_FAILED');}
