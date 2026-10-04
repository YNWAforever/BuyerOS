/** N00 preparation only: validates metadata and records reservations; performs no HTTP,
 * build, resource creation, account linking, or deletion. A reference is provenance,
 * not an approval grant. The operator must first obtain the runbook's human approval. */
import {randomBytes} from 'node:crypto';
import {openSync,closeSync,writeFileSync,readFileSync,fsyncSync,renameSync,unlinkSync,mkdirSync,rmdirSync,lstatSync,realpathSync} from 'node:fs';
import {resolve,join,basename,relative,isAbsolute} from 'node:path';
import {tmpdir} from 'node:os';
import {pathToFileURL} from 'node:url';
import {fixtureChildEnvironment} from './neon-compatibility-harness.mjs';
import {validateRealTarget,assertRealTargetReadback as readback} from './neon-real-target.mjs';
export {validateRealTarget};
const PROPOSAL='buyeros-neon-auth-n00-20261004',ORG='org-soft-sunset-25251479';
const LIMIT=200,RESERVE=20,BUILD_LIMIT=2,BUILD_TIMEOUT=20*60_000;
const PURPOSES=new Set(['setup','auth','cleanup','reconcile']),OUTCOMES=new Set(['pending','accepted','rejected','unknown']);
function need(value,code) {if(!value)throw new Error('N00_REAL_'+code);}
function exactKeys(value,keys) {need(value&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).every(k=>keys.includes(k))&&keys.every(k=>Object.hasOwn(value,k)),'SCHEMA');}
function instant(value) {need(typeof value==='string'&&/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/.test(value)&&Number.isFinite(Date.parse(value))&&new Date(value).toISOString()===value,'TIME');return Date.parse(value);}
function clock(value) {need(Number.isFinite(value),'TIME');return value;}
function reference(value) {need(typeof value==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9_.:/-]{0,199}$/.test(value)&&!value.includes('..')&&!value.includes('://'),'REFERENCE');return value;}
function id(value) {need(typeof value==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9_-]{4,95}$/.test(value),'TARGET_REQUIRED');return value;}
function manifest(target) {const value=structuredClone(target);delete value.fingerprint;return value;}
export function realBuildEnvironment(parent) {return fixtureChildEnvironment(parent);}
export function realRuntimeEnvironment(parent,target,secret,now=Date.now()) {
 const valid=validateRealTarget(target,now);need(typeof secret==='string'&&/^[a-zA-Z0-9_-]{43,128}$/.test(secret),'COOKIE_SECRET');
 return {...realBuildEnvironment(parent),NEON_AUTH_BASE_URL:valid.auth.baseUrl,NEON_AUTH_COOKIE_SECRET:secret,
 N00_AUTH_ISSUER:valid.auth.issuer,N00_AUTH_AUDIENCE:valid.auth.audience,N00_AUTH_JWKS_URL:valid.auth.jwksUrl,
 N00_AUTH_ALGORITHM:'EdDSA',N00_TARGET_FINGERPRINT:valid.fingerprint,N00_REAL_TARGET_JSON:JSON.stringify(manifest(valid))};
}
function ownedRoot(root) {
 const path=resolve(root);need(/^buyeros-n00-real-[a-zA-Z0-9_-]{6,}$/.test(basename(path)),'JOURNAL_ROOT');
 const allowed=[resolve(tmpdir()),resolve('test-results/neon-real-preflight')];
 need(allowed.some(base=>{const child=relative(base,path);return child&&!child.startsWith('..')&&!isAbsolute(child);}),'JOURNAL_ROOT');
 need(lstatSync(path).isDirectory()&&!lstatSync(path).isSymbolicLink()&&realpathSync(path)===path,'JOURNAL_ROOT');return path;
}
function validateJournal(state) {
 exactKeys(state,['schemaVersion','proposal','approvalReference','approvedAt','limit','cleanupReserve','buildLimit','buildTimeoutMs','target','identity','requests','builds']);
 need(state.schemaVersion===1&&state.proposal===PROPOSAL&&state.limit===LIMIT&&state.cleanupReserve===RESERVE&&state.buildLimit===BUILD_LIMIT&&state.buildTimeoutMs===BUILD_TIMEOUT,'JOURNAL_SCOPE');
 reference(state.approvalReference);instant(state.approvedAt);
 if(state.target){const valid=validateRealTarget(manifest(state.target),instant(state.target.expiresAt),{cleanup:true});need(valid.fingerprint===state.target.fingerprint&&instant(valid.createdAt)>=instant(state.approvedAt),'BOUND_TARGET');}
 need(Array.isArray(state.requests)&&state.requests.length<=LIMIT&&Array.isArray(state.builds)&&state.builds.length<=BUILD_LIMIT,'BUDGET');
 const ids=new Set();
 for(const [index,item] of state.requests.entries()) {
  exactKeys(item,['sequence','purpose','operationId','reservedAt','outcome','evidenceRef']);
  reference(item.operationId);instant(item.reservedAt);need(instant(item.reservedAt)>=instant(state.approvedAt),'TIME');
  need(!ids.has(item.operationId)&&item.sequence===index+1&&PURPOSES.has(item.purpose)&&OUTCOMES.has(item.outcome),'JOURNAL_REQUEST');ids.add(item.operationId);
  need((item.outcome==='pending')===(item.evidenceRef===null),'JOURNAL_REQUEST');
  if(item.evidenceRef!==null)reference(item.evidenceRef);
  if(item.purpose==='auth')need(state.target,'BOUND_TARGET');
  if(state.target&&!['cleanup','reconcile'].includes(item.purpose))need(instant(item.reservedAt)<instant(state.target.expiresAt),'EXPIRED');
  if(!['cleanup','reconcile'].includes(item.purpose))need(item.sequence<=LIMIT-RESERVE,'BUDGET');
 }
 for(const [index,item] of state.builds.entries()) {
  exactKeys(item,['sequence','target','reservedAt','deadline']);need(['portable','vercel'].includes(item.target)&&item.sequence===index+1,'BUILD_SCOPE');
  const reserved=instant(item.reservedAt),deadline=instant(item.deadline);need(reserved>=instant(state.approvedAt)&&deadline>reserved&&deadline-reserved<=BUILD_TIMEOUT&&(!state.target||deadline<=instant(state.target.expiresAt)),'BUILD_TIMEOUT');
 }
 if(state.identity){need(state.target,'BOUND_TARGET');identity(state.identity,state.target,instant(state.target.expiresAt));}
 return state;
}
function identity(value,target,now) {
 exactKeys(value,['id','authId','projectId','createdAt']);id(value.id);
 need(value.authId===target.authId&&value.projectId===target.projectId&&instant(value.createdAt)>=instant(target.createdAt)&&instant(value.createdAt)<=now,'OWNED_IDENTITY');
 return structuredClone(value);
}
export class RealRunJournal {
 constructor(root) {this.root=ownedRoot(root);this.path=join(this.root,'journal.json');this.lock=join(this.root,'journal.lock');}
 static create(root,{approvalReference,approvedAt}) {
  need(approvalReference,'AUTHORIZATION_REFERENCE_REQUIRED');reference(approvalReference);instant(approvedAt);
  const run=new RealRunJournal(root),state={schemaVersion:1,proposal:PROPOSAL,approvalReference,approvedAt,limit:LIMIT,cleanupReserve:RESERVE,buildLimit:BUILD_LIMIT,buildTimeoutMs:BUILD_TIMEOUT,target:null,identity:null,requests:[],builds:[]};
  const fd=openSync(run.path,'wx',0o600);try {writeFileSync(fd,JSON.stringify(state,null,2)+'\n');fsyncSync(fd);}finally {closeSync(fd);}return run;
 }
 snapshot() {ownedRoot(this.root);need(lstatSync(this.path).isFile()&&!lstatSync(this.path).isSymbolicLink(),'JOURNAL_PATH');return validateJournal(JSON.parse(readFileSync(this.path,'utf8')));}
 update(change) {
  ownedRoot(this.root);try {mkdirSync(this.lock);}catch {throw new Error('N00_REAL_JOURNAL_BUSY');}
  let temporary;
  try {
   const state=this.snapshot(),result=change(state);validateJournal(state);
   temporary=join(this.root,'journal.'+randomBytes(8).toString('hex')+'.tmp');
   const fd=openSync(temporary,'wx',0o600);try {writeFileSync(fd,JSON.stringify(state,null,2)+'\n');fsyncSync(fd);}finally {closeSync(fd);}
   renameSync(temporary,this.path);temporary=undefined;return result;
  }finally {if(temporary)unlinkSync(temporary);rmdirSync(this.lock);}
 }
 bindTarget(target,now=Date.now()) {
  const valid=validateRealTarget(target,now);return this.update(state=>{
   need(instant(valid.createdAt)>=instant(state.approvedAt),'CREATION_BEFORE_APPROVAL');
   need(!state.target||state.target.fingerprint===valid.fingerprint,'BOUND_TARGET');state.target=valid;return valid.fingerprint;
  });
 }
 bindIdentity(value,now=Date.now()) {return this.update(state=>{need(state.target&&!state.identity,'ONE_OWNED_IDENTITY');need(clock(now)<instant(state.target.expiresAt),'EXPIRED');state.identity=identity(value,state.target,now);});}
 reserveRequest(purpose,operationId,now=Date.now()) {
  reference(operationId);need(PURPOSES.has(purpose),'PURPOSE');clock(now);
  return this.update(state=>{
   need(now>=instant(state.approvedAt),'TIME');need(purpose!=='auth'||state.target,'BOUND_TARGET');
   need(!state.requests.some(item=>item.operationId===operationId),'RECONCILE_BEFORE_RETRY');
   if(state.target&&!['cleanup','reconcile'].includes(purpose))need(now<instant(state.target.expiresAt),'EXPIRED');
   const cap=['cleanup','reconcile'].includes(purpose)?LIMIT:LIMIT-RESERVE;need(state.requests.length<cap,'BUDGET_EXHAUSTED');
   const item={sequence:state.requests.length+1,purpose,operationId,reservedAt:new Date(now).toISOString(),outcome:'pending',evidenceRef:null};state.requests.push(item);return structuredClone(item);
  });
 }
 settleRequest(operationId,outcome,evidenceRef) {
  reference(operationId);reference(evidenceRef);need(['accepted','rejected','unknown'].includes(outcome),'OUTCOME');
  return this.update(state=>{const item=state.requests.find(value=>value.operationId===operationId);need(item?.outcome==='pending','RECONCILE_BEFORE_RETRY');item.outcome=outcome;item.evidenceRef=evidenceRef;});
 }
 reserveBuild(target,now=Date.now()) {
  need(['portable','vercel'].includes(target),'BUILD_SCOPE');clock(now);
  return this.update(state=>{
   need(now>=instant(state.approvedAt),'TIME');need(state.builds.length<BUILD_LIMIT,'BUILD_BUDGET');
   const deadline=Math.min(now+BUILD_TIMEOUT,state.target?instant(state.target.expiresAt):now+BUILD_TIMEOUT);need(deadline>now,'EXPIRED');
   const item={sequence:state.builds.length+1,target,reservedAt:new Date(now).toISOString(),deadline:new Date(deadline).toISOString()};state.builds.push(item);return structuredClone(item);
  });
 }
}
export function cleanupTargets(state,freshReadback,now=Date.now()) {
 validateJournal(state);need(state.target,'BOUND_TARGET');readback(freshReadback,state.target,clock(now));
 need(now-instant(freshReadback.observedAt)<=5*60_000,'FRESH_READBACK_REQUIRED');
 const {projectId,branchId,authId}=state.target;
 return [...(state.identity?[{kind:'identity',id:state.identity.id,projectId,authId}]:[]),{kind:'auth',id:authId,projectId,branchId},{kind:'project',id:projectId,orgId:ORG}];
}
if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href) {
 try {
  need(process.argv.length===4&&process.argv[2]==='check','USAGE_CHECK_TARGET_JSON');
  const valid=validateRealTarget(JSON.parse(readFileSync(process.argv[3],'utf8')));
  console.log(JSON.stringify({configuration_valid:true,fingerprint:valid.fingerprint,external_authorized:false,external_started:false,built_runtime_verified:false,N00_complete:false}));
 }catch(error){console.error(error.message.startsWith('N00_REAL_')?error.message:'N00_REAL_INVALID_INPUT');process.exitCode=1;}
}
