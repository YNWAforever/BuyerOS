import {normalizeReturnPath, type AuthAdapter} from './auth';

export interface PublicNeonConfig {authPath: string;}
export interface NeonChannel {
  postMessage(event: {type: 'logout' | 'invalidated'}): void;
  subscribe(listener: (event: unknown) => void): () => void;
  close?(): void;
}
export interface NeonEnvironment {
  location: {origin: string; href: string; assign(url: string): void};
  storage: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;
  fetch: typeof fetch;
  crypto: Crypto;
  now: () => number;
  channel?: NeonChannel;
}
const transactionKey = 'buyeros-neon-return', invalidatedKey='buyeros-neon-invalidated';
class InvalidatedSession extends Error {}
function browserChannel(): NeonChannel | undefined {
  if (typeof BroadcastChannel === 'undefined') {
    // Older browsers share only an invalidation event. No token or draft data enters localStorage.
    const key='buyeros-session-invalidation';
    return {postMessage:event=>{try{window.localStorage.setItem(key,JSON.stringify(event));window.localStorage.removeItem(key);}catch{/* Browser storage capability remains a real-environment gate. */}},
      subscribe:listener=>{const receive=(event:StorageEvent)=>{if(event.key!==key||!event.newValue||event.newValue.length>64)return;try{listener(JSON.parse(event.newValue));}catch{/* Ignore malformed invalidations. */}};
        window.addEventListener('storage',receive);return()=>window.removeEventListener('storage',receive);}};
  }
  const channel = new BroadcastChannel('buyeros-session-invalidation');
  return {postMessage: event => channel.postMessage(event), subscribe: listener => {
    const receive = (event: MessageEvent) => listener(event.data);
    channel.addEventListener('message', receive);
    return () => channel.removeEventListener('message', receive);
  }, close: () => channel.close()};
}
function metadata(token: unknown, expectedSubject: string, now: number): {token: string; expires: number} {
  if (typeof token !== 'string' || token.length > 16384 || token.split('.').length !== 3) throw new Error('Invalid session token');
  const part = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
  const claims: unknown = JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(part.padEnd(Math.ceil(part.length / 4) * 4, '=')), c => c.charCodeAt(0))));
  if (!claims || typeof claims !== 'object' || Array.isArray(claims)) throw new Error('Invalid session token');
  const {sub, exp} = claims as Record<string, unknown>;
  if (sub !== expectedSubject || typeof exp !== 'number' || !Number.isFinite(exp) || exp * 1000 <= now + 30_000) throw new Error('Session expired or changed');
  // Browser metadata is never authorization. The API verifies signature/trust and current DB mapping/roles.
  return {token, expires: exp * 1000};
}

/** Cookie transport to the unpatched server SDK. JWTs stay in this instance's memory.
 * The pinned browser SDK broadcasts sessionData (including token); this boundary intentionally
 * uses its server routes without importing that client or patching its cookies/cache/trust.
 */
