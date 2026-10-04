import {createServer} from 'node:http';
import {generateKeyPairSync,sign,createHmac,randomBytes} from 'node:crypto';
import {spawn,spawnSync,execFile,execFileSync} from 'node:child_process';
import {existsSync,readFileSync,statSync,mkdtempSync,writeFileSync,mkdirSync,realpathSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {resolve,join,relative} from 'node:path';
import {pathToFileURL} from 'node:url';
import {assertLoopbackUrl,fixtureChildEnvironment,staticAssetPath} from './neon-compatibility-harness.mjs';
import {createOwnedAuthServer,createCountedAuthProxy} from './neon-counted-proxy.mjs';
import {RealRunJournal} from './neon-real-preflight.mjs';
const target=process.env.BUYEROS_N00_TARGET,requestedRunId=process.env.BUYEROS_N00_RUN_ID;
if(requestedRunId&&!/^[a-f0-9]{12}$/.test(requestedRunId))throw new Error('N00 fixture run ID refused');
if(!['portable','vercel'].includes(target))throw new Error('N00 requires portable or vercel actual output');
// The Vercel bridge runs in this process too: strip inherited application/provider env.
const isolatedEnv=fixtureChildEnvironment(process.env);
for(const key of Object.keys(process.env))delete process.env[key];
Object.assign(process.env,isolatedEnv,{BUYEROS_N00_TARGET:target});
const upstream=assertLoopbackUrl('http://127.0.0.1:44891/fixture/auth');
// Synthetic budget-record shape only: never Neon readback or owner authorization.
const budgetRoot=mkdtempSync(join(tmpdir(),'buyeros-n00-real-')),runLabel=requestedRunId??randomBytes(6).toString('hex'),created=Date.now(),stamp=new Date(created).toISOString();
const fixtureIds={projectId:'fictional-project-'+runLabel,branchId:'fictional-branch-'+runLabel,authId:'fictional-auth-'+runLabel};
const fixtureScope={...fixtureIds,orgId:'org-soft-sunset-25251479',name:'buyeros-neon-auth-n00-20261004',regionId:'aws-ap-southeast-1'};
const budget=RealRunJournal.create(budgetRoot,{approvalReference:'fixture-only-no-external-authority',approvedAt:stamp});
budget.bindTarget({schemaVersion:1,proposal:'buyeros-neon-auth-n00-20261004',sourceSha:execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim(),...fixtureScope,creationMode:'new-empty',createdAt:stamp,expiresAt:new Date(created+2*60*60_000).toISOString(),
 readback:{...fixtureScope,observedAt:stamp,subscription:'free_v3',emailDeliveryEnabled:false,emailPasswordEnabled:false,emailHooksEnabled:false,methods:['google'],trustedOrigins:['http://localhost:44890']},
 auth:{baseUrl:'https://budget-shape.fixture.invalid/auth',issuer:'https://budget-shape.fixture.invalid',audience:'fictional-budget-shape',jwksUrl:'https://budget-shape.fixture.invalid/auth/jwks',algorithm:'EdDSA',keyType:'OKP',curve:'Ed25519'}},created);
const proofFolder=resolve('test-results/neon-counted-transport',target+'-'+runLabel);mkdirSync(proofFolder);
const ownership={fixture_only:true,runId:runLabel,pid:process.pid,target,budget_root:budgetRoot};
writeFileSync(join(budgetRoot,'fixture-owner.json'),JSON.stringify(ownership)+'\n',{flag:'wx'});writeFileSync(join(proofFolder,'runtime.json'),JSON.stringify(ownership)+'\n',{flag:'wx'});
const children=[];let appServer,proxyServer,stopping=false;
function captureBudget() {
 const report=proxyServer?.fixtureReport(),folder=proofFolder;
 const records=budget.snapshot().requests;
 // Export counters/outcomes only. The synthetic validation record is not provider evidence.
 writeFileSync(join(folder,'budget.json'),JSON.stringify({fixture_only:true,external_requests:0,runner_head_at_execution:budget.snapshot().target.sourceSha,compiled_inputs:'test-results/neon-compatibility/build-inputs.json',metrics:report?.metrics??null,requests:records,limit:200,cleanup_reserve:20,sdk_fixture_base:upstream.href,owned_backend_port:44894,real_configuration_verified:false},null,2)+'\n');
 for(const record of records)if(record.evidenceRef){const file=join(budgetRoot,record.evidenceRef);if(existsSync(file))writeFileSync(join(folder,record.evidenceRef),readFileSync(file));}
 if(realpathSync(budgetRoot)!==resolve(budgetRoot)||!relative(resolve(tmpdir()),budgetRoot).startsWith('buyeros-n00-real-'))throw new Error('unowned fixture journal cleanup');
 rmSync(budgetRoot,{recursive:true});writeFileSync(join(folder,'cleanup.json'),JSON.stringify({fixture_only:true,owned_journal_removed:true,external_resources:0})+'\n');
}
const {privateKey,publicKey}=generateKeyPairSync('ed25519');
const kid='fictional-n00-key',jwk={...publicKey.export({format:'jwk'}),kid,alg:'EdDSA',use:'sig'};
const user={id:'n00-user',name:'Fictional N00',email:'n00@fixture.invalid',emailVerified:false,createdAt:new Date().toISOString(),updatedAt:new Date().toISOString()};
const session={id:'n00-session',userId:user.id,token:'fictional-session',createdAt:user.createdAt,updatedAt:user.updatedAt,expiresAt:new Date(Date.now()+3_600_000).toISOString()};
function issue(kind='valid') {
 const now=Math.floor(Date.now()/1000),header={alg:kind==='wrong-algorithm'?'HS256':'EdDSA',kid:kind==='unknown-kid'?'fictional-unknown':kid,typ:'JWT'};
 const claims={sub:user.id,iss:kind==='wrong-issuer'?'https://wrong.invalid':upstream.origin,aud:kind==='wrong-audience'?'wrong-audience':upstream.origin,iat:now,exp:kind==='expired'?now-120:now+900};
 const message=[header,claims].map(v=>Buffer.from(JSON.stringify(v)).toString('base64url')).join('.');
 const signature=kind==='wrong-algorithm'?createHmac('sha256','fictional').update(message).digest():sign(null,Buffer.from(message),privateKey);
 return `${message}.${signature.toString('base64url')}`;
}
const cookie='__Secure-neon-auth.session_token=fictional-session; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=3600';
let authenticated=false;
// Fictional managed callback protocol only; no provider/account/network activation.
const appOrigin='http://localhost:44890';
const flows=new Map(),verifiers=new Map();
const challengeName='__Secure-neon-auth.session_challenge';
const challengeCookie=(value,maxAge=300)=>challengeName+'='+value+'; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age='+maxAge;
function cookieValue(header,name){return (header??'').split(';').map(part=>part.trim()).find(part=>part.startsWith(name+'='))?.slice(name.length+1);}
const authServer=createOwnedAuthServer(async(req,res)=>{
 const url=new URL(req.url,upstream.origin),path=url.pathname;
 const active=authenticated&&(req.headers.cookie??'').includes('__Secure-neon-auth.session_token=fictional-session');
 res.setHeader('Content-Type','application/json');
 if(path==='/fixture-token'){res.end(JSON.stringify({token:issue(url.searchParams.get('kind')??'valid')}));return;}
 if(path==='/fixture/auth/.well-known/jwks.json'){res.end(JSON.stringify({keys:[jwk]}));return;}
 if(path==='/fixture/auth/sign-in/email'&&req.method==='POST'){
  let body='';for await(const chunk of req)body+=chunk;
  const credentials=JSON.parse(body);if(credentials.email!==user.email||credentials.password!=='fictional-password'){res.statusCode=401;res.end('{}');return;}
  authenticated=true;res.setHeader('Set-Cookie',cookie);res.end(JSON.stringify({redirect:false,token:session.token,user}));return;
 }
 if(path==='/fixture/auth/sign-in/social'&&req.method==='POST'){
  let body='';for await(const chunk of req)body+=chunk;
  const input=JSON.parse(body);let callback;try{callback=new URL(input.callbackURL);}catch{}
  if(input.provider!=='google'||callback?.origin!==appOrigin||callback.pathname!=='/compat/return'||req.headers.origin!==appOrigin||req.headers['x-neon-auth-middleware']!=='true'){res.statusCode=400;res.end('{"code":"INVALID_FIXTURE_FLOW"}');return;}
  if(flows.size>=50){res.statusCode=429;res.end('{}');return;}
  const state=randomBytes(24).toString('base64url'),challenge=randomBytes(24).toString('base64url');
  flows.set(state,{challenge,callback:callback.href,expires:Date.now()+300_000});authenticated=false;
  res.setHeader('Set-Cookie',challengeCookie(challenge));res.end(JSON.stringify({redirect:true,url:upstream.href+'/callback/google?state='+state}));return;
 }
 if(path==='/fixture/auth/callback/google'){
  const state=url.searchParams.get('state'),flow=flows.get(state);flows.delete(state);
  if(!flow||flow.expires<=Date.now()){res.statusCode=401;res.end('{"code":"INVALID_FIXTURE_STATE"}');return;}
  const verifier=randomBytes(24).toString('base64url');verifiers.set(verifier,flow);
  const callback=new URL(flow.callback);callback.searchParams.set('neon_auth_session_verifier',verifier);
  res.statusCode=302;res.setHeader('Location',callback.href);res.end();return;
 }
 if(path==='/fixture/auth/get-session'){
  if(url.searchParams.has('neon_auth_session_verifier')){
   const value=url.searchParams.get('neon_auth_session_verifier'),flow=verifiers.get(value);
   if(!flow||flow.expires<=Date.now()||cookieValue(req.headers.cookie,challengeName)!==flow.challenge||req.headers.origin!==appOrigin||req.headers['x-neon-auth-middleware']!=='true'){res.statusCode=401;res.end('{"code":"INVALID_FIXTURE_VERIFIER"}');return;}
   verifiers.delete(value);authenticated=true;res.setHeader('Set-Cookie',[cookie,challengeCookie('',0)]);res.setHeader('set-auth-jwt',issue());res.end(JSON.stringify({session,user}));return;
  }
  if(active)res.setHeader('set-auth-jwt',issue());res.end(JSON.stringify(active?{session,user}:null));return;
 }
 if(path==='/fixture/auth/token'){res.statusCode=active?200:401;res.end(JSON.stringify(active?{token:issue()}:{code:'UNAUTHORIZED'}));return;}
 if(path==='/fixture/auth/sign-out'&&req.method==='POST'){authenticated=false;res.setHeader('Set-Cookie',cookie.replace('fictional-session','').replace('Max-Age=3600','Max-Age=0'));res.end('{"success":true}');return;}
 if(path==='/fixture/auth/callback/fixture'&&url.searchParams.get('state')==='fictional-state'){authenticated=true;res.statusCode=302;res.setHeader('Set-Cookie',cookie);res.setHeader('Location','http://localhost:44890/compat');res.end('{}');return;}
 res.statusCode=404;res.end('{"fixtureOnly":true}');
});
try {
 await new Promise((ok,bad)=>{authServer.once('error',bad);authServer.listen(44894,'127.0.0.1',ok);});
 proxyServer=createCountedAuthProxy({backend:authServer,journal:budget,stopNonce:runLabel,onStop:()=>stop()});
 await new Promise((ok,bad)=>{proxyServer.once('error',bad);proxyServer.listen(44891,'127.0.0.1',ok);});
}catch(error){stop(1);throw error;}
// Deliberate env allowlist: no inherited Auth/DB/provider credentials reach fixture children.
const childEnv=fixtureChildEnvironment(process.env);
function launch(command,args){const child=spawn(command,args,{env:childEnv,stdio:'inherit',windowsHide:true});children.push(child);child.on('error',error=>{console.error(error);stop(1);});child.on('exit',code=>{if(!stopping)stop(code??1);});return child;}
async function stop(code=0){
 if(stopping)return;stopping=true;
 appServer?.close();proxyServer?.closeAllConnections();proxyServer?.close();authServer.closeAllConnections();authServer.close();
 // Independent owned child trees must terminate concurrently: sequential Windows
 // taskkill timeouts exceeded Playwright's cleanup deadline on portable output.
 const childResults=await Promise.all(children.map(child=>new Promise(ok=>{
  if(child.exitCode!==null||!child.pid){ok({pid:child.pid,already_exited:true});return;}
  if(process.platform==='win32')execFile('taskkill',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,timeout:5000},error=>ok({pid:child.pid,terminated:child.exitCode!==null,command_exit:error?.code??0}));
  else{child.once('exit',()=>ok({pid:child.pid,terminated:true}));child.kill();setTimeout(()=>ok({pid:child.pid,terminated:child.exitCode!==null}),5000).unref();}
 })));
 await new Promise(ok=>setTimeout(ok,500));
 try{
  for(let i=0;i<children.length;i++){
   const child=children[i],result=childResults[i];result.event_terminated=child.exitCode!==null||child.signalCode!==null;
   // On Windows the taskkill command can finish before ChildProcess updates its
   // exit fields. Require OS ESRCH for this exact owned PID, not command exit0.
   try{process.kill(child.pid,0);result.process_absent=false;}catch(error){if(error.code!=='ESRCH')throw error;result.process_absent=true;}
  }
  writeFileSync(join(proofFolder,'child-cleanup.json'),JSON.stringify({fixture_only:true,children:childResults})+'\n');
  if(childResults.some(result=>!result.process_absent))throw new Error('N00_FIXTURE_CHILD_STILL_RUNNING');captureBudget();
 }catch(error){console.error('N00 fixture evidence/cleanup failed',error.code??error.message);code=1;}
 process.exit(code);
}
process.on('SIGTERM',()=>stop());process.on('SIGINT',()=>stop());process.on('exit',()=>{for(const child of children){if(process.platform==='win32'&&child.exitCode===null&&child.pid)spawnSync('taskkill',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,stdio:'ignore',timeout:5000});else child.kill();}});
launch('uv',['run','--frozen','--project','services/api','python',resolve('tests/fixtures/neon-compatibility/verify.py')]);
// Wait for the actual diagnostic process, before advertising app readiness.
const readyDeadline=Date.now()+20_000;let apiReady=false;
while(Date.now()<readyDeadline&&!stopping){try{apiReady=(await fetch('http://127.0.0.1:44892/verify',{signal:AbortSignal.timeout(1000)})).status===401;if(apiReady)break;}catch{}await new Promise(ok=>setTimeout(ok,100));}
if(!apiReady){stop(1);throw new Error('N00 FastAPI diagnostic did not become ready');}
if(target==='portable'){
 const config=resolve('test-results/neon-compatibility/portable/dist/server/wrangler.json');if(!existsSync(config))throw new Error('actual portable output missing');
 launch(process.execPath,['node_modules/wrangler/bin/wrangler.js','dev','--local','--config',config,'--ip','127.0.0.1','--port','44890']);
}else{
 const entry=resolve('test-results/neon-compatibility/vercel/.vercel/output/functions/__server.func/index.mjs');if(!existsSync(entry))throw new Error('actual Vercel output missing');
 process.env.NODE_ENV='production';const {default:handler}=await import(pathToFileURL(entry).href);
 appServer=createServer(async(req,res)=>{try{
  const pathname=new URL(req.url,'http://localhost:44890').pathname;
  if(['GET','HEAD'].includes(req.method)&&pathname!=='/'){const file=staticAssetPath(resolve('test-results/neon-compatibility/vercel/.vercel/output/static'),pathname);if(existsSync(file)&&statSync(file).isFile()){res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'application/octet-stream');res.end(req.method==='HEAD'?undefined:readFileSync(file));return;}}
  const body=[];for await(const chunk of req)body.push(chunk);
  const request=new Request(`http://localhost:44890${req.url}`,{method:req.method,headers:req.headers,...(!['GET','HEAD'].includes(req.method)?{body:Buffer.concat(body)}:{})});
  const response=await handler.fetch(request,{waitUntil(){}});
  res.statusCode=response.status;for(const [key,value]of response.headers)if(key!=='set-cookie')res.setHeader(key,value);
  const cookies=response.headers.getSetCookie();if(cookies.length)res.setHeader('Set-Cookie',cookies);
  res.end(Buffer.from(await response.arrayBuffer()));
 }catch(error){console.error(error);res.statusCode=500;res.end('N00 built handler failure');}});
 await new Promise((ok,bad)=>{appServer.once('error',bad);appServer.listen(44890,'127.0.0.1',ok);});
}
