// Owned loopback server + synthetic provider protocol. Real emitted Vercel function and
// unpatched Neon server SDK; no DB/provider/production/human acceptance, never deployed.
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {resolve,sep} from 'node:path';
import {generateKeyPairSync,sign} from 'node:crypto';
const origin='https://c61-session.example.test',provider='https://ep-c61-session.neonauth.us-east-2.aws.neon.tech/neondb/auth';
Object.assign(process.env,{NODE_ENV:'production',VERCEL_ENV:'preview',BUYEROS_AUTH_PROVIDER:'neon',BUYEROS_NEON_AUTH_ROUTE_ENABLED:'1',BUYEROS_NEON_ENVIRONMENT:'preview',BUYEROS_NEON_AUTH_URL:provider,BUYEROS_NEON_EXPECTED_AUTH_URL:provider,BUYEROS_PUBLIC_ORIGIN:origin,BUYEROS_NEON_EXPECTED_PUBLIC_ORIGIN:origin,BUYEROS_NEON_COOKIE_SECRET:'C61_SYNTHETIC_OWNED_SESSION_COOKIE_'.repeat(2)});
let signedIn=false,sessionReads=0,tokenReads=0,emailCalls=0,apiCalls=0;
const keys=generateKeyPairSync('ed25519');
function token(){const body=[{alg:'EdDSA',kid:'owned-fixture'},{sub:'neon-user',iss:provider,aud:'owned-fixture-api',exp:Math.floor(Date.now()/1000)+900}].map(x=>Buffer.from(JSON.stringify(x)).toString('base64url')).join('.');return body+'.'+sign(null,Buffer.from(body),keys.privateKey).toString('base64url');}
const user={id:'neon-user',email:'synthetic@example.test',name:'Synthetic fixture',emailVerified:true,createdAt:'2026-10-01T00:00:00Z',updatedAt:'2026-10-01T00:00:00Z'};
const data=()=>({user,session:{id:'synthetic-session',token:'synthetic-opaque-cookie',userId:user.id,expiresAt:'2030-01-01T00:00:00Z',createdAt:'2026-10-01T00:00:00Z',updatedAt:'2026-10-01T00:00:00Z'}});
globalThis.fetch=async(url,options={})=>{
 const target=String(url);if(!target.startsWith(provider+'/'))throw Error('Owned SDK fixture refuses external fetch '+target);
 const path=target.slice(provider.length).split('?')[0];
 if(path==='/sign-in/email'){emailCalls++;const body=JSON.parse(options.body);if(body.email!==user.email||body.password!=='synthetic-only')return Response.json({code:'INVALID_CREDENTIALS'},{status:401});signedIn=true;return Response.json({redirect:false,token:'synthetic-opaque-cookie',user},{headers:{'set-cookie':'__Secure-neon-auth.session_token=synthetic-opaque-cookie; Path=/; HttpOnly; Secure; SameSite=Lax'}});}
 if(path==='/get-session'){sessionReads++;return Response.json(signedIn?data():null);}
 if(path==='/token'){tokenReads++;return signedIn?Response.json({token:token()}):Response.json({code:'UNAUTHORIZED'},{status:401});}
 if(path==='/sign-out'){signedIn=false;return Response.json({success:true},{headers:{'set-cookie':'__Secure-neon-auth.session_token=; Max-Age=0; Path=/; HttpOnly; Secure; SameSite=Lax'}});}
 throw Error('Unknown synthetic protocol '+path);
};
const {default:built}=await import('../../../.vercel/output/functions/__server.func/index.mjs');
const envelope=value=>Response.json({data_mode:'live',request_id:'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',data:value});
const server=createServer(async(req,res)=>{try{
 const url=new URL(req.url,origin);
 if(url.pathname==='/__owned_health'){res.writeHead(200);res.end('owned-ready');return;}
 if(url.pathname==='/__owned_reset'){signedIn=false;sessionReads=tokenReads=emailCalls=apiCalls=0;res.end('reset');return;}
 if(url.pathname==='/__owned_state'){res.setHeader('content-type','application/json');res.end(JSON.stringify({sessionReads,tokenReads,emailCalls,apiCalls,signedIn}));return;}
 let response;
 if(url.pathname.startsWith('/v1/')){
  apiCalls++;if(!signedIn||!req.headers.authorization?.startsWith('Bearer '))response=Response.json({code:'UNAUTHORIZED'},{status:401});
  else if(url.pathname==='/v1/workspaces')response=envelope({items:[{id:'A',name:'Synthetic workspace',roles:['operator'],membership_id:'member-A'}],offset:0,limit:100,total:1});
  else if(url.pathname==='/v1/workspaces/A/projects')response=envelope({items:[{id:'P',workspace_id:'A',name:'Synthetic project',status:'active',version:1}],offset:0,limit:100,total:1});
  else if(url.pathname==='/v1/workspaces/A/projects/P')response=envelope({id:'P',workspace_id:'A',name:'Synthetic project',status:'active',version:1,sender_identity:null,active_icp_version_id:null});
  else if(url.pathname==='/v1/workspaces/A/projects/P/drafts')response=envelope({items:[],offset:0,limit:8,total:0});
  else if(url.pathname==='/v1/workspaces/A/drafts/D')response=envelope({id:'D',workspace_id:'A',project_id:'P',buyer_id:'B',revision_id:'R',revision_number:1,version:1,language:'en',subject:'Synthetic draft',body:'Original synthetic body',status:'draft',claims:[],source_refs:[],content_hash:'synthetic-hash',context_hash:'synthetic-context',evidence_set_hash:'synthetic-evidence',grounding_status:'needs_review',approval_id:null,approval_review:null,recipient_contact_id:null});
  else if(url.pathname==='/v1/workspaces/A/preferences')response=envelope({locale:'zh-HK',version:1});
  else response=Response.json({code:'NOT_FOUND'},{status:404});
 }else{
  const staticRoot=resolve('.vercel/output/static'),file=resolve(staticRoot,'.'+url.pathname);
  if(file.startsWith(staticRoot+sep)){try{const content=await readFile(file);response=new Response(content,{headers:{'content-type':url.pathname.endsWith('.js')?'application/javascript':url.pathname.endsWith('.css')?'text/css':'application/octet-stream'}});}catch{}}
  if(!response){const chunks=[];for await(const chunk of req)chunks.push(chunk);const headers=new Headers();for(const[k,v]of Object.entries(req.headers))if(v)headers.set(k,Array.isArray(v)?v.join(','):v);headers.set('host',new URL(origin).host);
   response=await built.fetch(new Request(url,{method:req.method,headers,...(!['GET','HEAD'].includes(req.method)?{body:Buffer.concat(chunks)}:{})}),{waitUntil(){}});}
 }
 res.statusCode=response.status;for(const[k,v]of response.headers)if(k!=='set-cookie')res.setHeader(k,v);if(response.headers.getSetCookie().length)res.setHeader('set-cookie',response.headers.getSetCookie());res.end(Buffer.from(await response.arrayBuffer()));
 }catch(error){res.writeHead(500);res.end(String(error));}});
server.listen(5189,'127.0.0.1');for(const event of ['SIGINT','SIGTERM'])process.on(event,()=>server.close(()=>process.exit(0)));
