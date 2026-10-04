import {createServer} from 'node:http';
import {generateKeyPairSync,sign,createHmac} from 'node:crypto';
import {spawn,spawnSync} from 'node:child_process';
import {existsSync,readFileSync,statSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {assertLoopbackUrl,fixtureChildEnvironment,staticAssetPath} from './neon-compatibility-harness.mjs';
const target=process.env.BUYEROS_N00_TARGET;
if(!['portable','vercel'].includes(target))throw new Error('N00 requires portable or vercel actual output');
// The Vercel bridge runs in this process too: strip inherited application/provider env.
const isolatedEnv=fixtureChildEnvironment(process.env);
for(const key of Object.keys(process.env))delete process.env[key];
Object.assign(process.env,isolatedEnv,{BUYEROS_N00_TARGET:target});
const upstream=assertLoopbackUrl('http://127.0.0.1:44891/fixture/auth');
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
const authServer=createServer(async(req,res)=>{
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
 if(path==='/fixture/auth/get-session'){if(active)res.setHeader('set-auth-jwt',issue());res.end(JSON.stringify(active?{session,user}:null));return;}
 if(path==='/fixture/auth/token'){res.statusCode=active?200:401;res.end(JSON.stringify(active?{token:issue()}:{code:'UNAUTHORIZED'}));return;}
 if(path==='/fixture/auth/sign-out'&&req.method==='POST'){authenticated=false;res.setHeader('Set-Cookie',cookie.replace('fictional-session','').replace('Max-Age=3600','Max-Age=0'));res.end('{"success":true}');return;}
 if(path==='/fixture/auth/callback/fixture'&&url.searchParams.get('state')==='fictional-state'){authenticated=true;res.statusCode=302;res.setHeader('Set-Cookie',cookie);res.setHeader('Location','http://localhost:44890/compat');res.end('{}');return;}
 res.statusCode=404;res.end('{"fixtureOnly":true}');
});
await new Promise((ok,bad)=>{authServer.once('error',bad);authServer.listen(44891,'127.0.0.1',ok);});
const children=[];let appServer;
// Deliberate env allowlist: no inherited Auth/DB/provider credentials reach fixture children.
const childEnv=fixtureChildEnvironment(process.env);
function launch(command,args){const child=spawn(command,args,{env:childEnv,stdio:'inherit',windowsHide:true});children.push(child);child.on('error',error=>{console.error(error);stop(1);});child.on('exit',code=>{if(!stopping)stop(code??1);});return child;}
let stopping=false;
function stop(code=0){if(stopping)return;stopping=true;for(const child of children){if(process.platform==='win32'&&child.exitCode===null&&child.pid)spawnSync('taskkill',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,stdio:'ignore',timeout:5000});else child.kill();}appServer?.close();authServer.close();setTimeout(()=>process.exit(code),500).unref();}
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
