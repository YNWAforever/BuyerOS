/** Same-origin entry to the internal FastAPI service. Tokens stay in the caller's request. */
export const dynamic = 'force-dynamic';

const requestHeaders = [
  'accept', 'accept-language', 'authorization', 'content-type',
  'idempotency-key', 'if-match', 'if-none-match', 'last-event-id', 'x-request-id',
];
const responseHeaders = [
  'allow', 'cache-control', 'content-disposition', 'content-type', 'etag',
  'retry-after', 'vary', 'x-request-id',
];

async function proxy(request: Request): Promise<Response> {
  const binding = process.env.BUYEROS_INTERNAL_API_URL;
  if (!binding) {
    return Response.json({code: 'SERVICE_UNAVAILABLE', message: 'API service unavailable',
      request_id: crypto.randomUUID(), retryable: true},
      {status: 503, headers: {'Cache-Control': 'private, no-store'}});
  }

  let base: URL;
  let target: URL;
  try {
    base = new URL(binding.endsWith('/') ? binding : `${binding}/`);
    if (!['http:', 'https:'].includes(base.protocol)) throw new Error('invalid binding');
    const incoming = new URL(request.url);
    if (!incoming.pathname.startsWith('/v1/')) throw new Error('invalid API path');
    target = new URL(`${incoming.pathname.slice(1)}${incoming.search}`, base);
  } catch {
    return Response.json({code: 'SERVICE_UNAVAILABLE', message: 'API service unavailable',
      request_id: crypto.randomUUID(), retryable: true},
      {status: 503, headers: {'Cache-Control': 'private, no-store'}});
  }

  const headers = new Headers();
  for (const name of requestHeaders) {
    const value = request.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: request.method === 'GET' || request.method === 'HEAD' ? undefined : request.body,
      duplex: 'half',
      cache: 'no-store',
      redirect: 'manual',
      signal: request.signal,
    } as RequestInit & {duplex: 'half'});
    const forwarded = new Headers();
    for (const name of responseHeaders) {
      const value = upstream.headers.get(name);
      if (value !== null) forwarded.set(name, value);
    }
    const location = upstream.headers.get('location');
    if (location) {
      const redirect = new URL(location, target);
      if (redirect.origin === target.origin) {
        const prefix = base.pathname.replace(/\/$/, '');
        if (!redirect.pathname.startsWith(`${prefix}/v1/`)) throw new Error('invalid API redirect');
        forwarded.set('Location', `${redirect.pathname.slice(prefix.length)}${redirect.search}${redirect.hash}`);
      } else {
        forwarded.set('Location', location);
      }
    }
    forwarded.set('Cache-Control', 'private, no-store');
    return new Response(upstream.body, {status: upstream.status, headers: forwarded});
  } catch {
    return Response.json({code: 'SERVICE_UNAVAILABLE', message: 'API service unavailable',
      request_id: crypto.randomUUID(), retryable: true},
      {status: 503, headers: {'Cache-Control': 'private, no-store'}});
  }
}

export const GET = proxy;
export const HEAD = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
