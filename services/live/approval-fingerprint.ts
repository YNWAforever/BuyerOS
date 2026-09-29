/** Versioned exact-approval context serialization; mirrors Python v2. */
export const APPROVAL_SERIALIZER_VERSION = 'approval-cjson-v2';
export const APPROVAL_CONTEXT_FIELDS = [
  'draft_id','revision_id','revision_number','content_hash','subject','body','kind','language',
  'recipient','sender','icp','buyer','fit','review','evidence','offer_fact_ids','policy','suppression',
] as const;
type Json = string|number|boolean|null|Json[]|{[key:string]:Json};
function normalize(value:Json):Json{
  if(typeof value==='string')return value.replace(/\r\n/g,'\n');
  if(Array.isArray(value))return value.map(normalize);
  if(value!==null&&typeof value==='object')
    return Object.fromEntries(Object.keys(value).sort().map(key=>[key,normalize(value[key])]));
  return value;
}
export async function fingerprintCurrent(context:Record<string,Json>):Promise<string>{
  const actual=Object.keys(context).sort(), expected=[...APPROVAL_CONTEXT_FIELDS].sort();
  if(JSON.stringify(actual)!==JSON.stringify(expected))throw new Error('approval context fields do not match v2 schema');
  const raw=JSON.stringify(normalize({serializer_version:APPROVAL_SERIALIZER_VERSION,context}));
  const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(raw));
  return 'sha256:'+Array.from(new Uint8Array(bytes),value=>value.toString(16).padStart(2,'0')).join('');
}
