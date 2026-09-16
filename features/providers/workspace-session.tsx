'use client';
import {createContext, useContext, useState, type ReactNode} from 'react';
import {SessionScope} from '@/services/live/session';
import {createLiveClient} from '@/services/live/client';
import {useDataMode} from './data-mode';

interface SessionValue { session: SessionScope; client: ReturnType<typeof createLiveClient>; }
const SessionContext = createContext<SessionValue | null>(null);

export function WorkspaceSessionProvider({children}: {children: ReactNode}) {
  const {mode, apiBaseUrl} = useDataMode();
  const [value] = useState<SessionValue>(() => {
    const session = new SessionScope({mode, actor: ''});
    session.next({});
    return {session, client: createLiveClient(fetch, apiBaseUrl)};
  });
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useWorkspaceSession(): SessionValue {
  const value = useContext(SessionContext);
  if (value === null) throw new Error('useWorkspaceSession requires WorkspaceSessionProvider');
  return value;
}
