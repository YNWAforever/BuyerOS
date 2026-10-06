/** Counted fictional APIRequestContext consumer only. Raw contexts/parent OS are NOT confined. */
import {request} from '@playwright/test';
import {assertFixtureExecutionBoundary,ownedFixtureSdkUrl} from './neon-execution-boundary.mjs';
const safe=new Set(['GET','HEAD']),methods=new Set(['GET','HEAD','POST']);
function need(value,code){if(!value)throw new Error('N00_APIREQUEST_'+code);}
export async function createFixtureApiRequestContext(options){
 need(options&&Object.keys(options).every(k=>['gateway','execution','journal','nonce','timeoutMs'].includes(k)),'CONTEXT');
 const {gateway,execution,journal,nonce,timeoutMs=3000}=options;
 need(Number.isInteger(timeoutMs)&&timeoutMs>=20&&timeoutMs<=3000,'TIMEOUT');
 const owned={gateway,execution,journal,nonce},url=ownedFixtureSdkUrl(owned),origin=new URL(url).origin,fingerprint=journal.snapshot().target.fingerprint;
 function current(){assertFixtureExecutionBoundary(execution,journal);need(ownedFixtureSdkUrl(owned)===url,'BOUND_GATEWAY');need(journal.snapshot().target.fingerprint===fingerprint,'BOUND_TARGET');}
 let context;try{context=await request.newContext({timeout:timeoutMs,ignoreHTTPSErrors:false,storageState:{cookies:[],origins:[]},extraHTTPHeaders:{'x-n00-owner':nonce}});}catch{throw new Error('N00_APIREQUEST_CONTEXT_FAILED');}
 try{current();}catch(error){try{await context.dispose();}catch{throw new Error('N00_APIREQUEST_CONTEXT_CLEANUP_FAILED');}throw error;}
 let disposed=false,disposal;
 function payload(input){
  need(input&&Object.keys(input).every(k=>['path','method','body','headers'].includes(k))&&methods.has(input.method),'REQUEST');
  let headers;try{headers=[...new Headers(input.headers)];}catch{throw new Error('N00_APIREQUEST_REQUEST');}
  const value={channel:'browser',method:input.method,path:input.path,body:input.body===undefined?'':input.body,headers};
  // Reuse original validation/holds; the gateway is the only reservation/dispatch owner.
  const held=execution.holds(value);if(!safe.has(value.method)&&held)throw new Error('N00_EXECUTION_HELD_INTENT');
  const data=JSON.stringify(value);need(Buffer.byteLength(data)<=32768,'ENVELOPE_LIMIT');return data;
 }
 return Object.freeze({async dispatch(input){
  need(!disposed,'DISPOSED');current();const data=payload(input);let response;
  try{response=await context.fetch(origin+'/dispatch',{method:'POST',data,headers:{'content-type':'application/json'},maxRedirects:0,maxRetries:0,timeout:timeoutMs});}catch{throw new Error('N00_APIREQUEST_TRANSPORT_UNKNOWN');}
  try {
   need(!disposed,'DISPOSED');current();need(response.status()<300||response.status()>=400,'WIRE_REDIRECT_REFUSED');
   const body=await response.body();need(!disposed,'DISPOSED');current();need(body.length<=8388608,'WIRE_RESPONSE_LIMIT');let value;try{value=JSON.parse(body.toString('utf8'));}catch{throw new Error('N00_APIREQUEST_WIRE_RESPONSE');}
   if(response.status()!==200){if(value&&typeof value.code==='string'&&value.code.length<=96&&/^N00_[A-Z0-9_]+$/.test(value.code))throw new Error(value.code);throw new Error('N00_APIREQUEST_WIRE_RESPONSE');}
   need(value&&Number.isInteger(value.status)&&value.status>=100&&value.status<=599&&typeof value.body==='string'&&(value.location===null||typeof value.location==='string'&&value.location.startsWith('/fixture/auth/'))&&['accepted','rejected','unknown'].includes(value.outcome)&&value.fixture_only===true&&value.external_verified===false&&/^execution-http-\d+\.json$/.test(value.evidenceRef)&&Array.isArray(value.headers)&&value.headers.every(h=>Array.isArray(h)&&h.length===2&&h.every(v=>typeof v==='string')),'WIRE_RESPONSE');
   return value;
  }finally{try{await response.dispose();}catch{throw new Error('N00_APIREQUEST_RESPONSE_CLEANUP_FAILED');}need(!disposed,'DISPOSED');current();}
 },async dispose(){
  if(!disposal){disposed=true;disposal=context.dispose().then(()=>({fixture_only:true,external_verified:false,owned_context_disposed:true})).catch(()=>{throw new Error('N00_APIREQUEST_CONTEXT_CLEANUP_FAILED');});}return disposal;
 }});
}
