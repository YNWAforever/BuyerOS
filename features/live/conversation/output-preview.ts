/**
 * Increment 2.5: inline output preview. The server is the only author of the
 * preview HTML; this module only builds the bounded read request, caps the body
 * and maps honest failure states. No retries live here (the UI may offer a manual
 * retry for genuinely transient failures).
 */
export const PREVIEW_MAX_BYTES=64*1024;
/** Strict sandbox: no tokens means no scripts, forms, popups or same-origin. */
export const PREVIEW_SANDBOX='';
export function previewSandboxTokens():readonly string[]{
  return [];
}
export type PreviewError='denied'|'missing'|'unavailable';
export type PreviewOutcome={kind:'ready';html:string;truncated:boolean}|{kind:'error';error:PreviewError};
export type PreviewRequest={
  baseUrl:string;workspace:string;project:string;outputId:string;revision:number;
};
function nonBlank(value:unknown):value is string{
  return typeof value==='string'&&value.trim().length>0;
}
/** `/v1/workspaces/{ws}/projects/{pj}/sales-outputs/{id}/preview?revision=N` */
export function previewRequestUrl(input:PreviewRequest):string|null{
  if(!nonBlank(input.workspace)||!nonBlank(input.project)||!nonBlank(input.outputId))return null;
  if(!Number.isSafeInteger(input.revision)||input.revision<1)return null;
  const base=input.baseUrl.replace(/\/+$/,'');
  return `${base}/v1/workspaces/${encodeURIComponent(input.workspace)}/projects/${encodeURIComponent(input.project)}`+
    `/sales-outputs/${encodeURIComponent(input.outputId)}/preview?revision=${encodeURIComponent(String(input.revision))}`;
}
export function previewStatusKind(status:number):'ok'|PreviewError{
  if(status>=200&&status<300)return 'ok';
  if(status===401||status===403)return 'denied';
  if(status===404)return 'missing';
  return 'unavailable';
}
export function previewNoticeKey(value:PreviewError|'truncated'):string{
  switch(value){
    case 'denied':return 'You no longer have access to this output.';
    case 'missing':return 'This output is no longer available.';
    case 'truncated':return 'Preview truncated';
    default:return 'Preview unavailable';
  }
}
async function readCapped(response:Response,maxBytes:number):Promise<{html:string;truncated:boolean}>{
  if(!response.body){
    const text=await response.text();
    const bytes=new TextEncoder().encode(text);
    if(bytes.length<=maxBytes)return {html:text,truncated:false};
    return {html:new TextDecoder().decode(bytes.subarray(0,maxBytes)),truncated:true};
  }
  const reader=response.body.getReader();
  const chunks:Uint8Array[]=[];
  let total=0,truncated=false;
  try{
    while(total<maxBytes){
      const {done,value}=await reader.read();
      if(done)break;
      const remaining=maxBytes-total;
      if(value.length>remaining){chunks.push(value.subarray(0,remaining));total=maxBytes;truncated=true;void reader.cancel().catch(()=>{});break;}
      chunks.push(value);total+=value.length;
    }
  }finally{try{reader.releaseLock();}catch{/* already released */}}
  const merged=new Uint8Array(total);
  let offset=0;
  for(const chunk of chunks){merged.set(chunk,offset);offset+=chunk.length;}
  return {html:new TextDecoder().decode(merged),truncated};
}
/**
 * One authenticated same-origin GET at the output's own revision. Callers decide
 * when to call it (expansion/retry only); this function never retries or polls.
 */
export async function fetchOutputPreview(input:PreviewRequest&{
  token?:string;signal?:AbortSignal;fetchImpl?:typeof fetch;maxBytes?:number;
}):Promise<PreviewOutcome>{
  const url=previewRequestUrl(input);
  if(!url)return {kind:'error',error:'unavailable'};
  const fetchImpl=input.fetchImpl??fetch;
  let response:Response;
  try{
    response=await fetchImpl(url,{method:'GET',cache:'no-store',signal:input.signal,
      headers:{Accept:'text/html',...(input.token?{Authorization:`Bearer ${input.token}`}:{})}});
  }catch{return {kind:'error',error:'unavailable'};}
  const kind=previewStatusKind(response.status);
  if(kind!=='ok')return {kind:'error',error:kind};
  try{
    const {html,truncated}=await readCapped(response,input.maxBytes??PREVIEW_MAX_BYTES);
    return {kind:'ready',html,truncated};
  }catch{return {kind:'error',error:'unavailable'};}
}
