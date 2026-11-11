/**
 * Increment 2.5: inline output preview. The server is the only author of the
 * preview HTML; this module only builds the bounded read request, caps the body
 * and maps honest failure states. No retries live here (the UI may offer a manual
 * retry for genuinely transient failures).
 */
export const PREVIEW_MAX_BYTES=64*1024;
export const PREVIEW_TIMEOUT_MS=10_000;
/** Strict sandbox: no tokens means no scripts, forms, popups or same-origin. */
export const PREVIEW_SANDBOX='';
/**
 * A srcdoc document does not inherit the response's CSP header, so the same
 * `default-src 'none'` policy is prepended as a meta policy before server HTML.
 */
export const PREVIEW_CSP_META='<meta http-equiv="Content-Security-Policy" content="default-src \'none\'">';
export function sandboxedPreviewHtml(html:string):string{
  return PREVIEW_CSP_META+html;
}
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
/** A login/error page must never be rendered as the saved output. */
export function previewContentTypeAllowed(value:string|null):boolean{
  return typeof value==='string'&&/^text\/html\b/i.test(value.trim());
}
export function previewNoticeKey(value:PreviewError|'truncated'):string{
  switch(value){
    case 'denied':return 'You no longer have access to this output.';
    case 'missing':return 'This output is no longer available.';
    case 'truncated':return 'Preview truncated';
    default:return 'Preview unavailable';
  }
}
function redirectedAway(response:Response):boolean{
  if(!response.redirected||!response.url)return false;
  try{
    const path=new URL(response.url).pathname;
    return !(path.includes('/sales-outputs/')&&path.endsWith('/preview'));
  }catch{return true;}
}
function decode(chunks:Uint8Array[],total:number):string{
  const merged=new Uint8Array(total);
  let offset=0;
  for(const chunk of chunks){merged.set(chunk,offset);offset+=chunk.length;}
  return new TextDecoder().decode(merged);
}
async function readCapped(response:Response,maxBytes:number,signal?:AbortSignal):Promise<{html:string;truncated:boolean}>{
  if(!response.body){
    // Null-body fallback only exists for non-streaming runtimes/statuses; keep it
    // bounded and honour a declared oversized Content-Length without buffering.
    const declared=Number(response.headers.get('content-length'));
    if(Number.isFinite(declared)&&declared>maxBytes)return {html:'',truncated:true};
    const text=await response.text();
    const bytes=new TextEncoder().encode(text);
    if(bytes.length>maxBytes)return {html:new TextDecoder().decode(bytes.subarray(0,maxBytes)),truncated:true};
    return {html:text,truncated:false};
  }
  const reader=response.body.getReader();
  const chunks:Uint8Array[]=[];
  let total=0,truncated=false;
  const cancel=()=>{void reader.cancel().catch(()=>{});};
  const onAbort=()=>cancel();
  signal?.addEventListener('abort',onAbort,{once:true});
  try{
    while(!signal?.aborted){
      const {done,value}=await reader.read();
      if(done)break;
      const remaining=maxBytes-total;
      if(value.length>remaining){
        if(remaining>0)chunks.push(value.subarray(0,remaining));
        total=maxBytes;truncated=true;cancel();
        break;
      }
      chunks.push(value);total+=value.length;
      if(total===maxBytes){
        // Exact-boundary EOF probe: the loop must not stop on a full budget without
        // proving there is nothing after it, or an aligned oversized body is silently cut.
        let probe=await reader.read();
        while(!probe.done&&probe.value.length===0)probe=await reader.read();
        if(!probe.done){truncated=true;cancel();}
        break;
      }
    }
  }finally{
    signal?.removeEventListener('abort',onAbort);
    try{reader.releaseLock();}catch{/* already released */}
  }
  if(signal?.aborted)throw new DOMException('aborted','AbortError');
  return {html:decode(chunks,total),truncated};
}
/**
 * One authenticated same-origin GET at the output's own revision. Callers decide
 * when to call it (expansion/retry only); this function never retries or polls.
 * The signal aborts both the request and the body read.
 */
export async function fetchOutputPreview(input:PreviewRequest&{
  token?:string;signal?:AbortSignal;fetchImpl?:typeof fetch;maxBytes?:number;timeoutMs?:number;
}):Promise<PreviewOutcome>{
  const url=previewRequestUrl(input);
  if(!url)return {kind:'error',error:'unavailable'};
  if(input.signal?.aborted)return {kind:'error',error:'unavailable'};
  const timeout=new AbortController();
  const timer=setTimeout(()=>timeout.abort(),input.timeoutMs??PREVIEW_TIMEOUT_MS);
  const signal=input.signal?AbortSignal.any([input.signal,timeout.signal]):timeout.signal;
  const fetchImpl=input.fetchImpl??fetch;
  try{
    let response:Response;
    try{
      response=await fetchImpl(url,{method:'GET',cache:'no-store',signal,
        headers:{Accept:'text/html',...(input.token?{Authorization:`Bearer ${input.token}`}:{})}});
    }catch{return {kind:'error',error:'unavailable'};}
    if(signal.aborted)return {kind:'error',error:'unavailable'};
    const kind=previewStatusKind(response.status);
    if(kind!=='ok')return {kind:'error',error:kind};
    if(!previewContentTypeAllowed(response.headers.get('content-type'))||redirectedAway(response))
      return {kind:'error',error:'unavailable'};
    try{
      const {html,truncated}=await readCapped(response,input.maxBytes??PREVIEW_MAX_BYTES,signal);
      if(signal.aborted)return {kind:'error',error:'unavailable'};
      return {kind:'ready',html,truncated};
    }catch{return {kind:'error',error:'unavailable'};}
  }finally{clearTimeout(timer);}
}
