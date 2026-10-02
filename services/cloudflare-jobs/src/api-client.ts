import { requestSchemas, parseResponse, type InternalOperation, type InternalRequest, type InternalResponse } from './protocol';

type ApiSettings = Pick<Env, 'WORKER_API_ORIGIN' | 'WORKER_API_ALLOWED_ORIGINS' | 'WORKER_CURRENT_KEY_ID' | 'WORKER_CURRENT_SECRET'> & Partial<Pick<Env, 'LOCAL_TEST_MODE'>> & { WORKER_API_PROTECTION_BYPASS?: string };
const paths = {
  workerClaim: '/v1/internal/worker/claim', workerExecuteStep: '/v1/internal/worker/step',
  workerStepStatus: '/v1/internal/worker/status', workerRecordPublication: '/v1/internal/worker/publication',
  workerMaintenance: '/v1/internal/worker/maintenance',
} satisfies Record<InternalOperation, string>;

function apiOrigin(settings: ApiSettings): string {
  const url = new URL(settings.WORKER_API_ORIGIN);
  const allowed: unknown = JSON.parse(settings.WORKER_API_ALLOWED_ORIGINS);
  const loopback = settings.LOCAL_TEST_MODE === 'true' && ['127.0.0.1', '[::1]'].includes(url.hostname);
  if (url.username || url.password || url.search || url.hash || url.pathname !== '/' ||
      (url.protocol !== 'https:' && !(loopback && url.protocol === 'http:')) ||
      !Array.isArray(allowed) || allowed.length > 5 || !allowed.every(item => typeof item === 'string') ||
      !allowed.includes(url.origin)) throw new Error('worker API origin is not approved');
  return url.origin;
}

const hex = (bytes: ArrayBuffer) => Array.from(new Uint8Array(bytes), byte => byte.toString(16).padStart(2, '0')).join('');

export async function buildSignedRequest<K extends InternalOperation>(settings: ApiSettings, operation: K, body: InternalRequest<K>,
  options: { timestamp?: number; nonce?: string; timeoutMs?: number } = {}): Promise<Request> {
  const path = paths[operation];
  if (!path) throw new Error('unknown worker API operation');
  const origin = apiOrigin(settings);
  const payload = JSON.stringify(requestSchemas[operation].parse(body));
  const encoded = new TextEncoder().encode(payload);
  const secret = new TextEncoder().encode(settings.WORKER_CURRENT_SECRET);
  if (encoded.byteLength > 8192 || secret.byteLength < 32 || secret.byteLength > 4096 ||
      !/^[A-Za-z0-9_-]{1,64}$/.test(settings.WORKER_CURRENT_KEY_ID)) throw new Error('invalid worker signing configuration');
  const timestamp = options.timestamp ?? Math.floor(Date.now() / 1000);
  const nonce = options.nonce ?? crypto.randomUUID();
  if (!Number.isSafeInteger(timestamp) || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(nonce)) {
    throw new Error('invalid worker signature metadata');
  }
  const digest = hex(await crypto.subtle.digest('SHA-256', encoded));
  const canonical = new TextEncoder().encode(`POST\n${path}\n${timestamp}\n${nonce}\n${digest}`);
  const key = await crypto.subtle.importKey('raw', secret, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const signature = hex(await crypto.subtle.sign('HMAC', key, canonical));
  const headers = new Headers({ 'content-type': 'application/json', 'x-buyeros-worker-key-id': settings.WORKER_CURRENT_KEY_ID,
    'x-buyeros-worker-timestamp': String(timestamp), 'x-buyeros-worker-nonce': nonce, 'x-buyeros-worker-signature': signature });
  const protectionBypass = settings.WORKER_API_PROTECTION_BYPASS;
  if (protectionBypass !== undefined) {
    if (!/^[\x21-\x7E]{1,4096}$/.test(protectionBypass)) throw new Error('invalid worker protection configuration');
    headers.set('x-vercel-protection-bypass', protectionBypass);
  }
  return new Request(origin + path, {
    method: 'POST', body: payload, redirect: 'manual',
    signal: AbortSignal.timeout(Math.max(1, Math.min(75_000, options.timeoutMs ?? 75_000))),
    headers,
  });
}

async function boundedJson(response: Response): Promise<unknown> {
  if (!response.body) throw new Error('worker API body missing');
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let bytes = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      bytes += value.byteLength;
      if (bytes > 8192) throw new Error('worker API response exceeds protocol bound');
      chunks.push(value);
    }
  } finally {
    await reader.cancel();
  }
  const result = new Uint8Array(bytes);
  let offset = 0;
  for (const chunk of chunks) { result.set(chunk, offset); offset += chunk.byteLength; }
  return JSON.parse(new TextDecoder('utf-8', { fatal: true, ignoreBOM: false }).decode(result));
}

export class WorkerApiError extends Error {
  constructor(readonly status: number) { super('worker API request failed'); }
}

export async function callWorkerApi<K extends InternalOperation>(settings: ApiSettings, operation: K, body: InternalRequest<K>, timeoutMs = 75_000): Promise<InternalResponse<K>> {
  const request = await buildSignedRequest(settings, operation, body, { timeoutMs });
  const response = await fetch(request);
  if (!response.ok) { await response.body?.cancel(); throw new WorkerApiError(response.status); }
  return parseResponse(operation, await boundedJson(response));
}
