/** Public OIDC Authorization Code + PKCE adapter. Tokens exist only in this instance's memory. */
export interface AuthAdapter {
  signIn(returnPath: string): Promise<void>;
  completeCallback(): Promise<void>;
  getAccessToken(): Promise<string>;
  signOut(): Promise<void>;
  subject(): string;
  returnPath(): string;
  expiresAt(): number;
}
export interface AuthConfig {issuer: string; clientId: string; audience: string; clientSecret?: never;}
interface AuthEnvironment {
  location: {origin: string; href: string; assign(url: string): void};
  storage: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;
  fetch: typeof fetch;
  crypto: Crypto;
  now: () => number;
}
const transactionKey = 'buyeros-oidc-transaction';
const enc = new TextEncoder();
function base64url(bytes: Uint8Array): string {
  let binary = '';
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
function decodePart(value: string): Record<string, unknown> {
  const padded = value.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(value.length / 4) * 4, '=');
  const bytes = Uint8Array.from(atob(padded), char => char.charCodeAt(0));
  const parsed: unknown = JSON.parse(new TextDecoder().decode(bytes));
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) throw new Error('Invalid OIDC token');
  return parsed as Record<string, unknown>;
}
export function normalizeReturnPath(value: string): string {
  if (!value.startsWith('/app') || (value.length > 4 && !['/', '?', '#'].includes(value[4])) || value.startsWith('//') || value.includes('\\') || /[\r\n]/.test(value)) return '/app';
  return value;
}
function random(env: AuthEnvironment): string {
  const bytes = new Uint8Array(32);
  env.crypto.getRandomValues(bytes);
  return base64url(bytes);
}
function issuerOf(value: string): string {
  const url = new URL(value);
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || url.pathname !== '/' || !url.hostname) throw new Error('Public HTTPS OIDC issuer required');
  return `${url.origin}/`;
}
export function createAuthAdapter(config: AuthConfig, provided?: AuthEnvironment): AuthAdapter {
  if ('clientSecret' in config || !config.clientId || !config.audience) throw new Error('Public OIDC configuration required');
  const issuer = issuerOf(config.issuer);
  const env = provided ?? {location: window.location, storage: window.sessionStorage, fetch: window.fetch.bind(window), crypto: window.crypto, now: Date.now};
  const redirectUri = `${env.location.origin}/auth/callback`;
  let accessToken: string | undefined;
  let subject = '';
  let expiry = 0;
  let completedReturnPath = '/app';
  async function verifyIdToken(raw: string, nonce: string): Promise<string> {
    const parts = raw.split('.');
    if (parts.length !== 3) throw new Error('Invalid OIDC ID token');
    const header = decodePart(parts[0]);
    const claims = decodePart(parts[1]);
    if (header.alg !== 'RS256' || typeof header.kid !== 'string') throw new Error('Unsupported OIDC signature');
    if (claims.iss !== issuer || !(claims.aud === config.clientId || (Array.isArray(claims.aud) && claims.aud.includes(config.clientId))) || claims.nonce !== nonce || typeof claims.sub !== 'string' || !claims.sub || typeof claims.exp !== 'number' || claims.exp * 1000 <= env.now()) throw new Error('OIDC identity mismatch');
    const response = await env.fetch(`${issuer}.well-known/jwks.json`, {cache: 'no-store'});
    if (!response.ok) throw new Error('OIDC keys unavailable');
    const body: unknown = await response.json();
    const keys = typeof body === 'object' && body !== null && 'keys' in body ? (body as {keys: unknown}).keys : null;
    if (!Array.isArray(keys)) throw new Error('Invalid OIDC key set');
    const jwk = keys.find((candidate: unknown) => typeof candidate === 'object' && candidate !== null && (candidate as Record<string, unknown>).kid === header.kid && (candidate as Record<string, unknown>).kty === 'RSA' && (candidate as Record<string, unknown>).use === 'sig');
    if (!jwk) throw new Error('OIDC signing key unavailable');
    const key = await env.crypto.subtle.importKey('jwk', jwk, {name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256'}, false, ['verify']);
    const signature = Uint8Array.from(atob(parts[2].replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(parts[2].length / 4) * 4, '=')), char => char.charCodeAt(0));
    const verified = await env.crypto.subtle.verify('RSASSA-PKCS1-v1_5', key, signature, enc.encode(`${parts[0]}.${parts[1]}`));
    if (!verified) throw new Error('Invalid OIDC signature');
    return claims.sub;
  }
  return {
    async signIn(returnPath) {
      const verifier = random(env);
      const challenge = base64url(new Uint8Array(await env.crypto.subtle.digest('SHA-256', enc.encode(verifier))));
      const state = random(env), nonce = random(env);
      env.storage.setItem(transactionKey, JSON.stringify({state, nonce, verifier, returnPath: normalizeReturnPath(returnPath)}));
      const url = new URL('authorize', issuer);
      for (const [key, value] of Object.entries({response_type:'code', client_id:config.clientId, redirect_uri:redirectUri, scope:'openid profile', audience:config.audience, code_challenge:challenge, code_challenge_method:'S256', state, nonce})) url.searchParams.set(key, value);
      env.location.assign(url.toString());
    },
    async completeCallback() {
      const transaction = env.storage.getItem(transactionKey);
      env.storage.removeItem(transactionKey);
      const params = new URL(env.location.href).searchParams;
      if (!transaction || params.has('error')) throw new Error('OIDC callback rejected');
      const pending: unknown = JSON.parse(transaction);
      if (typeof pending !== 'object' || pending === null) throw new Error('OIDC transaction missing');
      const tx = pending as Record<string, unknown>;
      if (typeof tx.state !== 'string' || tx.state !== params.get('state') || typeof tx.verifier !== 'string' || typeof tx.nonce !== 'string' || !params.get('code')) throw new Error('OIDC state mismatch');
      const response = await env.fetch(new URL('oauth/token', issuer), {method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'}, body:new URLSearchParams({grant_type:'authorization_code', client_id:config.clientId, code:params.get('code')!, code_verifier:tx.verifier, redirect_uri:redirectUri})});
      if (!response.ok) throw new Error('OIDC token exchange failed');
      const body: unknown = await response.json();
      if (typeof body !== 'object' || body === null) throw new Error('OIDC token response invalid');
      const token = body as Record<string, unknown>;
      if (typeof token.access_token !== 'string' || typeof token.id_token !== 'string' || typeof token.expires_in !== 'number' || token.expires_in <= 0) throw new Error('OIDC token response invalid');
      const verifiedSubject = await verifyIdToken(token.id_token, tx.nonce);
      accessToken = token.access_token;
      subject = verifiedSubject;
      expiry = env.now() + Math.min(token.expires_in * 1000, 86_400_000);
      completedReturnPath = normalizeReturnPath(typeof tx.returnPath === 'string' ? tx.returnPath : '/app');
    },
    async getAccessToken() {
      if (!accessToken || env.now() >= expiry - 30_000) { accessToken = undefined; subject = ''; throw new Error('Sign-in expired'); }
      return accessToken;
    },
    async signOut() {
      accessToken = undefined; subject = ''; expiry = 0;
      env.storage.removeItem(transactionKey);
      const url = new URL('v2/logout', issuer);
      url.searchParams.set('client_id', config.clientId);
      url.searchParams.set('returnTo', `${env.location.origin}/app`);
      env.location.assign(url.toString());
    },
    subject: () => subject,
    returnPath: () => completedReturnPath,
    expiresAt: () => expiry,
  };
}
