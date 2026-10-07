export class LiveError extends Error {
  constructor(message: string, readonly code: string, readonly status: number, readonly requestId: string, readonly retryable: boolean, readonly retryAfter?: string) {
    super(message);
  }
}

/** User-action guidance; do not expose raw server detail or retry writes blindly. */
export function describeLiveError(error: unknown): string {
  if (!(error instanceof LiveError)) return 'Request failed. Try again after checking the connection.';
  const guidance = error.status === 401 ? 'Sign in again to continue.'
    : error.status === 412 ? 'Refresh and compare the latest version before retrying.'
    : error.status === 409 ? 'Review the conflict and start a new action if the payload changed.'
    : error.status === 403 ? 'You do not have permission for this action.'
    : error.status === 404 ? 'The selected item was not found in this workspace.'
    : error.status === 429 || error.status >= 500 || error.retryable ? 'Service temporarily unavailable. Retry after checking the status.'
    : 'Review the entered values and try again.';
  return error.requestId ? `${guidance} Request ID: ${error.requestId}` : guidance;
}

/** A request was aborted because the scope changed. Normal, never an error state. */
export class LiveCancelled extends Error {}

export interface AccessDenied {scope: string; workspace: string;}

export interface LiveRequest {
  path: string;
  method?: string;
  token?: string;
  scope: string;
  signal?: AbortSignal;
  body?: unknown;
  formData?: FormData;
  idempotencyKey?: string;
  ifMatch?: string;
}

async function bodyOf(response: {json: () => Promise<unknown>}): Promise<Record<string, unknown>> {
  try {
    const parsed = await response.json();
    return typeof parsed === 'object' && parsed !== null ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

/**
 * The API base URL is resolved server-side and threaded down through `DataModeProvider`. Without it
 * a live read would be sent to the app's own origin (`fetch(path)`) instead of the API. The default
 * `''` keeps the path used as-is for callers that pass no base URL.
 */
export function createLiveClient(fetchImpl: typeof fetch = fetch, baseUrl = '') {
  const root = baseUrl.replace(/\/$/, '');
  const accessListeners = new Set<(event: AccessDenied) => void>();
  function notifyAccessDenied(path: string, scope: string, status: number, signal?: AbortSignal) {
    const workspace = path.match(/^\/v1\/workspaces\/([^/?]+)(?:[/?]|$)/)?.[1];
    if (!workspace || signal?.aborted || ![403, 404].includes(status)) return;
    for (const listener of accessListeners) listener({workspace, scope});
  }
  return {
    subscribeAccessDenied(listener: (event: AccessDenied) => void): () => void {
      accessListeners.add(listener);
      return () => {accessListeners.delete(listener);};
    },
    async requestContent({path, token, scope, signal}: Pick<LiveRequest,'path'|'token'|'scope'|'signal'>): Promise<{text:string;contentType:string}> {
      let response: Awaited<ReturnType<typeof fetch>>;
      try {
        response = await fetchImpl(`${root}${path}`, {method:'GET',
          headers:{Accept:'text/csv, text/plain',...(token?{Authorization:`Bearer ${token}`}:{})}, signal});
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') throw new LiveCancelled('cancelled');
        throw new LiveError('request failed','NETWORK_ERROR',0,'',true);
      }
      if (!response.ok) {
        const errorBody = await bodyOf(response as unknown as {json: () => Promise<unknown>});
        notifyAccessDenied(path, scope, response.status, signal);
        throw new LiveError(typeof errorBody.message==='string'?errorBody.message:'request failed',
          typeof errorBody.code==='string'?errorBody.code:'UNKNOWN_ERROR', response.status,
          typeof errorBody.request_id==='string'?errorBody.request_id:response.headers.get('X-Request-ID')||'',
          errorBody.retryable===true);
      }
      const contentType=response.headers.get('Content-Type')||'';
      if (!contentType.startsWith('text/csv')&&!contentType.startsWith('text/plain'))
        throw new LiveError('Invalid export content','INVALID_CONTENT',response.status,
          response.headers.get('X-Request-ID')||'',false);
      const text=await response.text();
      if (new TextEncoder().encode(text).byteLength>1_000_000)
        throw new LiveError('Export exceeds client size limit','INVALID_CONTENT',response.status,
          response.headers.get('X-Request-ID')||'',false);
      return {text,contentType};
    },
    async request<T>({path, method = 'GET', token, scope, signal, body, formData, idempotencyKey, ifMatch}: LiveRequest): Promise<T> {
      const headers: Record<string, string> = {Accept: 'application/json'};
      if (token) headers.Authorization = `Bearer ${token}`;
      if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey;
      if (ifMatch) headers['If-Match'] = ifMatch;
      if (body !== undefined && formData !== undefined) throw new LiveError('ambiguous request body', 'INVALID_REQUEST', 0, '', false);
      let payload: string | FormData | undefined = formData;
      if (body !== undefined) {
        headers['Content-Type'] = 'application/json';
        payload = JSON.stringify(body);
      }
      let response: Awaited<ReturnType<typeof fetch>>;
      try {
        response = await fetchImpl(`${root}${path}`, {method, headers, signal, body: payload});
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') throw new LiveCancelled('cancelled');
        throw new LiveError('request failed', 'NETWORK_ERROR', 0, '', true);
      }
      if (!response.ok) {
        const errorBody = await bodyOf(response as unknown as {json: () => Promise<unknown>});
        const code = typeof errorBody.code === 'string' ? errorBody.code : 'UNKNOWN_ERROR';
        const message = typeof errorBody.message === 'string' ? errorBody.message : 'request failed';
        const headerId = response.headers?.get('X-Request-ID') || '';
        const requestId = typeof errorBody.request_id === 'string' ? errorBody.request_id : headerId;
        notifyAccessDenied(path, scope, response.status, signal);
        throw new LiveError(message, code, response.status, requestId, errorBody.retryable === true, response.headers?.get('Retry-After') || undefined);
      }
      if (response.status === 204) return undefined as T;
      const responseBody = await bodyOf(response as unknown as {json: () => Promise<unknown>});
      if (responseBody.data_mode !== 'live' || typeof responseBody.request_id !== 'string' || !Object.hasOwn(responseBody, 'data')) {
        throw new LiveError('Invalid live response', 'INVALID_ENVELOPE', response.status, response.headers?.get('X-Request-ID') || '', false);
      }
      return responseBody.data as T;
    },
  };
}

export type LiveClient = ReturnType<typeof createLiveClient>;
