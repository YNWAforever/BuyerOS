'use client';
import {createContext, useContext, useEffect, useMemo, useState, useSyncExternalStore, type ReactNode} from 'react';
import {SessionScope} from '@/services/live/session';
import {createLiveClient} from '@/services/live/client';
import {createAuthAdapter, type AuthAdapter, type AuthConfig} from '@/services/live/auth';
import {createNeonAuthAdapter} from '@/services/live/neon-auth';
import {bindAuthSession} from '@/services/live/auth-session';
import {DraftRecovery} from '@/services/live/draft-recovery';
import type {PublicAuth} from '@/lib/auth/public-auth';
import {useDataMode} from './data-mode';

export type AuthBootstrap = {kind: 'initializing'} | {kind: 'disabled'} | {kind: 'ready'; auth: AuthAdapter} | {kind: 'configuration_error'; message: string};
interface SessionValue {draftRecovery:DraftRecovery; authBootstrap: AuthBootstrap; session: SessionScope; client: ReturnType<typeof createLiveClient>; auth: AuthAdapter | null; authError: string | null;}
const SessionContext = createContext<SessionValue | null>(null);
const noBrowserChange = () => () => {};
const inBrowser = () => true;
const onServer = () => false;

export function WorkspaceSessionProvider({children, authConfig, publicAuth}: {children: ReactNode; authConfig?: AuthConfig | null; publicAuth?:PublicAuth}) {
  const {mode, apiBaseUrl} = useDataMode();
  const [base] = useState(() => {let storage:Storage|undefined;try{if(typeof window!=='undefined')storage=window.sessionStorage;}catch{/* In-memory recovery still works. */}return {session:new SessionScope({mode,actor:''}),client:createLiveClient(fetch,apiBaseUrl),draftRecovery:new DraftRecovery(storage)};});
  const [hydrated,setHydrated]=useState<{auth:AuthAdapter;error:string|null}|null>(null);
  // The server and hydration pass agree on a null adapter; the browser then instantiates it.
  const browser = useSyncExternalStore(noBrowserChange, inBrowser, onServer);
  const selectedConfig=publicAuth?.provider==='auth0'?publicAuth.config:authConfig;
  const issuer=selectedConfig?.issuer,clientId=selectedConfig?.clientId,audience=selectedConfig?.audience;
  const provider=publicAuth?.provider,authPath=publicAuth?.provider==='neon'?publicAuth.config.authPath:undefined,
    socialInitOrigin=publicAuth?.provider==='neon'?publicAuth.config.socialInitOrigin:undefined,
    socialInitPath=publicAuth?.provider==='neon'?publicAuth.config.socialInitPath:undefined,
    providerError=publicAuth?.provider==='unavailable'?publicAuth.message:undefined;
  const authState = useMemo((): Pick<SessionValue, 'auth' | 'authError' | 'authBootstrap'> => {
    if (mode !== 'live') return {auth: null, authError: null, authBootstrap: {kind:'disabled'}};
    if (!browser) return {auth: null, authError: null, authBootstrap: {kind:'initializing'}};
    const invalid = (message:string) => ({auth:null, authError:message, authBootstrap:{kind:'configuration_error' as const,message}});
    if(provider==='unavailable')return invalid(providerError??'Sign-in configuration unavailable. Ask an administrator to restore sign-in.');
    if(provider==='neon'){try{const auth=createNeonAuthAdapter({authPath:authPath??'',socialInitOrigin:socialInitOrigin??'',socialInitPath:socialInitPath??''});return {auth,authError:null,authBootstrap:{kind:'ready',auth}};}catch{return invalid('Neon sign-in configuration is unavailable. Ask an administrator to restore sign-in.');}}
    if (!issuer || !clientId || !audience) return invalid('Sign-in is not configured. Ask an administrator to finish public sign-in setup, then use Sign in.');
    try {const auth=createAuthAdapter({issuer, clientId, audience});return {auth, authError:null, authBootstrap:{kind:'ready',auth}};}
    catch {return invalid('Sign-in configuration is invalid. Ask an administrator to correct it, then use Sign in.');}
  }, [browser,mode,issuer,clientId,audience,provider,authPath,socialInitOrigin,socialInitPath,providerError]);
  useEffect(() => {
    const auth=authState.auth;if(!auth)return;
    let active=true;
    const binding=bindAuthSession(base.session,auth,base.client,{hydrate:!window.location.pathname.startsWith('/auth/')});
    void binding.ready.then(()=>{if(active)setHydrated({auth,error:null});}).catch(()=>{
      if(active)setHydrated({auth,error:'Sign-in failed. BuyerOS could not check for an existing session. Choose Sign in and enter your email and password.'});
    });
    return()=>{active=false;binding.dispose();};
  },[authState.auth,base.session,base.client]);
  const initializing=authState.auth&&hydrated?.auth!==authState.auth;
  const value={...base,...authState,authError:hydrated&&hydrated.auth===authState.auth?hydrated.error:authState.authError,
    authBootstrap:initializing?{kind:'initializing' as const}:authState.authBootstrap};
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
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
