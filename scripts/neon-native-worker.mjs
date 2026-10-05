/** Fixed fixture worker. Private pipes, fictional requests, no provider/DB adapter. */
import {createInterface} from 'node:readline';
import {get} from 'node:http';
import {createConnection} from 'node:net';
import {spawnSync} from 'node:child_process';
const input=createInterface({input:process.stdin,crlfDelay:Infinity})[Symbol.asyncIterator]();
const send=value=>process.stdout.write(JSON.stringify(value)+'\n');
const next=async()=>{const item=await input.next();if(item.done||item.value.length>65536)throw new Error('private input');return JSON.parse(item.value);};
let stage='configuration';
try {
 const cfg=await next();if(!/^\d+\.\d+\.\d+\.\d+$/.test(cfg.probeHost)||cfg.probePort!==38479||!Array.isArray(cfg.requests)||cfg.requests.length>8)throw new Error('fixture scope');
 stage='environment';const allowed=new Set(['PATH','HOSTNAME','NODE_VERSION','YARN_VERSION','HOME','PWD','BUYEROS_STRICT_INTEGRATION']);if(!Object.keys(process.env).every(k=>allowed.has(k)))throw new Error('inherited environment');
 stage='native-probes';const base='http://'+cfg.probeHost+':'+cfg.probePort;
 const http=await new Promise(resolve=>{const req=get(base+'/native/http',response=>{response.resume();response.on('end',()=>resolve(true));});req.on('error',()=>resolve(false));req.setTimeout(300,()=>req.destroy());});
 let fetched=false;try{const res=await fetch(base+'/native/fetch',{signal:AbortSignal.timeout(300),redirect:'manual'});await res.text();fetched=res.status===200;}catch{}
 const tcp=await new Promise(resolve=>{const socket=createConnection({host:cfg.probeHost,port:cfg.probePort});const finish=ok=>{socket.destroy();resolve(ok);};socket.on('connect',()=>finish(true));socket.on('error',()=>finish(false));socket.setTimeout(300,()=>finish(false));});
 const source="fetch(process.argv[1],{signal:AbortSignal.timeout(300),redirect:'manual'}).then(async r=>{await r.text();process.stdout.write(String(r.status))}).catch(()=>process.exitCode=1)";
 const cli=spawnSync(process.execPath,['-e',source,base+'/native/subprocess'],{encoding:'utf8',timeout:2000,env:process.env});
 const probes={http_connected:http,fetch_connected:fetched,tcp_connected:tcp,subprocess_connected:cli.status===0&&cli.stdout==='200'};
 stage='private-receipts';const receipts=[];for(let i=0;i<cfg.requests.length;i++){send({type:'request',index:i,request:cfg.requests[i]});const response=await next();if(response.type!=='receipt'||response.index!==i)throw new Error('receipt pairing');receipts.push(response.value);}
 send({type:'complete',probes,receipts,environment_clean:true,environment_names:Object.keys(process.env).sort()});
}catch(error){send({type:'refused',code:'N00_NATIVE_WORKER_REFUSED',stage,error_name:error.name});process.exitCode=1;}finally{process.stdin.destroy();}
