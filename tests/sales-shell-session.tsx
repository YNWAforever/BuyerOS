// Isolated authenticated identity; production shell, SessionScope and router remain real.
import {useSyncExternalStore} from 'react';
import {SessionScope} from '../services/live/session';
import {createLiveClient} from '../services/live/client';
import {DraftRecovery} from '../services/live/draft-recovery';
const query=new URLSearchParams(location.search);
export const session=new SessionScope({mode:'live',actor:'shell-fixture',workspace:query.get('workspace')??'a1000000-0000-4000-8000-000000000001',project:query.get('project')??'a2000000-0000-4000-8000-000000000001'});
session.setToken('isolated-fixture-token');
const client=createLiveClient();
const auth={signIn:async()=>{},signOut:async()=>{},accountEmail:()=> 'fixture@example.test'};
const value={session,client,auth,authError:null,authBootstrap:{kind:'ready',auth},draftRecovery:new DraftRecovery()};
export function useWorkspaceSession(){return value;}
export function useSessionSnapshot(){return useSyncExternalStore(session.subscribe,session.getSnapshot,session.getSnapshot);}
export function useDataMode(){return {mode:'live',apiBaseUrl:''};}
