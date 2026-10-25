type Environment = Record<string, string | undefined>;
type Transport = typeof fetch;

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const on = (value: string | undefined) => value === '1' || value === 'true';
const error = (code: string, status: number, retryable = false) => reply({code,retryable},status);
const unavailable = () => error('intake_unavailable',503,true);

function reply(body: unknown, status = 200) {
  return Response.json(body,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
}

function configuration(env: Environment) {
  if (!on(env.MARKETING_ENABLED) || (!on(env.MARKETING_SYNTHETIC_MODE) && !on(env.MARKETING_REAL_INTAKE_APPROVED))) return null;
  try {
    const upstream = new URL(env.MARKETING_API_ORIGIN || '');
    const publicOrigin = new URL(env.MARKETING_PUBLIC_ORIGIN || '');
    for (const [url,value] of [[upstream,env.MARKETING_API_ORIGIN],[publicOrigin,env.MARKETING_PUBLIC_ORIGIN]] as const) {
      if (url.origin !== value || url.username || url.password || !['http:','https:'].includes(url.protocol)
        || (url.protocol === 'http:' && !['localhost','127.0.0.1','[::1]'].includes(url.hostname))) return null;
    }
    if (!env.MARKETING_GATEWAY_KEY || env.MARKETING_GATEWAY_KEY.length < 32 || !/^[\x20-\x7e]+$/.test(env.MARKETING_GATEWAY_KEY)) return null;
    return {upstream:upstream.origin,origin:publicOrigin.origin,key:env.MARKETING_GATEWAY_KEY,synthetic:on(env.MARKETING_SYNTHETIC_MODE)};
  } catch { return null; }
}

async function boundedBody(stream: ReadableStream<Uint8Array> | null) {
  if (!stream) return '';
  const reader = stream.getReader();
  const decoder = new TextDecoder('utf-8',{fatal:true});
  let total = 0;
  let body = '';
  try {
    while (true) {
      const {done,value} = await reader.read();
      if (done) return body + decoder.decode();
      total += value.byteLength;
      if (total > 8192) {
        await reader.cancel();
        throw new Error('body limit');
      }
      body += decoder.decode(value,{stream:true});
    }
  } finally { reader.releaseLock(); }
}

/** Transport injection is only for deterministic local tests. No tenant session enters this boundary. */
export function marketingHandlers(readEnvironment: () => Environment, transport: Transport = fetch) {
  async function handle(request: Request, method: 'GET' | 'POST') {
    const config = configuration(readEnvironment());
    if (!config) return unavailable();
    const suppliedOrigin = request.headers.get('Origin');
    if (new URL(request.url).origin !== config.origin || (suppliedOrigin !== config.origin
      && !(method === 'GET' && suppliedOrigin === null && request.headers.get('Sec-Fetch-Site') === 'same-origin'))) {
      return error('forbidden',403);
    }
    const headers = new Headers({'Origin':config.origin,'X-Marketing-Gateway-Key':config.key});
    let body: string | undefined;
    if (method === 'POST') {
      try {
        const key = request.headers.get('Idempotency-Key') || '';
        const size = request.headers.get('Content-Length');
        if (!uuid.test(key) || request.headers.get('Content-Type')?.split(';')[0].trim().toLowerCase() !== 'application/json'
          || (size !== null && (!/^\d+$/.test(size) || Number(size) > 8192))) return error('invalid_request',422);
        body = await boundedBody(request.body);
        const parsed: unknown = JSON.parse(body);
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return error('invalid_request',422);
        headers.set('Idempotency-Key',key);
        headers.set('Content-Type','application/json');
      } catch { return error('invalid_request',422); }
    }
    try {
      const upstream = await transport(config.upstream + '/marketing/leads' + (method === 'GET' ? '/challenge' : ''),{
        method,headers,body,cache:'no-store',credentials:'omit',redirect:'error',signal:AbortSignal.timeout(8000),
      });
      const result = JSON.parse(await boundedBody(upstream.body));
      if (method === 'GET' && upstream.status === 200 && typeof result.challenge_id === 'string' && uuid.test(result.challenge_id)) {
        return reply({challenge_id:result.challenge_id});
      }
      if (method === 'POST' && [200,201].includes(upstream.status) && result.status === 'received'
        && typeof result.receipt_id === 'string' && uuid.test(result.receipt_id) && result.synthetic === config.synthetic) {
        return reply({receipt_id:result.receipt_id,status:'received',synthetic:result.synthetic},upstream.status);
      }
      const allowed: Record<number, readonly string[]> = {403:['forbidden'],409:['idempotency_conflict'],422:['invalid_request','challenge_invalid'],429:['rate_limited'],503:['intake_unavailable']};
      if (typeof result.code === 'string' && allowed[upstream.status]?.includes(result.code)) {
        return error(result.code,upstream.status,upstream.status === 429 || upstream.status === 503);
      }
      return unavailable();
    } catch { return unavailable(); }
  }
  return {GET:(request: Request) => handle(request,'GET'),POST:(request: Request) => handle(request,'POST')};
}
