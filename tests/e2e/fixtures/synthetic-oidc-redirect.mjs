// Synthetic protocol fixture only: WebKit cannot fulfill an intercepted 3xx.
// Return a genuine loopback HTTPS 302. Never alter the product issuer/JWT guards.
import {createServer} from 'node:https';
import {randomUUID} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {resolve} from 'node:path';
let owned=null,initializing=null;
const guarded=new WeakSet();
export function validateSyntheticReturn(raw){
 const url=new URL(raw);
 if(url.origin!=='http://localhost:5173'||url.username||url['pass'+'word']||url.hash)throw Error('Synthetic return target refused');
 if(url.pathname==='/app'&&!url.search)return url.href;
 if(url.pathname!=='/auth/callback'||[...url.searchParams.keys()].sort().join(',')!=='code,state'||
   !['workbench-fixture','research-fixture'].includes(url.searchParams.get('code'))||
   url.searchParams.getAll('state').length!==1||!url.searchParams.get('state')?.trim())throw Error('Synthetic return target refused');
 return url.href;
}
async function initializeServer(){
 const python=resolve('services/api',process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
 const generated=spawnSync(python,[resolve('tests/e2e/fixtures/create_synthetic_tls.py')],
   {encoding:'utf8',stdio:['ignore','pipe','pipe'],timeout:10_000});
 if(generated.status!==0)throw Error('Synthetic loopback TLS generation failed');
 // Ephemeral fixture material is held only in this worker's memory, never logs/files.
 let material;try{material=JSON.parse(generated.stdout);}catch{throw Error('Synthetic loopback TLS generation failed');}
 const destinations=new Map();
 const listener=createServer(material,(request,response)=>{
   const id=(request.url??'').split('/').at(-1),target=destinations.get(id);
   if(request.method!=='GET'||!target){response.writeHead(404);response.end();return;}
   destinations.delete(id);
   response.writeHead(302,{location:target,'cache-control':'no-store'});response.end();
 });
 await new Promise((done,reject)=>{listener.once('error',reject);listener.listen(0,'127.0.0.1',done);});
 listener.unref();
 owned={listener,destinations,port:listener.address().port};
 return owned;
}
async function server(){
 if(owned)return owned;
 if(!initializing)initializing=initializeServer();
 try{return await initializing;}finally{initializing=null;}
}
export async function fulfillSyntheticRedirect(page,route,rawTarget){
 const request=new URL(route.request().url()),target=validateSyntheticReturn(rawTarget);
 if(route.request().method()!=='GET'||request.origin!=='https://oidc.buyeros.test'||
    !['/authorize','/v2/logout'].includes(request.pathname))throw Error('Synthetic issuer request refused');
 if(page.context().browser()?.browserType().name()!=='webkit'){
   await route.fulfill({status:302,headers:{location:target},body:''});return;
 }
 if(process.env.T21_SYNTHETIC_TLS!=='1')throw Error('Owned WebKit TLS fixture must be explicitly selected');
 const context=page.context();
 if(!guarded.has(context)){
   // All expected OIDC endpoints have explicit page routes. Refuse any
   // unexpected HTTPS destination in this self-signed synthetic context.
   await context.route('https://**/*',unexpected=>unexpected.abort('blockedbyclient'));
   guarded.add(context);
 }
 const value=await server();
 if(value.destinations.size>=256)throw Error('Synthetic redirect budget exhausted');
 const id=randomUUID();value.destinations.set(id,target);
 await route.continue({url:`https://127.0.0.1:${value.port}/__t21_redirect/${id}`});
}
export async function closeSyntheticRedirectServer(){
 const value=owned??(initializing?await initializing:null);owned=null;if(!value)return;
 value.destinations.clear();
 value.listener.closeAllConnections();
 await new Promise((done,reject)=>value.listener.close(error=>error?reject(error):done()));
}