export function createNeonAuthAdapter(config: PublicNeonConfig, provided?: NeonEnvironment): AuthAdapter {
  if (config.authPath !== '/api/auth') throw new Error('Same-origin Neon auth path required');
  const env = provided ?? {location: window.location, storage: window.sessionStorage, fetch: window.fetch.bind(window), crypto: window.crypto, now: Date.now, channel: browserChannel()};
  let token = '', subject = '', expires = 0, generation = 0, blocked = env.storage.getItem(invalidatedKey)==='1', returnPath = '/app';
  let renewal: Promise<string> | null = null, initialization: Promise<void> | null = null;
  const listeners = new Set<() => void>();
  function clear(type: 'logout' | 'invalidated', broadcast = true) {
    const changed = !blocked || !!token || !!subject;
    try{env.storage.setItem(invalidatedKey,'1');}catch{/* Current instance remains blocked if per-tab storage is unavailable. */}
    generation++; blocked = true; token = ''; subject = ''; expires = 0; renewal = null; initialization = null;
    if (changed) {for (const listener of listeners) listener(); if (broadcast) env.channel?.postMessage({type});}
  }
  const stop = env.channel?.subscribe(event => {
    if (!event || typeof event !== 'object' || Array.isArray(event)) return;
    const data = event as Record<string, unknown>;
    if (Object.keys(data).length === 1 && (data.type === 'logout' || data.type === 'invalidated')) clear(data.type, false);
  });
  async function request(path: string, body?: Record<string, unknown>): Promise<unknown> {
    const response = await env.fetch(config.authPath + path, {method: body ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store', redirect: 'error',
      headers: {Accept: 'application/json', ...(body ? {'Content-Type': 'application/json'} : {})}, body: body ? JSON.stringify(body) : undefined});
    if (!response.ok) throw new Error('Neon session unavailable');
    const text = await response.text();
    if (new TextEncoder().encode(text).byteLength > 128_000) throw new Error('Invalid session response');
    return JSON.parse(text);
  }
  function guard(captured: number) {if (generation !== captured || blocked) throw new InvalidatedSession('Session invalidated');}
  async function refresh(rejectedToken?: string): Promise<string> {
    if (blocked || !subject) throw new InvalidatedSession('Sign in again');
    if (rejectedToken && token && token !== rejectedToken && expires > env.now() + 30_000) return token;
    if (renewal) return renewal;
    const captured = generation, expected = subject;
    const work = (async () => {
      try {
        const result = await request('/token'); guard(captured);
        const value = metadata((result as {token?: unknown} | null)?.token, expected, env.now());
        token = value.token; expires = value.expires; return token;
      } catch (error) {if (generation === captured) clear('invalidated'); throw error;}
    })();
    renewal = work;
    try {return await work;} finally {if (renewal === work) renewal = null;}
  }
  async function initialize(): Promise<void> {
    if (initialization) return initialization;
    if (blocked) return;
    const captured = generation;
    const work = (async () => {
      try {
        const current = new URL(env.location.href), verifier = current.pathname === '/auth/callback' ? current.searchParams.get('neon_auth_session_verifier') : null;
        if (verifier && (verifier.length > 4096 || current.searchParams.getAll('neon_auth_session_verifier').length !== 1)) throw new Error('Invalid session verifier');
        const result = await request('/get-session' + (verifier ? '?neon_auth_session_verifier=' + encodeURIComponent(verifier) : '')); guard(captured);
        if (result === null || (result && typeof result === 'object' && (result as {session?: unknown}).session === null)) return;
        const id = (result as {user?: {id?: unknown}} | null)?.user?.id;
        if (typeof id !== 'string' || !id || id.length > 255 || /[\u0000-\u001f\u007f]/.test(id)) throw new Error('Invalid cookie session');
        subject = id; await refresh(); guard(captured);
      } catch (error) {if (generation === captured) clear('invalidated'); throw error;}
    })();
    initialization = work;
    return work;
  }
  function transaction(): {state: string; returnPath: string; createdAt: number} {
    const raw = env.storage.getItem(transactionKey); if (!raw) throw new Error('Start sign-in again');
    if (raw.length > 4096) throw new Error('Invalid return transaction');
    const value = JSON.parse(raw), age = env.now() - value.createdAt;
    if (typeof value.state !== 'string' || !/^[0-9a-f-]{36}$/.test(value.state) || typeof value.createdAt !== 'number'
      || !Number.isFinite(age) || age < 0 || age > 600_000 || value.returnPath !== normalizeReturnPath(value.returnPath)) throw new Error('Invalid return transaction');
    return value;
  }
  function callbackUrl(): string {return env.location.origin + '/auth/callback?state=' + encodeURIComponent(transaction().state);}
  return {
    provider: 'neon', initialize,
    async signIn(path) {
      const state = env.crypto.randomUUID(); returnPath = normalizeReturnPath(path);
      env.storage.setItem(transactionKey, JSON.stringify({state, returnPath, createdAt: env.now()}));
      env.location.assign('/auth/sign-in?state=' + encodeURIComponent(state));
    },
    async signInEmail(email, password) {
      if (!email.trim() || email.length > 320 || !password || password.length > 4096) throw new Error('Email and password required');
      const callbackURL = callbackUrl();
      await request('/sign-in/email', {email: email.trim(), password, callbackURL});
      env.location.assign(callbackURL);
    },
    async signInGoogle() {
      const callbackURL = callbackUrl();
      const result = await request('/sign-in/social', {provider: 'google', callbackURL, disableRedirect: true});
      const url = new URL((result as {url?: string} | null)?.url ?? '');
      // Neon Auth first redirects through its own /sign-in/social/init hop, which then forwards to Google.
      const neonInit = url.hostname.endsWith('.neon.tech') && url.pathname.endsWith('/sign-in/social/init');
      if (url.protocol !== 'https:' || (url.hostname !== 'accounts.google.com' && !neonInit) || url.username || url.password || url.port) throw new Error('Invalid Google redirect');
      env.location.assign(url.href);
    },
    async completeCallback() {
      const tx = transaction(), current = new URL(env.location.href);
      env.storage.removeItem(transactionKey);
      if (current.origin !== env.location.origin || current.pathname !== '/auth/callback' || current.searchParams.get('state') !== tx.state || current.searchParams.getAll('state').length !== 1) throw new Error('Invalid return state');
      returnPath = tx.returnPath;env.storage.removeItem(invalidatedKey); blocked = false; initialization = null;
      await initialize(); if (!token) throw new Error('Sign-in did not create a session');
    },
    async getAccessToken() {if (blocked || !subject) throw new InvalidatedSession('Sign in again'); return expires <= env.now() + 30_000 ? refresh() : token;},
    refreshAccessToken: refresh,
    async signOut() {clear('logout'); env.storage.removeItem(transactionKey); try {await request('/sign-out', {});} finally {env.location.assign('/app');}},
    invalidate() {clear('invalidated');},
    subscribeInvalidated(listener) {listeners.add(listener); return () => {listeners.delete(listener);};},
    dispose() {clear('invalidated', false); stop?.(); env.channel?.close?.(); listeners.clear();},
    subject: () => subject, expiresAt: () => expires, returnPath: () => returnPath,
  };
}
