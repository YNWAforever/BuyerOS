/** Local N00 execution model only. Owned loopback HTTP; never an external proxy.
 * SDK, browser and the fixed fixture CLI share reservations and write holds.
 * This does not contain arbitrary provider CLIs, OS egress or human Google traffic. */
import {createServer} from 'node:http';
import {createHash} from 'node:crypto';
import {openSync,closeSync,writeFileSync,readFileSync,fsyncSync,lstatSync} from 'node:fs';
import {join,dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn} from 'node:child_process';
import {RealRunJournal} from './neon-real-preflight.mjs';
import {ownedAuthServerUrl} from './neon-counted-proxy.mjs';
import {fixtureChildEnvironment} from './neon-compatibility-harness.mjs';
const gateways=new WeakMap(),boundaries=new WeakMap(),channels=new Set(['sdk','browser','cli','control']);
const safe=new Set(['GET','HEAD']),methods=new Set(['GET','HEAD','POST','DELETE']);
const BODY_LIMIT=32768,RESPONSE_LIMIT=1048576;
function need(value,code){if(!value)throw new Error('N00_EXECUTION_'+code);}
function hash(value){return createHash('sha256').update(value).digest('hex');}
function durable(path,value){const fd=openSync(path,'wx',0o600);try{writeFileSync(fd,JSON.stringify(value,null,2)+'\n');fsyncSync(fd);}finally{closeSync(fd);}}
function readReceipt(journal,item){need(/^execution-http-\d+\.json$/.test(item.evidenceRef??''),'EVIDENCE');const path=join(journal.root,item.evidenceRef);need(lstatSync(path).isFile()&&!lstatSync(path).isSymbolicLink(),'EVIDENCE');const data=JSON.parse(readFileSync(path,'utf8'));need(data.sequence===item.sequence&&data.target_fingerprint===journal.snapshot().target.fingerprint&&data.fixture_only===true&&data.outcome===item.outcome&&/^[a-f0-9]{64}$/.test(data.intent_hash),'EVIDENCE');return data;}
async function bytes(body,limit){const chunks=[];let count=0;if(!body)return Buffer.alloc(0);for await(const chunk of body){count+=chunk.length;need(count<=limit,'RESPONSE_LIMIT');chunks.push(Buffer.from(chunk));}return Buffer.concat(chunks);}
export function createFixtureExecutionBoundary({backend,journal,now=Date.now,timeoutMs=3000}){
 const origin=ownedAuthServerUrl(backend);need(journal instanceof RealRunJournal&&journal.snapshot().target,'BOUND_TARGET');
 const target=journal.snapshot().target;need([target.projectId,target.branchId,target.authId].every(v=>v.startsWith('fictional-execution-'))&&[target.auth.baseUrl,target.auth.issuer,target.auth.jwksUrl].every(v=>new URL(v).hostname.endsWith('.fixture.invalid')),'FIXTURE_TARGET');
 need(Number.isInteger(timeoutMs)&&timeoutMs>=20&&timeoutMs<=3000,'TIMEOUT');
 function validate(input){need(input&&Object.keys(input).every(k=>['channel','path','method','body','headers'].includes(k)),'REQUEST');const {channel,path,method,body=''}=input;
  need(channels.has(channel)&&methods.has(method)&&typeof body==='string','REQUEST');need(Buffer.byteLength(body)<=BODY_LIMIT,'BODY_LIMIT');need(!safe.has(method)||body==='','REQUEST');
  need(typeof path==='string'&&/^\/fixture\/(auth|control)\/[a-zA-Z0-9_/-]+$/.test(path)&&!path.includes('//')&&!path.includes('..'),'PATH');
  let purpose='auth';if(path.startsWith('/fixture/control/')){purpose=method==='DELETE'?'cleanup':'reconcile';need(channel==='control'&&['GET','DELETE'].includes(method)&&body==='','CONTROL');
   if(path==='/fixture/control/target')need(method==='GET','CONTROL');else{const match=/^\/fixture\/control\/(identity|auth|project)\/([a-zA-Z0-9_-]+)$/.exec(path);need(match,'CONTROL');const state=journal.snapshot(),ids={identity:state.identity?.id,auth:target.authId,project:target.projectId};need(ids[match[1]]===match[2],'OWNED_RESOURCE');}
  }else need(channel!=='control','CONTROL');
  return {channel,path,method,body,purpose,headers:new Headers(input.headers),intent:hash(target.fingerprint+'\n'+method+'\n'+path+'\n'+body)};
 }
 function held(intent){for(const item of journal.snapshot().requests){if(!item.operationId.startsWith('execution-http-')){if(['pending','unknown'].includes(item.outcome))return true;continue;}if(item.outcome==='pending')return true;try{const receipt=readReceipt(journal,item);if(!safe.has(receipt.method)&&receipt.intent_hash===intent)return true;}catch{return true;}}return false;}
 const execution={async dispatch(input){const value=validate(input);need(ownedAuthServerUrl(backend)===origin,'OWNED_BACKEND');need(journal.snapshot().target.fingerprint===target.fingerprint,'BOUND_TARGET');if(!safe.has(value.method))need(!held(value.intent),'HELD_INTENT');
  const sequence=journal.snapshot().requests.length+1,operationId='execution-http-'+sequence;
  const reservation=journal.reserveRequest(value.purpose,operationId,now());let status=null,body='',location=null,outcome='unknown',reason='transport-unknown',responseHeaders=[];
  try{const response=await fetch(origin+value.path,{method:value.method,headers:value.headers,...(!safe.has(value.method)?{body:value.body}:{}),redirect:'manual',signal:AbortSignal.timeout(timeoutMs)});status=response.status;
   body=(await bytes(response.body,RESPONSE_LIMIT)).toString('utf8');const redirect=response.headers.get('location');if(redirect){const next=new URL(redirect,origin);need(next.origin===origin&&!next.username&&!next.password&&!next.hash&&!next.search,'REDIRECT_REFUSED');validate({...input,path:next.pathname,method:'GET',body:''});location=next.pathname;}
   responseHeaders=[...response.headers].filter(([key])=>!['connection','content-length','transfer-encoding','location','set-cookie'].includes(key));const cookies=response.headers.getSetCookie();for(const cookie of cookies)responseHeaders.push(['set-cookie',cookie]);
   outcome=status>=500&&!safe.has(value.method)?'unknown':status>=400?'rejected':'accepted';reason='http-response';
  }catch(error){body='';location=null;responseHeaders=[];reason=error.message?.startsWith('N00_EXECUTION_')?error.message:'transport-unknown';}
  const ref='execution-http-'+reservation.sequence+'.json';try{durable(join(journal.root,ref),{schemaVersion:1,fixture_only:true,external_verified:false,sequence,channel:value.channel,method:value.method,path:value.path,intent_hash:value.intent,target_fingerprint:target.fingerprint,status,outcome,reason});journal.settleRequest(operationId,outcome,ref);}catch{throw new Error('N00_EXECUTION_EVIDENCE');}
  if(reason==='N00_EXECUTION_REDIRECT_REFUSED')throw new Error(reason);
  return {status:status??503,body,location,outcome,headers:responseHeaders,evidenceRef:ref,fixture_only:true,external_verified:false};
 },holds(input){const value=validate(input);return held(value.intent);},report(){return {fixture_only:true,external_verified:false,arbitrary_cli_contained:false,real_provider_traffic_contained:false,journal:journal.snapshot()};}};
 boundaries.set(execution,journal);return execution;
}
export function assertFixtureExecutionBoundary(execution,journal){need(boundaries.has(execution)&&boundaries.get(execution).root===journal?.root,'CLEANUP_BOUNDARY');}
export function createFixtureExecutionGateway({execution,nonce}){
 need(boundaries.has(execution)&&/^[a-zA-Z0-9_-]{43,128}$/.test(nonce??''),'GATEWAY_OWNER');
 const server=createServer(async(req,res)=>{try{
  if(req.method==='GET'&&req.url==='/'){res.setHeader('Content-Type','text/html');res.end('<!doctype html><html><body><h1>N00 accounting fixture</h1></body></html>');return;}
  need(req.headers['x-n00-owner']===nonce,'GATEWAY_OWNER');const origin='http://127.0.0.1:'+server.address().port;need(!req.headers.origin||req.headers.origin===origin,'GATEWAY_ORIGIN');
  if(req.url?.startsWith('/sdk/auth/')){const path='/fixture/auth/'+req.url.slice('/sdk/auth/'.length);const body=(await bytes(req,BODY_LIMIT)).toString('utf8');const headers=new Headers();for(const [key,value] of Object.entries(req.headers))if(!['host','connection','content-length','x-n00-owner'].includes(key)&&value!==undefined)headers.set(key,Array.isArray(value)?value.join(', '):value);const result=await execution.dispatch({channel:'sdk',path,method:req.method,body,headers});res.statusCode=result.status;for(const [key,value] of result.headers)res.appendHeader(key,value);if(result.location)res.setHeader('Location','/sdk/auth/'+result.location.slice('/fixture/auth/'.length));res.end(result.body);return;}
  need(req.method==='POST'&&req.url==='/dispatch','GATEWAY_PATH');const input=JSON.parse((await bytes(req,BODY_LIMIT)).toString('utf8'));const result=await execution.dispatch(input);res.setHeader('Content-Type','application/json');res.end(JSON.stringify(result));
 }catch(error){res.statusCode=403;res.setHeader('Content-Type','application/json');res.end(JSON.stringify({code:error.message?.startsWith('N00_')?error.message:'N00_EXECUTION_GATEWAY_REFUSED',fixture_only:true,external_verified:false}));}});
 gateways.set(server,nonce);return server;
}
export function runFixtureCli({gateway,nonce,request,parentEnvironment=process.env}){
 need(gateways.has(gateway)&&gateways.get(gateway)===nonce,'CLI_OWNER');const address=gateway.address();need(gateway.listening&&address?.address==='127.0.0.1','CLI_OWNER');need(request?.channel==='cli','CLI_CHANNEL');
 const environment={...fixtureChildEnvironment(parentEnvironment),N00_FIXTURE_CLI_URL:'http://127.0.0.1:'+address.port,N00_FIXTURE_CLI_NONCE:nonce};
 return new Promise((ok,bad)=>{const child=spawn(process.execPath,[resolve(dirname(fileURLToPath(import.meta.url)),'neon-execution-cli.mjs')],{env:environment,stdio:['pipe','pipe','pipe'],windowsHide:true});let output='',size=0;const timer=setTimeout(()=>child.kill(),5000);child.stdout.on('data',chunk=>{size+=chunk.length;if(size>RESPONSE_LIMIT)child.kill();else output+=chunk;});child.stderr.resume();child.on('error',()=>{clearTimeout(timer);bad(new Error('N00_EXECUTION_CLI_FAILED'));});child.on('close',code=>{clearTimeout(timer);try{need(code===0&&size<=RESPONSE_LIMIT,'CLI_FAILED');ok(JSON.parse(output));}catch{bad(new Error('N00_EXECUTION_CLI_FAILED'));}});child.stdin.end(JSON.stringify(request));});
}
