import assert from 'node:assert/strict';
import {mkdtempSync,rmSync,realpathSync,existsSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve,relative} from 'node:path';
import {RealRunJournal} from '../../../scripts/neon-real-preflight.mjs';
import {createOwnedAuthServer} from '../../../scripts/neon-counted-proxy.mjs';
export async function listen(server) {await new Promise((ok,bad)=>{server.once('error',bad);server.listen(0,'127.0.0.1',ok);});return 'http://127.0.0.1:'+server.address().port;}
export async function close(server) {if(server.listening){server.closeAllConnections();await new Promise(ok=>server.close(ok));}}
export async function executionFixture(handler) {
 const root=mkdtempSync(join(tmpdir(),'buyeros-n00-real-')),created=Date.now(),stamp=new Date(created).toISOString();
 const target={schemaVersion:1,proposal:'buyeros-neon-auth-n00-20261004',sourceSha:'e0256f303502d4332400a837b99903926f74c842',projectId:'fictional-execution-project',branchId:'fictional-execution-branch',authId:'fictional-execution-auth',orgId:'org-soft-sunset-25251479',name:'buyeros-neon-auth-n00-20261004',regionId:'aws-ap-southeast-1',creationMode:'new-empty',createdAt:stamp,expiresAt:new Date(created+7200000).toISOString(),readback:{projectId:'fictional-execution-project',branchId:'fictional-execution-branch',authId:'fictional-execution-auth',orgId:'org-soft-sunset-25251479',name:'buyeros-neon-auth-n00-20261004',regionId:'aws-ap-southeast-1',observedAt:stamp,subscription:'free_v3',emailDeliveryEnabled:false,emailPasswordEnabled:false,emailHooksEnabled:false,methods:['google'],trustedOrigins:['http://localhost:44890']},auth:{baseUrl:'https://execution.fixture.invalid/auth',issuer:'https://issuer.fixture.invalid',audience:'fictional-execution-audience',jwksUrl:'https://execution.fixture.invalid/auth/jwks',algorithm:'EdDSA',keyType:'OKP',curve:'Ed25519'}};
 const journal=RealRunJournal.create(root,{approvalReference:'fixture-only-no-external-authority',approvedAt:stamp});journal.bindTarget(target,created);
 const identity={id:'fictional-execution-identity',authId:target.authId,projectId:target.projectId,createdAt:stamp};
 const resources=new Map([['identity',identity.id],['auth',target.authId],['project',target.projectId]].map(([kind,id])=>[kind,{kind,id,projectId:target.projectId,authId:target.authId,orgId:target.orgId,exists:true}]));
 const model={commits:0,hits:[],resources,loseDelete:null,rejectDelete:null,readbackPatch:null,clock:()=>Date.now()};
 const backend=createOwnedAuthServer(async(req,res)=>{
  const path=new URL(req.url,'http://127.0.0.1').pathname;model.hits.push([req.method,path]);
  if(handler&&await handler(req,res,{journal,model,target,identity}))return;
  res.setHeader('Content-Type','application/json');
  if(path==='/fixture/control/target'){res.end(JSON.stringify({...target.readback,observedAt:new Date(model.clock()).toISOString(),...model.readbackPatch}));return;}
  const match=/^\/fixture\/control\/(identity|auth|project)\/([a-zA-Z0-9_-]+)$/.exec(path);
  if(match){const resource=resources.get(match[1]);if(match[2]!==resource.id){res.statusCode=403;res.end('{}');return;}
   if(req.method==='DELETE'){if(model.rejectDelete===resource.kind){res.statusCode=500;res.end('{}');return;}resource.exists=false;if(model.loseDelete===resource.kind){req.socket.destroy();return;}res.statusCode=204;res.end();return;}
   res.end(JSON.stringify({...resource,observedAt:new Date(model.clock()).toISOString()}));return;
  }
  if(path==='/fixture/auth/token'){res.end('{"token":"fictional.a.b"}');return;}
  if(path==='/fixture/auth/redirect'){res.statusCode=302;res.setHeader('Location','/fixture/auth/token');res.end();return;}
  if(path==='/fixture/auth/commit'){for await(const chunk of req)assert.ok(chunk);model.commits++;req.socket.destroy();return;}
  res.end('{"ok":true}');
 });
 const url=await listen(backend),servers=[backend];
 return {root,journal,target,identity,model,backend,url,servers,async cleanup(){for(const server of servers.reverse())await close(server);assert.equal(realpathSync(root),resolve(root));assert.ok(relative(resolve(tmpdir()),root).startsWith('buyeros-n00-real-'));rmSync(root,{recursive:true,force:true});assert.equal(existsSync(root),false);assert.ok(servers.every(server=>!server.listening));return {fixture_only:true,external_verified:false,owned_journal_removed:true,owned_servers_closed:true};}};
}
