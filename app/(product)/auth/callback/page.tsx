'use client';
import {useEffect, useRef, useState} from 'react';
import {useRouter} from 'next/navigation';
import type {AuthAdapter} from '@/services/live/auth';
import {completeSessionCallback} from '@/services/live/auth-session';
import {useWorkspaceSession} from '@/features/providers/workspace-session';
import {useAuthLocale} from '@/features/live/auth-locale';

export default function AuthCallbackPage() {
  const {auth, session, authBootstrap} = useWorkspaceSession();
  const {t,picker}=useAuthLocale();
  const router = useRouter();
  const [error, setError] = useState('');
  const completion=useRef<{auth:AuthAdapter;promise:Promise<string>}|null>(null),activeAuth=useRef<AuthAdapter|null>(null);
  useEffect(() => {
    let active = true;
    if (!auth) return;
    // React may replay effects in development; one callback code can only be exchanged once.
    const identity=session.identity();activeAuth.current=auth;
    if(completion.current?.auth!==auth)completion.current={auth,promise:completeSessionCallback(auth,session,()=>activeAuth.current===auth)};
    void completion.current.promise.then(path => {
      if (active) router.replace(path);
    }).catch(() => { if (active&&session.isCurrent(identity)) { session.setToken(undefined); setError('Sign-in failed. Please start again.'); } });
    return () => {active=false;if(activeAuth.current===auth)activeAuth.current=null;};
  }, [auth, router, session]);
  const configurationError=authBootstrap.kind==='configuration_error';
  const message = error || (configurationError ? authBootstrap.message : authBootstrap.kind==='disabled' ? 'Live sign-in is disabled' : 'Completing sign-in…');
  return <main className="main-shell live-workspace live-signin auth-callback"><section className="panel live-signin-card" role={error || configurationError ? 'alert' : 'status'}>{t(message)}</section>{error&&<>
    {/* eslint-disable-next-line @next/next/no-html-link-for-pages -- Native recovery abandons the failed callback transaction. */}
    <a className="live-auth-restart" href="/app">{t('Start again')}</a></>}{picker}</main>;
}
