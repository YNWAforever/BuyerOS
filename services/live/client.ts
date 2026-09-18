export class LiveError extends Error {
  constructor(message: string, readonly code: string, readonly status: number, readonly requestId: string, readonly retryable: boolean) {
    super(message);
  }
}

/** A request was aborted because the scope changed. Normal, never an error state. */
export class LiveCancelled extends Error {}

export interface LiveRequest {
  path: string;
  method?: string;
  token?: string;
  scope: string;
  signal?: AbortSignal;
  body?: unknown;
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
  return {
    async request<T>({path, method = 'GET', token, scope, signal, body, idempotencyKey, ifMatch}: LiveRequest): Promise<T> {
      void scope;
      const headers: Record<string, string> = {Accept: 'application/json'};
      if (token) headers.Authorization = `Bearer ${token}`;
      if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey;
      if (ifMatch) headers['If-Match'] = ifMatch;
      let payload: string | undefined;
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
        const requestId = typeof errorBody.request_id === 'string' ? errorBody.request_id : '';
        throw new LiveError(message, code, response.status, requestId, errorBody.retryable === true);
      }
      const responseBody = await bodyOf(response as unknown as {json: () => Promise<unknown>});
      return (responseBody as {data?: T}).data as T;
    },
  };
}

export type LiveClient = ReturnType<typeof createLiveClient>;
