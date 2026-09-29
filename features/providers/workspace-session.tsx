'use client';
import {createContext, useContext, useEffect, useMemo, useState, useSyncExternalStore, type ReactNode} from 'react';
import {SessionScope} from '@/services/live/session';
import {createLiveClient} from '@/services/live/client';
import {createAuthAdapter, type AuthAdapter, type AuthConfig} from '@/services/live/auth';
import {useDataMode} from './data-mode';

interface SessionValue {session: SessionScope; client: ReturnType<typeof createLiveClient>; auth: AuthAdapter | null; authError: string | null;}
const SessionContext = createContext<SessionValue | null>(null);
const noBrowserChange = () => () => {};
const inBrowser = () => true;
const onServer = () => false;

export function WorkspaceSessionProvider({children, authConfig}: {children: ReactNode; authConfig?: AuthConfig | null}) {
  const {mode, apiBaseUrl} = useDataMode();
  const [base] = useState(() => ({session: new SessionScope({mode, actor: ''}), client: createLiveClient(fetch, apiBaseUrl)}));
  // The server and hydration pass agree on a null adapter; the browser then instantiates it.
  const browser = useSyncExternalStore(noBrowserChange, inBrowser, onServer);
  const issuer = authConfig?.issuer, clientId = authConfig?.clientId, audience = authConfig?.audience;
  const authState = useMemo((): Pick<SessionValue, 'auth' | 'authError'> => {
    if (!browser || mode !== 'live') return {auth: null, authError: null};
    if (!issuer || !clientId || !audience) return {auth: null, authError: null};
    try {return {auth: createAuthAdapter({issuer, clientId, audience}), authError: null};}
    catch {return {auth: null, authError: 'Public OIDC configuration is invalid'};}
  }, [browser, mode, issuer, clientId, audience]);
  useEffect(() => {
    const auth = authState.auth;
    if (!auth) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const arm = () => {
      if (timer) clearTimeout(timer);
      if (!base.session.token()) return;
      const delay = auth.expiresAt() - Date.now() - 30_000;
      if (delay <= 0) {base.session.setToken(undefined); return;}
      timer = setTimeout(() => base.session.setToken(undefined), delay);
    };
    arm();
    const stop = base.session.subscribe(arm);
    return () => {stop(); if (timer) clearTimeout(timer);};
  }, [authState.auth, base.session]);
  return <SessionContext.Provider value={{...base, ...authState}}>{children}</SessionContext.Provider>;
}

export function useWorkspaceSession(): SessionValue {
  const value = useContext(SessionContext);
  if (value === null) throw new Error('useWorkspaceSession requires WorkspaceSessionProvider');
  return value;
}
export function useSessionSnapshot() {
  const {session} = useWorkspaceSession();
  return useSyncExternalStore(session.subscribe, session.getSnapshot, session.getSnapshot);
}
