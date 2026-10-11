import type {AuthAdapter} from './auth';
import {LiveCancelled, type LiveClient} from './client';
import type {SessionScope} from './session';

/** Owns async hydration and refresh without making token renewal a scope transition. */
export function bindAuthSession(session: SessionScope, auth: AuthAdapter, client: LiveClient, options: {hydrate?: boolean} = {}) {
  let active = true, timer: ReturnType<typeof setTimeout> | undefined, renewing = false;
  const initialIdentity = session.identity();
  const guard = (identity: string) => {if (!active || !session.isCurrent(identity)) throw new LiveCancelled('scope changed');};
  const invalidate = () => {if (active) session.setToken(undefined);};
  const stopInvalidated = auth.subscribeInvalidated?.(invalidate);
  async function refresh(rejected: string, identity: string) {
    guard(identity);
    if (!auth.refreshAccessToken) throw new Error('Sign in again');
    const token = await auth.refreshAccessToken(rejected); guard(identity);
    if (auth.subject() !== session.current().actor) throw new LiveCancelled('session changed');
    session.setToken(token); return token;
  }
  client.setAuthRecovery(auth.refreshAccessToken ? {refresh, isCurrent: identity => active && session.isCurrent(identity), onUnauthorized: () => auth.invalidate?.()} : undefined);
  const arm = () => {
    if (timer) clearTimeout(timer);
    const token = session.token(); if (!active || !token || renewing) return;
    const delay = Math.max(0, auth.expiresAt() - Date.now() - 30_000);
    timer = setTimeout(() => {
      if (!auth.refreshAccessToken) {invalidate(); return;}
      const identity = session.identity(); renewing = true;
      void refresh(token, identity).catch(() => {if (active && session.isCurrent(identity)) {auth.invalidate?.(); invalidate();}})
        .finally(() => {renewing = false; if (active && session.isCurrent(identity)) arm();});
    }, delay);
  };
  const stopSession = session.subscribe(arm);
  const ready = (async () => {
    if (!auth.initialize || options.hydrate === false) return;
    await auth.initialize(); guard(initialIdentity);
    if (!auth.subject()) return;
    const token = await auth.getAccessToken(); guard(initialIdentity);
    session.next({actor: auth.subject(), workspace: null, project: null}); session.setToken(token);
  })();
  arm();
  return {ready, dispose() {active = false; stopInvalidated?.(); stopSession(); if (timer) clearTimeout(timer); client.setAuthRecovery(undefined);}};
}

/** Callback exchange is single-use at the caller and may only publish its captured generation. */
export async function completeSessionCallback(auth: AuthAdapter, session: SessionScope, isActive: () => boolean = () => true): Promise<string> {
  const identity=session.identity();
  const guard=()=>{if(!isActive()||!session.isCurrent(identity))throw new LiveCancelled('scope changed');};
  await auth.completeCallback();guard();
  const token=await auth.getAccessToken();guard();
  session.next({actor:auth.subject(),workspace:null,project:null});session.setToken(token);
  return auth.returnPath();
}
