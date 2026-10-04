/** Fictional-only SDK transport into the durable counted loopback proxy.
 * Does not accept real targets or intercept every possible SDK/browser/CLI transport. */
import {assertRuntimeProbeTarget} from './neon-runtime-probe.mjs';
const key=Symbol.for('buyeros.n00.runtime-flow.fixture-transport');
const paths=new Set(['/get-session','/token','/jwks','/sign-in/social','/callback/google','/sign-out']);
export function installFlowFixtureTransport(config,host=globalThis,diagnosticNonce=null) {
 assertRuntimeProbeTarget(config);
 if(diagnosticNonce!==null&&!/^[-_a-zA-Z0-9]{43,128}$/.test(diagnosticNonce))throw new Error('N00_FLOW_OWNER_REQUIRED');
 if(host[key]){if(host[key].fingerprint!==config.fingerprint||host[key].nonce!==diagnosticNonce)throw new Error('N00_FLOW_CONTEXT_CHANGED');return host[key].transport;}
 const base=new URL(config.sdk.baseUrl),original=host.fetch.bind(host);
 let blocked=0,forwarded=0,diagnostic=0;
 host.fetch=async(input,init)=>{
  let request,url;
  try{url=new URL(input instanceof Request?input.url:String(input));if(url.username||url.password||url.hash||/%|\\/.test(url.pathname))throw new Error();request=new Request(input,init);}
  catch{blocked++;throw new Error('N00_FLOW_FETCH_REFUSED');}
  if(url.href==='http://127.0.0.1:44892/verify'&&diagnosticNonce&&request.method==='GET'&&request.headers.get('x-n00-owner')===diagnosticNonce){diagnostic++;return original(url.href,{method:'GET',headers:request.headers,redirect:'manual',signal:request.signal});}
  const suffix=url.pathname.slice(base.pathname.length);
  if(url.origin!==base.origin||!url.pathname.startsWith(base.pathname+'/')||!paths.has(suffix)){blocked++;throw new Error('N00_FLOW_FETCH_REFUSED');}
  const to=new URL('http://127.0.0.1:44891/fixture/auth'+suffix+url.search);
  forwarded++;
  return original(to.href,{method:request.method,headers:request.headers,...(!['GET','HEAD'].includes(request.method)?{body:await request.arrayBuffer()}:{}),redirect:'manual',signal:request.signal});
 };
 const transport=Object.freeze({metrics:()=>Object.freeze({fixture_only:true,blocked,forwarded,diagnostic,external_requests:0})});
 Object.defineProperty(host,key,{value:{fingerprint:config.fingerprint,nonce:diagnosticNonce,transport}});return transport;
}
