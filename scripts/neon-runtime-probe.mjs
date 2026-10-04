/** Fixture-only built-runtime inspection: no provider transport permitted. */
const key=Symbol.for('buyeros.n00.runtime-probe.fetch-guard');
export function assertRuntimeProbeTarget(config) {
 let valid=false;
 try {valid=['projectId','branchId','authId'].every(k=>config[k].startsWith('fictional-probe-'))&&
  [config.sdk.baseUrl,config.trust.issuer,config.trust.jwksUrl].every(v=>new URL(v).hostname.endsWith('.fixture.invalid'))&&
  config.trust.audience.startsWith('fictional-probe-');}catch {valid=false;}
 if(!valid)throw new Error('N00_PROBE_FICTIONAL_ONLY');
}
export function installProbeFetchGuard(host=globalThis) {
 if(host[key])return host[key];
 let blocked=0;
 host.fetch=async()=>{blocked++;throw new Error('N00_PROBE_FETCH_DISABLED');};
 const guard=Object.freeze({metrics:()=>Object.freeze({blocked,forwarded:0,fixture_only:true})});
 Object.defineProperty(host,key,{value:guard});return guard;
}
