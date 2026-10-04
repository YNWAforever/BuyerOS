/** Owned loopback protocol verifier only. No domain API, DB, membership or role access. */
function reply(status,code){return Response.json({code,external_verified:false},{status,headers:{'Cache-Control':'no-store'}});}
export async function verifyWithOwnedDiagnostic({environment:env,description,request,fetch:send=globalThis.fetch}) {
 if(env.N00_DIAGNOSTIC_URL!=='http://127.0.0.1:44892/verify'||!/^[-_a-zA-Z0-9]{43,128}$/.test(env.N00_DIAGNOSTIC_NONCE??'')||env.N00_DIAGNOSTIC_FINGERPRINT!==description.fingerprint)return reply(503,'N00_DIAGNOSTIC_NOT_BOUND');
 if(request.method!=='POST'||request.headers.get('origin')!==new URL(request.url).origin)return reply(403,'N00_DIAGNOSTIC_ORIGIN_REFUSED');
 const bearer=request.headers.get('authorization')??'';
 if(bearer.length>16384||!/^Bearer [a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+$/.test(bearer))return reply(401,'N00_DIAGNOSTIC_BEARER_REQUIRED');
 try {
  const response=await send(env.N00_DIAGNOSTIC_URL,{headers:new Headers({authorization:bearer,'x-n00-owner':env.N00_DIAGNOSTIC_NONCE}),redirect:'manual',signal:AbortSignal.timeout(3000)});
  if(response.status===401)return reply(401,'N00_DIAGNOSTIC_TOKEN_REFUSED');
  if(response.status!==200)return reply(503,'N00_DIAGNOSTIC_UNKNOWN');
  const data=await response.json();
  if(data.fingerprint!==description.fingerprint||typeof data.subject!=='string'||!data.subject||data.protocol_fixture_only!==true)return reply(503,'N00_DIAGNOSTIC_CONTEXT_REFUSED');
  return Response.json({subject:data.subject,fingerprint:data.fingerprint,protocol_fixture_only:true,external_verified:false},{headers:{'Cache-Control':'no-store'}});
 }catch{return reply(503,'N00_DIAGNOSTIC_UNKNOWN');}
}

export function validDiagnosticReceipt(value,expected){return !!value&&typeof value==='object'&&value.subject===expected.subject&&value.fingerprint===expected.fingerprint&&value.protocol_fixture_only===true&&value.external_verified===false;}
