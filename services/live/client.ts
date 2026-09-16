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
}

async function bodyOf(response: {json: () => Promise<unknown>}): Promise<Record<string, unknown>> {
  try {
    const parsed = await response.json();
    return typeof parsed === 'object' && parsed !== null ? (parsed as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

export function createLiveClient(fetchImpl: typeof fetch = fetch) {
  return {
    async request<T>({path, method = 'GET', token, scope, signal}: LiveRequest): Promise<T> {
      void scope;
      const headers: Record<string, string> = {Accept: 'application/json'};
      if (token) headers.Authorization = `Bearer ${token}`;
      let response: Awaited<ReturnType<typeof fetch>>;
      try {
        response = await fetchImpl(path, {method, headers, signal});
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') throw new LiveCancelled('cancelled');
        throw new LiveError('request failed', 'NETWORK_ERROR', 0, '', true);
      }
      if (!response.ok) {
        const body = await bodyOf(response as unknown as {json: () => Promise<unknown>});
        const code = typeof body.code === 'string' ? body.code : 'UNKNOWN_ERROR';
        const message = typeof body.message === 'string' ? body.message : 'request failed';
        const requestId = typeof body.request_id === 'string' ? body.request_id : '';
        throw new LiveError(message, code, response.status, requestId, body.retryable === true);
      }
      const body = await bodyOf(response as unknown as {json: () => Promise<unknown>});
      return (body as {data?: T}).data as T;
    },
  };
}

export type LiveClient = ReturnType<typeof createLiveClient>;
