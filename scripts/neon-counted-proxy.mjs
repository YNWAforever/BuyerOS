/** Count only fictional auth traffic to a newly owned loopback HTTP server.
 * No external hostname/configuration, paid provider, or real account is accepted. */
import {createServer} from 'node:http';
import {createHash} from 'node:crypto';
import {openSync,closeSync,writeFileSync,fsyncSync} from 'node:fs';
import {join} from 'node:path';
import {RealRunJournal} from './neon-real-preflight.mjs';
const owned=new WeakSet(),safeMethods=new Set(['GET','HEAD']);
const hop=new Set(['host','connection','content-length','transfer-encoding','keep-alive','upgrade','proxy-authenticate','proxy-authorization','te','trailer','content-encoding']);
const BODY_LIMIT=32*1024,RESPONSE_LIMIT=1024*1024;
function deny(code,status=503){return Object.assign(new Error(code),{status});}
function address(server) {const value=server?.address?.();if(!owned.has(server)||!server.listening||!value||typeof value==='string'||value.address!=='127.0.0.1')throw deny('N00_FIXTURE_OWNED_BACKEND_REQUIRED');return 'http://127.0.0.1:'+value.port;}
export function createOwnedAuthServer(handler) {const server=createServer(handler);owned.add(server);return server;}
function unknownWrites(journal) {
 // Old receipts do not authenticate method/intent metadata. A resumed unresolved
 // reservation therefore holds every state-changing request until reconciliation.
 // Reads remain available; corrupt/legacy receipt data cannot erase this hold.
 return {hashes:new Set(),all:journal.snapshot().requests.some(record=>record.purpose==='auth'&&['pending','unknown'].includes(record.outcome))};
}
function respond(res,status,code) {if(!res.headersSent){res.statusCode=status;res.setHeader('Content-Type','application/json');res.setHeader('X-N00-Fixture-Only','true');}res.end(JSON.stringify({code,fixture_only:true}));}
async function bodyBytes(req) {
 const chunks=[];let size=0;
 for await(const chunk of req){size+=chunk.length;if(size<=BODY_LIMIT)chunks.push(chunk);}
 if(size>BODY_LIMIT)throw deny('N00_FIXTURE_BODY_LIMIT',413);return Buffer.concat(chunks);
}
async function responseBytes(response) {
 const chunks=[];let size=0;if(!response.body)return Buffer.alloc(0);
 const reader=response.body.getReader();
 try {while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>RESPONSE_LIMIT){await reader.cancel();throw deny('N00_FIXTURE_RESPONSE_LIMIT');}chunks.push(value);}return Buffer.concat(chunks);}
 finally {reader.releaseLock();}
}
export function createCountedAuthProxy({backend,journal,now=Date.now,timeoutMs=3000,stopNonce,onStop}) {
 const upstream=address(backend);
 if(onStop&&(!/^[a-f0-9]{12}$/.test(stopNonce??'')||typeof onStop!=='function'))throw deny('N00_FIXTURE_STOP_OWNER_REQUIRED');
 if(!(journal instanceof RealRunJournal)||!journal.snapshot().target)throw deny('N00_FIXTURE_BOUND_TARGET_REQUIRED');
 if(!Number.isInteger(timeoutMs)||timeoutMs<20||timeoutMs>3000)throw deny('N00_FIXTURE_TIMEOUT_REQUIRED');
 const blocked=unknownWrites(journal),inFlight=new Set(),metrics={received:0,forwarded:0,locally_rejected:0,unknown:0};
 const proxy=createServer(async(req,res)=>{
  if(req.method==='POST'&&req.url==='/n00-fixture-stop'&&onStop){if(req.headers['x-n00-owner']!==stopNonce){respond(res,403,'N00_FIXTURE_STOP_OWNER_REFUSED');return;}res.once('finish',onStop);respond(res,200,'N00_FIXTURE_STOPPING');return;}
  if(req.method==='GET'&&req.url==='/n00-fixture-budget'){const records=journal.snapshot().requests;res.setHeader('Content-Type','application/json');res.setHeader('Cache-Control','no-store');res.end(JSON.stringify({fixture_only:true,external_requests:0,reserved:records.length,forwarded:metrics.forwarded,pending:records.filter(v=>v.outcome==='pending').length,rejected:records.filter(v=>v.outcome==='rejected').length,unknown:records.filter(v=>v.outcome==='unknown').length,limit:200,cleanup_reserve:20}));return;}
  metrics.received++;let reservation,fingerprint=null,path=null,upstreamStarted=false,held=false;
  const method=req.method??'GET';let write=!safeMethods.has(method);
  function settle(outcome,status,reason) {
   if(outcome==='unknown'&&write){if(fingerprint)blocked.hashes.add(fingerprint);else blocked.all=true;}
   if(outcome==='unknown')metrics.unknown++;
   const ref='fixture-http-'+reservation.sequence+'.json';
   const fd=openSync(join(journal.root,ref),'wx',0o600);
   try {writeFileSync(fd,JSON.stringify({schemaVersion:1,fixture_only:true,sequence:reservation.sequence,method,path,state_changing:write,fingerprint,status,reason,outcome},null,2)+'\n');fsyncSync(fd);}finally {closeSync(fd);}
   journal.settleRequest(reservation.operationId,outcome,ref);
  }
  try {
   // Synchronous durable reservation happens before body collection or HTTP dispatch.
   const next=journal.snapshot().requests.length+1;
   reservation=journal.reserveRequest('auth','fixture-http-'+next,now());
   if(!req.url?.startsWith('/')||req.url.startsWith('//'))throw deny('N00_FIXTURE_PATH_REFUSED',400);
   const url=new URL(req.url,upstream);path=url.pathname;
   if(url.origin!==upstream||(!path.startsWith('/fixture/')&&path!=='/fixture-token')||/%|\\/.test(path))throw deny('N00_FIXTURE_PATH_REFUSED',400);
   // Managed callbacks and verifier exchange consume one-use state even via GET.
   write=write||path.startsWith('/fixture/auth/callback/')||(path==='/fixture/auth/get-session'&&url.searchParams.has('neon_auth_session_verifier'));
   // One-use state is the intent: incidental query fields cannot turn an
   // uncertain exchange into a new attempt. Values enter only the hash.
   const query=path==='/fixture/auth/get-session'&&url.searchParams.has('neon_auth_session_verifier')
    ?new URLSearchParams({neon_auth_session_verifier:url.searchParams.get('neon_auth_session_verifier')})
    :path.startsWith('/fixture/auth/callback/')&&url.searchParams.has('state')
     ?new URLSearchParams({state:url.searchParams.get('state')}):new URLSearchParams(url.searchParams);
   query.sort();
   req.setTimeout(timeoutMs,()=>req.destroy());
   const body=await bodyBytes(req);req.setTimeout(0);fingerprint=createHash('sha256').update(method+'\n'+path+'\n'+query.toString()+'\n').update(body).digest('hex');
   if(write&&(blocked.all||blocked.hashes.has(fingerprint)))throw deny('N00_FIXTURE_UNKNOWN_AUTH_RESULT',409);
   const headers=new Headers();for(const [key,value] of Object.entries(req.headers))if(!hop.has(key)&&value!==undefined)headers.set(key,Array.isArray(value)?value.join(', '):value);
   if(write){if(inFlight.has(fingerprint))throw deny('N00_FIXTURE_AUTH_IN_FLIGHT',409);inFlight.add(fingerprint);held=true;}
   metrics.forwarded++;upstreamStarted=true;
   const response=await fetch(url,{method,headers,...(!safeMethods.has(method)?{body}:{}),redirect:'manual',signal:AbortSignal.timeout(timeoutMs)});
   const bytes=await responseBytes(response);let location=response.headers.get('location');
   if(location) {
    const to=new URL(location,upstream),own=proxy.address(),publicOrigin='http://127.0.0.1:'+own.port;
    if(to.username||to.password||to.hash)throw deny('N00_FIXTURE_REDIRECT_REFUSED',502);
    if(to.origin===upstream)to.host=new URL(publicOrigin).host;
    else if(to.origin!==publicOrigin&&!(to.origin==='http://localhost:44890'&&['/compat','/compat/return'].includes(to.pathname)))throw deny('N00_FIXTURE_REDIRECT_REFUSED',502);
    location=to.href;
   }
   const outcome=response.status>=500&&write?'unknown':response.status>=400?'rejected':'accepted';
   settle(outcome,response.status,'upstream-response');
   res.statusCode=response.status;
   for(const [key,value] of response.headers)if(!hop.has(key)&&!['set-cookie','location'].includes(key))res.setHeader(key,value);
   const cookies=response.headers.getSetCookie();if(cookies.length)res.setHeader('Set-Cookie',cookies);
   if(location)res.setHeader('Location',location);res.setHeader('X-N00-Fixture-Only','true');res.end(bytes);
  }catch(error) {
   const code=error.message?.startsWith('N00_')?error.message:'N00_FIXTURE_UPSTREAM_UNKNOWN';
   const status=code.includes('BUDGET')?429:code.includes('EXPIRED')?403:error.status??503;
   metrics.locally_rejected++;
   if(reservation){try {settle(upstreamStarted?'unknown':'rejected',status,code);}catch {if(write)blocked.all=true;}}
   respond(res,status,code);
  }finally {req.setTimeout(0);if(held)inFlight.delete(fingerprint);}
 });
 proxy.fixtureReport=()=>({fixture_only:true,external_requests:0,metrics:{...metrics},journal:journal.snapshot()});
 return proxy;
}

export {address as ownedAuthServerUrl};
