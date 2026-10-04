/** Shared N00 target contract only. No filesystem, HTTP, SDK, or approval action. */
import {createHash} from 'node:crypto';
const PROPOSAL='buyeros-neon-auth-n00-20261004',ORG='org-soft-sunset-25251479',REGION='aws-ap-southeast-1',TTL=2*60*60_000;
const FORBIDDEN=new Set(['nameless-bar-15324691','rapid-night-21766635']);
function need(value,code) {if(!value)throw new Error('N00_REAL_'+code);}
function exactKeys(value,keys) {need(value&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).every(k=>keys.includes(k))&&keys.every(k=>Object.hasOwn(value,k)),'SCHEMA');}
function instant(value) {need(typeof value==='string'&&/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/.test(value)&&Number.isFinite(Date.parse(value))&&new Date(value).toISOString()===value,'TIME');return Date.parse(value);}
function clock(value) {need(Number.isFinite(value),'TIME');return value;}
function id(value) {need(typeof value==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9_-]{4,95}$/.test(value),'TARGET_REQUIRED');return value;}
function endpoint(value) {
 need(typeof value==='string'&&value.length<=2048,'TARGET_REQUIRED');let url;
 try {url=new URL(value);}catch {throw new Error('N00_REAL_HTTPS_CONFIG');}
 need(url.protocol==='https:'&&!url.username&&!url.password&&!url.search&&!url.hash&&!url.port&&
 !/^(localhost|127\.|\[|0\.0\.0\.0$)/i.test(url.hostname)&&url.hostname.includes('.')&&!/%|\\/.test(value),'HTTPS_CONFIG');return url;
}
function canonical(value) {if(Array.isArray(value))return value.map(canonical);if(value&&typeof value==='object')return Object.fromEntries(Object.keys(value).sort().map(k=>[k,canonical(value[k])]));return value;}
function fingerprint(value) {const stable=structuredClone(value);delete stable.readback.observedAt;return createHash('sha256').update(JSON.stringify(canonical(stable))).digest('hex');}
export function assertRealTargetReadback(value,target,now) {
 exactKeys(value,['projectId','branchId','authId','orgId','name','regionId','observedAt','subscription','emailDeliveryEnabled','emailPasswordEnabled','emailHooksEnabled','methods','trustedOrigins']);
 for(const key of ['projectId','branchId','authId','orgId','name','regionId'])need(value[key]===target[key],'READBACK');
 need(instant(value.observedAt)>=instant(target.createdAt)&&instant(value.observedAt)<=clock(now),'READBACK');
 need(value.subscription==='free_v3','FREE_PLAN');
 need(value.emailDeliveryEnabled===false&&value.emailPasswordEnabled===false&&value.emailHooksEnabled===false,'EMAIL_DISABLED');
 need(JSON.stringify(value.methods)==='["google"]'&&JSON.stringify(value.trustedOrigins)==='["http://localhost:44890"]','METHODS_AND_ORIGIN');
}
export function validateRealTarget(value,now=Date.now(),{cleanup=false}={}) {
 need(value?.projectId&&value?.branchId&&value?.authId,'TARGET_REQUIRED');
 exactKeys(value,['schemaVersion','proposal','sourceSha','projectId','branchId','authId','orgId','name','regionId','creationMode','createdAt','expiresAt','readback','auth']);
 need(value.schemaVersion===1&&value.proposal===PROPOSAL&&value.name===PROPOSAL&&value.orgId===ORG&&value.regionId===REGION,'SCOPE');
 need(value.creationMode==='new-empty'&&!FORBIDDEN.has(value.projectId),'NEW_EMPTY_TARGET');
 for(const key of ['projectId','branchId','authId'])id(value[key]);
 need(/^[a-f0-9]{40}$/.test(value.sourceSha??''),'SOURCE_SHA');
 const created=instant(value.createdAt),expires=instant(value.expiresAt);
 need(created<=clock(now)&&expires-created===TTL,'TWO_HOUR_SCOPE');need(cleanup||now<expires,'EXPIRED');
 assertRealTargetReadback(value.readback,value,now);
 exactKeys(value.auth,['baseUrl','issuer','audience','jwksUrl','algorithm','keyType','curve']);
 const base=endpoint(value.auth.baseUrl),jwks=endpoint(value.auth.jwksUrl);endpoint(value.auth.issuer);
 need(jwks.origin===base.origin,'JWKS_ORIGIN');
 need(typeof value.auth.audience==='string'&&/^[^\s\x00-\x1f\x7f]{1,512}$/.test(value.auth.audience),'AUDIENCE_REQUIRED');
 need(value.auth.algorithm==='EdDSA'&&value.auth.keyType==='OKP'&&value.auth.curve==='Ed25519','ED25519_TRUST');
 return {...structuredClone(value),fingerprint:fingerprint(value)};
}
